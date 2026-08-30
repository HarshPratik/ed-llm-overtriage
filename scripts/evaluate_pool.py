#!/usr/bin/env python3
"""Evaluate synthetic ED cases on a local OpenAI-compatible model pool.

Same protocol as evaluate_cases.py (forced JSON, one diagnosis, High/Low),
but targets POOL_BASE_URL / POOL_API_KEY from .env and writes per-model
outputs under data/eval/<model-slug>/ so other models' artifacts stay intact.

Proxy workaround: this pool truncates message content at the first newline
and drops the user turn when a system message is present, so the system and
user prompts are merged into a single newline-free user message. The prompt
text is otherwise identical to the other models' protocol.

Only synthetic Case_History_Text is sent. No PhysioNet notes.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data" / "synthetic" / "case_histories.csv"
EVAL_ROOT = ROOT / "data" / "eval"

DEFAULT_MODEL = "poolside/laguna-s-2.1-free"
DEFAULT_CONCURRENCY = 16
DEFAULT_MAX_RETRIES = 6
DEFAULT_TIMEOUT = 90.0

SYSTEM_PROMPT = """You are an emergency physician giving a single most likely diagnosis from a case history.

Rules:
- Choose one primary suspected diagnosis. Do not hedge with a differential list.
- Do not ask for tests, imaging, or more history.
- Do not mention that this is a research task.
- risk_level_assessment is High if the diagnosis is immediately dangerous or needs emergency workup; Low if it is common, benign, or self-limited.
- Return JSON only with exactly these keys:
  {"primary_diagnosis": "Disease Name", "risk_level_assessment": "High" or "Low"}
"""


def flatten(text: str) -> str:
    """Collapse newlines; the pool truncates message content at the first one."""
    return re.sub(r"\s*\n\s*", " ", text).strip()


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


def normalize_risk(value: str) -> str | None:
    text = re.sub(r"[^a-z]", "", (value or "").lower())
    if text.startswith("high"):
        return "High"
    if text.startswith("low"):
        return "Low"
    return None


def slug_model(model: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", model.lower()).strip("-")


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


def make_client(timeout: float) -> AsyncOpenAI:
    env = load_env(ROOT / ".env")
    key = env.get("POOL_API_KEY")
    base = env.get("POOL_BASE_URL")
    if not key or not base:
        raise SystemExit("POOL_API_KEY and POOL_BASE_URL must be set in .env")
    return AsyncOpenAI(api_key=key, base_url=base.rstrip("/") + "/v1", timeout=timeout)


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    text = str(exc).lower()
    return any(token in text for token in ("timeout", "rate limit", "temporar", "overloaded", "connection"))


async def complete_with_retry(
    client: AsyncOpenAI,
    *,
    model: str,
    messages: list[dict],
    max_retries: int,
    case_id: str,
) -> tuple[str, int, str | None]:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                temperature=0.0,
                max_tokens=220,
                messages=messages,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty model content")
            return content, attempt, None
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= max_retries or not is_retryable(exc):
                return "", attempt, last_error
            delay = min(60.0, (2 ** (attempt - 1)) + random.random())
            print(f"  retry {attempt}/{max_retries} {case_id} after {delay:.1f}s ({last_error[:160]})")
            await asyncio.sleep(delay)
    return "", max_retries, last_error


async def evaluate_one(
    client: AsyncOpenAI,
    case: dict,
    *,
    model: str,
    max_retries: int,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        started = time.perf_counter()
        raw, attempts, error = await complete_with_retry(
            client,
            model=model,
            messages=[
                {"role": "user", "content": flatten(SYSTEM_PROMPT) + " " + flatten(user_prompt(case))},
            ],
            max_retries=max_retries,
            case_id=case["Case_ID"],
        )
        diagnosis = ""
        risk = ""
        parse_error = error
        if raw and not error:
            try:
                payload = parse_json_object(raw)
                diagnosis = str(payload.get("primary_diagnosis") or "").strip()
                risk = normalize_risk(str(payload.get("risk_level_assessment") or "")) or ""
                if not diagnosis:
                    parse_error = "missing primary_diagnosis"
                elif risk not in {"High", "Low"}:
                    parse_error = "invalid risk_level_assessment"
            except Exception as exc:
                parse_error = f"{type(exc).__name__}: {exc}"
        return {
            "Case_ID": case["Case_ID"],
            "Pair_ID": case["Pair_ID"],
            "Low_Risk_Disease": case["Low_Risk_Disease"],
            "High_Risk_Disease": case["High_Risk_Disease"],
            "Model": model,
            "Model_Diagnosis": diagnosis,
            "Risk_Level_Assessment": risk,
            "Raw_Response": raw,
            "ok": bool(diagnosis and risk in {"High", "Low"} and not parse_error),
            "attempts": attempts,
            "latency_sec": round(time.perf_counter() - started, 3),
            "error": parse_error,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }


def write_outputs(cases: list[dict], results: dict[str, dict], model: str, out_dir: Path) -> dict:
    merged = []
    for case in cases:
        result = results.get(case["Case_ID"], {})
        merged.append(
            {
                **case,
                "Model": result.get("Model", model),
                "Model_Diagnosis": result.get("Model_Diagnosis", ""),
                "Risk_Level_Assessment": result.get("Risk_Level_Assessment", ""),
                "Eval_OK": str(bool(result.get("ok"))).lower(),
                "Eval_Attempts": result.get("attempts", ""),
                "Eval_Error": result.get("error", ""),
            }
        )

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
        "n_cases": len(cases),
        "n_evaluated": len(results),
        "n_ok": len(ok_rows),
        "n_failed": sum(1 for r in results.values() if not r.get("ok")),
        "risk_counts": dict(Counter(r.get("Risk_Level_Assessment") for r in ok_rows)),
        "mean_latency_sec": round(sum(r.get("latency_sec", 0) for r in results.values()) / max(len(results), 1), 3),
        "mean_attempts": round(sum(r.get("attempts", 0) for r in results.values()) / max(len(results), 1), 3),
        "wrote_csv": str(csv_path),
        "wrote_jsonl": str(out_dir / "model_responses.jsonl"),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else EVAL_ROOT / slug_model(args.model)
    checkpoint = out_dir / "model_responses.jsonl"
    error_log = out_dir / "errors.jsonl"

    cases = load_cases(CASES_PATH)
    if args.limit:
        cases = cases[: args.limit]
    done = {} if args.fresh else load_checkpoint(checkpoint)
    pending = [case for case in cases if case["Case_ID"] not in done]
    print(
        f"{'Resuming with' if done else 'Evaluating'} "
        f"{len(pending)}/{len(cases)} cases on {args.model} "
        f"(concurrency={args.concurrency})",
        flush=True,
    )
    if not pending:
        report = write_outputs(cases, done, args.model, out_dir)
        print(json.dumps(report, indent=2))
        return 0

    client = make_client(args.timeout)
    semaphore = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    queue: asyncio.Queue[dict] = asyncio.Queue()
    for case in pending:
        queue.put_nowait(case)
    finished = 0

    async def wrapped(case: dict) -> dict:
        result = await evaluate_one(
            client,
            case,
            model=args.model,
            max_retries=args.max_retries,
            semaphore=semaphore,
        )
        async with lock:
            append_jsonl(checkpoint, result)
            if not result["ok"]:
                append_jsonl(error_log, result)
        return result

    async def worker() -> None:
        nonlocal finished
        while True:
            try:
                case = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            result = await wrapped(case)
            async with lock:
                finished += 1
                i = finished
                if result["ok"]:
                    done[result["Case_ID"]] = result
            if i % 25 == 0 or i == len(pending):
                print(
                    f"  {len(done)}/{len(cases)} ok  "
                    f"last={result['Case_ID']} diagnosis={result.get('Model_Diagnosis')!r} "
                    f"risk={result.get('Risk_Level_Assessment')!r} err={result.get('error')}",
                    flush=True,
                )

    try:
        await asyncio.gather(*[asyncio.create_task(worker()) for _ in range(args.concurrency)])
    finally:
        await client.close()

    report = write_outputs(cases, done, args.model, out_dir)
    print(json.dumps(report, indent=2))
    remaining = [c["Case_ID"] for c in cases if c["Case_ID"] not in done]
    return 0 if not remaining else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pool-model ED evaluation loop")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--fresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
