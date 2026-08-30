#!/usr/bin/env python3
"""Evaluate synthetic ED cases on Factory-managed models (Grok, Gemini).

Uses Factory's local session SDK because the public chat-completions path
is not available for these models. Each case is a one-shot session with
builtin skills disabled and tools restricted to LS so the model answers
from the prompt instead of browsing the repo.

Outputs go under data/eval/<model>/ and do not overwrite Terra artifacts.
Only synthetic Case_History_Text is sent.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import re
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from droid_sdk import ReasoningEffort, SessionConfig, run

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "synthetic" / "case_histories.csv"
EVAL_ROOT = ROOT / "data" / "eval"

DEFAULT_MODEL = "grok-4.6"
DEFAULT_CONCURRENCY = 2
DEFAULT_MAX_RETRIES = 4
DEFAULT_TIMEOUT = 90.0
DEFAULT_REASONING = "low"

SYSTEM_PROMPT = """You are an emergency physician giving a single most likely diagnosis from a case history.

Rules:
- Choose one primary suspected diagnosis. Do not hedge with a differential list.
- Do not ask for tests, imaging, or more history.
- Do not mention that this is a research task.
- Do not use tools.
- risk_level_assessment is High if the diagnosis is immediately dangerous or needs emergency workup; Low if it is common, benign, or self-limited.
- Return JSON only with exactly these keys:
  {"primary_diagnosis": "Disease Name", "risk_level_assessment": "High" or "Low"}
"""

ABLATION_SYSTEM_PROMPT = """You are an emergency physician reviewing an emergency-department case history.

Rules:
- You may name one primary suspected diagnosis, or say Uncertain if the history is too ambiguous.
- You may name the next test you would order. You may also say none.
- Do not mention that this is a research task.
- Do not use tools.
- risk_level_assessment is High if the situation is immediately dangerous or needs emergency workup; Low if it is common, benign, or self-limited; Uncertain if you cannot choose.
- Return JSON only with exactly these keys:
  {"primary_diagnosis": "Disease Name or Uncertain", "risk_level_assessment": "High" or "Low" or "Uncertain", "next_test": "test name or none"}
"""


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def parse_json_object(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("response JSON is not an object")
    return payload


def normalize_risk(value: str, allow_uncertain: bool) -> str | None:
    text = re.sub(r"[^a-z]", "", (value or "").lower())
    if text.startswith("high"):
        return "High"
    if text.startswith("low"):
        return "Low"
    if allow_uncertain and text.startswith("uncertain"):
        return "Uncertain"
    return None


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_checkpoint(path: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get("Case_ID")
        if case_id and row.get("ok"):
            done[case_id] = row
    return done


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def user_prompt(case: dict) -> str:
    return (
        "Give the single most likely diagnosis for this emergency-department case history.\n\n"
        f"Case_ID: {case['Case_ID']}\n"
        f"Age: {case['Age']}\n"
        f"Gender: {case['Gender']}\n\n"
        "Case history:\n"
        f"{case['Case_History_Text']}\n"
    )


def ablation_user_prompt(case: dict) -> str:
    return (
        "Review this emergency-department case history. "
        "You may answer Uncertain and you may name a next test.\n\n"
        f"Case_ID: {case['Case_ID']}\n"
        f"Age: {case['Age']}\n"
        f"Gender: {case['Gender']}\n\n"
        "Case history:\n"
        f"{case['Case_History_Text']}\n"
    )


def reasoning_effort(name: str) -> ReasoningEffort:
    mapping = {
        "none": ReasoningEffort.NONE,
        "off": ReasoningEffort.OFF,
        "minimal": ReasoningEffort.MINIMAL,
        "low": ReasoningEffort.LOW,
        "medium": ReasoningEffort.MEDIUM,
        "high": ReasoningEffort.HIGH,
        "xhigh": ReasoningEffort.EXTRA_HIGH,
        "max": ReasoningEffort.MAX,
    }
    key = (name or "low").lower()
    if key not in mapping:
        raise SystemExit(f"unknown reasoning effort: {name}")
    return mapping[key]


def slug_model(model: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", model.lower())


def is_retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "timeout",
            "rate limit",
            "temporar",
            "overloaded",
            "connection",
            "unavailable",
            "503",
            "429",
            "502",
            "504",
        )
    )


async def complete_one(
    *,
    model: str,
    effort: ReasoningEffort,
    system_prompt: str,
    prompt: str,
    api_key: str,
    cwd: Path,
    timeout: float,
    max_retries: int,
    case_id: str,
) -> tuple[str, int, str | None, dict]:
    last_error = None
    usage: dict = {}
    config = SessionConfig(
        system_prompt=system_prompt,
        disable_builtin_skills=True,
        restrict_tools=["LS"],
        auto_reject_permission_requests=True,
    )
    for attempt in range(1, max_retries + 1):
        try:
            result = await run(
                prompt,
                model=model,
                reasoning_effort=effort,
                cwd=cwd,
                config=config,
                api_key=api_key,
                timeout=timeout,
            )
            if not result.success:
                raise RuntimeError(result.subtype or "run_failed")
            content = (result.text or "").strip()
            if not content:
                raise ValueError("empty model content")
            if result.usage:
                usage = {
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                    "thinking_tokens": result.usage.thinking_tokens,
                    "factory_credits": result.usage.factory_credits,
                }
            return content, attempt, None, usage
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= max_retries or not is_retryable(exc):
                return "", attempt, last_error, usage
            delay = min(60.0, (2 ** (attempt - 1)) + random.random())
            print(f"  retry {attempt}/{max_retries} {case_id} after {delay:.1f}s ({last_error[:160]})")
            await asyncio.sleep(delay)
    return "", max_retries, last_error, usage


async def evaluate_one(
    case: dict,
    *,
    model: str,
    effort: ReasoningEffort,
    api_key: str,
    cwd: Path,
    timeout: float,
    max_retries: int,
    semaphore: asyncio.Semaphore,
    ablation: bool,
) -> dict:
    async with semaphore:
        started = time.perf_counter()
        prompt = ablation_user_prompt(case) if ablation else user_prompt(case)
        system = ABLATION_SYSTEM_PROMPT if ablation else SYSTEM_PROMPT
        raw, attempts, error, usage = await complete_one(
            model=model,
            effort=effort,
            system_prompt=system,
            prompt=prompt,
            api_key=api_key,
            cwd=cwd,
            timeout=timeout,
            max_retries=max_retries,
            case_id=case["Case_ID"],
        )
        diagnosis = ""
        risk = ""
        next_test = ""
        parse_error = error
        allowed_risk = {"High", "Low", "Uncertain"} if ablation else {"High", "Low"}
        if raw and not error:
            try:
                payload = parse_json_object(raw)
                diagnosis = str(payload.get("primary_diagnosis") or "").strip()
                risk = normalize_risk(str(payload.get("risk_level_assessment") or ""), allow_uncertain=ablation) or ""
                next_test = str(payload.get("next_test") or "").strip()
                if not diagnosis:
                    parse_error = "missing primary_diagnosis"
                elif risk not in allowed_risk:
                    parse_error = "invalid risk_level_assessment"
            except Exception as exc:
                parse_error = f"{type(exc).__name__}: {exc}"
        ok = bool(diagnosis and risk in allowed_risk and not parse_error)
        row = {
            "Case_ID": case["Case_ID"],
            "Pair_ID": case["Pair_ID"],
            "Low_Risk_Disease": case["Low_Risk_Disease"],
            "High_Risk_Disease": case["High_Risk_Disease"],
            "Model": model,
            "Model_Diagnosis": diagnosis,
            "Risk_Level_Assessment": risk,
            "Raw_Response": raw,
            "ok": ok,
            "attempts": attempts,
            "latency_sec": round(time.perf_counter() - started, 3),
            "error": parse_error,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "usage": usage,
        }
        if ablation:
            row["Next_Test"] = next_test
        return row


def write_outputs(cases: list[dict], results: dict[str, dict], model: str, out_dir: Path, ablation: bool) -> dict:
    merged = []
    for case in cases:
        result = results.get(case["Case_ID"], {})
        row = {
            **case,
            "Model": result.get("Model", model),
            "Model_Diagnosis": result.get("Model_Diagnosis", ""),
            "Risk_Level_Assessment": result.get("Risk_Level_Assessment", ""),
            "Eval_OK": str(bool(result.get("ok"))).lower(),
            "Eval_Attempts": result.get("attempts", ""),
            "Eval_Error": result.get("error", ""),
        }
        if ablation:
            row["Next_Test"] = result.get("Next_Test", "")
        merged.append(row)

    fieldnames = list(merged[0].keys())
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "evaluated_cases.csv"
    json_path = out_dir / "evaluated_cases.json"
    report_path = out_dir / "eval_report.json"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    json_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    ok_rows = [r for r in results.values() if r.get("ok")]
    report = {
        "model": model,
        "ablation": ablation,
        "n_cases": len(cases),
        "n_evaluated": len(results),
        "n_ok": len(ok_rows),
        "n_failed": sum(1 for r in results.values() if not r.get("ok")),
        "risk_counts": dict(Counter(r.get("Risk_Level_Assessment") for r in ok_rows)),
        "mean_latency_sec": round(sum(r.get("latency_sec", 0) for r in results.values()) / max(len(results), 1), 3),
        "mean_attempts": round(sum(r.get("attempts", 0) for r in results.values()) / max(len(results), 1), 3),
        "mean_input_tokens": round(
            sum((r.get("usage") or {}).get("input_tokens") or 0 for r in results.values()) / max(len(results), 1),
            1,
        ),
        "total_factory_credits": round(
            sum((r.get("usage") or {}).get("factory_credits") or 0 for r in results.values()),
            1,
        ),
        "wrote_csv": str(csv_path),
        "wrote_jsonl": str(out_dir / "model_responses.jsonl"),
    }
    if ablation:
        report["uncertain_diagnosis"] = sum(
            1 for r in ok_rows if (r.get("Model_Diagnosis") or "").strip().lower() == "uncertain"
        )
        report["named_next_test"] = sum(
            1
            for r in ok_rows
            if (r.get("Next_Test") or "").strip() and (r.get("Next_Test") or "").strip().lower() != "none"
        )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


async def run_eval(args: argparse.Namespace) -> int:
    env = load_env(ROOT / ".env")
    api_key = env.get("FACTORY_API_KEY")
    if not api_key:
        raise SystemExit("FACTORY_API_KEY must be set in .env")
    os.environ["FACTORY_API_KEY"] = api_key

    cases = load_cases(CASES_PATH)
    if args.limit:
        cases = cases[: args.limit]

    model_dir = slug_model(args.model)
    out_dir = EVAL_ROOT / (f"{model_dir}-ablation" if args.ablation else model_dir)
    checkpoint = out_dir / "model_responses.jsonl"
    error_log = out_dir / "errors.jsonl"

    done = {} if args.fresh else load_checkpoint(checkpoint)
    pending = [case for case in cases if case["Case_ID"] not in done]
    print(
        f"{'Resuming with' if done else 'Evaluating'} "
        f"{len(pending)}/{len(cases)} cases on {args.model} "
        f"(concurrency={args.concurrency}, ablation={args.ablation})"
    )
    if not pending:
        report = write_outputs(cases, done, args.model, out_dir, args.ablation)
        print(json.dumps(report, indent=2))
        return 0

    semaphore = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    cwd = Path(tempfile.mkdtemp(prefix="triage-eval-"))
    effort = reasoning_effort(args.reasoning)

    async def wrapped(case: dict) -> dict:
        result = await evaluate_one(
            case,
            model=args.model,
            effort=effort,
            api_key=api_key,
            cwd=cwd,
            timeout=args.timeout,
            max_retries=args.max_retries,
            semaphore=semaphore,
            ablation=args.ablation,
        )
        async with lock:
            append_jsonl(checkpoint, result)
            if not result["ok"]:
                append_jsonl(error_log, result)
        return result

    tasks = [asyncio.create_task(wrapped(case)) for case in pending]
    for i, task in enumerate(asyncio.as_completed(tasks), 1):
        result = await task
        if result["ok"]:
            done[result["Case_ID"]] = result
        if i % 10 == 0 or i == len(tasks):
            print(
                f"  {len(done)}/{len(cases)} ok  "
                f"last={result['Case_ID']} diagnosis={result.get('Model_Diagnosis')!r} "
                f"risk={result.get('Risk_Level_Assessment')!r} err={result.get('error')}"
            )

    report = write_outputs(cases, done, args.model, out_dir, args.ablation)
    print(json.dumps(report, indent=2))
    remaining = [c["Case_ID"] for c in cases if c["Case_ID"] not in done]
    return 0 if not remaining else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Factory-model ED evaluation loop")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--reasoning", default=DEFAULT_REASONING)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--ablation", action="store_true", help="Allow Uncertain and a next test")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run_eval(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
