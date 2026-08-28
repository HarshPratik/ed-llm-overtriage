#!/usr/bin/env python3
"""Generate 1000 synthetic ED case histories from the 40 disease pairs.

No real PhysioNet notes are used. Cases are compositional: shared symptoms,
varied demographics, tone, and background history. Diagnosis names and
discriminating tests are excluded from the narrative.
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS_PATH = ROOT / "data" / "pairs" / "disease_pairs.json"
OUT_DIR = ROOT / "data" / "synthetic"
N_PER_PAIR = 25
SEED = 20260828

FIRST_F = [
    "Amina", "Sofia", "Priya", "Elena", "Maya", "Nora", "Fatima", "Chloe",
    "Hannah", "Lucia", "Mei", "Aisha", "Grace", "Leila", "Rosa", "Yuki",
    "Ingrid", "Carmen", "Nadia", "Helen", "Ruth", "Denise", "Keisha", "Tara",
    "Anika", "Marisol", "Joan", "Patricia", "Diane", "Linda",
]
FIRST_M = [
    "Omar", "James", "Diego", "Wei", "Andre", "Noah", "Hassan", "Carlos",
    "Marcus", "Raj", "Liam", "Mateo", "Kenji", "Samuel", "Victor", "Ibrahim",
    "Theo", "Owen", "Darius", "Frank", "Harold", "Luis", "Dev", "Peter",
    "Anton", "Jamal", "Sean", "Bruno", "Eric", "Walter",
]
LAST = [
    "Haddad", "Nguyen", "Patel", "Garcia", "Okafor", "Bergstrom", "Kowalski",
    "Silva", "Kim", "Ali", "Rossi", "Mwangi", "Costa", "Hughes", "Bennett",
    "Rahman", "Ibrahim", "Cho", "Martinez", "Walsh", "Diaz", "Okoye", "Singh",
    "Andersen", "Brooks", "Fernandez", "Novak", "Tanaka", "Murphy", "Khan",
]
OCCUPATIONS = [
    "warehouse supervisor", "software engineer", "bus driver",
    "home health aide", "restaurant cook", "accountant", "construction foreman",
    "retail manager", "nurse", "college student", "postal worker", "mechanic",
    "librarian", "security guard", "farmer", "graphic designer", "janitor",
    "high school coach", "pharmacist", "unemployed", "rideshare driver",
    "office administrator", "welder", "daycare worker",
]
RETIRED_OCCUPATIONS = [
    "retired teacher", "retired mechanic", "retired nurse", "retired accountant", "retired postal worker",
]
TONES = [
    "clinician_hpi",
    "patient_first",
    "triage_note",
    "family",
    "portal",
    "ems",
]
SETTINGS = [
    "the emergency department",
    "the emergency department after an urgent-care transfer",
    "the emergency department after a midnight walk-in",
    "the emergency department after EMS was called",
    "the emergency department on a weekend",
    "the emergency department during a busy afternoon",
]
DURATIONS = [
    "the past 45 minutes",
    "about two hours",
    "since last night",
    "the last three hours",
    "most of today",
    "the past day",
    "roughly six hours",
    "on and off since yesterday evening",
]

GLOBAL_FORBIDDEN = [
    r"\btroponin\b", r"\bd-?dimer\b", r"\bctpa\b", r"\bcta\b", r"\bmri showed\b",
    r"\bct showed\b", r"\becg showed\b", r"\bekg showed\b", r"\bst[ -]?elevation\b",
    r"\bwells score\b", r"\bbnp\b", r"\blipase\b", r"\bnstemi\b", r"\bstemi\b",
    r"\bheart attack\b", r"\bmyocardial infarction\b", r"\baortic dissection\b",
    r"\bpulmonary embolism\b", r"\bsubarachnoid\b", r"\bmeningitis\b",
    r"\bappendicitis\b", r"\bcholangitis\b", r"\bnecrotizing\b",
    r"\bepidural abscess\b", r"\bdiagnosed with\b", r"\bthe diagnosis is\b",
]

CLUSTER_BANKS = {
    "chest_pain": {
        "chiefs": [
            "a heavy pressure in the chest",
            "a burning discomfort behind the breastbone",
            "tightness across the upper chest",
            "an aching squeeze in the chest",
            "a dull weight sitting on the chest",
            "chest discomfort that comes in waves",
            "a sharp then lingering ache in the chest",
            "a band-like tightness through the chest",
        ],
        "onsets": [
            "after a large spicy meal",
            "while climbing a flight of stairs",
            "at rest on the couch",
            "after a cup of coffee",
            "overnight, waking from sleep",
            "while carrying groceries",
            "after bending to tie shoes",
            "during a stressful phone call",
        ],
        "assoc": [
            "mild nausea",
            "a sheen of sweat",
            "shortness of breath",
            "a sour taste in the mouth",
            "lightheadedness",
            "an uneasy feeling in the stomach",
            "fatigue out of proportion to the day",
            "a dry cough",
        ],
        "histories": [
            "occasional indigestion",
            "high blood pressure",
            "high cholesterol",
            "type 2 diabetes",
            "a long smoking history, now cut down",
            "anxiety treated years ago",
            "obesity and a sedentary job",
            "a parent with early heart disease",
        ],
    },
    "dyspnea": {
        "chiefs": [
            "shortness of breath",
            "a feeling of not getting a full breath",
            "air hunger",
            "tightness when breathing",
            "breathlessness with minimal walking",
            "a catch in the breath with each inhale",
        ],
        "onsets": [
            "over the past several hours",
            "suddenly this morning",
            "after a coughing fit",
            "while walking from the parking lot",
            "overnight, worse when lying flat",
            "after a long car ride",
            "following two days of a cold",
            "without a clear trigger",
        ],
        "assoc": [
            "a dry cough",
            "a productive cough",
            "chest tightness",
            "wheezing heard by a family member",
            "a low-grade feverish feeling",
            "leg heaviness",
            "lightheadedness",
            "sweating",
        ],
        "histories": [
            "years of smoking",
            "seasonal allergies",
            "high blood pressure",
            "a prior blood clot in a relative",
            "recent long travel",
            "obesity",
            "poorly controlled blood pressure",
            "a recent respiratory infection",
        ],
    },
    "palpitations": {
        "chiefs": [
            "a racing heartbeat",
            "a fluttering in the chest",
            "skipped beats that became a run of pounding",
            "a rapid, pounding pulse",
        ],
        "onsets": [
            "while sitting at a desk",
            "after climbing stairs",
            "overnight",
            "during an argument",
            "after extra coffee",
            "without warning at work",
        ],
        "assoc": [
            "lightheadedness",
            "shortness of breath",
            "chest tightness",
            "sweating",
            "a shaky feeling",
            "fatigue",
        ],
        "histories": [
            "thyroid issues in the family",
            "high blood pressure",
            "anxiety",
            "heavy caffeine use",
            "prior palpitations that always stopped",
            "sleep problems",
        ],
    },
    "headache": {
        "chiefs": [
            "a severe headache",
            "a pounding headache",
            "a sudden intense headache",
            "a one-sided throbbing headache",
            "a headache that built then stayed severe",
        ],
        "onsets": [
            "this morning at work",
            "while straining in the bathroom",
            "after a bright, noisy commute",
            "overnight",
            "during a meeting",
            "after skipping lunch",
        ],
        "assoc": [
            "nausea",
            "sensitivity to light",
            "a stiff, sore neck",
            "visual shimmering",
            "vomiting once",
            "dizziness",
            "a low feverish feeling",
            "trouble finding words for a minute",
        ],
        "histories": [
            "occasional headaches",
            "high blood pressure",
            "migraines in a sibling",
            "recent viral illness",
            "smoking",
            "anticoagulant use for another reason",
        ],
    },
    "neuro": {
        "chiefs": [
            "dizziness",
            "a spinning sensation",
            "a spell of weakness",
            "confusion after a brief episode",
            "unsteady walking",
        ],
        "onsets": [
            "when rolling over in bed",
            "after standing quickly",
            "this afternoon without warning",
            "after a brief staring spell",
            "on waking",
            "during breakfast",
        ],
        "assoc": [
            "nausea",
            "slurred speech for a few minutes",
            "numbness in one arm",
            "blurred vision",
            "a headache",
            "fatigue",
            "trouble keeping balance",
        ],
        "histories": [
            "high blood pressure",
            "diabetes",
            "prior similar spells",
            "smoking",
            "atrial fibrillation in a parent",
            "recent sleep deprivation",
        ],
    },
    "abdominal": {
        "chiefs": [
            "abdominal pain",
            "cramping in the belly",
            "a deep ache in the abdomen",
            "upper abdominal burning",
            "pain around the navel that later shifted",
        ],
        "onsets": [
            "after dinner",
            "overnight",
            "this morning after coffee",
            "over the past day",
            "after fatty food",
            "following two days of little stool",
        ],
        "assoc": [
            "nausea",
            "vomiting",
            "bloating",
            "a low-grade feverish feeling",
            "loss of appetite",
            "diarrhea",
            "constipation",
            "belching",
        ],
        "histories": [
            "right-upper-belly pain after fatty meals years ago",
            "frequent antacid use",
            "prior abdominal surgery",
            "alcohol use on weekends",
            "NSAID use for joint pain",
            "irritable bowels by self-report",
        ],
    },
    "flank": {
        "chiefs": [
            "flank pain",
            "pain in the side wrapping toward the groin",
            "a stabbing ache in the lower back on one side",
        ],
        "onsets": [
            "overnight",
            "after a long drive",
            "this morning",
            "after heavy lifting",
        ],
        "assoc": [
            "nausea",
            "vomiting once",
            "urinary urgency",
            "a feverish feeling",
            "blood-tinged urine mentioned by the patient",
            "restlessness",
        ],
        "histories": [
            "prior kidney stones",
            "recurrent urinary infections",
            "dehydration from work in heat",
            "diabetes",
        ],
    },
    "gi_bleed": {
        "chiefs": [
            "rectal bleeding",
            "dark sticky stools",
            "bright red blood with bowel movements",
            "black stools noticed today",
        ],
        "onsets": [
            "over the past day",
            "after straining",
            "since last night",
            "after several days of constipation",
        ],
        "assoc": [
            "fatigue",
            "lightheadedness on standing",
            "mild abdominal cramping",
            "nausea",
            "a racing heart when walking",
        ],
        "histories": [
            "straining with bowel movements for years",
            "daily ibuprofen for pain",
            "alcohol use",
            "blood thinner for another condition",
            "known liver disease in the family",
        ],
    },
    "syncope": {
        "chiefs": [
            "a brief loss of consciousness",
            "a near-fainting spell",
            "passing out for a few seconds",
            "a sudden slump to the floor",
        ],
        "onsets": [
            "after standing in a warm room",
            "while using the bathroom",
            "after a coughing fit",
            "without warning at the table",
            "after standing from a chair",
        ],
        "assoc": [
            "sweating beforehand",
            "nausea",
            "a slow recovery of color",
            "palpitations",
            "no clear warning",
            "confusion for a minute afterward",
        ],
        "histories": [
            "dehydration",
            "blood pressure medicine recently increased",
            "anemia mentioned last year",
            "a murmur never evaluated",
            "diabetes",
        ],
    },
    "ams": {
        "chiefs": [
            "confusion",
            "not acting like the usual self",
            "waxing and waning alertness",
            "disorientation to the day",
        ],
        "onsets": [
            "over the past day",
            "since a minor bump to the head last week",
            "after a fall at home",
            "overnight",
        ],
        "assoc": [
            "low-grade fever",
            "urinary frequency",
            "unsteady gait",
            "a headache",
            "poor oral intake",
            "sleepiness",
        ],
        "histories": [
            "blood thinner after a prior clot",
            "recurrent urinary infections",
            "mild memory problems",
            "lives alone with a walker",
            "diabetes and high blood pressure",
        ],
    },
    "fever": {
        "chiefs": [
            "fever",
            "feeling burned up and weak",
            "shaking chills then fever",
            "a high temperature at home",
        ],
        "onsets": [
            "since last night",
            "over two days",
            "after a day of urinary burning",
            "this afternoon",
        ],
        "assoc": [
            "burning with urination",
            "backache",
            "nausea",
            "confusion",
            "fast breathing noticed by family",
            "muscle aches",
        ],
        "histories": [
            "recurrent bladder infections",
            "diabetes",
            "a recent hospital stay",
            "kidney stones years ago",
            "an indwelling catheter at times",
        ],
    },
    "leg": {
        "chiefs": [
            "pain and swelling in one leg",
            "a heavy, aching calf",
            "one-sided ankle and calf swelling",
            "redness and tightness in the lower leg",
        ],
        "onsets": [
            "over two days",
            "after a long flight",
            "since a small scrape",
            "after sitting through a conference",
        ],
        "assoc": [
            "warmth over the area",
            "mild feverish feeling",
            "pain when walking",
            "tightness of the skin",
            "no injury remembered",
        ],
        "histories": [
            "prior clot in the family",
            "recent surgery",
            "obesity",
            "athlete's foot",
            "diabetes",
            "estrogen therapy",
        ],
    },
    "soft_tissue": {
        "chiefs": [
            "spreading redness in the skin",
            "a painful swollen patch on the limb",
            "an infection in the skin that is getting worse",
        ],
        "onsets": [
            "over 24 hours",
            "after a small cut",
            "since a bug bite",
            "after a day of fever",
        ],
        "assoc": [
            "fever",
            "pain that seems worse than the skin looks",
            "rapid swelling",
            "chills",
            "fatigue",
        ],
        "histories": [
            "diabetes",
            "a neglected puncture wound last week",
            "a prior similar infection",
            "obesity",
            "chronic wounds",
        ],
    },
    "back_pain": {
        "chiefs": [
            "severe low back pain",
            "midline back pain",
            "back pain shooting into a leg",
            "a deep ache in the lumbar spine",
        ],
        "onsets": [
            "after lifting a box",
            "over several days",
            "after a feverish week",
            "without a clear injury",
        ],
        "assoc": [
            "fever",
            "leg numbness",
            "trouble urinating",
            "night pain",
            "muscle spasm",
            "fatigue",
        ],
        "histories": [
            "prior disc problems",
            "a recent skin abscess treated as an outpatient",
            "diabetes",
            "a recent skin infection",
            "office work with poor ergonomics",
            "osteoporosis mentioned once",
        ],
    },
}

PAIR_OVERRIDES = {
    "PAIR-001": {"age": (34, 78), "extra_hist": ["heartburn after late meals", "an uncle with early heart disease"]},
    "PAIR-002": {"age": (38, 80), "extra_hist": ["untreated high blood pressure"]},
    "PAIR-003": {"age": (22, 72), "extra_hist": ["recent upper-body workout", "a desk job with poor posture"]},
    "PAIR-004": {"age": (40, 82), "extra_hist": ["longstanding high blood pressure", "a family history of vascular disease"]},
    "PAIR-005": {"age": (48, 84), "extra_hist": ["an irregular heartbeat mentioned once", "sleep apnea untreated"]},
    "PAIR-006": {"age": (28, 70), "extra_hist": ["oral contraceptive use", "recent ankle sprain with reduced walking"]},
    "PAIR-007": {"age": (52, 82), "extra_hist": ["home nebulizer treatments", "a long smoking history"]},
    "PAIR-008": {"age": (22, 68), "extra_hist": ["childhood wheezing", "high blood pressure"]},
    "PAIR-009": {"age": (18, 70), "extra_hist": ["a week of a lingering cold"]},
    "PAIR-010": {"age": (50, 84), "extra_hist": ["home nebulizer", "steroid bursts twice a year"]},
    "PAIR-011": {"age": (55, 86), "extra_hist": ["swollen ankles some evenings", "sleeps on two pillows sometimes"]},
    "PAIR-012": {"age": (48, 86), "extra_hist": ["a productive cough last winter"]},
    "PAIR-013": {"age": (24, 78), "extra_hist": ["recent orthopedic surgery", "oral contraceptives"]},
    "PAIR-014": {"age": (18, 50), "extra_hist": ["inhaler as needed", "recent long bus trip"]},
    "PAIR-015": {"age": (55, 88), "extra_hist": ["swollen legs in the evenings", "sleeps on two pillows"]},
    "PAIR-016": {"age": (18, 72), "extra_hist": ["energy drinks", "prior racing-heart spells that always stopped"]},
    "PAIR-017": {"age": (22, 55), "extra_hist": ["weight loss without trying", "heat intolerance"]},
    "PAIR-018": {"age": (22, 70), "extra_hist": ["smoking", "prior similar headaches"]},
    "PAIR-019": {"age": (20, 68), "extra_hist": ["oral contraceptives", "headaches in a parent"]},
    "PAIR-020": {"age": (28, 72), "extra_hist": ["morning headaches", "subtle personality change per spouse"]},
    "PAIR-021": {"age": (16, 45), "extra_hist": ["college roommate with a viral illness", "recent sore throat in contacts"]},
    "PAIR-022": {"age": (40, 82), "extra_hist": ["diabetes", "high blood pressure"]},
    "PAIR-023": {"age": (18, 78), "extra_hist": ["poor sleep for several nights", "sleep deprivation"]},
    "PAIR-024": {"age": (22, 48), "extra_hist": ["prior optic symptoms years ago", "fatigue in heat"]},
    "PAIR-025": {"age": (18, 80), "extra_hist": ["prior abdominal surgery years ago", "little oral intake"]},
    "PAIR-026": {"age": (16, 45), "extra_hist": ["no prior surgeries", "recent viral contacts"]},
    "PAIR-027": {"age": (45, 88), "extra_hist": ["opioid pain medicine", "low fiber diet"]},
    "PAIR-028": {"age": (28, 75), "extra_hist": ["right-upper-belly pain after fatty meals years ago", "a low-grade fever last night"]},
    "PAIR-029": {"age": (28, 70), "extra_hist": ["weekend alcohol", "right-upper-belly pain after fatty meals years ago"]},
    "PAIR-030": {"age": (28, 72), "extra_hist": ["daily ibuprofen", "smoking"]},
    "PAIR-031": {"age": (45, 82), "extra_hist": ["constipation", "a screening colonoscopy years ago"]},
    "PAIR-032": {"age": (40, 80), "extra_hist": ["diabetes", "indigestion after meals"]},
    "PAIR-033": {"age": (22, 68), "extra_hist": ["prior stones", "recent dehydration after outdoor work"]},
    "PAIR-034": {"age": (28, 86), "extra_hist": ["blood thinner", "daily NSAIDs"]},
    "PAIR-035": {"age": (18, 88), "extra_hist": ["beta blocker", "dehydration"]},
    "PAIR-036": {"age": (68, 92), "extra_hist": ["a blood thinner after a prior clot", "a ground-level fall last week"]},
    "PAIR-037": {"age": (22, 88), "extra_hist": ["diabetes", "indwelling catheter at times"]},
    "PAIR-038": {"age": (24, 80), "extra_hist": ["recent flight", "a small calf scrape"]},
    "PAIR-039": {"age": (22, 70), "extra_hist": ["diabetes", "a neglected puncture wound"]},
    "PAIR-040": {"age": (28, 75), "extra_hist": ["a recent skin infection", "poorly controlled diabetes"]},
}

PRONOUNS = {
    "woman": ("She", "she", "her", "her", "hers"),
    "man": ("He", "he", "him", "his", "his"),
    "person": ("They", "they", "them", "their", "theirs"),
}


def load_pairs() -> list[dict]:
    payload = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    return payload["pairs"]


def pick_person(rng: random.Random, age_lo: int, age_hi: int, case_i: int) -> dict:
    roll = case_i % 20
    if roll == 19:
        gender = "person"
        first = rng.choice(FIRST_F + FIRST_M)
    elif case_i % 2 == 0:
        gender = "woman"
        first = rng.choice(FIRST_F)
    else:
        gender = "man"
        first = rng.choice(FIRST_M)
    age = rng.randint(age_lo, age_hi)
    last = rng.choice(LAST)
    occupation = rng.choice(OCCUPATIONS)
    if age >= 70 and rng.random() < 0.55:
        occupation = rng.choice(RETIRED_OCCUPATIONS)
    if age <= 22:
        occupation = rng.choice(["college student", "retail manager", "daycare worker", "unemployed"])
    subj, subj_l, obj, poss, poss_abs = PRONOUNS[gender]
    return {
        "first": first,
        "last": last,
        "age": age,
        "gender": gender,
        "occupation": occupation,
        "Subj": subj,
        "subj": subj_l,
        "obj": obj,
        "poss": poss,
    }


def join_list(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def occupation_clause(occupation: str, person: str = "third") -> str:
    if person == "first":
        if occupation == "unemployed":
            return "I am currently unemployed"
        if occupation.startswith("retired"):
            return f"I am a {occupation}"
        return f"I work as {article(occupation)} {occupation}"
    if occupation == "unemployed":
        return "is currently unemployed"
    if occupation.startswith("retired"):
        return f"is a {occupation}"
    return f"works as {article(occupation)} {occupation}"


def arrived_how(companion: str) -> str:
    return "alone" if companion == "alone" else companion


def duration_for(duration: str) -> str:
    if duration.startswith(("since", "on and off", "after")):
        return duration
    return f"for {duration}"


def facts_for(rng: random.Random, pair: dict, case_i: int) -> dict:
    cluster = pair["cluster"]
    bank = CLUSTER_BANKS[cluster]
    over = PAIR_OVERRIDES[pair["pair_id"]]
    person = pick_person(rng, *over["age"], case_i)
    chiefs = list(bank["chiefs"])
    onsets = list(bank["onsets"])
    assoc = list(bank["assoc"])
    hist = list(bank["histories"]) + list(over.get("extra_hist", []))
    rng.shuffle(chiefs)
    rng.shuffle(onsets)
    rng.shuffle(assoc)
    rng.shuffle(hist)
    n_assoc = 2 + (case_i % 3)
    n_hist = 1 + (case_i % 3)
    tone = TONES[case_i % len(TONES)]
    setting = SETTINGS[(case_i * 3) % len(SETTINGS)]
    duration = DURATIONS[(case_i * 5) % len(DURATIONS)]
    return {
        **person,
        "pair": pair,
        "chief": chiefs[0],
        "onset": onsets[0],
        "assoc_list": assoc[:n_assoc],
        "hist_list": hist[:n_hist],
        "tone": tone,
        "setting": setting,
        "duration": duration,
        "companion": rng.choice(
            ["alone", "with a spouse", "with an adult child", "with a coworker", "with a neighbor"]
        ),
        "pain": rng.choice(["4/10", "5/10", "6/10", "7/10", "hard to rate"]),
        "temp": rng.choice(["36.8 C", "37.2 C", "37.6 C", "38.1 C", "not recorded at the door"]),
        "hr": rng.choice(["78", "88", "96", "104", "112", "62"]),
        "sbp": rng.choice(["118", "132", "146", "158", "108"]),
        "rr": rng.choice(["16", "18", "20", "22", "24"]),
        "o2": rng.choice(["98% on room air", "96% on room air", "94% on room air", "93% on room air"]),
    }


def vitals_line(f: dict) -> str:
    return (
        f"Door vitals, if obtained, were temperature {f['temp']}, heart rate {f['hr']}, "
        f"blood pressure {f['sbp']}/80s, respiratory rate {f['rr']}, oxygen saturation {f['o2']}. "
        "No laboratory or imaging results are available yet."
    )


def render_clinician(f: dict) -> str:
    assoc = join_list(f["assoc_list"])
    hist = join_list(f["hist_list"])
    gword = "woman" if f["gender"] == "woman" else "man" if f["gender"] == "man" else "adult"
    return (
        f"{f['first']} {f['last']} is a {f['age']}-year-old {gword} who {occupation_clause(f['occupation'])} "
        f"and presents to {f['setting']} {arrived_how(f['companion'])} for {f['chief']} lasting {f['duration']}. "
        f"The symptoms began {f['onset']}. Associated features include {assoc}. "
        f"Pain is described as {f['pain']}. Background history includes {hist}. "
        f"{f['Subj']} denies a ready explanation and has not taken a new prescription today. "
        f"{vitals_line(f)} The remainder of the story is intentionally limited to the history of present illness."
    )


def render_patient(f: dict) -> str:
    assoc = join_list(f["assoc_list"])
    hist = join_list(f["hist_list"])
    return (
        f"I'm {f['first']}, {f['age']}. {occupation_clause(f['occupation'], 'first')}. {duration_for(f['duration']).capitalize()} I've had {f['chief']}. "
        f"It started {f['onset']}. I also have {assoc}. I'd call it {f['pain']}. "
        f"I do have {hist}. I came to the hospital {f['companion']}. "
        f"Nobody has told me test results. I just want someone to figure out if this is dangerous or not."
    )


def render_triage(f: dict) -> str:
    assoc = "; ".join(f["assoc_list"])
    hist = "; ".join(f["hist_list"])
    g = f["gender"][0].upper()
    return (
        f"CC: {f['chief']}. {f['age']}{g} {f['occupation']}. Onset {f['duration']}, began {f['onset']}. "
        f"Associated: {assoc}. Pain {f['pain']}. PMH/context: {hist}. Arrival {f['companion']}. "
        f"T {f['temp']} HR {f['hr']} BP {f['sbp']}/82 RR {f['rr']} SpO2 {f['o2']}. "
        f"No labs/imaging back. Patient in {f['setting']}."
    )


def render_family(f: dict) -> str:
    assoc = join_list(f["assoc_list"])
    hist = join_list(f["hist_list"])
    rel = "my wife" if f["gender"] == "woman" else "my husband" if f["gender"] == "man" else "my partner"
    return (
        f"This is about {rel}, {f['first']}, who is {f['age']} and {occupation_clause(f['occupation'])}. "
        f"{duration_for(f['duration']).capitalize()} {f['subj']} has had {f['chief']}, starting {f['onset']}. "
        f"We also noticed {assoc}. {f['Subj']} has {hist}. "
        f"We came in {('together' if f['companion'] in {'alone', 'with a spouse'} else f['companion'])}. "
        f"Nobody has given us scan or blood results yet. We are worried it could be serious, but we do not know."
    )


def render_portal(f: dict) -> str:
    assoc = join_list(f["assoc_list"])
    hist = join_list(f["hist_list"])
    return (
        f"Hi, I am {f['first']} {f['last']}, {f['age']}. {occupation_clause(f['occupation'], 'first')}. "
        f"I have had {f['chief']} {duration_for(f['duration'])}. It started {f['onset']}. "
        f"Also {assoc}. History: {hist}. Pain about {f['pain']}. "
        f"I am writing from {f['setting']}. No test results have been shared with me."
    )


def render_ems(f: dict) -> str:
    g = "F" if f["gender"] == "woman" else "M" if f["gender"] == "man" else "X"
    assoc = ", ".join(f["assoc_list"])
    hist = ", ".join(f["hist_list"])
    return (
        f"{f['age']}{g} {f['occupation']}, arrived {arrived_how(f['companion'])}. "
        f"Chief complaint {f['chief']} x {f['duration']}, began {f['onset']}. "
        f"Associated {assoc}. Background {hist}. "
        f"Vitals T {f['temp']} HR {f['hr']} BP {f['sbp']}/80 RR {f['rr']} SpO2 {f['o2']}. "
        f"No 12-lead interpretation provided. No point-of-care labs. Transport to {f['setting']}."
    )


RENDERERS = {
    "clinician_hpi": render_clinician,
    "patient_first": render_patient,
    "triage_note": render_triage,
    "family": render_family,
    "portal": render_portal,
    "ems": render_ems,
}


def forbidden_patterns(pair: dict) -> list[str]:
    extra = [
        re.escape(pair["low_risk_disease"]),
        re.escape(pair["high_risk_disease"]),
    ]
    return GLOBAL_FORBIDDEN + extra


def contains_forbidden(text: str, pair: dict) -> str | None:
    for pat in forbidden_patterns(pair):
        if re.search(pat, text, flags=re.I):
            return pat
    return None


def symptoms_field(pair: dict, facts: dict) -> str:
    bits = [pair["shared_symptoms"], facts["chief"], *facts["assoc_list"]]
    # de-dupe while preserving order
    seen = set()
    out = []
    for b in bits:
        key = b.lower()
        if key not in seen:
            seen.add(key)
            out.append(b)
    return "; ".join(out)


def generate() -> tuple[list[dict], dict]:
    pairs = load_pairs()
    rng_master = random.Random(SEED)
    rows: list[dict] = []
    retries = 0
    case_n = 0
    for pair in pairs:
        used_text = set()
        for i in range(N_PER_PAIR):
            for attempt in range(40):
                rng = random.Random(rng_master.randint(0, 10**9) + i * 17 + attempt)
                facts = facts_for(rng, pair, i)
                text = RENDERERS[facts["tone"]](facts)
                text = re.sub(r" +", " ", text).strip()
                hit = contains_forbidden(text, pair)
                key = re.sub(r"\W+", " ", text.lower()).strip()
                if hit or key in used_text or len(text) < 280:
                    retries += 1
                    continue
                used_text.add(key)
                case_n += 1
                rows.append(
                    {
                        "Case_ID": f"CH-{case_n:04d}",
                        "Pair_ID": pair["pair_id"],
                        "Cluster": pair["cluster"],
                        "Symptoms": symptoms_field(pair, facts),
                        "Low_Risk_Disease": pair["low_risk_disease"],
                        "High_Risk_Disease": pair["high_risk_disease"],
                        "Age": facts["age"],
                        "Gender": facts["gender"],
                        "Tone": facts["tone"],
                        "Case_History_Text": text,
                    }
                )
                break
            else:
                raise RuntimeError(f"Could not build unique case for {pair['pair_id']} index {i}")
    report = {
        "n_cases": len(rows),
        "n_pairs": len(pairs),
        "n_per_pair": N_PER_PAIR,
        "retries": retries,
        "unique_texts": len({r["Case_History_Text"] for r in rows}),
        "gender_counts": dict(Counter(r["Gender"] for r in rows)),
        "tone_counts": dict(Counter(r["Tone"] for r in rows)),
        "cluster_counts": dict(Counter(r["Cluster"] for r in rows)),
        "mean_age": round(sum(r["Age"] for r in rows) / len(rows), 1),
        "mean_chars": round(sum(len(r["Case_History_Text"]) for r in rows) / len(rows), 1),
        "min_chars": min(len(r["Case_History_Text"]) for r in rows),
        "max_chars": max(len(r["Case_History_Text"]) for r in rows),
        "generator": "compositional templates (no LLM; no PhysioNet note text)",
        "seed": SEED,
    }
    return rows, report


def validate(rows: list[dict]) -> list[str]:
    errors = []
    if len(rows) != 40 * N_PER_PAIR:
        errors.append(f"expected {40 * N_PER_PAIR} rows, got {len(rows)}")
    texts = [r["Case_History_Text"] for r in rows]
    if len(set(texts)) != len(texts):
        errors.append("duplicate case texts")
    by_pair = Counter(r["Pair_ID"] for r in rows)
    bad_pairs = {k: v for k, v in by_pair.items() if v != N_PER_PAIR}
    if bad_pairs:
        errors.append(f"uneven pair counts: {bad_pairs}")
    for r in rows:
        hit = contains_forbidden(r["Case_History_Text"], {
            "low_risk_disease": r["Low_Risk_Disease"],
            "high_risk_disease": r["High_Risk_Disease"],
        })
        if hit:
            errors.append(f"{r['Case_ID']} forbidden {hit}")
            if len(errors) > 12:
                break
    genders = Counter(r["Gender"] for r in rows)
    if genders["woman"] < 350 or genders["man"] < 350:
        errors.append(f"gender imbalance {dict(genders)}")
    return errors


def main() -> int:
    rows, report = generate()
    errors = validate(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "case_histories.csv"
    json_path = OUT_DIR / "case_histories.json"
    report_path = OUT_DIR / "generation_report.json"
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
        "Case_History_Text",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    report["errors"] = errors
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        return 1
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
