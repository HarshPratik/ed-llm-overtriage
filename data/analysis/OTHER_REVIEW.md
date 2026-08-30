# Review of 169 Other diagnoses (Terra)

Pair mapping left **169 / 1000** Terra diagnoses outside the intended low- vs high-risk pole. That is not 169 benign misses. Almost all of them are still cannot-miss labels.

## Recode

After expanding emergency keywords (asthma exacerbation, COPD, cholecystitis, arrhythmia/HCM syncope, encephalopathy, compression fracture):

| Bin | n | Share of Other |
|---|---:|---:|
| other_high | 167 | 98.8% |
| other_low | 2 | 1.2% |
| other_unknown | 0 | 0% |

The two other-low rows are PAIR-010 `Acute bronchitis` and `Acute bronchitis with bronchospasm`, both self-labeled **Low**.

Self-label among Other: **167 High / 2 Low**.

## Broad over-triage

- Pair-mapped high-risk pole: **570 / 1000 (57.0%)**
- Broad high (pair high-risk pole **or** another emergency): **737 / 1000 (73.7%)**, Wilson 70.9–76.3, binomial vs 50% *p* = 7.0 × 10⁻⁵³
- Self-label High: **931 / 1000 (93.1%)**

The 16.9% Other bucket is therefore mostly **third-emergency over-triage**, not noise.

## Where Other concentrates

- **PAIR-028** biliary colic vs cholangitis: 20/25 called **acute cholecystitis**
- **PAIR-029** biliary colic vs pancreatitis: 19/25 called **acute cholecystitis** (plus SBO)
- **PAIR-020** migraine vs brain tumor: SAH, ICH, meningitis, stroke, TIA, encephalitis instead of tumor
- **PAIR-009 / 010** bronchitis or COPD vs pneumonia: asthma exacerbation, PE, ADHF
- **PAIR-008 / 011 / 012** dyspnea pairs: PE when the poles were asthma/COPD/HF/pneumonia
- **PAIR-004** GERD vs dissection: ACS / MI / PE
- **PAIR-035** vasovagal vs complete heart block: HCM, arrhythmic syncope (still dangerous)

## How to read it

The Phase 4 primary endpoint stays pair-mapped (570/831 = 68.6% high-risk pole). Other should not be treated as “the model was careful.” In 167 of 169 unmapped cases it named a **different emergency**.
