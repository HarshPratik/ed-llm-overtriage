# Phase 3–4 analysis

Target model: **sarvam-105b**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

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

- High-risk pole: 466 (46.6%, 95% CI 43.5–49.7)
- Low-risk pole: 319 (31.9%)
- Other: 215 (21.5%)

Among cases mapped to either pole (n = 785):

- High-risk pole: 59.36% (95% CI 55.9–62.7)
- Binomial test vs 50%, alternative = greater: p = 8.679e-08
- Two-sided binomial p = 1.736e-07
- Chi-square vs 50/50: χ² = 27.53, p = 1.549e-07

Broad over-triage (high-risk pole or another emergency diagnosis): 62.7% of 1000 (p = 4.363e-16 vs 50%).

Model self-label High: 83.9% of 1000 (p = 1.830e-111 vs 50%).

Per-pair high-risk-pole rate: mean 46.6%, SD 34.57%, variance 1195.12, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-005 Atrial fibrillation vs NSTEMI: 96.0% high-risk pole
- PAIR-037 Uncomplicated UTI vs Sepsis: 92.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 92.0% high-risk pole
- PAIR-023 Seizure with postictal state vs Ischemic stroke: 92.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 88.0% high-risk pole
- PAIR-017 Hyperthyroidism vs Atrial fibrillation with rapid ventricular response: 84.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-030 Gastritis vs Perforated peptic ulcer: 0.0% high-risk pole (6 other)
- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (2 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (8 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (18 other)
- PAIR-020 Migraine vs Brain tumor: 4.0% high-risk pole (21 other)
- PAIR-003 Costochondritis vs STEMI: 4.0% high-risk pole (0 other)

## Clusters

- fever: high-risk pole 92.0% (self-High 96.0%)
- back_pain: high-risk pole 76.0% (self-High 88.0%)
- neuro: high-risk pole 76.0% (self-High 85.3%)
- chest_pain: high-risk pole 74.4% (self-High 80.8%)
- gi_bleed: high-risk pole 72.0% (self-High 100.0%)
- leg: high-risk pole 72.0% (self-High 92.0%)
- ams: high-risk pole 64.0% (self-High 100.0%)
- palpitations: high-risk pole 42.0% (self-High 72.0%)
- dyspnea: high-risk pole 40.0% (self-High 99.2%)
- headache: high-risk pole 38.0% (self-High 64.0%)
- soft_tissue: high-risk pole 28.0% (self-High 88.0%)
- abdominal: high-risk pole 25.5% (self-High 78.5%)
- flank: high-risk pole 16.0% (self-High 80.0%)
- syncope: high-risk pole 4.0% (self-High 32.0%)

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
