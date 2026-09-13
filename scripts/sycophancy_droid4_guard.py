#!/usr/bin/env python3
"""Stop Terra/Gemini sycophancy evals if Factory falls back to Droid Core, then
resume the same models after the Standard-usage window resets.

Never changes --model. Resume is checkpoint-only (no --fresh).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAUSE_PATH = ROOT / "data" / "eval" / "sycophancy_factory_pause.json"
TERRA_JSONL = ROOT / "data" / "eval" / "gpt-5.6-terra-sycophancy" / "sycophancy_responses.jsonl"
GEMINI_JSONL = ROOT / "data" / "eval" / "gemini-3.7-flash-sycophancy" / "sycophancy_responses.jsonl"
SESSIONS = Path.home() / ".factory" / "sessions"
PYTHON = Path(r"C:\Python311\python.exe")
DROID_BIN = Path(r"C:\Users\harsh\bin")
DROID_CORE_RE = re.compile(
    r"^(inkling|glm-|kimi-|nemotron-|deepseek-|minimax-|droid[\s_-]*core)",
    re.I,
)
MODELS = ("gpt-5.6-terra", "gemini-3.7-flash")
ALLOWED = {m.lower() for m in MODELS}
POLL_SEC = 5.0
RESET_WAIT_SEC = 38 * 60
POST_KILL_GRACE_SEC = 90


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def count_ok(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("ok"):
            n += 1
    return n


def is_droid_core(model_id: str) -> bool:
    return bool(DROID_CORE_RE.search((model_id or "").strip()))


def is_fallback_model(model_id: str) -> bool:
    text = (model_id or "").strip()
    if not text or text.lower() in ALLOWED:
        return False
    return True


def recent_fallback(max_age_sec: float = 120.0) -> tuple[str, float] | None:
    cutoff = time.time() - max_age_sec
    newest = None
    newest_mtime = 0.0
    if not SESSIONS.exists():
        return None
    try:
        session_dirs = [p for p in SESSIONS.iterdir() if "triage-syc" in p.name]
    except OSError:
        return None
    for session_dir in session_dirs:
        try:
            names = os.listdir(session_dir)
        except OSError:
            continue
        for name in names:
            if not name.endswith(".settings.json"):
                continue
            path = session_dir / name
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            model = str(data.get("model") or "")
            if is_fallback_model(model) and mtime >= newest_mtime:
                newest = model
                newest_mtime = mtime
    if newest is None:
        return None
    return newest, newest_mtime


def sycophancy_pids() -> list[int]:
    cmd = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -match 'sycophancy_test.py' "
        "-and $_.CommandLine -notmatch 'sycophancy_droid4_guard' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: list[int] = []
    for raw in (proc.stdout or "").split():
        try:
            pids.append(int(raw))
        except ValueError:
            continue
    return pids


def kill_sycophancy() -> list[int]:
    pids = sycophancy_pids()
    for pid in pids:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force"],
            check=False,
        )
        print(f"killed sycophancy pid {pid}", flush=True)
    return pids


def model_running(model: str) -> bool:
    cmd = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -match 'sycophancy_test.py' "
        f"-and $_.CommandLine -match '{model}' }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool((proc.stdout or "").strip())


def write_pause(reason: str, detected_model: str) -> None:
    payload = {
        "reason": reason,
        "detected_model": detected_model,
        "paused_at": utc_now(),
        "terra_ok": count_ok(TERRA_JSONL),
        "gemini_ok": count_ok(GEMINI_JSONL),
        "resume_models": list(MODELS),
    }
    PAUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAUSE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote pause file terra_ok={payload['terra_ok']} gemini_ok={payload['gemini_ok']}", flush=True)


def start_model(model: str) -> None:
    if count_ok(ROOT / "data" / "eval" / f"{model}-sycophancy" / "sycophancy_responses.jsonl") >= 1000:
        print(f"{model} already n_ok=1000; skip", flush=True)
        return
    if model_running(model):
        print(f"{model} already running; skip start", flush=True)
        return
    env = os.environ.copy()
    env.pop("FACTORY_API_KEY", None)
    env["PYTHONUNBUFFERED"] = "1"
    env["PATH"] = str(DROID_BIN) + os.pathsep + env.get("PATH", "")
    log_path = ROOT / "data" / "eval" / f"{model}-sycophancy" / "guard_resume.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("a", encoding="utf-8")
    handle.write(f"\n--- resume {utc_now()} {model} ---\n")
    handle.flush()
    subprocess.Popen(
        [
            str(PYTHON),
            str(ROOT / "scripts" / "sycophancy_test.py"),
            "--model",
            model,
            "--concurrency",
            "2",
            "--timeout",
            "120",
            "--max-retries",
            "4",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    print(f"resumed {model}", flush=True)


def both_done() -> bool:
    return count_ok(TERRA_JSONL) >= 1000 and count_ok(GEMINI_JSONL) >= 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pause sycophancy evals on Droid Core fallback")
    parser.add_argument(
        "--resume-at",
        default="",
        help="UTC timestamp for the first Factory limit reset (keeps the original window)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.resume_at:
        first_resume_at = datetime.fromisoformat(args.resume_at).timestamp()
    else:
        first_resume_at = time.time() + RESET_WAIT_SEC
    print(
        f"Droid Core guard started; first Factory reset estimate {datetime.fromtimestamp(first_resume_at, tz=timezone.utc).isoformat()}",
        flush=True,
    )
    print(
        f"live models terra_ok={count_ok(TERRA_JSONL)} gemini_ok={count_ok(GEMINI_JSONL)}",
        flush=True,
    )
    paused_once = False
    last_resume_mtime = 0.0
    while True:
        if both_done():
            if PAUSE_PATH.exists():
                PAUSE_PATH.unlink()
            print("both models n_ok=1000; guard exiting", flush=True)
            return 0
        detected = recent_fallback()
        if detected and detected[1] > last_resume_mtime:
            detected_model, _mtime = detected
            kind = "Droid Core" if is_droid_core(detected_model) else "non-paper model"
            print(f"STOP: Factory session model is {detected_model!r} ({kind})", flush=True)
            write_pause("droid_core_fallback", detected_model)
            kill_sycophancy()
            time.sleep(2)
            kill_sycophancy()
            if paused_once:
                wake = time.time() + RESET_WAIT_SEC
            else:
                wake = max(first_resume_at, time.time() + POST_KILL_GRACE_SEC)
                paused_once = True
            wait_s = max(0, wake - time.time())
            print(f"waiting {wait_s:.0f}s for Factory limits to reset; will resume {list(MODELS)}", flush=True)
            time.sleep(wait_s)
            if PAUSE_PATH.exists():
                PAUSE_PATH.unlink()
            last_resume_mtime = time.time()
            print(f"resuming same models at {utc_now()}", flush=True)
            for model in MODELS:
                start_model(model)
            time.sleep(POLL_SEC)
            continue
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    sys.exit(main())
