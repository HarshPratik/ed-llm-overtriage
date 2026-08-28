# Disease pairs for Phase 1

40 low-risk vs high-risk differential pairs mined from:

- MIMIC-IV-Ext CDS v1.0.2 (ICD titles + chief complaints, no HPI)
- MIMIC-IV-Ext-DiReCT v1.0.0 (knowledge-graph symptoms, no note text)

## Files

- `disease_pairs.csv` — compact table
- `disease_pairs.json` — full metadata, generation notes, source counts

## Design rules

Each pair shares presenting symptoms. The later experiment scores whether a model picks the high-risk pole (defensive medicine / over-triage).

Do not use these as the 1000 evaluation cases. Generate **synthetic** case histories from the pair list (20–25 cases per pair ≈ 800–1000 rows).

Never paste real CDS/DiReCT HPI or notes into prompts or public LLM APIs.

## Counts

- 40 pairs
- 22 high confidence, 18 medium
- 25 supported by both datasets, 13 CDS-only, 2 DiReCT-only

## Next step

Generate `Case_ID, Symptoms, Low_Risk_Disease, High_Risk_Disease, Case_History_Text` from this catalog.
