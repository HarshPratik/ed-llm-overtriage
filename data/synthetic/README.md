# Phase 1 synthetic case histories

1000 unique ED case histories, 25 per disease pair, written by **gpt-5.6-sol** on the custom OpenAI-compatible endpoint in `.env`. No real PhysioNet notes were sent to the model.

## Files

- `case_histories.csv` — main table
- `case_histories.json` — same rows
- `case_histories_with_diagnosis.csv` — Phase 1 cases plus `Model_Diagnosis` from gpt-5.6-terra
- `generation_report.json` — counts and validation summary

## Columns

`Case_ID`, `Pair_ID`, `Cluster`, `Symptoms`, `Low_Risk_Disease`, `High_Risk_Disease`, `Age`, `Gender`, `Tone`, `Source`, `Case_History_Text`

Required Phase 1 fields are present. Extra columns are for audit and later analysis.

## Generation rules

- Shared symptoms only; both poles remain plausible
- No diagnosis names in the narrative
- No ECG/troponin/D-dimer/CT/MRI/BNP/lipase results
- Six tones: clinician HPI, patient first-person, triage note, family, portal message, EMS
- Varied age, gender, occupation, and background history

## Regenerating

```powershell
python scripts/generate_case_histories_llm.py
```

If a run is interrupted, it resumes from `case_histories.llm.jsonl`.
