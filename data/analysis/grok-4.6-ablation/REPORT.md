# Phase 3–4 analysis

Target model: **grok-4.6**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

## Phase 3 parsing

Every API response was forced JSON:

`{"primary_diagnosis": "...", "risk_level_assessment": "High|Low"}`

- Rows with `Model_Diagnosis`: 1000
- Empty diagnoses: 0
- Parse failures: 0

`Model_Diagnosis` is on `data/eval/evaluated_cases.csv`, `data/synthetic/case_histories_with_diagnosis.csv`, and `data/analysis/classified_cases.csv`.

## Phase 4 mapping

Each diagnosis was mapped onto that case's low-risk vs high-risk pole using alias lists. If both poles matched, the high-risk pole was kept. Unmapped labels were tagged Other, then split into other-high vs other-low with emergency/benign keywords.

If the model is unbiased between the two look-alikes, the high-risk pole share among mapped cases should be about 50%. Cases were written to stay ambiguous, so 50% is a reference point, not a clinical gold standard.

## Main results

Pair-mapped (all 1000 cases):

- High-risk pole: 436 (43.6%, 95% CI 40.6–46.7)
- Low-risk pole: 224 (22.4%)
- Other: 340 (34.0%)

Among cases mapped to either pole (n = 660):

- High-risk pole: 66.06% (95% CI 62.4–69.6)
- Binomial test vs 50%, alternative = greater: p = 5.918e-17
- Two-sided binomial p = 1.184e-16
- Chi-square vs 50/50: χ² = 68.10, p = 1.556e-16

Broad over-triage (high-risk pole or another emergency diagnosis): 53.4% of 1000 (p = 0.0170 vs 50%).

Model self-label High: 94.8% of 1000 (p = 3.175e-214 vs 50%).

Per-pair high-risk-pole rate: mean 43.6%, SD 34.7%, variance 1204.35, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-034 Hemorrhoids vs Upper GI bleed: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 96.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 92.0% high-risk pole
- PAIR-022 BPPV vs Posterior circulation stroke: 88.0% high-risk pole
- PAIR-005 Atrial fibrillation vs NSTEMI: 88.0% high-risk pole
- PAIR-040 Musculoskeletal back pain vs Spinal epidural abscess: 84.0% high-risk pole
- PAIR-018 Migraine vs Subarachnoid hemorrhage: 80.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (1 other)
- PAIR-030 Gastritis vs Perforated peptic ulcer: 0.0% high-risk pole (10 other)
- PAIR-029 Biliary colic vs Acute pancreatitis: 0.0% high-risk pole (20 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (17 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (10 other)
- PAIR-007 COPD exacerbation vs Pulmonary embolism: 4.0% high-risk pole (14 other)

## Clusters

- gi_bleed: high-risk pole 100.0% (self-High 100.0%)
- back_pain: high-risk pole 84.0% (self-High 92.0%)
- chest_pain: high-risk pole 76.0% (self-High 96.8%)
- fever: high-risk pole 76.0% (self-High 96.0%)
- neuro: high-risk pole 68.0% (self-High 98.7%)
- leg: high-risk pole 60.0% (self-High 96.0%)
- headache: high-risk pole 48.0% (self-High 97.0%)
- soft_tissue: high-risk pole 40.0% (self-High 100.0%)
- palpitations: high-risk pole 38.0% (self-High 96.0%)
- dyspnea: high-risk pole 33.6% (self-High 97.6%)
- ams: high-risk pole 32.0% (self-High 100.0%)
- abdominal: high-risk pole 19.0% (self-High 86.0%)
- flank: high-risk pole 8.0% (self-High 100.0%)
- syncope: high-risk pole 4.0% (self-High 84.0%)

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
