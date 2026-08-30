# Phase 3–4 analysis

Target model: **minimax/minimax-m3-free**. Generator: gpt-5.6-sol. N = 1000 synthetic ED cases.

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

- High-risk pole: 512 (51.2%, 95% CI 48.1–54.3)
- Low-risk pole: 275 (27.5%)
- Other: 213 (21.3%)

Among cases mapped to either pole (n = 787):

- High-risk pole: 65.06% (95% CI 61.7–68.3)
- Binomial test vs 50%, alternative = greater: p = 1.158e-17
- Two-sided binomial p = 2.316e-17
- Chi-square vs 50/50: χ² = 71.37, p = 2.960e-17

Broad over-triage (high-risk pole or another emergency diagnosis): 70.8% of 1000 (p = 8.457e-41 vs 50%).

Model self-label High: 89.7% of 1000 (p = 4.608e-159 vs 50%).

Per-pair high-risk-pole rate: mean 51.2%, SD 36.4%, variance 1325.29, range 0.0–100.0.

## Strongest high-risk-pole pairs

- PAIR-001 GERD vs NSTEMI: 100.0% high-risk pole
- PAIR-017 Hyperthyroidism vs Atrial fibrillation with rapid ventricular response: 100.0% high-risk pole
- PAIR-006 GERD vs Pulmonary embolism: 100.0% high-risk pole
- PAIR-002 GERD vs STEMI: 100.0% high-risk pole
- PAIR-038 Cellulitis vs Deep vein thrombosis: 96.0% high-risk pole
- PAIR-004 GERD vs Aortic dissection: 96.0% high-risk pole
- PAIR-027 Constipation vs Small bowel obstruction: 96.0% high-risk pole
- PAIR-013 Community-acquired pneumonia vs Pulmonary embolism: 96.0% high-risk pole

## Weakest high-risk-pole pairs

These are not evidence against over-triage. Several still get a High self-label, or the model names a third emergency (acute cholecystitis, PE, SAH) that is not the pair's high-risk pole.

- PAIR-016 Supraventricular tachycardia vs Ventricular tachycardia: 0.0% high-risk pole (0 other)
- PAIR-028 Biliary colic vs Acute cholangitis: 0.0% high-risk pole (25 other)
- PAIR-031 Uncomplicated diverticulitis vs Diverticulitis with perforation or abscess: 0.0% high-risk pole (2 other)
- PAIR-020 Migraine vs Brain tumor: 4.0% high-risk pole (22 other)
- PAIR-029 Biliary colic vs Acute pancreatitis: 4.0% high-risk pole (24 other)
- PAIR-008 Asthma exacerbation vs Acute decompensated heart failure: 4.0% high-risk pole (8 other)

## Clusters

- leg: high-risk pole 96.0% (self-High 96.0%)
- fever: high-risk pole 92.0% (self-High 96.0%)
- gi_bleed: high-risk pole 92.0% (self-High 92.0%)
- chest_pain: high-risk pole 83.2% (self-High 90.4%)
- neuro: high-risk pole 80.0% (self-High 90.7%)
- ams: high-risk pole 60.0% (self-High 100.0%)
- palpitations: high-risk pole 50.0% (self-High 86.0%)
- headache: high-risk pole 46.0% (self-High 85.0%)
- back_pain: high-risk pole 44.0% (self-High 80.0%)
- dyspnea: high-risk pole 42.4% (self-High 98.4%)
- abdominal: high-risk pole 30.0% (self-High 89.0%)
- syncope: high-risk pole 28.0% (self-High 60.0%)
- soft_tissue: high-risk pole 20.0% (self-High 80.0%)
- flank: high-risk pole 12.0% (self-High 52.0%)

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
