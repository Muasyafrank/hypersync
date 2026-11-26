# HyperSync blood-pressure population model card

**Status:** research prototype for decision support. The model is **not clinically validated, not clinically approved, not a diagnostic tool, and not evidence of clinical benefit**.

## Artefact identity

| Item | Value |
| --- | --- |
| File | `backend/ml/models/bp_status_model.joblib` |
| Version | `4.0.1-steps-survey-calibrated` |
| SHA-256 | `45c7adf6df1a707e0560cf110be9cd82da51c73ade610391436f3237fd331652` |
| Algorithm | Survey-weighted, regularised logistic regression with a five-knot cubic spline for age |
| Output | Calibrated probability that a survey respondent with a similar age, sex and lifestyle profile was in the concurrent elevated/high blood-pressure group |
| Feature set | `age`, `sex`, `smoked`, `alcohol_consumed`, `salt_score`, `activity_minutes`, `diet_adherence` |
| Calibration | Platt scaling fitted on the locked validation split only |
| Contribution uncertainty | 200 stratified PSU-bootstrap replicates resampling training and validation PSUs |
| Runtime artefact size | 36,346 bytes |
| Build environment | CPython 3.13.14 on Linux; dependency-lock SHA-256 `2d720d57fcd8c60110f8437f8035b42168fff3a1fbe8f75f5dade54ba4183892` |

The checksum is stored in machine-readable form in `backend/ml/models/SHA256SUMS`. The raw survey file is not committed.

## Data provenance and target

- **Source:** Kenya STEPS NCD Risk Factor Survey 2015 (Kenya National Bureau of Statistics, Ministry of Health, and World Health Organization).
- **Original file:** `backend/data/2015_STEPS_Data.sav` in the controlled development environment.
- **Raw-file SHA-256:** `081b3cbf4be2b7f840af1f6b3c7c731c6187d3eebf3591e08b4743879b1c5b12`.
- **Canonical training-data SHA-256:** `8242dd85710f0bff917f59b0fbda4fce4116ec836b3a883b9ad19379ae1ffc40`.
- **Split-lock SHA-256:** `c3a7dacdb7b265f110e1c79c7782b3601511c3c336dcd23461d0bfc1452cd609`.
- **Analytic population:** 4,278 respondents after core filters and pregnancy exclusion; 38.3% survey-weighted are in the elevated/high group.
- **Target:** the mean of the second and third STEPS blood-pressure readings, with both readings required. The target is `elevated` or `high` versus `not_at_risk`.
- **Measurement weight:** `wstep2`; PSU and stratum are retained for splitting and clustered uncertainty.

Full cleaning, exclusion, missingness, survey-design, and reuse details are in `backend/ml/DATA_CARD.md`.

## Training and evaluation design

The build is locked and reproducible:

1. Verify the raw-file digest.
2. Clean the survey using explicit STEPS skip/missing rules.
3. Read the committed PSU split lock; never silently regenerate it.
4. Select regularisation strength by five-fold PSU-grouped cross-validation inside the training split only.
5. Fit the final regularised logistic model on the training split with survey weights.
6. Fit Platt calibration on validation only.
7. Evaluate once on the untouched locked test split.
8. Build weighted/unweighted metrics, calibration summaries, sex/age/residence subgroups, target and missing-data sensitivities, and PSU-cluster uncertainty.
9. Build 200 stratified PSU-bootstrap draws for per-prediction contribution intervals, resampling both training and validation PSUs within strata.

Training and split seeds are both `20261125`. The selected regularisation value is `C=0.2`. The published build requires CPython 3.13.14 on Linux and the fully hashed dependency lock `backend/ml/requirements-lock.txt` (SHA-256 `2d720d57fcd8c60110f8437f8035b42168fff3a1fbe8f75f5dade54ba4183892`). The build refuses a different Python patch, operating-system family, dependency-lock hash, or a missing `PYTHONHASHSEED=0`. Library versions and the full numerical environment are recorded in `backend/ml/artifacts/metrics.json`; volatile host-kernel details are kept out of the hashed runtime bundle.

## Input contract and missing values

| Model feature | HyperSync source |
| --- | --- |
| `age` | Patient profile date of birth; survey age range 18–69 years |
| `sex` | Patient profile sex (`Male`/`Female`); the model has no representation for `Other` |
| `smoked` | Current-smoking answer from the patient's lifestyle log |
| `alcohol_consumed` | Alcohol use in the previous 30 days, matching the survey exposure period |
| `salt_score` | Salt-frequency answer mapped `none=0`, `low=1`, `moderate=2`, `high=3` |
| `activity_minutes` | Usual-day active minutes including work, walking and sport, capped at 240 minutes/day |
| `diet_adherence` | Whether the patient usually meets the five-serving fruit-and-vegetable target |

The lifestyle features are resolved independently from valid answers in the model-exposure look-back. A newer partial check-in does not erase a different feature answered on an earlier day, and each feature keeps its own missingness state. The app questions use current, past-30-day, or usual-day wording to reduce mismatch with STEPS, but the daily-log mapping remains approximate.

Each of the seven semantic inputs has a matching explicit missingness indicator. Missing values use training-split, survey-weighted defaults while the indicator remains set. The patient-facing estimate names missing fields, states that defaults are used, and says the estimate is not fully personalised. An unspecified sex is never described as the patient's own sex. Activity above 240 minutes is capped and disclosed.

The survey covers ages 18–69, but the locked test does not support generalising a percentage to every age band. The runtime therefore withholds the population estimate outside **ages 18–29**, the only granular age band with positive discrimination and Brier skill in the locked test. Deterministic reading and lifestyle guidance still runs. This is a conservative runtime gate, not a claim that the 18–29 model is accurate.

The estimate is population context. It does not use the patient's current blood-pressure readings as features and must not be described as explaining them.

## Locked-test performance

The locked test split contains 871 respondents in 40 PSUs. Weighted survey prevalence is 38.0%.

| Measure | Estimate | 95% PSU-cluster interval |
| --- | ---: | ---: |
| AUROC | 0.637 | 0.602–0.669 |
| PR-AUC | 0.498 | 0.438–0.562 |
| Brier score | 0.223 | 0.211–0.236 |
| Log loss | 0.638 | 0.611–0.664 |
| Calibration slope | 1.039 | 0.781–1.300 |
| Calibration intercept | 0.036 | -0.264–0.286 |
| Calibration in the large | 0.004 | -0.048–0.052 |
| Expected calibration error | 0.053 | 0.047–0.106 |

Unweighted locked-test AUROC is 0.640 and Brier score is 0.224. The 2,000-replicate interval holds the locked-test predictions fixed, resamples PSUs with replacement within strata, and applies sampled-PSU multiplicities to the original survey weights. It is **not** a complete three-stage survey-design variance estimate.

Overall discrimination is modest. The Brier skill score over the weighted prevalence baseline is only 0.052, so the model's improvement over a prevalence-only baseline is small.

## Calibration

Platt scaling was fitted only on the locked validation split. Its fitted parameters are slope 0.709 and intercept -0.191. After applying those parameters, the post-calibration diagnostic on validation is slope 1.000 and intercept approximately 0.000. On test, the weighted mean prediction is 37.6% versus observed prevalence 38.0%. Expected calibration error uses ten equal-count bins whose edges were frozen from the locked validation predictions before test evaluation. The same edges define the published test curve, chart, headline ECE, and PSU-cluster interval. They are in `backend/ml/artifacts/metrics.json`; the chart is `backend/ml/artifacts/calibration.png`.

The calibration looks reasonable overall, but a good overall curve does not establish subgroup or individual calibration.

## Sensitivity analyses

Both sensitivity checks use the frozen primary model and locked test predictions; neither refits the model.

| Scenario | AUROC | PR-AUC | Brier score | Calibration slope | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| All seven inputs missing and defaulted, with every missingness flag set | 0.500 | 0.380 | 0.245 | 0.041 | Stress-test baseline: the model has no useful discrimination without patient inputs. |
| Third-reading-only target | 0.648 | 0.496 | 0.219 | 1.144 | 315 of 4,278 binary labels change; the result is close to the primary test result. |

The all-missing row is a deliberately extreme stress test, not an expected routine result. It shows why incomplete patient inputs must be disclosed and why the estimate is population context rather than an individual assessment.

## Subgroup results

All values below are weighted locked-test results. Small subgroups have substantial uncertainty.

| Subgroup | n | AUROC | PR-AUC | Brier | Calibration slope |
| --- | ---: | ---: | ---: | ---: | ---: |
| Female | 532 | 0.693 | 0.556 | 0.215 | 1.560 |
| Male | 339 | 0.585 | 0.457 | 0.233 | 0.625 |
| Age 18–39 | 517 | 0.602 | 0.398 | 0.211 | 1.165 |
| Age 40–59 | 263 | 0.510 | 0.498 | 0.251 | 0.287 |
| Age 60–69 | 91 | 0.447 | 0.692 | 0.245 | -0.588 |
| Age 18–29 | 281 | 0.560 | 0.390 | 0.190 | 1.537 |
| Age 30–44 | 317 | 0.515 | 0.437 | 0.248 | 0.119 |
| Age 45–59 | 182 | 0.485 | 0.518 | 0.253 | -0.098 |
| Rural | 454 | 0.656 | 0.520 | 0.223 | 1.166 |
| Urban | 417 | 0.567 | 0.430 | 0.224 | 0.637 |

The age 60–69 result is materially worse than the overall result, including AUROC below 0.5 and an unstable calibration slope. Age 30–44 and age 45–59 also show near-random discrimination. This means the overall performance must not be generalized to every age or sex group. The model remains a research prototype, and subgroup monitoring and further validation are required before any clinical use.

## Survey associations in the fitted model

These are adjusted associations in the same weighted model, with 95% intervals from the training-PSU resampling component of the stratified bootstrap. These coefficient-only intervals do not include validation-calibration or preprocessing uncertainty. They are not causal effects and are not estimates of what will happen if one person changes a habit.

| Factor | Adjusted odds ratio (95% interval) |
| --- | ---: |
| +10 years of age (mean spline contrast) | 1.396 (1.288–1.508) |
| Male vs female | 1.024 (0.836–1.215) |
| Currently smokes | 0.813 (0.542–1.269) |
| Alcohol in the last 30 days | 1.683 (1.233–2.149) |
| +1 salt level | 0.859 (0.744–0.965) |
| +30 active minutes/day | 0.956 (0.902–1.008) |
| Meets fruit/vegetable target | 1.151 (0.785–1.746) |

Some directions are not the direction expected from general clinical guidance, and several intervals include no effect. This is a reason to keep the wording non-causal, avoid attributing an individual outcome to a habit, and treat the coefficient table as exploratory. The app labels a factor as survey-supported only when the interval supports the harmful direction; other lifestyle wording is explicitly general clinical guidance.

## Per-prediction contributions

The existing recommendation response stores a plain-language explanation in its `message` field. The explanation gives the two largest absolute contributions among smoking, salt, alcohol, physical activity, and diet.

- A contribution is a **calibrated log-odds difference from the weighted training reference profile**. The patient-facing text calls these model points, not percentage points.
- If an input is missing and its contribution is displayed, that contribution is labelled as missing information rather than as the patient's behaviour. The overall estimate names every defaulted field separately.
- Its 95% range comes from 200 stratified PSU-bootstrap draws. Each draw resamples training PSUs for the classifier and validation PSUs for calibration, while keeping the fitted age-spline and scaling transform fixed. The range therefore captures training-coefficient and validation-calibration sampling variation, but not all preprocessing uncertainty.
- A range crossing zero is described as uncertain.
- Contributions are model uncertainty summaries, not causal effects, not Shapley values, and not complete predictive intervals.
- Contributions explain only the population estimate; they do not explain the patient's blood-pressure reading.

The runtime API response shape remains unchanged: `recommendation_id`, `message`, `based_on_trend`, `confidence`, `source`, and `created_at`.

## Safety and runtime behaviour

- Any low reading in the current recommendation window uses low-pressure safety wording only.
- Any very-high reading (systolic at least 180 mmHg or diastolic at least 110 mmHg) uses urgent-care safety wording only.
- A very-high value takes precedence over a conflicting low value. Safety routing takes priority over the average and attaches no model estimate and no lifestyle advice.
- The public stored blood-pressure band remains `high`; `very_high` is an internal safety boundary.
- A very-high saved reading keeps urgent wording even if recommendation refresh fails. The backend also records a distinct acute `very_high_reading` clinician alert, separate from seven-day trend alerts.
- Patient-facing recommendation output never contains a diagnosis or any medication/drug/dose content, medication or treatment timing, treatment start/stop instructions, or treatment-change advice. Treatment-review logic is clinician-only.
- Patient text targets short English sentences suitable for approximately grade 6–8 reading level.
- The model is local and deterministic. There is no external LLM and no third-party inference or data transfer.
- The patient-facing population message names the 2015 Kenya STEPS source and year so it is not mistaken for a current prevalence estimate.
- A missing, corrupt, digest-mismatched, or contract-invalid artefact fails closed: the endpoint continues with deterministic readings/lifestyle guidance, silently omits the population estimate, and logs the failure internally.
- The bundle is loaded and validated during application startup. A real loopback Uvicorn HTTP gate checks that both the first request and p95 remain below 300 ms without an LLM.

## Intended use and limits

- Provides a clearly labelled population probability as context for concurrent survey elevated/high blood-pressure status.
- Supports review of the patient's own reading trend and actionable, non-treatment lifestyle guidance.
- Does not diagnose hypertension, forecast future risk, prescribe treatment, recommend a drug or dose, or replace clinical judgement.
- Does not use the patient's blood-pressure readings as model features because the training survey has no longitudinal reading history.
- Does not establish that changing a logged lifestyle factor will change an individual's blood pressure.
- Maps current, past-30-day, usual-day, and daily lifestyle questions to STEPS imperfectly.
- Training data include medication use for some respondents, which may hide measured risk; medication adherence is deliberately not a model feature.
- Modest overall discrimination and weak subgroup performance mean the probability must not be presented as an individual prediction.

The clinical wording and thresholds remain unsigned and require human review in `docs/advice-for-clinical-review.md`. The plain-language limitations and ethics statement is `docs/limitations-and-ethics.md`.

## Reproduction and versioning

A clean checkout does **not** need the raw survey file for normal application operation. The small versioned artefact above is committed and is loaded by the recommendation engine. The runtime reads the artefact once, verifies the SHA-256 of those exact bytes, and unpickles only that verified in-memory payload. It then validates the bundle's version, build environment, feature/input contract, defaults, labels, thresholds, calibration, contribution arrays, effects, and provenance hashes.

Verify the committed artefact from the repository root:

```bash
(cd backend/ml/models && sha256sum -c SHA256SUMS)
cd backend
.venv/bin/pytest tests/test_model_artifact.py tests/test_ml_training.py
```

From a fresh shell at the repository root, rebuild with CPython 3.13.14 on Linux, the separately obtained raw survey file, and the pinned environment:

```bash
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
.venv/bin/pip install --require-hashes -r ml/requirements-lock.txt
# The test/lint tools are not needed to rebuild. Install requirements-dev.txt
# separately in a development environment if you also want to run the gates.
# Place the source survey at data/2015_STEPS_Data.sav
PYTHONHASHSEED=0 .venv/bin/python -m ml.train_model --features current
```

The training command stages the runtime artefact and refuses to publish a current-model build unless its digest matches `backend/ml/model_contract.py`. It rewrites the runtime artefact, `SHA256SUMS`, metrics, and charts only after that contract check passes. The split lock is authoritative and is not rewritten. For an intentional artefact change, use a temporary `PENDING_` contract value to obtain the new staged digest, set the final digest in `model_contract.py`, and rerun before committing; never publish a `PENDING_` contract. Changes that alter fitted predictions, features, thresholds, or data cleaning require a model-version bump. Uncertainty/reporting changes still require a new artefact hash, checksum, model card, and the full backend and frontend gates.
