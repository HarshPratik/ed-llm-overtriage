# Phase 3–4 analysis outputs

Terra lives in this folder. Replication models have their own subfolders. The six-model table is `COMPARISON.md`. Cross-model figure and κ: `python scripts/summarize_models.py`.

## Regenerating

```powershell
python scripts/analyze_bias.py
```

## Files

- `classified_cases.csv` — case-level mapping of `Model_Diagnosis` onto each pair
- `pair_summary.csv` — 40 pairs with counts, percents, binomial p-values
- `cluster_summary.csv` — symptom clusters
- `subgroup_summary.csv` — gender, tone, age band
- `unmapped_diagnoses.csv` — diagnoses that did not match either pole
- `top_diagnoses.csv` — most frequent raw labels
- `stats.json` — frequencies, Wilson CIs, binomial and chi-square tests
- `REPORT.md` — written summary
- `figures/` — bar, pie, heatmap, pair-rate, stacked cluster, self-vs-mapped, top diagnoses

## Mapping rule

Match `Model_Diagnosis` to that case's low-risk vs high-risk pole using aliases. If both poles match, keep high-risk. Unmapped labels are Other; emergency keywords become other-high.

Primary endpoint: among pair-mapped cases, is the high-risk pole share greater than 50%?
