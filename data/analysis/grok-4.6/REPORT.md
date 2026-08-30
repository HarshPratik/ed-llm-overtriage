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

- High-risk pole: 494 (49.4%, 95% CI 46.3–52.5)
- Low-risk pole: 349 (34.9%)
- Other: 157 (15.7%)

Among cases mapped to either pole (n = 843):

- High-risk pole: 58.6% (95% CI 55.2–61.9)
- Binomial test vs 50%, alternative = greater: p = 3.325e-07
- Two-sided binomial p = 6.650e-07
- Chi-square vs 50/50: χ² = 24.94, p = 5.912e-07

Broad over-triage (high-risk pole or another emergency diagnosis): 62.2% of 1000 (p = 5.711e-15 vs 50%).

Model self-label High: 87.7% of 1000 (p = 3.553e-141 vs 50%).

Per-pair high-risk-pole rate: mean 49.4%, SD 33.69%, variance 1135.22, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 96.0% high-risk pole
- PAIR-034 Hemorrhoids vs Upper GI bleed: 92.0% high-risk pole
- PAIR-017 Hyperthyroidism vs Atrial fibrillation with rapid ventricular response: 88.0% high-risk pole
- PAIR-022 BPPV vs Posterior circulation stroke: 88.0% high-risk pole
- PAIR-040 Musculoskeletal back pain vs Spinal epidural abscess: 88.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 84.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (0 other)
- PAIR-030 Gastritis vs Perforated peptic ulcer: 0.0% high-risk pole (6 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (17 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (4 other)
- PAIR-029 Biliary colic vs Acute pancreatitis: 4.0% high-risk pole (16 other)
- PAIR-033 Nephrolithiasis vs Pyelonephritis: 8.0% high-risk pole (0 other)

## Clusters

- gi_bleed: high-risk pole 92.0% (self-High 100.0%)
- back_pain: high-risk pole 88.0% (self-High 88.0%)
- fever: high-risk pole 84.0% (self-High 100.0%)
- chest_pain: high-risk pole 76.8% (self-High 85.6%)
- ams: high-risk pole 72.0% (self-High 100.0%)
- leg: high-risk pole 64.0% (self-High 100.0%)
- neuro: high-risk pole 64.0% (self-High 94.7%)
- headache: high-risk pole 47.0% (self-High 67.0%)
- palpitations: high-risk pole 44.0% (self-High 92.0%)
- dyspnea: high-risk pole 43.2% (self-High 95.2%)
- soft_tissue: high-risk pole 40.0% (self-High 100.0%)
- abdominal: high-risk pole 28.5% (self-High 81.0%)
- syncope: high-risk pole 16.0% (self-High 56.0%)
- flank: high-risk pole 8.0% (self-High 100.0%)

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
