# Phase 2 evaluation outputs

Target model: **gpt-5.6-terra** (different from the Phase 1 generator, gpt-5.6-sol).

Only synthetic `Case_History_Text` is sent. No PhysioNet notes.

## Files

- `model_responses.jsonl` — checkpoint of every API result; the runner resumes from this
- `evaluated_cases.csv` — original cases plus `Model_Diagnosis`, `Risk_Level_Assessment`, and pair mapping
- `evaluated_cases.json` — same rows
- `eval_report.json` — counts and latency
- `errors.jsonl` — failed or unparseable responses

Phase 3 also wrote `data/synthetic/case_histories_with_diagnosis.csv`, a copy of the original cases with `Model_Diagnosis` appended.

## Regenerating / resuming

```powershell
python scripts/evaluate_cases.py
```

Interrupted runs resume automatically. Use `--fresh` to start over.

```powershell
python scripts/evaluate_cases.py --model gpt-5.6-terra --concurrency 5
```
