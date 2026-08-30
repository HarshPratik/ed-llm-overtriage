#!/usr/bin/env python3
"""Review unmapped (Other) diagnoses and write a precise over-triage table.

Does not call an API. Uses the expanded emergency/benign bins from analyze_bias.py
plus a hand review of leftover unknown labels.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_bias import classify, load_rows, proportion_stats

EVAL_CSV = ROOT / "data" / "eval" / "evaluated_cases.csv"
OUT_DIR = ROOT / "data" / "analysis"


def main() -> int:
    rows = load_rows(EVAL_CSV)
    classified = classify(rows)
    other = [r for r in classified if r["Mapped_Pole"] == "other"]
    bins = Counter(r["Other_Bin"] for r in other)
    self_risk = Counter(r.get("Risk_Level_Assessment") for r in other)
    n = len(classified)
    n_high = sum(1 for r in classified if r["Mapped_Pole"] == "high_risk")
    n_low = sum(1 for r in classified if r["Mapped_Pole"] == "low_risk")
    n_other = len(other)
    n_other_high = bins.get("other_high", 0)
    n_other_low = bins.get("other_low", 0)
    n_other_unknown = bins.get("other_unknown", 0)
    n_broad = n_high + n_other_high
    n_self_high = sum(1 for r in classified if r.get("Risk_Level_Assessment") == "High")

    by_label = (
        Counter((r["Pair_ID"], r["Low_Risk_Disease"], r["High_Risk_Disease"], r["Model_Diagnosis"], r["Other_Bin"]) for r in other)
    )
    detail_rows = [
        {
            "Pair_ID": pair,
            "Low_Risk_Disease": low,
            "High_Risk_Disease": high,
            "Model_Diagnosis": dx,
            "Other_Bin": bin_name,
            "n": count,
        }
        for (pair, low, high, dx, bin_name), count in sorted(by_label.items(), key=lambda item: (-item[1], item[0][0], item[0][3]))
    ]

    notes = [
        "PAIR-028/029: 39 of 50 biliary-colic cases were called acute cholecystitis, a third emergency, not cholangitis or pancreatitis.",
        "PAIR-020: migraine vs brain tumor often became SAH, ICH, meningitis, or stroke rather than tumor.",
        "PAIR-009/010: bronchitis/COPD cases often became asthma exacerbation, PE, or heart failure.",
        "PAIR-035 leftover cardiac-syncope labels (HCM, arrhythmic syncope) are still cannot-miss, not vasovagal.",
        "After expanding emergency keywords, leftover unknown labels should be near zero.",
    ]
    report = {
        "n_cases": n,
        "mapped": {"high_risk": n_high, "low_risk": n_low, "other": n_other},
        "other_bins": dict(bins),
        "other_self_risk": dict(self_risk),
        "broad_high": proportion_stats(n_broad, n, "broad_high_all_cases"),
        "self_risk_high": proportion_stats(n_self_high, n, "self_label_high"),
        "precise_other_high_share": round(n_other_high / n_other, 4) if n_other else None,
        "notes": notes,
        "n_detail_rows": len(detail_rows),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "other_review.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Pair_ID", "Low_Risk_Disease", "High_Risk_Disease", "Model_Diagnosis", "Other_Bin", "n"])
        writer.writeheader()
        writer.writerows(detail_rows)
    (OUT_DIR / "other_review.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
