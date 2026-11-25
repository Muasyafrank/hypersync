# HyperSync risk model: what the data can and cannot do

The deployed artefact is `ml/models/bp_status_model.joblib`. Its version,
feature contract, limitations and SHA-256 checksum are recorded in
`ml/models/MODEL_CARD.md`; the machine-readable evaluation summary is in
`ml/artifacts/metrics.json`.

A clean checkout does **not** need the raw `.sav` survey file for normal
operation. The small versioned model artefact is committed. Retraining with
`python -m ml.train_model` is an optional maintenance task that requires the
separately obtained raw survey file and `requirements-ml.txt`; the current-feature
command also regenerates `ml/models/SHA256SUMS`. The experimental BMI command
writes separately named model/checksum/report files and cannot overwrite the
published runtime artefact.

## Reproducible current evaluation

The training target is the Kenya STEPS 2015 respondent's `elevated` or `high`
blood-pressure group, using the same low-first classification as the
application. The current feature-complete training set contains 4,282
respondents; 41.7% are in that group.

`ml/train_model.py` compares three candidates with the same repeated stratified
5-fold cross-validation (3 repeats). The committed results are:

| Model | Mean CV AUC | Standard error | Mean Brier score |
| --- | ---: | ---: | ---: |
| Logistic regression with an age spline (deployed) | 0.656 | 0.005 | 0.2253 |
| Random forest | 0.656 | 0.005 | 0.2313 |
| Gradient boosting | 0.655 | 0.004 | 0.2265 |

A separate five-fold out-of-fold calibration report gives a calibration slope
of 0.983 and mean predicted/observed shares of 0.417/0.417. The familiar 20%
hold-out split contains 857 respondents and gives AUC 0.629, sensitivity 0.574
and specificity 0.638 at a threshold of 0.417. The cross-validation estimate is
the more stable model-selection figure; the hold-out result is recorded as a
secondary check.

These are local survey-model discrimination and calibration measures. They are
not evidence of clinical benefit, safety, calibration in HyperSync users, or
effectiveness of the app's recommendations.

## Why the deployed model is logistic regression

The candidate models have effectively the same discrimination in repeated
cross-validation, while the deployed logistic model's calibration is close to
the observed training share. The final model is refitted on all available
feature-complete rows and stores its training-population medians for disclosed
fallbacks.

The bundle version, exact feature list and SHA-256 digest are part of the
runtime contract. The endpoint verifies the digest before unpickling, validates
the version and the unpacked bundle's exact feature/input contract before use,
and continues without a population estimate if the artefact does not match.

## How survey effects affect factor ordering

The adjusted effects below come from one full-data logistic regression with a
95% bootstrap interval, holding the other included factors fixed. They are
**not** repeated-cross-validation results.

| Factor | Adjusted odds ratio (95% bootstrap interval) | Interval excludes 1? |
| --- | ---: | --- |
| +10 years of age | 1.52 (1.45–1.60) | yes |
| Alcohol in the last 30 days | 1.46 (1.21–1.74) | yes |
| +30 active minutes/day | 0.97 (0.95–0.99) | yes, but small |
| Salt level +1 | 0.96 (0.91–1.02) | no |
| Currently smokes | 0.85 (0.64–1.09) | no |
| Meets fruit/vegetable target | 1.08 (0.85–1.34) | no |

“No clear effect” does not mean salt or diet do not matter. It means these
single survey questions are too crude to detect an effect reliably. The app
therefore credits a factor to the survey only when its interval excludes “no
effect”; other wording is labelled as general clinical guidance rather than
model-derived evidence.

## Limits to keep in mind

- The deployed estimate is a **population probability used as context**, not a
  diagnosis or an individual clinical prediction.
- STEPS is cross-sectional: association at one moment, not proof that changing a
  habit changes a given person's blood pressure.
- The survey questions differ from what the app logs. STEPS asks about the last
  30 days and “how often do you add salt”; HyperSync logs a daily entry. Treat
  the mapping in `_build_model_features` as approximate.
- Activity minutes are capped at 240/day in the application, matching the
  training pipeline, and that adjustment is disclosed to the patient. The
  population estimate is omitted for ages outside the training population's
  18–100 range.
- 11% of respondents were on blood pressure medication, which may hide their
  risk. Medication adherence is deliberately not a model feature.
- Missing profile or lifestyle inputs use recorded training-population medians,
  and the patient-facing estimate names the defaulted fields.

## Experimental BMI path

BMI is not collected by the current application and is not part of the published
runtime artefact. `python -m ml.train_model --features bmi` is an experimental
maintenance path that writes a separate model, checksum and reports directory.
It must not be described as a validated or clinically beneficial improvement.
