#!/usr/bin/env python3
"""Compare Terra vs later Factory-model evals on the same 1000 cases."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_csv(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["Case_ID"]: row for row in csv.DictReader(handle)}


def rate(rows: list[dict], key: str, value: str) -> dict:
    n = len(rows)
    k = sum(1 for r in rows if r.get(key) == value)
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terra", type=Path, default=ROOT / "data" / "eval" / "evaluated_cases.csv")
    parser.add_argument("--other", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    terra = load_csv(args.terra)
    other = load_csv(args.other)
    ids = sorted(set(terra) & set(other))
    paired = []
    for case_id in ids:
        a = terra[case_id]
        b = other[case_id]
        paired.append(
            {
                "Case_ID": case_id,
                "Pair_ID": a.get("Pair_ID"),
                "Terra_Diagnosis": a.get("Model_Diagnosis"),
                "Terra_Risk": a.get("Risk_Level_Assessment"),
                "Terra_Pole": a.get("Mapped_Pole"),
                "Other_Diagnosis": b.get("Model_Diagnosis"),
                "Other_Risk": b.get("Risk_Level_Assessment"),
                "Other_Pole": b.get("Mapped_Pole"),
                "Same_Risk": a.get("Risk_Level_Assessment") == b.get("Risk_Level_Assessment"),
                "Same_Pole": a.get("Mapped_Pole") == b.get("Mapped_Pole"),
            }
        )

    report = {
        "n_overlap": len(ids),
        "terra_self_high": rate(list(terra[i] for i in ids), "Risk_Level_Assessment", "High"),
        "other_self_high": rate(list(other[i] for i in ids), "Risk_Level_Assessment", "High"),
        "terra_high_pole": rate(list(terra[i] for i in ids), "Mapped_Pole", "high_risk"),
        "other_high_pole": rate(list(other[i] for i in ids), "Mapped_Pole", "high_risk"),
        "same_risk": rate(paired, "Same_Risk", True),
        "same_pole": rate(paired, "Same_Pole", True),
        "risk_crosstab": dict(Counter((r["Terra_Risk"], r["Other_Risk"]) for r in paired)),
        "pole_crosstab": dict(Counter((r["Terra_Pole"], r["Other_Pole"]) for r in paired)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    with (args.out.parent / "model_agreement.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(paired[0].keys()) if paired else ["Case_ID"])
        writer.writeheader()
        writer.writerows(paired)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
