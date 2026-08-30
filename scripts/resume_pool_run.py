#!/usr/bin/env python3
"""Restart evaluate_pool.py until a full pass makes no new unique OK rows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def unique_ok(jsonl: Path) -> int:
    ids: set[str] = set()
    if not jsonl.exists():
        return 0
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("ok") and row.get("Case_ID"):
            ids.add(row["Case_ID"])
    return len(ids)


def main() -> int:
    model = sys.argv[1]
    extra = sys.argv[2:]
    slug = model.lower().replace("/", "-")
    jsonl = ROOT / "data" / "eval" / slug / "model_responses.jsonl"
    log_path = ROOT / "data" / "eval" / slug / "run.log"
    jsonl.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(ROOT / "scripts" / "evaluate_pool.py"), "--model", model, *extra]
    max_rounds = 12
    for round_i in range(1, max_rounds + 1):
        before = unique_ok(jsonl)
        print(f"round {round_i} start unique_ok={before} model={model}", flush=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n--- round {round_i} unique_ok={before} ---\n")
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env)
        after = unique_ok(jsonl)
        print(
            f"round {round_i} exit={proc.returncode} unique_ok={after} delta={after - before}",
            flush=True,
        )
        if proc.returncode == 0 or after >= 1000:
            return 0
        if after <= before:
            return proc.returncode or 1
        time.sleep(3)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
