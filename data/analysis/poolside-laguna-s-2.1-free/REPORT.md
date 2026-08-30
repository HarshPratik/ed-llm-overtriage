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

- High-risk pole: 468 (46.8%, 95% CI 43.7–49.9)
- Low-risk pole: 266 (26.6%)
- Other: 266 (26.6%)

Among cases mapped to either pole (n = 734):

- High-risk pole: 63.76% (95% CI 60.2–67.2)
- Binomial test vs 50%, alternative = greater: p = 4.138e-14
- Two-sided binomial p = 8.277e-14
- Chi-square vs 50/50: χ² = 55.59, p = 8.922e-14

Broad over-triage (high-risk pole or another emergency diagnosis): 68.6% of 1000 (p = 8.199e-33 vs 50%).

Model self-label High: 86.4% of 1000 (p = 1.998e-130 vs 50%).

Per-pair high-risk-pole rate: mean 46.8%, SD 32.69%, variance 1068.47, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 100.0% high-risk pole
- PAIR-038 Cellulitis vs Deep vein thrombosis: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 100.0% high-risk pole
- PAIR-021 Viral syndrome vs Meningitis: 92.0% high-risk pole
- PAIR-005 Atrial fibrillation vs NSTEMI: 92.0% high-risk pole
- PAIR-034 Hemorrhoids vs Upper GI bleed: 88.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (2 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (24 other)
- PAIR-030 Gastritis vs Perforated peptic ulcer: 0.0% high-risk pole (7 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (4 other)
- PAIR-004 GERD vs Aortic dissection: 8.0% high-risk pole (23 other)
- PAIR-039 Cellulitis vs Necrotizing fasciitis: 12.0% high-risk pole (0 other)

## Clusters

- leg: high-risk pole 100.0% (self-High 100.0%)
- gi_bleed: high-risk pole 88.0% (self-High 100.0%)
- fever: high-risk pole 80.0% (self-High 96.0%)
- back_pain: high-risk pole 64.0% (self-High 92.0%)
- chest_pain: high-risk pole 64.0% (self-High 84.8%)
- neuro: high-risk pole 62.7% (self-High 84.0%)
- dyspnea: high-risk pole 55.2% (self-High 95.2%)
- headache: high-risk pole 52.0% (self-High 86.0%)
- palpitations: high-risk pole 30.0% (self-High 72.0%)
- ams: high-risk pole 24.0% (self-High 92.0%)
- abdominal: high-risk pole 18.5% (self-High 79.0%)
- flank: high-risk pole 16.0% (self-High 76.0%)
- soft_tissue: high-risk pole 12.0% (self-High 92.0%)
- syncope: high-risk pole 12.0% (self-High 60.0%)

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
