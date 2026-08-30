# Phase 3–4 analysis

Target model: **gpt-5.6-terra**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

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

- High-risk pole: 570 (57.0%, 95% CI 53.9–60.0)
- Low-risk pole: 261 (26.1%)
- Other: 169 (16.9%)

Among cases mapped to either pole (n = 831):

- High-risk pole: 68.59% (95% CI 65.4–71.7)
- Binomial test vs 50%, alternative = greater: p = 1.509e-27
- Two-sided binomial p = 3.017e-27
- Chi-square vs 50/50: χ² = 114.90, p = 8.281e-27

Broad over-triage (high-risk pole or another emergency diagnosis): 73.7% of 1000 (p = 7.012e-53 vs 50%).

Model self-label High: 93.1% of 1000 (p = 5.335e-194 vs 50%).

Per-pair high-risk-pole rate: mean 57.0%, SD 34.76%, variance 1208.41, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-034 Hemorrhoids vs Upper GI bleed: 100.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 100.0% high-risk pole
- PAIR-022 BPPV vs Posterior circulation stroke: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-037 Uncomplicated UTI vs Sepsis: 96.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 92.0% high-risk pole
- PAIR-005 Atrial fibrillation vs NSTEMI: 92.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (20 other)
- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (1 other)
- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (0 other)
- PAIR-030 Gastritis vs Perforated peptic ulcer: 4.0% high-risk pole (9 other)
- PAIR-029 Biliary colic vs Acute pancreatitis: 8.0% high-risk pole (22 other)
- PAIR-009 Acute bronchitis vs Pneumonia: 12.0% high-risk pole (14 other)

## Clusters

- gi_bleed: high-risk pole 100.0% (self-High 100.0%)
- fever: high-risk pole 96.0% (self-High 100.0%)
- back_pain: high-risk pole 88.0% (self-High 92.0%)
- chest_pain: high-risk pole 84.0% (self-High 92.0%)
- leg: high-risk pole 84.0% (self-High 96.0%)
- neuro: high-risk pole 80.0% (self-High 100.0%)
- ams: high-risk pole 72.0% (self-High 100.0%)
- headache: high-risk pole 59.0% (self-High 90.0%)
- dyspnea: high-risk pole 48.0% (self-High 95.6%)
- palpitations: high-risk pole 46.0% (self-High 98.0%)
- soft_tissue: high-risk pole 40.0% (self-High 100.0%)
- abdominal: high-risk pole 35.0% (self-High 86.0%)
- syncope: high-risk pole 32.0% (self-High 80.0%)
- flank: high-risk pole 20.0% (self-High 96.0%)

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
