# Kenya STEPS 2015 data card for the HyperSync population model

## Data source

- **Dataset:** Kenya STEPS NCD Risk Factor Survey 2015, produced by the Kenya National Bureau of Statistics (KNBS), Ministry of Health (MoH), and World Health Organization (WHO).
- **Official study catalogue:** <https://extranet.who.int/ncdsmicrodata/index.php/catalog/study/KEN_2015_STEPS_v01>
- **Official country report:** <https://cdn.who.int/media/docs/default-source/ncds/ncd-surveillance/data-reporting/keynya/kenya-2015-steps-report.pdf?sfvrsn=5b9d5782_5>
- **Local source file:** `backend/data/2015_STEPS_Data.sav` in the controlled development environment. It is not committed to Git.
- **Raw-file SHA-256:** `081b3cbf4be2b7f840af1f6b3c7c731c6187d3eebf3591e08b4743879b1c5b12`.
- **Access and reuse:** users must obtain the survey file through the official channels and follow the applicable WHO/KNBS/MoH terms. This repository does not redistribute the respondent-level file.

The public survey contains no names, emails, dates of birth, national IDs, or free-text patient notes in the model input. It contains survey responses and measurement values. The HyperSync runtime never sends these records to a third party.

## Survey design

The build retains the survey-design fields needed for weighting, grouped splitting, and clustered uncertainty estimates:

| Field | Use |
| --- | --- |
| `wstep2` | Measurement weight for the blood-pressure/physical-measurement target |
| `psu` | Primary sampling unit; rows from one PSU never cross train/validation/test boundaries |
| `stratum` | Residence stratum (rural/urban); PSU allocation and bootstrap sampling are stratified |

Weights are normalised within each analysis split only to a mean of one for numerical fitting. The original weights remain unchanged in the canonical training-data hash.

## Analytic population and outcome

- Raw respondent rows: **4,500**.
- Rows remaining after core age, validity, and BP filters: **4,417**.
- Known-pregnancy respondents excluded from the analytic model: **136**.
- Respondents with unknown pregnancy status excluded rather than assumed not pregnant: **3**.
- Final analytic model rows: **4,278**.
- Survey-weighted elevated/high share: **38.3%** (unweighted share: **41.6%**).
- Supported application age: **18–69 years**; the raw survey also contains a small number of people outside that range, who are excluded.
- Zero-weight rows remaining in the analytic set: **0**.

### Primary outcome

The outcome is **concurrent survey blood-pressure status**, not a diagnosis and not future risk. It is `elevated` or `high` versus `not_at_risk`, using the application thresholds:

1. very-high safety boundary first: systolic at least 180 mmHg **or** diastolic at least 110 mmHg is part of the public `high` group;
2. low when systolic is below 90 mmHg **or** diastolic is below 60 mmHg;
3. high when systolic is at least 150 mmHg **or** diastolic is at least 90 mmHg;
4. elevated when systolic is at least 135 mmHg **or** diastolic is at least 85 mmHg;
5. controlled otherwise.

The very-high boundary takes precedence over a conflicting low value. For this binary event, the 114 low-reading respondents in the analytic population are in the `not_at_risk` group, alongside controlled readings. This is a survey event definition, not a clinical judgement that a low reading is harmless. Low readings are safety-routed in the application and never receive the model estimate.

The primary exposure is the **mean of the second and third STEPS blood-pressure readings**. Both readings are required. The first reading is not used as a fallback because mixing measurement protocols would make the target harder to audit. A sensitivity evaluation also applies the frozen model to a third-reading-only target; 315 of 4,278 binary labels change.

The survey target is cross-sectional. It cannot establish whether a habit causes blood pressure, predict an individual future event, or measure the effect of changing treatment.

## Feature construction

| Model input | STEPS mapping |
| --- | --- |
| `age` | Age in single years, restricted to 18–69 |
| `sex` | `Men`/`Women` encoded as the binary model input; no other category is inferred |
| `smoked` | Current tobacco-smoking response |
| `alcohol_consumed` | Alcohol use in the previous 30 days; a blank is treated as a structural skip only for respondents who did not drink in the past year or never drank alcohol |
| `salt_score` | Salt-frequency response mapped to the application scale `none=0`, `low=1`, `moderate=2`, `high=3` |
| `activity_minutes` | Mean daily minutes across vigorous work, moderate work, walking/cycling for transport, vigorous sport, and moderate sport; capped at 240 minutes/day |
| `diet_adherence` | Whether mean daily fruit and vegetable servings meet the five-serving target |
| `*_missing` | Explicit indicator for each model input; missing answers are not silently treated as healthy or zero |

The STEPS code `77` is treated as missing in diet and physical-activity quantities. A structurally skipped amount after zero days is kept separate from an invalid amount after one or more days. Missing values in the final model are imputed only with training-split weighted defaults while their missingness indicators remain set.

Physical activity includes all five STEPS activity domains. An invalid participation code is missing rather than evidence of no activity. An active block is complete only when the respondent supplies valid days, hours, and minutes; an incomplete block makes the total activity value missing rather than silently lower than observed.

Medication use is not a model feature. It is answered only by some respondents already diagnosed with hypertension, so including it would either discard most of the survey or leak diagnosis status into the outcome model.

Final model-input missingness:

| Input | Missing rows |
| --- | ---: |
| Age | 0 |
| Sex | 0 |
| Smoking | 0 |
| Alcohol | 0 |
| Salt | 4 |
| Physical activity | 101 |
| Diet | 43 |

## Locked split and reproducible hashes

The split is locked in `backend/ml/artifacts/split_assignments.csv` and is never regenerated during a normal build.

- Split-lock SHA-256: `c3a7dacdb7b265f110e1c79c7782b3601511c3c336dcd23461d0bfc1452cd609`.
- Canonical training-data SHA-256: `8242dd85710f0bff917f59b0fbda4fce4116ec836b3a883b9ad19379ae1ffc40`.
- Model seed: `20261125`; split seed: `20261125`.
- Build environment: CPython 3.13.14 on Linux; dependency-lock SHA-256 `2d720d57fcd8c60110f8437f8035b42168fff3a1fbe8f75f5dade54ba4183892`; `PYTHONHASHSEED=0` and single-threaded numerical libraries.

| Split | Rows | PSUs | Survey-weighted outcome share |
| --- | ---: | ---: | ---: |
| Train | 2,538 | 120 | 39.2% |
| Validation | 869 | 40 | 36.4% |
| Test | 871 | 40 | 38.0% |

PSUs are allocated 60/20/20 within each residence stratum. The validation split alone is used to fit the Platt calibrator. The locked test split is assessed once and is not used for regularisation selection, calibration, or model fitting.

## Intended use and prohibited use

**Intended use:** provide a clearly labelled population estimate as context alongside a patient's own readings and deterministic lifestyle guidance in a research prototype.

**Not intended for:** diagnosis, treatment selection, medication or dose advice, individual future-risk forecasting, causal inference, triage, clinician sign-off, or evidence of clinical benefit. Patient-facing recommendation output must never contain a diagnosis or any medication/drug/dose content, medication or treatment timing, treatment start/stop instructions, or treatment-change advice.

## Data and model limitations

- The 2015 survey is historical, national, and cross-sectional. It may not represent current Kenyan patterns or every community served by HyperSync.
- Survey questions are coarse and do not map exactly onto HyperSync's daily logs. For example, STEPS asks about recent alcohol use and salt frequency, while the app records a daily check-in.
- Medication use may lower measured blood pressure among some respondents. This is one reason medication is not used to explain model risk.
- The survey design is retained, but the reported test interval is a PSU-cluster interval, not a full three-stage survey-design variance estimate.
- Overall discrimination is modest. Some age and sex subgroups have substantially worse discrimination or calibration than the overall test result. The model card records those subgroup results; they must not be hidden by an overall average.
- Self-reported lifestyle measures can contain recall, social-desirability, and measurement error.
- The population model does not use the patient's blood-pressure readings because STEPS contains no longitudinal reading history. Its estimate must not be presented as an explanation of the patient's current reading.
- No patient-level forecasting, causal model, external LLM, or third-party data transfer is included.

The plain-language disclosure for patients and evaluators is in `docs/limitations-and-ethics.md`.
