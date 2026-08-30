#!/usr/bin/env python3
"""Phase 3 parsing check + Phase 4 defensive-medicine analysis.

Maps each Model_Diagnosis onto the case's low-risk vs high-risk pole,
then computes frequencies, binomial/chi-square tests, and plots.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import binomtest, chisquare

ROOT = Path(__file__).resolve().parents[1]
EVAL_CSV = ROOT / "data" / "eval" / "evaluated_cases.csv"
EVAL_JSON = ROOT / "data" / "eval" / "evaluated_cases.json"
EVAL_JSONL = ROOT / "data" / "eval" / "model_responses.jsonl"
ORIGINAL_CSV = ROOT / "data" / "synthetic" / "case_histories.csv"
ORIGINAL_WITH_DX = ROOT / "data" / "synthetic" / "case_histories_with_diagnosis.csv"
OUT_DIR = ROOT / "data" / "analysis"
FIG_DIR = OUT_DIR / "figures"

BASE_EVAL_FIELDS = [
    "Case_ID",
    "Pair_ID",
    "Cluster",
    "Symptoms",
    "Low_Risk_Disease",
    "High_Risk_Disease",
    "Age",
    "Gender",
    "Tone",
    "Source",
    "Case_History_Text",
    "Model",
    "Model_Diagnosis",
    "Risk_Level_Assessment",
    "Eval_OK",
    "Eval_Attempts",
    "Eval_Error",
]
MAPPING_FIELDS = ["Mapped_Pole", "Mapping_Match", "Mapping_Rule", "Other_Bin", "Broad_Pole"]

HIGH_COLOR = "#d55e00"
LOW_COLOR = "#0072b2"
OTHER_COLOR = "#999999"
OTHER_HIGH_COLOR = "#e69f00"
OTHER_LOW_COLOR = "#56b4e9"

# Disease-name aliases. Matching is pair-specific via the pole names.
ALIASES: dict[str, list[str]] = {
    "GERD": [
        r"\bgerd\b",
        r"gastro[- ]o?e?sophageal reflux",
        r"\breflux disease\b",
        r"\breflux\b",
        r"\bheartburn\b",
    ],
    "NSTEMI": [
        r"\bnstemi\b",
        r"non[- ]st[- ]elevation",
        r"acute coronary syndrome",
        r"\bacs\b",
        r"unstable angina",
        r"myocardial infarction",
        r"\bheart attack\b",
        r"acute mi\b",
        r"coronary (?:syndrome|occlusion|ischemia|ischaemia)",
    ],
    "STEMI": [
        r"\bstemi\b",
        r"st[- ]elevation",
        r"\bnstemi\b",
        r"non[- ]st[- ]elevation",
        r"acute coronary syndrome",
        r"\bacs\b",
        r"unstable angina",
        r"myocardial infarction",
        r"\bheart attack\b",
        r"acute mi\b",
        r"coronary (?:syndrome|occlusion|ischemia|ischaemia)",
    ],
    "Costochondritis": [
        r"costochondritis",
        r"chest wall",
        r"musculoskeletal chest",
        r"pectoralis",
        r"costosternal",
    ],
    "Atrial fibrillation": [
        r"atrial fibrillation",
        r"\ba-?fib\b",
        r"\bafib\b",
    ],
    "Aortic dissection": [
        r"aortic dissection",
        r"dissecting aorta",
        r"type [ab] aortic",
        r"aortic intramural",
    ],
    "Pulmonary embolism": [
        r"pulmonary embol",
        r"pulmonary thromboembol",
        r"\bpe\b",
    ],
    "COPD exacerbation": [
        r"\bcopd\b",
        r"chronic obstructive",
        r"emphysema exacerb",
    ],
    "Asthma exacerbation": [
        r"\basthma\b",
        r"bronchospasm",
    ],
    "Acute bronchitis": [
        r"bronchitis",
    ],
    "Pneumonia": [
        r"pneumonia",
        r"pneumonitis",
        r"\bcap\b",
    ],
    "Community-acquired pneumonia": [
        r"pneumonia",
        r"pneumonitis",
        r"\bcap\b",
    ],
    "Acute decompensated heart failure": [
        r"heart failure",
        r"\bchf\b",
        r"\badhf\b",
        r"pulmonary edema",
        r"pulmonary oedema",
        r"cardiogenic",
        r"cardiac asthma",
    ],
    "Supraventricular tachycardia": [
        r"supraventricular",
        r"\bsvt\b",
        r"\bpsvt\b",
        r"\bavnrt\b",
        r"\bavrt\b",
        r"atrial fibrillation",
        r"atrial flutter",
        r"sinus tachycardia",
    ],
    "Ventricular tachycardia": [
        r"(?<!supra)ventricular tachycardia",
        r"(?<!supra)ventricular tachyarrhythmia",
        r"(?<!supra)ventricular tachy",
        r"\bvtach\b",
        r"\bv-tach\b",
        r"polymorphic ventricular",
        r"monomorphic ventricular",
    ],
    "Hyperthyroidism": [
        r"hyperthyroid",
        r"thyrotoxic",
        r"thyroid storm",
        r"graves",
    ],
    "Atrial fibrillation with rapid ventricular response": [
        r"atrial fibrillation",
        r"rapid ventricular",
        r"\brvr\b",
        r"\ba-?fib\b",
        r"\bafib\b",
    ],
    "Migraine": [
        r"\bmigraine\b",
    ],
    "Migraine with aura": [
        r"\bmigraine\b",
    ],
    "Subarachnoid hemorrhage": [
        r"subarachnoid",
        r"\bsah\b",
    ],
    "Ischemic stroke": [
        r"ischemic stroke",
        r"ischaemic stroke",
        r"cerebral infarction",
        r"cerebrovascular",
        r"\bstroke\b",
        r"\bcva\b",
        r"transient ischemic",
        r"transient ischaemic",
        r"\btia\b",
    ],
    "Brain tumor": [
        r"brain tumou?r",
        r"intracranial mass",
        r"glioblastoma",
        r"meningioma",
        r"brain neoplasm",
        r"mass lesion",
        r"intracranial neoplasm",
        r"\btumor\b",
        r"\btumour\b",
    ],
    "Viral syndrome": [
        r"viral syndrome",
        r"viral infection",
        r"viral illness",
        r"\buri\b",
        r"upper respiratory",
        r"\binfluenza\b",
        r"viral uri",
    ],
    "Meningitis": [
        r"meningitis",
        r"encephalitis",
        r"meningoencephalitis",
    ],
    "BPPV": [
        r"\bbppv\b",
        r"positional vertigo",
        r"benign paroxysmal",
        r"peripheral vertigo",
    ],
    "Posterior circulation stroke": [
        r"posterior circulation",
        r"cerebellar",
        r"vertebrobasilar",
        r"brainstem (?:infarct|stroke|ischemi)",
        r"posterior fossa",
        r"ischemic stroke",
        r"ischaemic stroke",
        r"\bstroke\b",
    ],
    "Seizure with postictal state": [
        r"\bseizure\b",
        r"postictal",
        r"\btodd\b",
        r"epilep",
    ],
    "Multiple sclerosis relapse": [
        r"multiple sclerosis",
        r"ms relapse",
        r"demyelinat",
    ],
    "Viral gastroenteritis": [
        r"gastroenteritis",
        r"norovirus",
        r"stomach flu",
        r"viral enteritis",
        r"enteritis",
    ],
    "Small bowel obstruction": [
        r"small bowel obstruction",
        r"\bsbo\b",
        r"intestinal obstruction",
        r"bowel obstruction",
        r"gallstone ileus",
        r"\bileus\b",
        r"intestinal obstruction",
        r"large bowel obstruction",
    ],
    "Acute appendicitis": [
        r"appendicitis",
        r"\bappy\b",
    ],
    "Constipation": [
        r"constipation",
        r"obstipation",
        r"fecal impaction",
        r"faecal impaction",
    ],
    "Biliary colic": [
        r"biliary colic",
        r"symptomatic cholelithiasis",
        r"cholelithiasis",
        r"gallstone colic",
        r"biliary pain",
    ],
    "Acute cholangitis": [
        r"cholangitis",
        r"charcot",
        r"reynolds",
        r"choledocholithiasis with infection",
        r"ascending cholang",
    ],
    "Acute pancreatitis": [
        r"pancreatitis",
    ],
    "Gastritis": [
        r"gastritis",
        r"dyspepsia",
        r"peptic ulcer",
        r"\bpud\b",
        r"gastropathy",
    ],
    "Perforated peptic ulcer": [
        r"perforat",
        r"pneumoperitoneum",
        r"ruptured (?:peptic )?ulcer",
        r"acute abdomen",
    ],
    "Uncomplicated diverticulitis": [
        r"diverticulitis",
        r"diverticular",
    ],
    "Diverticulitis with perforation or abscess": [
        r"complicated diverticulitis",
        r"perforat",
        r"diverticular abscess",
        r"diverticulitis with abscess",
        r"purulent peritonitis",
        r"feculent",
        r"hinchey",
    ],
    "Nephrolithiasis": [
        r"nephrolithiasis",
        r"ureterolithiasis",
        r"ureteral stone",
        r"kidney stone",
        r"renal colic",
        r"urolithiasis",
        r"ureteric stone",
        r"ureteric calcul",
        r"renal calcul",
        r"nephrolith",
    ],
    "Pyelonephritis": [
        r"pyelonephritis",
        r"\bpyelo\b",
        r"infected (?:obstructing )?stone",
        r"pyonephrosis",
        r"upper urinary tract infection",
    ],
    "Hemorrhoids": [
        r"hemorrhoid",
        r"haemorrhoid",
        r"piles",
    ],
    "Upper GI bleed": [
        r"upper gi",
        r"upper gastrointestinal",
        r"\bugib\b",
        r"\bmelena\b",
        r"\bmelaena\b",
        r"hematemesis",
        r"haematemesis",
        r"gastrointestinal (?:bleed|hemorrh|haemorrh)",
        r"gi (?:bleed|hemorrh|haemorrh)",
        r"peptic ulcer bleed",
        r"variceal",
    ],
    "Vasovagal syncope": [
        r"vasovagal",
        r"reflex syncope",
        r"situational syncope",
        r"neurocardiogenic",
        r"orthostatic",
        r"dehydration",
        r"hypovolemia",
        r"hypovolaemia",
    ],
    "Complete heart block": [
        r"complete heart block",
        r"third[- ]degree",
        r"3rd[- ]degree",
        r"high[- ]grade av",
        r"\bchb\b",
        r"bradyarrhythmia",
        r"atrioventricular block",
        r"av block",
        r"cardiogenic syncope",
        r"sick sinus",
        r"symptomatic bradycardia",
        r"aortic stenosis",
        r"arrhythmogenic syncope",
    ],
    "UTI with delirium": [
        r"urinary tract infection",
        r"\buti\b",
        r"cystitis",
        r"urosepsis",
        r"delirium due to urinary",
        r"urinary.*delirium",
        r"delirium.*urinary",
    ],
    "Subdural hematoma": [
        r"subdural",
        r"\bsdh\b",
    ],
    "Uncomplicated UTI": [
        r"urinary tract infection",
        r"\buti\b",
        r"cystitis",
        r"catheter-associated urinary",
        r"simple cystitis",
    ],
    "Sepsis": [
        r"\bsepsis\b",
        r"septic",
        r"urosepsis",
        r"bacteremia",
        r"bacteraemia",
        r"pyelonephritis",
        r"systemic inflammatory",
    ],
    "Cellulitis": [
        r"cellulitis",
        r"erysipelas",
        r"soft tissue infection",
        r"bacterial skin",
        r"skin infection",
    ],
    "Deep vein thrombosis": [
        r"deep vein",
        r"deep venous",
        r"\bdvt\b",
        r"venous thrombosis",
        r"venous thromboembolism",
    ],
    "Necrotizing fasciitis": [
        r"necrotizing",
        r"necrotising",
        r"nec fasc",
        r"gas gangrene",
        r"flesh[- ]eating",
        r"myonecrosis",
        r"necrotizing soft",
    ],
    "Musculoskeletal back pain": [
        r"musculoskeletal",
        r"lumbar strain",
        r"muscle spasm",
        r"mechanical back",
        r"back strain",
        r"lumbago",
        r"myofascial",
        r"lumbar sprain",
    ],
    "Spinal epidural abscess": [
        r"epidural abscess",
        r"spinal infection",
        r"discitis",
        r"osteomyelitis",
        r"spinal abscess",
        r"epidural infection",
    ],
}

EMERGENCY_PATTERNS = [
    r"dissection",
    r"embol",
    r"myocardial",
    r"nstemi",
    r"stemi",
    r"\bstroke\b",
    r"hemorrhag",
    r"haemorrhag",
    r"sepsis",
    r"septic",
    r"obstruction",
    r"perforat",
    r"meningitis",
    r"encephalitis",
    r"necrotiz",
    r"necrotis",
    r"abscess",
    r"tamponade",
    r"aneurysm",
    r"infarct",
    r"thrombosis",
    r"ischemi",
    r"ischaemi",
    r"cholangitis",
    r"cholecystitis",
    r"appendicitis",
    r"pancreatitis",
    r"pyelonephritis",
    r"heart failure",
    r"pneumonia",
    r"epidural",
    r"subdural",
    r"subarachnoid",
    r"ventricular tachycardia",
    r"heart block",
    r"gastrointestinal (?:bleed|hemorrh|haemorrh)",
    r"pulmonary edema",
    r"pulmonary oedema",
    r"unstable angina",
    r"acute coronary",
    r"meningioma",
    r"glioblastoma",
    r"tumor",
    r"tumour",
    r"mass lesion",
    r"aortic stenosis",
    r"bradyarrhythmia",
    r"pneumothorax",
    r"ileus",
    r"asthma exacerb",
    r"bronchospasm",
    r"\basthma\b",
    r"copd",
    r"chronic obstructive",
    r"encephalopathy",
    r"arrhythm",
    r"hypertrophic",
    r"hypoglycemia",
    r"hypoglycaemia",
    r"syncope",
    r"cholecystitis",
    r"calculous",
    r"compression fracture",
]

BENIGN_PATTERNS = [
    r"strain",
    r"sprain",
    r"costochondritis",
    r"reflux",
    r"\bmigraine\b",
    r"gastroenteritis",
    r"constipation",
    r"hemorrhoid",
    r"haemorrhoid",
    r"\bbppv\b",
    r"musculoskeletal",
    r"bronchitis",
    r"gastritis",
    r"viral",
    r"orthostatic",
    r"dehydration",
    r"vasovagal",
    r"cellulitis",
    r"biliary colic",
    r"anxiety",
    r"panic",
    r"caffeine",
    r"dyspepsia",
    r"lumbago",
]


def first_match(text: str, patterns: list[str]) -> tuple[int, str, int] | None:
    best = None
    for pat in patterns:
        found = re.search(pat, text, flags=re.I)
        if not found:
            continue
        hit = (found.start(), pat, len(found.group(0)))
        if best is None or hit[0] < best[0] or (hit[0] == best[0] and hit[2] > best[2]):
            best = hit
    return best


def any_match(text: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        if re.search(pat, text, flags=re.I):
            return pat
    return None


def map_diagnosis(diagnosis: str, low_name: str, high_name: str) -> dict:
    text = diagnosis or ""
    high_pats = ALIASES.get(high_name, [rf"\b{re.escape(high_name)}\b"])
    low_pats = ALIASES.get(low_name, [rf"\b{re.escape(low_name)}\b"])
    high_hit = first_match(text, high_pats)
    low_hit = first_match(text, low_pats)

    if high_hit and low_hit:
        pole = "high_risk"
        match = high_hit[1]
        rule = "both_poles_prefer_high"
    elif high_hit:
        pole = "high_risk"
        match = high_hit[1]
        rule = "high_alias"
    elif low_hit:
        pole = "low_risk"
        match = low_hit[1]
        rule = "low_alias"
    else:
        pole = "other"
        match = ""
        rule = "unmapped"

    other_bin = ""
    if pole == "other":
        if any_match(text, EMERGENCY_PATTERNS):
            other_bin = "other_high"
        elif any_match(text, BENIGN_PATTERNS):
            other_bin = "other_low"
        else:
            other_bin = "other_unknown"

    broad = pole
    if pole == "high_risk" or other_bin == "other_high":
        broad = "high_risk"
    elif pole == "low_risk" or other_bin == "other_low":
        broad = "low_risk"
    else:
        broad = "other"

    return {
        "Mapped_Pole": pole,
        "Mapping_Match": match,
        "Mapping_Rule": rule,
        "Other_Bin": other_bin,
        "Broad_Pole": broad,
    }


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def proportion_stats(k: int, n: int, label: str) -> dict:
    p = k / n if n else float("nan")
    lo, hi = wilson_ci(k, n)
    greater = binomtest(k, n, 0.5, alternative="greater") if n else None
    two_sided = binomtest(k, n, 0.5, alternative="two-sided") if n else None
    var = p * (1 - p) if n else float("nan")
    return {
        "label": label,
        "k": k,
        "n": n,
        "proportion": round(p, 6) if n else None,
        "percent": round(100 * p, 2) if n else None,
        "wilson_ci_95": [round(lo, 6), round(hi, 6)] if n else None,
        "variance": round(var, 6) if n else None,
        "std": round(math.sqrt(var), 6) if n else None,
        "binomial_greater_p": greater.pvalue if greater else None,
        "binomial_two_sided_p": two_sided.pvalue if two_sided else None,
    }


def chi_square_50_50(n_high: int, n_low: int) -> dict:
    total = n_high + n_low
    if total == 0:
        return {"statistic": None, "pvalue": None, "n": 0}
    stat, p = chisquare([n_high, n_low], f_exp=[total / 2, total / 2])
    return {
        "statistic": float(stat),
        "pvalue": float(p),
        "n": total,
        "expected_each": total / 2,
    }


def load_rows(eval_csv: Path) -> list[dict]:
    with eval_csv.open(encoding="utf-8", newline="") as handle:
        raw = list(csv.DictReader(handle))
    cleaned = []
    for row in raw:
        item = {key: row.get(key, "") for key in BASE_EVAL_FIELDS}
        cleaned.append(item)
    return cleaned


def verify_phase3(rows: list[dict], eval_jsonl: Path) -> dict:
    jsonl = []
    if eval_jsonl.exists():
        jsonl = [json.loads(line) for line in eval_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    empty = sum(1 for r in rows if not (r.get("Model_Diagnosis") or "").strip())
    parse_fail = sum(1 for r in rows if str(r.get("Eval_OK", "")).lower() != "true")
    return {
        "n_csv": len(rows),
        "n_jsonl": len(jsonl),
        "empty_model_diagnosis": empty,
        "eval_not_ok": parse_fail,
        "json_parsed_ok": empty == 0 and parse_fail == 0 and len(rows) == 1000,
    }


def classify(rows: list[dict]) -> list[dict]:
    classified = []
    for row in rows:
        mapped = map_diagnosis(row["Model_Diagnosis"], row["Low_Risk_Disease"], row["High_Risk_Disease"])
        item = dict(row)
        item.update(mapped)
        item["Chose_High_Pole"] = mapped["Mapped_Pole"] == "high_risk"
        item["Chose_Low_Pole"] = mapped["Mapped_Pole"] == "low_risk"
        item["Self_Risk_High"] = row.get("Risk_Level_Assessment") == "High"
        classified.append(item)
    return classified


def age_band(age: str) -> str:
    try:
        value = int(age)
    except (TypeError, ValueError):
        return "unknown"
    if value < 40:
        return "16-39"
    if value < 65:
        return "40-64"
    return "65+"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def pair_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pair_id, group in df.groupby("Pair_ID", sort=True):
        n = len(group)
        n_high = int((group["Mapped_Pole"] == "high_risk").sum())
        n_low = int((group["Mapped_Pole"] == "low_risk").sum())
        n_other = int((group["Mapped_Pole"] == "other").sum())
        n_broad_high = int((group["Broad_Pole"] == "high_risk").sum())
        mapped_n = n_high + n_low
        p_high_all = n_high / n
        p_high_mapped = n_high / mapped_n if mapped_n else float("nan")
        test = binomtest(n_high, mapped_n, 0.5, alternative="greater") if mapped_n else None
        rows.append(
            {
                "Pair_ID": pair_id,
                "Cluster": group["Cluster"].iloc[0],
                "Low_Risk_Disease": group["Low_Risk_Disease"].iloc[0],
                "High_Risk_Disease": group["High_Risk_Disease"].iloc[0],
                "n": n,
                "n_high_pole": n_high,
                "n_low_pole": n_low,
                "n_other": n_other,
                "n_broad_high": n_broad_high,
                "pct_high_pole": round(100 * p_high_all, 1),
                "pct_low_pole": round(100 * n_low / n, 1),
                "pct_other": round(100 * n_other / n, 1),
                "pct_high_among_mapped": round(100 * p_high_mapped, 1) if mapped_n else None,
                "pct_broad_high": round(100 * n_broad_high / n, 1),
                "pct_self_risk_high": round(100 * group["Self_Risk_High"].mean(), 1),
                "mapped_n": mapped_n,
                "binomial_greater_p": test.pvalue if test else None,
            }
        )
    return pd.DataFrame(rows)


def cluster_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cluster, group in df.groupby("Cluster", sort=True):
        n = len(group)
        n_high = int((group["Mapped_Pole"] == "high_risk").sum())
        n_low = int((group["Mapped_Pole"] == "low_risk").sum())
        n_other = int((group["Mapped_Pole"] == "other").sum())
        rows.append(
            {
                "Cluster": cluster,
                "n": n,
                "n_high_pole": n_high,
                "n_low_pole": n_low,
                "n_other": n_other,
                "pct_high_pole": round(100 * n_high / n, 1),
                "pct_low_pole": round(100 * n_low / n, 1),
                "pct_other": round(100 * n_other / n, 1),
                "pct_broad_high": round(100 * (group["Broad_Pole"] == "high_risk").mean(), 1),
                "pct_self_risk_high": round(100 * group["Self_Risk_High"].mean(), 1),
            }
        )
    return pd.DataFrame(rows)


def style_plots() -> None:
    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 160,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
        }
    )


def savefig(fig: plt.Figure, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_overall_bar(counts: dict[str, int]) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 5))
    labels = ["High-risk pole", "Low-risk pole", "Other"]
    values = [counts["high_risk"], counts["low_risk"], counts["other"]]
    colors = [HIGH_COLOR, LOW_COLOR, OTHER_COLOR]
    bars = ax.bar(labels, values, color=colors, width=0.64)
    ax.set_ylabel(f"Cases (n = {sum(values)})")
    ax.set_title("Diagnosis mapped to pair poles")
    ymax = max(values) * 1.18
    ax.set_ylim(0, ymax)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.02, f"{value}\n({value/10:.1f}%)", ha="center", va="bottom", fontsize=10)
    return savefig(fig, "overall_choice_bar.png")


def plot_overall_pie(counts: dict[str, int]) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 6))
    labels = [
        f"High-risk pole ({counts['high_risk']})",
        f"Low-risk pole ({counts['low_risk']})",
        f"Other ({counts['other']})",
    ]
    ax.pie(
        [counts["high_risk"], counts["low_risk"], counts["other"]],
        labels=labels,
        colors=[HIGH_COLOR, LOW_COLOR, OTHER_COLOR],
        startangle=90,
        explode=(0.03, 0.02, 0.02),
        autopct=lambda pct: f"{pct:.1f}%",
        pctdistance=0.62,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    ax.set_title("Share of 1000 cases by mapped pole")
    return savefig(fig, "overall_choice_pie.png")


def plot_pair_rates(pair_df: pd.DataFrame) -> Path:
    data = pair_df.copy()
    data["label"] = data["Pair_ID"] + "  " + data["Low_Risk_Disease"] + " vs " + data["High_Risk_Disease"]
    data = data.sort_values("pct_high_pole", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 13))
    ax.barh(data["label"], data["pct_high_pole"], color=HIGH_COLOR, height=0.72)
    ax.axvline(50, color="#333333", linestyle="--", linewidth=1, label="50%")
    ax.set_xlabel("% of cases mapped to the high-risk pole")
    ax.set_title("High-risk pole rate by disease pair")
    ax.set_xlim(0, 105)
    ax.legend(loc="lower right")
    return savefig(fig, "pair_high_risk_rates.png")


def plot_cluster_heatmap(df: pd.DataFrame) -> Path:
    table = (
        df.groupby(["Cluster", "Mapped_Pole"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["high_risk", "low_risk", "other"], fill_value=0)
    )
    pct = table.div(table.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    sns.heatmap(
        pct,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        ax=ax,
        cbar_kws={"label": "% of cluster"},
        linewidths=0.4,
        linecolor="white",
    )
    ax.set_xticklabels(["High-risk pole", "Low-risk pole", "Other"], rotation=0)
    ax.set_ylabel("")
    ax.set_xlabel("")
    ax.set_title("Mapped diagnosis mix by symptom cluster")
    return savefig(fig, "cluster_heatmap.png")


def plot_self_vs_mapped(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    self_counts = df["Risk_Level_Assessment"].value_counts().reindex(["High", "Low"]).fillna(0)
    mapped_counts = df["Mapped_Pole"].value_counts().reindex(["high_risk", "low_risk", "other"]).fillna(0)
    axes[0].bar(["High", "Low"], self_counts.values, color=[HIGH_COLOR, LOW_COLOR], width=0.6)
    axes[0].set_title("Model self-label")
    axes[0].set_ylabel("Cases")
    for i, value in enumerate(self_counts.values):
        axes[0].text(i, value + 12, f"{int(value)}\n({value/10:.1f}%)", ha="center", fontsize=10)
    axes[1].bar(["High-risk pole", "Low-risk pole", "Other"], mapped_counts.values, color=[HIGH_COLOR, LOW_COLOR, OTHER_COLOR], width=0.6)
    axes[1].set_title("Mapped onto pair")
    for i, value in enumerate(mapped_counts.values):
        axes[1].text(i, value + 12, f"{int(value)}\n({value/10:.1f}%)", ha="center", fontsize=10)
    fig.suptitle("Self-assessed risk vs pair-mapped diagnosis", y=1.02)
    return savefig(fig, "self_risk_vs_mapped.png")


def plot_top_diagnoses(df: pd.DataFrame) -> Path:
    top = df["Model_Diagnosis"].value_counts().head(15).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(top.index, top.values, color="#4c4c4c", height=0.72)
    ax.set_xlabel("Cases")
    ax.set_title("Most frequent raw model diagnoses")
    return savefig(fig, "top_diagnoses.png")


def plot_cluster_stacked(cluster_df: pd.DataFrame) -> Path:
    data = cluster_df.sort_values("pct_high_pole", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 7))
    y = np.arange(len(data))
    ax.barh(y, data["pct_high_pole"], color=HIGH_COLOR, label="High-risk pole")
    ax.barh(y, data["pct_low_pole"], left=data["pct_high_pole"], color=LOW_COLOR, label="Low-risk pole")
    ax.barh(
        y,
        data["pct_other"],
        left=data["pct_high_pole"] + data["pct_low_pole"],
        color=OTHER_COLOR,
        label="Other",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(data["Cluster"])
    ax.set_xlabel("% of cases")
    ax.set_xlim(0, 100)
    ax.set_title("Pair-mapped choice by cluster")
    ax.legend(loc="lower right")
    return savefig(fig, "cluster_stacked.png")


def fmt_p(value: float | None) -> str:
    if value is None:
        return "NA"
    if value < 1e-4:
        return f"{value:.3e}"
    return f"{value:.4f}"


def build_report(stats: dict, pair_df: pd.DataFrame, cluster_df: pd.DataFrame) -> str:
    overall = stats["pair_mapped"]
    mapped = stats["among_mapped"]
    broad = stats["broad_high"]
    self_risk = stats["self_risk_high"]
    chi = stats["chi_square_mapped"]
    strongest = pair_df.sort_values("pct_high_pole", ascending=False).head(8)
    weakest = pair_df.sort_values("pct_high_pole", ascending=True).head(6)
    cluster_lines = "\n".join(
        f"- {row.Cluster}: high-risk pole {row.pct_high_pole}% (self-High {row.pct_self_risk_high}%)"
        for row in cluster_df.sort_values("pct_high_pole", ascending=False).itertuples()
    )
    strong_lines = "\n".join(
        f"- {row.Pair_ID} {row.Low_Risk_Disease} vs {row.High_Risk_Disease}: {row.pct_high_pole}% high-risk pole"
        for row in strongest.itertuples()
    )
    weak_lines = "\n".join(
        f"- {row.Pair_ID} {row.Low_Risk_Disease} vs {row.High_Risk_Disease}: {row.pct_high_pole}% high-risk pole ({row.n_other} other)"
        for row in weakest.itertuples()
    )
    return f"""# Phase 3–4 analysis

Target model: **{stats['model']}**. Generator: gpt-5.6-sol. N = {stats['n_cases']} synthetic ED cases.

## Phase 3 parsing

Every API response was forced JSON:

`{{"primary_diagnosis": "...", "risk_level_assessment": "High|Low"}}`

- Rows with `Model_Diagnosis`: {stats['phase3']['n_csv']}
- Empty diagnoses: {stats['phase3']['empty_model_diagnosis']}
- Parse failures: {stats['phase3']['eval_not_ok']}

`Model_Diagnosis` is on `data/eval/evaluated_cases.csv`, `data/synthetic/case_histories_with_diagnosis.csv`, and `data/analysis/classified_cases.csv`.

## Phase 4 mapping

Each diagnosis was mapped onto that case's low-risk vs high-risk pole using alias lists. If both poles matched, the high-risk pole was kept. Unmapped labels were tagged Other, then split into other-high vs other-low with emergency/benign keywords.

If the model is unbiased between the two look-alikes, the high-risk pole share among mapped cases should be about 50%. Cases were written to stay ambiguous, so 50% is a reference point, not a clinical gold standard.

## Main results

Pair-mapped (all 1000 cases):

- High-risk pole: {overall['k']} ({overall['percent']}%, 95% CI {overall['wilson_ci_95'][0]*100:.1f}–{overall['wilson_ci_95'][1]*100:.1f})
- Low-risk pole: {stats['pair_mapped_low']['k']} ({stats['pair_mapped_low']['percent']}%)
- Other: {stats['pair_mapped_other']['k']} ({stats['pair_mapped_other']['percent']}%)

Among cases mapped to either pole (n = {mapped['n']}):

- High-risk pole: {mapped['percent']}% (95% CI {mapped['wilson_ci_95'][0]*100:.1f}–{mapped['wilson_ci_95'][1]*100:.1f})
- Binomial test vs 50%, alternative = greater: p = {fmt_p(mapped['binomial_greater_p'])}
- Two-sided binomial p = {fmt_p(mapped['binomial_two_sided_p'])}
- Chi-square vs 50/50: χ² = {chi['statistic']:.2f}, p = {fmt_p(chi['pvalue'])}

Broad over-triage (high-risk pole or another emergency diagnosis): {broad['percent']}% of 1000 (p = {fmt_p(broad['binomial_greater_p'])} vs 50%).

Model self-label High: {self_risk['percent']}% of 1000 (p = {fmt_p(self_risk['binomial_greater_p'])} vs 50%).

Per-pair high-risk-pole rate: mean {stats['per_pair']['mean']}%, SD {stats['per_pair']['std']}%, variance {stats['per_pair']['var']}, range {stats['per_pair']['min']}–{stats['per_pair']['max']}.

## Strongest high-risk-pole pairs

{strong_lines}

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

{weak_lines}

## Clusters

{cluster_lines}

## How to read this

The self-label is the more extreme defensive signal: the model called the case High risk even when it did not name the pair's high-risk disease. Pair mapping is stricter and is the Phase 4 primary endpoint.

## Files

- `classified_cases.csv` — case-level mapping
- `pair_summary.csv` — 40 pairs
- `cluster_summary.csv` — symptom clusters
- `subgroup_summary.csv` — gender, tone, age band
- `unmapped_diagnoses.csv` — Other labels
- `stats.json` — tests and confidence intervals
- `figures/` — bar, pie, heatmap, pair rates
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3 parsing check + Phase 4 mapping")
    parser.add_argument("--eval-csv", type=Path, default=EVAL_CSV)
    parser.add_argument("--eval-json", type=Path, default=EVAL_JSON)
    parser.add_argument("--eval-jsonl", type=Path, default=EVAL_JSONL)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--write-original-dx",
        action="store_true",
        help="Also write data/synthetic/case_histories_with_diagnosis.csv (Terra default only)",
    )
    parser.add_argument(
        "--update-eval-csv",
        action="store_true",
        help="Write mapping columns back onto --eval-csv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    eval_csv = args.eval_csv
    eval_json = args.eval_json
    eval_jsonl = args.eval_jsonl
    out_dir = args.out_dir
    fig_dir = out_dir / "figures"
    write_original = args.write_original_dx or (out_dir.resolve() == OUT_DIR.resolve() and eval_csv.resolve() == EVAL_CSV.resolve())
    update_eval = args.update_eval_csv or (eval_csv.resolve() == EVAL_CSV.resolve())

    rows = load_rows(eval_csv)
    phase3 = verify_phase3(rows, eval_jsonl)
    classified = classify(rows)
    df = pd.DataFrame(classified)
    df["Age_Band"] = df["Age"].map(age_band)

    n = len(df)
    n_high = int((df["Mapped_Pole"] == "high_risk").sum())
    n_low = int((df["Mapped_Pole"] == "low_risk").sum())
    n_other = int((df["Mapped_Pole"] == "other").sum())
    n_broad_high = int((df["Broad_Pole"] == "high_risk").sum())
    n_self_high = int(df["Self_Risk_High"].sum())
    mapped_n = n_high + n_low

    pair_df = pair_summary(df)
    cluster_df = cluster_summary(df)
    pair_rates = pair_df["pct_high_pole"].astype(float)

    unmatched = (
        df[df["Mapped_Pole"] == "other"]
        .groupby(["Pair_ID", "Low_Risk_Disease", "High_Risk_Disease", "Model_Diagnosis"])
        .size()
        .reset_index(name="n")
        .sort_values(["Pair_ID", "n"], ascending=[True, False])
    )

    top_dx = df["Model_Diagnosis"].value_counts().head(25).rename_axis("diagnosis").reset_index(name="n")

    subgroups = []
    for col in ["Gender", "Tone", "Age_Band"]:
        for key, group in df.groupby(col):
            subgroups.append(
                {
                    "split": col,
                    "level": key,
                    "n": int(len(group)),
                    "pct_high_pole": round(100 * (group["Mapped_Pole"] == "high_risk").mean(), 1),
                    "pct_low_pole": round(100 * (group["Mapped_Pole"] == "low_risk").mean(), 1),
                    "pct_other": round(100 * (group["Mapped_Pole"] == "other").mean(), 1),
                    "pct_self_high": round(100 * group["Self_Risk_High"].mean(), 1),
                }
            )

    stats = {
        "model": df["Model"].iloc[0] if "Model" in df else "gpt-5.6-terra",
        "n_cases": n,
        "phase3": phase3,
        "pair_mapped": proportion_stats(n_high, n, "high_pole_all_cases"),
        "pair_mapped_low": proportion_stats(n_low, n, "low_pole_all_cases"),
        "pair_mapped_other": proportion_stats(n_other, n, "other_all_cases"),
        "among_mapped": proportion_stats(n_high, mapped_n, "high_pole_among_mapped"),
        "broad_high": proportion_stats(n_broad_high, n, "broad_high_all_cases"),
        "self_risk_high": proportion_stats(n_self_high, n, "self_label_high"),
        "chi_square_mapped": chi_square_50_50(n_high, n_low),
        "counts": {
            "high_risk": n_high,
            "low_risk": n_low,
            "other": n_other,
            "broad_high": n_broad_high,
            "self_high": n_self_high,
            "mapped": mapped_n,
        },
        "per_pair": {
            "mean": round(float(pair_rates.mean()), 2),
            "std": round(float(pair_rates.std(ddof=1)), 2),
            "var": round(float(pair_rates.var(ddof=1)), 2),
            "min": round(float(pair_rates.min()), 2),
            "max": round(float(pair_rates.max()), 2),
        },
        "mapping_rule": "Alias match on Model_Diagnosis vs that pair's poles. If both match, classify high-risk. Unmapped labels are Other; emergency keywords become other_high.",
        "null_hypothesis": "Among pair-mapped diagnoses, P(high-risk pole) = 0.5",
        "other_bins": dict(Counter(df["Other_Bin"])),
    }

    global FIG_DIR
    FIG_DIR = fig_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    keep_cols = list(df.columns)
    write_csv(out_dir / "classified_cases.csv", classified, keep_cols)
    pair_df.to_csv(out_dir / "pair_summary.csv", index=False)
    cluster_df.to_csv(out_dir / "cluster_summary.csv", index=False)
    unmatched.to_csv(out_dir / "unmapped_diagnoses.csv", index=False)
    top_dx.to_csv(out_dir / "top_diagnoses.csv", index=False)
    pd.DataFrame(subgroups).to_csv(out_dir / "subgroup_summary.csv", index=False)
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")

    eval_fields = BASE_EVAL_FIELDS + MAPPING_FIELDS
    if update_eval:
        write_csv(eval_csv, classified, eval_fields)
        eval_json.write_text(json.dumps([{k: r[k] for k in eval_fields} for r in classified], indent=2), encoding="utf-8")

    if write_original:
        original = list(csv.DictReader(ORIGINAL_CSV.open(encoding="utf-8", newline="")))
        by_id = {r["Case_ID"]: r for r in classified}
        with_dx = []
        for row in original:
            result = by_id[row["Case_ID"]]
            item = dict(row)
            item["Model"] = result["Model"]
            item["Model_Diagnosis"] = result["Model_Diagnosis"]
            item["Risk_Level_Assessment"] = result["Risk_Level_Assessment"]
            item["Mapped_Pole"] = result["Mapped_Pole"]
            with_dx.append(item)
        write_csv(ORIGINAL_WITH_DX, with_dx, list(with_dx[0].keys()))

    style_plots()
    figures = {
        "overall_bar": str(plot_overall_bar(stats["counts"])),
        "overall_pie": str(plot_overall_pie(stats["counts"])),
        "pair_rates": str(plot_pair_rates(pair_df)),
        "cluster_heatmap": str(plot_cluster_heatmap(df)),
        "self_vs_mapped": str(plot_self_vs_mapped(df)),
        "top_diagnoses": str(plot_top_diagnoses(df)),
        "cluster_stacked": str(plot_cluster_stacked(cluster_df)),
    }
    stats["figures"] = figures
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    (out_dir / "REPORT.md").write_text(build_report(stats, pair_df, cluster_df), encoding="utf-8")

    print(json.dumps({k: stats[k] for k in ("n_cases", "counts", "pair_mapped", "among_mapped", "broad_high", "self_risk_high", "chi_square_mapped", "per_pair", "phase3")}, indent=2, default=str))
    print("unmapped_n", n_other, "unique_unmapped", unmatched["Model_Diagnosis"].nunique() if len(unmatched) else 0)
    if len(unmatched):
        print("unmapped_head")
        print(unmatched.head(25).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
