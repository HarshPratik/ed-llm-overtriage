# Phase 3–4 analysis

Target model: **MiniMax M3**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

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

- High-risk pole: 469 (46.9%, 95% CI 43.8–50.0)
- Low-risk pole: 221 (22.1%)
- Other: 310 (31.0%)

Among cases mapped to either pole (n = 690):

- High-risk pole: 67.97% (95% CI 64.4–71.3)
- Binomial test vs 50%, alternative = greater: p = 9.783e-22
- Two-sided binomial p = 1.957e-21
- Chi-square vs 50/50: χ² = 89.14, p = 3.685e-21

Broad over-triage (high-risk pole or another emergency diagnosis): 64.5% of 1000 (p = 1.728e-20 vs 50%).

Model self-label High: 87.4% of 1000 (p = 1.229e-138 vs 50%).

Per-pair high-risk-pole rate: mean 46.9%, SD 35.19%, variance 1238.14, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 96.0% high-risk pole
- PAIR-038 Cellulitis vs Deep vein thrombosis: 96.0% high-risk pole
- PAIR-004 GERD vs Aortic dissection: 96.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 96.0% high-risk pole
- PAIR-037 Uncomplicated UTI vs Sepsis: 96.0% high-risk pole
- PAIR-017 Hyperthyroidism vs Atrial fibrillation with rapid ventricular response: 92.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-020 Migraine vs Brain tumor: 0.0% high-risk pole (24 other)
- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (2 other)
- PAIR-029 Biliary colic vs Acute pancreatitis: 0.0% high-risk pole (24 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (24 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (6 other)
- PAIR-003 Costochondritis vs STEMI: 8.0% high-risk pole (18 other)

## Clusters

- fever: high-risk pole 96.0% (self-High 96.0%)
- leg: high-risk pole 96.0% (self-High 96.0%)
- gi_bleed: high-risk pole 84.0% (self-High 92.0%)
- chest_pain: high-risk pole 76.0% (self-High 92.0%)
- neuro: high-risk pole 69.3% (self-High 92.0%)
- palpitations: high-risk pole 46.0% (self-High 78.0%)
- dyspnea: high-risk pole 44.0% (self-High 98.4%)
- headache: high-risk pole 35.0% (self-High 89.0%)
- soft_tissue: high-risk pole 32.0% (self-High 84.0%)
- ams: high-risk pole 28.0% (self-High 100.0%)
- abdominal: high-risk pole 27.0% (self-High 76.5%)
- back_pain: high-risk pole 24.0% (self-High 76.0%)
- syncope: high-risk pole 24.0% (self-High 56.0%)
- flank: high-risk pole 16.0% (self-High 52.0%)

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
