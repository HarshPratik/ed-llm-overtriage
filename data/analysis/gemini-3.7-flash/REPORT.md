# Phase 3–4 analysis

Target model: **gemini-3.7-flash**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

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
- Low-risk pole: 371 (37.1%)
- Other: 160 (16.0%)

Among cases mapped to either pole (n = 840):

- High-risk pole: 55.83% (95% CI 52.5–59.2)
- Binomial test vs 50%, alternative = greater: p = 0.0004
- Two-sided binomial p = 0.0008
- Chi-square vs 50/50: χ² = 11.43, p = 0.0007

Broad over-triage (high-risk pole or another emergency diagnosis): 60.1% of 1000 (p = 9.008e-11 vs 50%).

Model self-label High: 83.2% of 1000 (p = 1.589e-106 vs 50%).

Per-pair high-risk-pole rate: mean 46.9%, SD 34.87%, variance 1215.99, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 96.0% high-risk pole
- PAIR-034 Hemorrhoids vs Upper GI bleed: 92.0% high-risk pole
- PAIR-017 Hyperthyroidism vs Atrial fibrillation with rapid ventricular response: 92.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 88.0% high-risk pole
- PAIR-005 Atrial fibrillation vs NSTEMI: 88.0% high-risk pole
- PAIR-037 Uncomplicated UTI vs Sepsis: 84.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (0 other)
- PAIR-030 Gastritis vs Perforated peptic ulcer: 0.0% high-risk pole (5 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (20 other)
- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (0 other)
- PAIR-033 Nephrolithiasis vs Pyelonephritis: 4.0% high-risk pole (0 other)
- PAIR-010 COPD exacerbation vs Pneumonia: 4.0% high-risk pole (10 other)

## Clusters

- gi_bleed: high-risk pole 92.0% (self-High 100.0%)
- back_pain: high-risk pole 84.0% (self-High 92.0%)
- fever: high-risk pole 84.0% (self-High 100.0%)
- chest_pain: high-risk pole 73.6% (self-High 82.4%)
- ams: high-risk pole 68.0% (self-High 100.0%)
- leg: high-risk pole 68.0% (self-High 72.0%)
- neuro: high-risk pole 61.3% (self-High 92.0%)
- palpitations: high-risk pole 46.0% (self-High 98.0%)
- dyspnea: high-risk pole 40.0% (self-High 95.2%)
- soft_tissue: high-risk pole 40.0% (self-High 80.0%)
- headache: high-risk pole 38.0% (self-High 60.0%)
- abdominal: high-risk pole 29.0% (self-High 72.0%)
- syncope: high-risk pole 8.0% (self-High 44.0%)
- flank: high-risk pole 4.0% (self-High 88.0%)

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
