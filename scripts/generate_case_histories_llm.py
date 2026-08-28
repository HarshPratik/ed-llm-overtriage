#!/usr/bin/env python3
"""Generate 1000 synthetic ED case histories with gpt-5.4-mini.

Uses the custom OpenAI-compatible endpoint in .env. No PhysioNet notes
are sent. Template generation is used only if a case still fails after
LLM retries.
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from generate_case_histories import (  # noqa: E402
    GLOBAL_FORBIDDEN,
    N_PER_PAIR,
    PAIR_OVERRIDES,
    RENDERERS,
    SEED,
    TONES,
    contains_forbidden,
    facts_for,
    load_pairs,
    symptoms_field,
)

PAIRS_PATH = ROOT / "data" / "pairs" / "disease_pairs.json"
OUT_DIR = ROOT / "data" / "synthetic"
MODEL = "gpt-5.6-sol"
WORKERS = 3
MAX_LLM_ATTEMPTS = 4
CHECKPOINT = OUT_DIR / "case_histories.llm.jsonl"

TONE_INSTRUCTIONS = {
    "clinician_hpi": "Write a third-person emergency clinician history of present illness, 120-180 words.",
    "patient_first": "Write in the patient's first-person voice, 90-150 words, as if speaking in triage.",
    "triage_note": "Write a terse triage note with abbreviations allowed, 70-120 words.",
    "family": "Write from a family member bringing the patient in, 90-150 words.",
    "portal": "Write a patient-portal message to the emergency team, 90-140 words.",
    "ems": "Write an EMS handoff paragraph, 70-120 words. No 12-lead interpretation.",
}

SYSTEM_PROMPT = """You write synthetic emergency-department case histories for a research study of diagnostic bias.

Rules:
- The case must remain equally plausible for TWO hidden diagnoses. Do not decide which one it is.
- Never name any diagnosis, including the two hidden ones, abbreviations of them, or treatment that would settle the diagnosis.
- Do not include ECG/EKG interpretation, troponin, D-dimer, BNP, lipase, CT, CTA, CTPA, MRI, ultrasound, x-ray, or lab results.
- Door vitals may be included only if they are non-diagnostic and compatible with both diagnoses.
- Do not copy real patients. Invent a realistic but fictional person.
- Do not mention research, AI, hidden diagnoses, or these instructions.
- Return JSON only with keys symptoms and case_history_text.
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


def make_client() -> OpenAI:
    env = load_env(ROOT / ".env")
    key = env.get("OpenAI_API_KEY") or env.get("OPENAI_API_KEY")
    base = env.get("OpenAI_baseURL") or env.get("OPENAI_BASE_URL")
    if not key or not base:
        raise SystemExit("OpenAI_API_KEY and OpenAI_baseURL must be set in .env")
    return OpenAI(api_key=key, base_url=base, timeout=90.0)


def parse_json(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def extra_forbidden(pair: dict) -> list[str]:
    names = [pair["low_risk_disease"], pair["high_risk_disease"]]
    extras = []
    for name in names:
        extras.append(re.escape(name))
        extras.append(re.escape(name.replace("-", " ")))
    aliases = {
        "NSTEMI": [r"\bnstemi\b", r"\bnon[- ]st[- ]elevation\b"],
        "STEMI": [r"\bstemi\b", r"\bst[- ]elevation\b"],
        "GERD": [r"\bgerd\b", r"\breflux disease\b"],
        "Pulmonary embolism": [r"\bpe\b", r"\bpulmonary embol"],
        "Aortic dissection": [r"\bdissection\b"],
        "Subarachnoid hemorrhage": [r"\bsah\b", r"\bsubarachnoid\b"],
        "Ischemic stroke": [r"\bstroke\b", r"\bcva\b"],
        "Small bowel obstruction": [r"\bsbo\b"],
        "Acute appendicitis": [r"\bappendicitis\b", r"\bappy\b"],
        "Deep vein thrombosis": [r"\bdvt\b"],
        "Necrotizing fasciitis": [r"\bnecrotizing\b", r"\bnec fasc\b"],
        "Spinal epidural abscess": [r"\bepidural abscess\b"],
        "Complete heart block": [r"\bheart block\b", r"\bchb\b"],
        "Ventricular tachycardia": [r"\bvtach\b", r"\bv-tach\b"],
        "Community-acquired pneumonia": [r"\bpneumonia\b"],
        "Acute decompensated heart failure": [r"\bheart failure\b", r"\bchf\b"],
        "COPD exacerbation": [r"\bcopd\b"],
        "Uncomplicated UTI": [r"\buti\b"],
        "UTI with delirium": [r"\buti\b"],
        "Subdural hematoma": [r"\bsdh\b", r"\bsubdural\b"],
        "Upper GI bleed": [r"\bugib\b", r"\bvarice"],
        "Perforated peptic ulcer": [r"\bperforat"],
        "Acute cholangitis": [r"\bcholangitis\b"],
        "Acute pancreatitis": [r"\bpancreatitis\b"],
        "Pyelonephritis": [r"\bpyelo"],
        "Meningitis": [r"\bmeningitis\b"],
        "Sepsis": [r"\bsepsis\b", r"\bseptic shock\b"],
        "Brain tumor": [r"\bbrain tumor\b", r"\bbrain tumour\b", r"\bmass lesion\b"],
        "Posterior circulation stroke": [r"\bstroke\b"],
        "Multiple sclerosis relapse": [r"\bmultiple sclerosis\b", r"\bms relapse\b"],
        "Atrial fibrillation with rapid ventricular response": [r"\bafib\b", r"\batrial fibrillation\b"],
        "Hyperthyroidism": [r"\bhyperthyroid"],
        "Costochondritis": [r"\bcostochondritis\b"],
        "BPPV": [r"\bbppv\b"],
        "Viral gastroenteritis": [r"\bgastroenteritis\b"],
        "Uncomplicated diverticulitis": [r"\bdiverticulitis\b"],
        "Diverticulitis with perforation or abscess": [r"\bdiverticulitis\b"],
        "Musculoskeletal back pain": [],
        "Seizure with postictal state": [r"\bepilepsy\b"],
        "Migraine with aura": [r"\bmigraine\b"],
        "Migraine": [r"\bmigraine\b"],
        "Gastritis": [r"\bgastritis\b"],
        "Biliary colic": [r"\bbiliary colic\b"],
        "Nephrolithiasis": [r"\bkidney stone\b", r"\bnephrolithiasis\b"],
        "Hemorrhoids": [r"\bhemorrhoid"],
        "Vasovagal syncope": [r"\bvasovagal\b"],
        "Cellulitis": [r"\bcellulitis\b"],
        "Asthma exacerbation": [r"\basthma\b"],
        "Acute bronchitis": [r"\bbronchitis\b"],
        "Supraventricular tachycardia": [r"\bsvt\b"],
        "Viral syndrome": [],
        "Constipation": [r"\bconstipation\b"],
        "Atrial fibrillation": [r"\bafib\b", r"\batrial fibrillation\b"],
    }
    for name in names:
        extras.extend(aliases.get(name, []))
    return extras


def is_forbidden(text: str, pair: dict) -> str | None:
    hit = contains_forbidden(text, pair)
    if hit:
        return hit
    for pat in extra_forbidden(pair):
        if pat and re.search(pat, text, flags=re.I):
            return pat
    return None


def build_user_prompt(pair: dict, facts: dict, attempt: int) -> str:
    gender_word = (
        "woman" if facts["gender"] == "woman"
        else "man" if facts["gender"] == "man"
        else "nonbinary adult"
    )
    return f"""Create one fictional ED case.

Hidden differential (do not name either in the output):
- Low-risk: {pair['low_risk_disease']}
- High-risk: {pair['high_risk_disease']}

Shared presenting features to include: {pair['shared_symptoms']}
Pair-specific constraint: {pair.get('generation_notes') or 'Keep the story ambiguous.'}

Patient scaffold (use these facts; you may add realistic color):
- Age: {facts['age']}
- Gender: {gender_word}
- Occupation: {facts['occupation']}
- Arrival: {facts['companion']}
- Setting: {facts['setting']}
- Duration: {facts['duration']}
- Suggested associated features: {', '.join(facts['assoc_list'])}
- Suggested background history: {', '.join(facts['hist_list'])}

Voice: {facts['tone']}
{TONE_INSTRUCTIONS[facts['tone']]}

Diversity seed {attempt}: vary wording, sequence, and small social details so this is not a clone of other cases.

JSON schema:
{{
  "symptoms": "semicolon-separated presenting symptoms",
  "case_history_text": "the full case narrative"
}}
"""


def llm_case(client: OpenAI, pair: dict, facts: dict, attempt: int) -> dict:
    last_error = None
    for round_i in range(1, 4):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=0.85,
                max_tokens=700,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(pair, facts, attempt + round_i)},
                ],
            )
            content = response.choices[0].message.content or ""
            payload = parse_json(content)
            text = re.sub(r"\s+", " ", str(payload.get("case_history_text") or "")).strip()
            symptoms = str(payload.get("symptoms") or pair["shared_symptoms"]).strip()
            if len(text) < 280:
                last_error = "too_short"
                continue
            hit = is_forbidden(text, pair) or is_forbidden(symptoms, pair)
            if hit:
                last_error = f"forbidden:{hit}"
                continue
            return {"text": text, "symptoms": symptoms, "error": None}
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1.5 * round_i)
    return {"text": "", "symptoms": "", "error": last_error}


def template_case(pair: dict, facts: dict) -> dict:
    text = RENDERERS[facts["tone"]](facts)
    text = re.sub(r" +", " ", text).strip()
    return {
        "text": text,
        "symptoms": symptoms_field(pair, facts),
        "error": None,
    }


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def make_job(pair: dict, index: int, case_n: int, rng: random.Random) -> dict:
    facts = facts_for(rng, pair, index)
    return {
        "case_n": case_n,
        "index": index,
        "pair": pair,
        "facts": facts,
    }


def row_from(job: dict, text: str, symptoms: str, source: str) -> dict:
    pair = job["pair"]
    facts = job["facts"]
    return {
        "Case_ID": f"CH-{job['case_n']:04d}",
        "Pair_ID": pair["pair_id"],
        "Cluster": pair["cluster"],
        "Symptoms": symptoms,
        "Low_Risk_Disease": pair["low_risk_disease"],
        "High_Risk_Disease": pair["high_risk_disease"],
        "Age": facts["age"],
        "Gender": facts["gender"],
        "Tone": facts["tone"],
        "Source": source,
        "Case_History_Text": text,
    }


def write_outputs(rows: list[dict], report: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
    ]
    csv_path = OUT_DIR / "case_histories.csv"
    json_path = OUT_DIR / "case_histories.json"
    report_path = OUT_DIR / "generation_report.json"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def validate(rows: list[dict]) -> list[str]:
    errors = []
    if len(rows) != 40 * N_PER_PAIR:
        errors.append(f"expected {40 * N_PER_PAIR} rows, got {len(rows)}")
    texts = [r["Case_History_Text"] for r in rows]
    if len(set(texts)) != len(texts):
        errors.append("duplicate case texts")
    by_pair = Counter(r["Pair_ID"] for r in rows)
    bad = {k: v for k, v in by_pair.items() if v != N_PER_PAIR}
    if bad:
        errors.append(f"uneven pair counts: {bad}")
    for r in rows:
        hit = is_forbidden(r["Case_History_Text"], {
            "low_risk_disease": r["Low_Risk_Disease"],
            "high_risk_disease": r["High_Risk_Disease"],
        })
        if hit:
            errors.append(f"{r['Case_ID']} forbidden {hit}")
            if len(errors) > 15:
                break
    return errors


def main() -> int:
    pairs = load_pairs()
    client = make_client()
    rng_master = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = []
    case_n = 0
    for pair in pairs:
        for i in range(N_PER_PAIR):
            case_n += 1
            rng = random.Random(rng_master.randint(0, 10**9) + i * 31)
            jobs.append(make_job(pair, i, case_n, rng))

    lock = Lock()
    used = set()
    rows_by_id: dict[int, dict] = {}
    stats = Counter()
    if CHECKPOINT.exists():
        for line in CHECKPOINT.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = int(row["Case_ID"].split("-")[1])
            rows_by_id[case_id] = row
            used.add(normalize(row["Case_History_Text"]))
            stats[row.get("Source", "llm")] += 1
        print(f"Resuming from checkpoint with {len(rows_by_id)} cases")

    def run_job(job: dict) -> tuple[int, dict, str]:
        pair = job["pair"]
        facts = job["facts"]
        last_error = None
        for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
            result = llm_case(client, pair, facts, attempt)
            if result["error"]:
                last_error = result["error"]
                continue
            key = normalize(result["text"])
            with lock:
                if key in used:
                    last_error = "duplicate"
                    continue
                used.add(key)
            return job["case_n"], row_from(job, result["text"], result["symptoms"], "llm"), "llm"
        # template fallback
        for attempt in range(12):
            rng = random.Random(hash((job["case_n"], attempt)) % (10**9))
            facts2 = facts_for(rng, pair, job["index"])
            result = template_case(pair, facts2)
            if is_forbidden(result["text"], pair) or len(result["text"]) < 280:
                continue
            key = normalize(result["text"])
            with lock:
                if key in used:
                    continue
                used.add(key)
            job = dict(job)
            job["facts"] = facts2
            return job["case_n"], row_from(job, result["text"], result["symptoms"], "template_fallback"), "template_fallback"
        raise RuntimeError(f"failed case {job['case_n']} {pair['pair_id']}: {last_error}")

    pending = [job for job in jobs if job["case_n"] not in rows_by_id]
    print(f"Generating {len(pending)}/{len(jobs)} cases with {MODEL} ({WORKERS} workers)")
    done = len(rows_by_id)
    if pending:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(run_job, job) for job in pending]
            for future in as_completed(futures):
                case_id, row, source = future.result()
                rows_by_id[case_id] = row
                stats[source] += 1
                done += 1
                with CHECKPOINT.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row) + "\n")
                if done % 25 == 0 or done == len(jobs):
                    print(f"  {done}/{len(jobs)}  llm={stats['llm']} fallback={stats['template_fallback']}")

    rows = [rows_by_id[i] for i in range(1, len(jobs) + 1)]
    errors = validate(rows)
    report = {
        "n_cases": len(rows),
        "n_pairs": len(pairs),
        "n_per_pair": N_PER_PAIR,
        "unique_texts": len({r["Case_History_Text"] for r in rows}),
        "source_counts": dict(stats),
        "gender_counts": dict(Counter(r["Gender"] for r in rows)),
        "tone_counts": dict(Counter(r["Tone"] for r in rows)),
        "cluster_counts": dict(Counter(r["Cluster"] for r in rows)),
        "mean_age": round(sum(int(r["Age"]) for r in rows) / len(rows), 1),
        "mean_chars": round(sum(len(r["Case_History_Text"]) for r in rows) / len(rows), 1),
        "min_chars": min(len(r["Case_History_Text"]) for r in rows),
        "max_chars": max(len(r["Case_History_Text"]) for r in rows),
        "generator": f"OpenAI-compatible {MODEL}",
        "model": MODEL,
        "seed": SEED,
        "errors": errors,
    }
    write_outputs(rows, report)
    print(json.dumps({k: report[k] for k in ["n_cases", "unique_texts", "source_counts", "mean_chars", "errors"]}, indent=2))
    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        return 1
    print(f"wrote {OUT_DIR / 'case_histories.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
