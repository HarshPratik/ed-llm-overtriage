# Phase 3–4 analysis

Target model: **glm-5.3-flash**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

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

- High-risk pole: 497 (49.7%, 95% CI 46.6–52.8)
- Low-risk pole: 311 (31.1%)
- Other: 192 (19.2%)

Among cases mapped to either pole (n = 808):

- High-risk pole: 61.51% (95% CI 58.1–64.8)
- Binomial test vs 50%, alternative = greater: p = 3.147e-11
- Two-sided binomial p = 6.294e-11
- Chi-square vs 50/50: χ² = 42.82, p = 6.011e-11

Broad over-triage (high-risk pole or another emergency diagnosis): 66.8% of 1000 (p = 5.312e-27 vs 50%).

Model self-label High: 79.9% of 1000 (p = 3.280e-85 vs 50%).

Per-pair high-risk-pole rate: mean 49.7%, SD 34.86%, variance 1215.09, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-034 Hemorrhoids vs Upper GI bleed: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 92.0% high-risk pole
- PAIR-037 Uncomplicated UTI vs Sepsis: 92.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 92.0% high-risk pole
- PAIR-017 Hyperthyroidism vs Atrial fibrillation with rapid ventricular response: 88.0% high-risk pole
- PAIR-027 Constipation vs Small bowel obstruction: 84.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (21 other)
- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (0 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (2 other)
- PAIR-029 Biliary colic vs Acute pancreatitis: 4.0% high-risk pole (22 other)
- PAIR-003 Costochondritis vs STEMI: 8.0% high-risk pole (0 other)
- PAIR-010 COPD exacerbation vs Pneumonia: 8.0% high-risk pole (11 other)

## Clusters

- gi_bleed: high-risk pole 100.0% (self-High 100.0%)
- fever: high-risk pole 92.0% (self-High 92.0%)
- ams: high-risk pole 80.0% (self-High 96.0%)
- back_pain: high-risk pole 76.0% (self-High 84.0%)
- neuro: high-risk pole 76.0% (self-High 92.0%)
- chest_pain: high-risk pole 73.6% (self-High 81.6%)
- headache: high-risk pole 50.0% (self-High 83.0%)
- leg: high-risk pole 48.0% (self-High 56.0%)
- palpitations: high-risk pole 44.0% (self-High 80.0%)
- dyspnea: high-risk pole 37.6% (self-High 87.6%)
- flank: high-risk pole 36.0% (self-High 60.0%)
- abdominal: high-risk pole 32.0% (self-High 70.5%)
- soft_tissue: high-risk pole 24.0% (self-High 56.0%)
- syncope: high-risk pole 16.0% (self-High 36.0%)

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
