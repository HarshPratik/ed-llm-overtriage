#!/usr/bin/env python3
"""Regenerate template-fallback cases with gpt-5.6-sol."""

from __future__ import annotations

import csv
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_case_histories import (  # noqa: E402
    GLOBAL_FORBIDDEN,
    PAIR_OVERRIDES,
    SEED,
    TONES,
    facts_for,
    load_pairs,
)
from generate_case_histories_llm import (  # noqa: E402
    MODEL,
    SYSTEM_PROMPT,
    TONE_INSTRUCTIONS,
    load_env,
    normalize,
    parse_json,
)

CSV_PATH = ROOT / "data" / "synthetic" / "case_histories.csv"
JSON_PATH = ROOT / "data" / "synthetic" / "case_histories.json"
REPORT_PATH = ROOT / "data" / "synthetic" / "generation_report.json"
WORKERS = 3

BANNED_ALIASES = {
    "Uncomplicated UTI": ["UTI", "urinary tract infection", "cystitis"],
    "UTI with delirium": ["UTI", "urinary tract infection", "cystitis"],
    "Sepsis": ["sepsis", "septic shock", "septic"],
    "Subdural hematoma": ["subdural", "SDH", "intracranial hemorrhage"],
    "Cellulitis": ["cellulitis"],
    "Deep vein thrombosis": ["DVT", "deep vein thrombosis", "deep venous thrombosis"],
    "Constipation": ["constipation", "obstipation"],
    "Small bowel obstruction": ["SBO", "bowel obstruction", "intestinal obstruction"],
    "COPD exacerbation": ["COPD", "emphysema"],
    "Pulmonary embolism": ["PE", "pulmonary embolism", "pulmonary embolus"],
    "Migraine": ["migraine"],
    "Subarachnoid hemorrhage": ["SAH", "subarachnoid"],
}


def forbidden_for(pair: dict) -> list[str]:
    pats = list(GLOBAL_FORBIDDEN)
    for name in (pair["low_risk_disease"], pair["high_risk_disease"]):
        pats.append(re.escape(name))
        for alias in BANNED_ALIASES.get(name, []):
            pats.append(rf"\b{re.escape(alias)}\b")
    return pats


def is_forbidden(text: str, pair: dict) -> str | None:
    for pat in forbidden_for(pair):
        if re.search(pat, text, flags=re.I):
            return pat
    return None


def make_client() -> OpenAI:
    env = load_env(ROOT / ".env")
    return OpenAI(
        api_key=env.get("OpenAI_API_KEY") or env.get("OPENAI_API_KEY"),
        base_url=env.get("OpenAI_baseURL") or env.get("OPENAI_BASE_URL"),
        timeout=90.0,
    )


def prompt(pair: dict, facts: dict, attempt: int, banned: list[str]) -> str:
    gender_word = (
        "woman" if facts["gender"] == "woman"
        else "man" if facts["gender"] == "man"
        else "nonbinary adult"
    )
    banned_txt = ", ".join(sorted(set(banned)))
    return f"""Create one fictional ED case. JSON only.

Hidden differential (never name either, never hint with abbreviations):
- Low-risk: {pair['low_risk_disease']}
- High-risk: {pair['high_risk_disease']}

Describe symptoms only. Do not write any of these strings: {banned_txt}

Shared features: {pair['shared_symptoms']}
Constraint: {pair.get('generation_notes') or 'Keep both diagnoses plausible.'}

Patient:
- Age {facts['age']}, {gender_word}, occupation {facts['occupation']}
- Arrival {facts['companion']}; setting {facts['setting']}; duration {facts['duration']}
- Associated: {', '.join(facts['assoc_list'])}
- History: {', '.join(facts['hist_list'])}

Voice: {facts['tone']}
{TONE_INSTRUCTIONS[facts['tone']]}
Diversity seed {attempt}.

{{"symptoms":"...","case_history_text":"..."}}
"""


def generate_one(client: OpenAI, pair: dict, facts: dict, attempt: int) -> dict | None:
    banned = [pair["low_risk_disease"], pair["high_risk_disease"]] + BANNED_ALIASES.get(pair["low_risk_disease"], []) + BANNED_ALIASES.get(pair["high_risk_disease"], [])
    last = None
    for round_i in range(1, 5):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=0.9,
                max_tokens=700,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + " If a common disease abbreviation would appear, rewrite around symptoms instead."},
                    {"role": "user", "content": prompt(pair, facts, attempt + round_i, banned)},
                ],
            )
            payload = parse_json(response.choices[0].message.content or "")
            text = re.sub(r"\s+", " ", str(payload.get("case_history_text") or "")).strip()
            symptoms = str(payload.get("symptoms") or pair["shared_symptoms"]).strip()
            if len(text) < 280:
                last = "too_short"
                continue
            hit = is_forbidden(text, pair) or is_forbidden(symptoms, pair)
            if hit:
                last = f"forbidden:{hit}"
                continue
            return {"text": text, "symptoms": symptoms}
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(1.2 * round_i)
    print("fail", pair["pair_id"], last)
    return None


def main() -> int:
    pairs = {p["pair_id"]: p for p in load_pairs()}
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    fallbacks = [r for r in rows if r.get("Source") == "template_fallback"]
    print(f"Repairing {len(fallbacks)} fallbacks with {MODEL}")
    if not fallbacks:
        return 0

    client = make_client()
    used = {normalize(r["Case_History_Text"]) for r in rows if r.get("Source") != "template_fallback"}
    by_id = {r["Case_ID"]: r for r in rows}
    rng = random.Random(SEED + 99)

    def repair(old: dict) -> tuple[str, dict] | None:
        pair = pairs[old["Pair_ID"]]
        idx = int(old["Case_ID"].split("-")[1])
        for attempt in range(8):
            facts = facts_for(random.Random(rng.randint(0, 10**9) + attempt), pair, idx % 25)
            facts["tone"] = old["Tone"] if old["Tone"] in TONES else facts["tone"]
            result = generate_one(client, pair, facts, attempt)
            if not result:
                continue
            key = normalize(result["text"])
            if key in used:
                continue
            used.add(key)
            updated = dict(old)
            updated["Age"] = str(facts["age"])
            updated["Gender"] = facts["gender"]
            updated["Symptoms"] = result["symptoms"]
            updated["Case_History_Text"] = result["text"]
            updated["Source"] = "llm"
            return old["Case_ID"], updated
        return None

    repaired = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(repair, row) for row in fallbacks]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result:
                case_id, updated = result
                by_id[case_id] = updated
                repaired += 1
            if i % 10 == 0 or i == len(fallbacks):
                print(f"  {i}/{len(fallbacks)} repaired={repaired}")

    new_rows = [by_id[r["Case_ID"]] for r in rows]
    fieldnames = list(rows[0].keys())
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)
    JSON_PATH.write_text(json.dumps(new_rows, indent=2), encoding="utf-8")
    remaining = sum(1 for r in new_rows if r.get("Source") == "template_fallback")
    print(f"repaired {repaired}; remaining fallbacks {remaining}")
    if REPORT_PATH.exists():
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        from collections import Counter
        report["source_counts"] = dict(Counter(r.get("Source") for r in new_rows))
        report["unique_texts"] = len({r["Case_History_Text"] for r in new_rows})
        report["mean_chars"] = round(sum(len(r["Case_History_Text"]) for r in new_rows) / len(new_rows), 1)
        report["model"] = MODEL
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
