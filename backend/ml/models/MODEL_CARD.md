# HyperSync blood-pressure population model card

**Status:** research prototype for decision support. The model is **not clinically validated, not a diagnostic tool, and not clinically approved**.

## Artefact identity

| Item | Value |
| --- | --- |
| File | `backend/ml/models/bp_status_model.joblib` |
| Version | `3.0.1-steps-logit-aligned` |
| SHA-256 | `917eab9781483939230306f82d8aa4fe7fd206c3de6b77424c923998f0b49094` |
| Algorithm | Logistic regression with a spline age curve |
| Output | Probability that a survey respondent is in the elevated/high blood-pressure group |
| Feature set | `age`, `sex`, `smoked`, `alcohol_consumed`, `salt_score`, `activity_minutes`, `diet_adherence` |

The checksum is also stored in machine-readable form in `backend/ml/models/SHA256SUMS`.

## Data provenance

- **Source:** Kenya STEPS NCD Risk Factor Survey 2015 (Kenya National Bureau of Statistics, Ministry of Health, and World Health Organization).
- **Original file:** `backend/data/2015_STEPS_Data.sav` in the development environment. The raw survey file is not committed to this repository.
- **Cleaning and feature mapping:** `backend/ml/steps_pipeline.py`.
- **Training and evaluation:** `backend/ml/train_model.py`.
- **Training population:** 4,282 usable respondents after excluding missing core fields, implausible readings, ages outside 18–100, and pregnancy records; 41.7% were in the elevated/high group.
- **Target definition:** the application checks **low first**: systolic below 90 mmHg **or** diastolic below 60 mmHg. A non-low reading is **high** when systolic is at least 150 mmHg **or** diastolic is at least 90 mmHg; otherwise it is **elevated** when systolic is at least 135 mmHg **or** diastolic is at least 85 mmHg. The model target is the resulting `elevated` or `high` group (that is, elevated/high and **not** low). There is no `180/110` urgent category in this model or the application.

## Input contract and missing values

| Model feature | HyperSync source |
| --- | --- |
| `age` | Patient profile date of birth; the survey training population was 18–100 years old |
| `sex` | Patient profile sex (`Male`/`Female`); the model has no representation for `Other` |
| `smoked` | Latest in-window lifestyle check-in |
| `alcohol_consumed` | Latest in-window lifestyle check-in |
| `salt_score` | Latest in-window salt answer, mapped `none=0`, `low=1`, `moderate=2`, `high=3` |
| `activity_minutes` | Latest in-window physical-activity minutes, capped at 240 minutes/day to match the training pipeline |
| `diet_adherence` | Latest in-window diet-adherence answer |

When a profile or lifestyle input is absent, the engine uses the training-population median stored in the model bundle. The patient-facing estimate names every missing field (for example, age, sex, smoking status, alcohol use, salt intake, physical activity or diet), states that defaults are used, and says that the estimate is not fully personalised. An unspecified sex is never described as the patient's own sex. Activity above 240 minutes is capped to the training contract and the patient-facing estimate discloses that adjustment. The population estimate is omitted for an age outside the model's supported 18–100 range rather than extrapolating beyond the training population. The model is shown as population context alongside the patient's own reading trend; it is not blended into that trend.

## Evaluation

All model-selection figures use repeated stratified 5-fold cross-validation with three repeats and identical folds across candidates.

| Measure | Result |
| --- | --- |
| Cross-validated AUC, deployed logistic model | 0.656 ± 0.005 |
| Cross-validated Brier score | 0.2253 |
| Out-of-fold calibration slope | 0.983 |
| Mean out-of-fold prediction / observed share | 0.417 / 0.417 |
| Hold-out AUC (20% split, n=857) | 0.629 |
| Hold-out sensitivity / specificity at threshold 0.417 | 0.574 / 0.638 |

These are local survey-model discrimination and calibration measures. They are not evidence of clinical benefit, safety, calibration in HyperSync users, or effectiveness of the app's recommendations.

## Intended use and limits

- Provides a clearly labelled population probability as context for elevated/high blood pressure.
- Supports review of the patient's own reading trend and actionable lifestyle guidance.
- Does not diagnose hypertension, prescribe treatment, recommend a drug or dose, or replace clinical judgement.
- Does not use the patient's blood-pressure readings as model features because the training survey has no longitudinal reading history.
- Does not establish that changing a logged lifestyle factor will change an individual's blood pressure; the survey is cross-sectional.
- Maps 30-day survey questions to a daily app log imperfectly.
- Training data include medication use for some respondents, which may hide risk, while medication adherence is deliberately not a model feature.
- Modest AUC means the probability should not be presented as an individual prediction.

The clinical wording and thresholds remain unsigned and require review in `docs/advice-for-clinical-review.md`.

## Reproduction and versioning

A clean checkout does **not** need the raw survey file for normal application operation: the small versioned artefact above is committed and is loaded by the recommendation engine. The runtime verifies its published SHA-256 digest before unpickling, then validates the unpacked bundle's version, exact feature and input contract, labels, thresholds and effect metadata before use. If the artefact is missing, corrupt or incompatible with the runtime contract, the endpoint continues with the patient's readings and lifestyle rules and does not show a population estimate.

Verify the committed artefact from `backend/`:

```bash
cd ml/models
sha256sum -c SHA256SUMS
cd ../..
pytest tests/test_model_artifact.py
```

Retraining requires the separately obtained raw survey file and the pinned ML dependencies:

```bash
cd backend
pip install -r requirements-ml.txt
# Place the source survey at data/2015_STEPS_Data.sav
python -m ml.train_model --features current
```

The training command rewrites `SHA256SUMS`. The experimental BMI feature set writes a separately named model, checksum and reports directory, so it cannot overwrite the published runtime artefact. Any intentional model, feature-contract, threshold, data-cleaning, or training-pipeline change requires a version bump, a regenerated model card/checksum, and the full backend test suite.
