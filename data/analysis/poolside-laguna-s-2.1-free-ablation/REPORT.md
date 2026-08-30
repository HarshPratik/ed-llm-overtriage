# Phase 3–4 analysis

Target model: **Laguna S-2.1**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

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

- High-risk pole: 489 (48.9%, 95% CI 45.8–52.0)
- Low-risk pole: 215 (21.5%)
- Other: 296 (29.6%)

Among cases mapped to either pole (n = 704):

- High-risk pole: 69.46% (95% CI 66.0–72.7)
- Binomial test vs 50%, alternative = greater: p = 9.605e-26
- Two-sided binomial p = 1.921e-25
- Chi-square vs 50/50: χ² = 106.64, p = 5.333e-25

Broad over-triage (high-risk pole or another emergency diagnosis): 68.5% of 1000 (p = 1.792e-32 vs 50%).

Model self-label High: 87.5% of 1000 (p = 1.767e-139 vs 50%).

Per-pair high-risk-pole rate: mean 48.9%, SD 32.8%, variance 1076.09, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 100.0% high-risk pole
- PAIR-038 Cellulitis vs Deep vein thrombosis: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 96.0% high-risk pole
- PAIR-023 Seizure with postictal state vs Ischemic stroke: 96.0% high-risk pole
- PAIR-034 Hemorrhoids vs Upper GI bleed: 92.0% high-risk pole
- PAIR-005 Atrial fibrillation vs NSTEMI: 88.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-030 Gastritis vs Perforated peptic ulcer: 0.0% high-risk pole (10 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (12 other)
- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (4 other)
- PAIR-020 Migraine vs Brain tumor: 4.0% high-risk pole (21 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 4.0% high-risk pole (22 other)
- PAIR-003 Costochondritis vs STEMI: 8.0% high-risk pole (11 other)

## Clusters

- leg: high-risk pole 100.0% (self-High 100.0%)
- gi_bleed: high-risk pole 92.0% (self-High 100.0%)
- fever: high-risk pole 80.0% (self-High 92.0%)
- neuro: high-risk pole 76.0% (self-High 89.3%)
- chest_pain: high-risk pole 61.6% (self-High 88.8%)
- back_pain: high-risk pole 56.0% (self-High 96.0%)
- dyspnea: high-risk pole 54.4% (self-High 94.4%)
- headache: high-risk pole 54.0% (self-High 91.0%)
- ams: high-risk pole 32.0% (self-High 100.0%)
- abdominal: high-risk pole 26.0% (self-High 75.5%)
- palpitations: high-risk pole 26.0% (self-High 76.0%)
- soft_tissue: high-risk pole 20.0% (self-High 100.0%)
- flank: high-risk pole 12.0% (self-High 68.0%)
- syncope: high-risk pole 8.0% (self-High 68.0%)

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
