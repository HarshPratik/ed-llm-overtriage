#!/usr/bin/env python3
"""Cross-model endpoints, pairwise Cohen's kappa, and Fleiss' kappa.

Reads the seven forced-JSON eval CSVs. Does not overwrite Terra artifacts.
"""

from __future__ import annotations

import csv
import json
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "analysis"
FIG_DIR = OUT_DIR / "figures"

MODELS = [
    ("gpt-5.6-terra", ROOT / "data" / "eval" / "evaluated_cases.csv"),
    ("grok-4.6", ROOT / "data" / "eval" / "grok-4.6" / "evaluated_cases.csv"),
    ("gemini-3.7-flash", ROOT / "data" / "eval" / "gemini-3.7-flash" / "evaluated_cases.csv"),
    ("glm-5.3-flash", ROOT / "data" / "eval" / "glm-5.3-flash" / "evaluated_cases.csv"),
    ("MiniMax M3", ROOT / "data" / "eval" / "minimax-minimax-m3-free" / "evaluated_cases.csv"),
    ("Laguna S-2.1", ROOT / "data" / "eval" / "poolside-laguna-s-2.1-free" / "evaluated_cases.csv"),
    ("sarvam-105b", ROOT / "data" / "eval" / "sarvam-105b" / "evaluated_cases.csv"),
]


def load_csv(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["Case_ID"]: row for row in csv.DictReader(handle)}


def cohen_kappa(a: list[str], b: list[str]) -> dict:
    n = len(a)
    labels = sorted(set(a) | set(b))
    idx = {lab: i for i, lab in enumerate(labels)}
    mat = np.zeros((len(labels), len(labels)), dtype=float)
    for x, y in zip(a, b):
        mat[idx[x], idx[y]] += 1
    po = float(np.trace(mat) / n)
    row = mat.sum(axis=1) / n
    col = mat.sum(axis=0) / n
    pe = float(row @ col)
    kappa = None if pe >= 1 else (po - pe) / (1 - pe)
    agree = sum(x == y for x, y in zip(a, b))
    return {"n": n, "observed": round(po, 4), "expected": round(pe, 4), "kappa": None if kappa is None else round(kappa, 4), "n_agree": agree}


def fleiss_kappa(ratings: np.ndarray) -> dict:
    """ratings: n_cases x n_raters of category ids."""
    n, r = ratings.shape
    cats = sorted(set(ratings.ravel().tolist()))
    k = len(cats)
    cat_index = {c: i for i, c in enumerate(cats)}
    counts = np.zeros((n, k), dtype=float)
    for i in range(n):
        for j in range(r):
            counts[i, cat_index[ratings[i, j]]] += 1
    p_j = counts.sum(axis=0) / (n * r)
    p_i = ((counts * counts).sum(axis=1) - r) / (r * (r - 1))
    p_bar = float(p_i.mean())
    p_e = float((p_j * p_j).sum())
    kappa = None if p_e >= 1 else (p_bar - p_e) / (1 - p_e)
    return {
        "n_cases": n,
        "n_raters": r,
        "n_categories": k,
        "p_bar": round(p_bar, 4),
        "p_e": round(p_e, 4),
        "kappa": None if kappa is None else round(kappa, 4),
    }


def endpoints(rows: list[dict]) -> dict:
    n = len(rows)
    self_high = sum(r.get("Risk_Level_Assessment") == "High" for r in rows)
    high_pole = sum(r.get("Mapped_Pole") == "high_risk" for r in rows)
    low_pole = sum(r.get("Mapped_Pole") == "low_risk" for r in rows)
    other = sum(r.get("Mapped_Pole") == "other" for r in rows)
    mapped = high_pole + low_pole
    broad = sum(r.get("Broad_Pole") == "high_risk" for r in rows)
    return {
        "n": n,
        "self_high": self_high,
        "self_high_pct": round(100 * self_high / n, 1),
        "high_pole": high_pole,
        "high_pole_pct": round(100 * high_pole / n, 1),
        "low_pole": low_pole,
        "low_pole_pct": round(100 * low_pole / n, 1),
        "other": other,
        "other_pct": round(100 * other / n, 1),
        "mapped": mapped,
        "high_among_mapped": high_pole,
        "high_among_mapped_pct": round(100 * high_pole / mapped, 1) if mapped else None,
        "broad_high": broad,
        "broad_high_pct": round(100 * broad / n, 1),
    }


def plot_endpoints(summary: dict, path: Path) -> None:
    names = list(summary["endpoints"])
    labels = list(names)
    self_h = [summary["endpoints"][n]["self_high_pct"] for n in names]
    mapped = [summary["endpoints"][n]["high_among_mapped_pct"] for n in names]
    broad = [summary["endpoints"][n]["broad_high_pct"] for n in names]
    x = np.arange(len(names))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12.5, 5.4))
    ax.bar(x - width, self_h, width, label="Self-label High", color="#d55e00")
    ax.bar(x, mapped, width, label="High-risk pole among mapped", color="#0072b2")
    ax.bar(x + width, broad, width, label="Broad high (pole or other emergency)", color="#e69f00")
    ax.axhline(50, color="#444444", linewidth=1, linestyle="--", label="50% reference")
    ax.set_ylabel("% of cases")
    ax.set_ylim(0, 105)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.set_title("Same 1000 cases, forced JSON prompt")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> int:
    tables = {name: load_csv(path) for name, path in MODELS}
    ids = sorted(set.intersection(*(set(t) for t in tables.values())))
    endpoints_by_model = {name: endpoints([tables[name][i] for i in ids]) for name, _ in MODELS}

    pairwise_risk = {}
    pairwise_pole = {}
    names = [name for name, _ in MODELS]
    for a, b in combinations(names, 2):
        risk_a = [tables[a][i]["Risk_Level_Assessment"] for i in ids]
        risk_b = [tables[b][i]["Risk_Level_Assessment"] for i in ids]
        pole_a = [tables[a][i]["Mapped_Pole"] for i in ids]
        pole_b = [tables[b][i]["Mapped_Pole"] for i in ids]
        pairwise_risk[f"{a} vs {b}"] = cohen_kappa(risk_a, risk_b)
        pairwise_pole[f"{a} vs {b}"] = cohen_kappa(pole_a, pole_b)

    risk_mat = np.array(
        [[1 if tables[name][i]["Risk_Level_Assessment"] == "High" else 0 for name, _ in MODELS] for i in ids],
        dtype=int,
    )
    pole_mat = np.array(
        [[{"high_risk": 0, "low_risk": 1, "other": 2}[tables[name][i]["Mapped_Pole"]] for name, _ in MODELS] for i in ids],
        dtype=int,
    )
    n_all_high = int((risk_mat.sum(axis=1) == len(names)).sum())
    n_any_low = int((risk_mat.sum(axis=1) < len(names)).sum())
    unanimous_high_pole = int((pole_mat == 0).all(axis=1).sum())

    fig_path = FIG_DIR / "cross_model_endpoints.png"
    report = {
        "n_overlap": len(ids),
        "models": names,
        "endpoints": endpoints_by_model,
        "all_seven_self_high": {"k": n_all_high, "n": len(ids), "pct": round(100 * n_all_high / len(ids), 1)},
        "not_unanimous_high": {"k": n_any_low, "n": len(ids)},
        "all_seven_high_pole": {"k": unanimous_high_pole, "n": len(ids), "pct": round(100 * unanimous_high_pole / len(ids), 1)},
        "fleiss_self_high": fleiss_kappa(risk_mat),
        "fleiss_mapped_pole": fleiss_kappa(pole_mat),
        "pairwise_self_risk_kappa": pairwise_risk,
        "pairwise_mapped_pole_kappa": pairwise_pole,
        "figure": str(fig_path.relative_to(ROOT)).replace("\\", "/"),
    }
    plot_endpoints(report, fig_path)
    out_json = OUT_DIR / "model_agreement.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n_overlap", "all_seven_self_high", "all_seven_high_pole", "fleiss_self_high", "fleiss_mapped_pole", "endpoints")}, indent=2))
    print("wrote", out_json)
    print("wrote", fig_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
