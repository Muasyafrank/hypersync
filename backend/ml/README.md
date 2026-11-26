# HyperSync survey model: build, evidence, and limits

The deployed artefact is `ml/models/bp_status_model.joblib`. Its identity, contract, measured performance, subgroup results, and limitations are in `ml/models/MODEL_CARD.md`; the data lineage is in `ml/DATA_CARD.md`; the machine-readable evaluation summary is in `ml/artifacts/metrics.json`.

A clean checkout does **not** need the raw `.sav` survey file for normal operation. The small versioned model artefact is committed. Retraining requires the separately obtained source file, the pinned environment, and the raw/split/training hashes below.

## Reproducible v4.1 build

From `backend/` with CPython 3.13.14 on Linux:

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r ml/requirements-lock.txt
# Place the source survey at data/2015_STEPS_Data.sav
PYTHONHASHSEED=0 python -m ml.train_model --features current
```

The command verifies the raw file, reads the committed split lock, trains and evaluates the model, and rewrites the runtime artefact, checksum, metrics, and charts. It does not silently regenerate the split.

| Build item | Published value |
| --- | --- |
| Model version | `4.0.1-steps-survey-calibrated` |
| Raw survey SHA-256 | `081b3cbf4be2b7f840af1f6b3c7c731c6187d3eebf3591e08b4743879b1c5b12` |
| Split-lock SHA-256 | `c3a7dacdb7b265f110e1c79c7782b3601511c3c336dcd23461d0bfc1452cd609` |
| Training-data SHA-256 | `8242dd85710f0bff917f59b0fbda4fce4116ec836b3a883b9ad19379ae1ffc40` |
| Runtime artefact SHA-256 | `45c7adf6df1a707e0560cf110be9cd82da51c73ade610391436f3237fd331652` |
| Dependency-lock SHA-256 | `2d720d57fcd8c60110f8437f8035b42168fff3a1fbe8f75f5dade54ba4183892` |
| Build environment | CPython 3.13.14 on Linux; `PYTHONHASHSEED=0` and single-threaded numerical libraries |
| Seeds | training `20261125`; split `20261125` |

The fully resolved dependency pins are in `ml/requirements-lock.txt`. The build records library versions and numerical environment settings in `metrics.json`.

## Design

- **Target:** concurrent survey elevated/high blood-pressure status, not diagnosis and not future risk.
- **Measurement:** mean of the second and third STEPS BP readings; both are required and the first reading is not a fallback.
- **Weighting:** `wstep2`, the survey measurement weight for the blood-pressure/physical-measurement target.
- **Split:** locked 60/20/20 PSU allocation within rural and urban strata: 120/40/40 PSUs.
- **Model:** weighted, regularised logistic regression with a five-knot cubic spline for age. `C` is selected by five-fold PSU-grouped CV inside training.
- **Calibration:** Platt scaling fitted on validation only and assessed once on test.
- **Uncertainty:** 2,000-replicate PSU-cluster intervals for fixed test metrics and a 200-replicate stratified PSU bootstrap for per-prediction contributions. The contribution bootstrap resamples both training and validation PSUs within strata.
- **Missing data:** training-split weighted defaults plus explicit missingness indicators; no test-derived imputation.

## Locked-test results

The locked test split has 871 respondents in 40 PSUs and 38.0% weighted prevalence.

| Measure | Weighted result | 95% PSU-cluster interval |
| --- | ---: | ---: |
| AUROC | 0.637 | 0.602–0.669 |
| PR-AUC | 0.498 | 0.438–0.562 |
| Brier score | 0.223 | 0.211–0.236 |
| Log loss | 0.638 | 0.611–0.664 |
| Calibration slope | 1.039 | 0.781–1.300 |
| Calibration intercept | 0.036 | -0.264–0.286 |
| Calibration in the large | 0.004 | -0.048–0.052 |
| Expected calibration error | 0.053 | 0.047–0.106 |

These are survey-model measures, not evidence of clinical benefit, safety in HyperSync users, calibration for a new population, or effectiveness of the app's recommendations. Expected calibration error uses ten equal-count bins frozen from the locked validation predictions; the same bins define the curve, chart, headline value, and bootstrap interval.

## Subgroup limitations and runtime age gate

Sex, age, and residence results are in `metrics.json` and the model card. The age 60–69 subgroup has AUROC 0.447 and calibration slope -0.588; age 30–44 has AUROC 0.515 and age 45–59 has AUROC 0.485. The overall average therefore must not be generalized to every user. The runtime withholds the population percentage outside ages 18–29, the only granular age band with positive discrimination and Brier skill in the locked test. Deterministic reading and lifestyle guidance still runs for every supported profile.

## How survey associations affect factor ordering

The model stores adjusted odds ratios with 95% intervals from the training-PSU resampling component of the stratified bootstrap. These coefficient-only intervals do not include validation-calibration or preprocessing uncertainty. The app labels a factor as survey-supported only when the interval supports the harmful direction. Other wording is clearly labelled general clinical guidance.

| Factor | Adjusted odds ratio (95% interval) |
| --- | ---: |
| +10 years of age (mean spline contrast) | 1.396 (1.288–1.508) |
| Male vs female | 1.024 (0.836–1.215) |
| Currently smokes | 0.813 (0.542–1.269) |
| Alcohol in the last 30 days | 1.683 (1.233–2.149) |
| +1 salt level | 0.859 (0.744–0.965) |
| +30 active minutes/day | 0.956 (0.902–1.008) |
| Meets fruit/vegetable target | 1.151 (0.785–1.746) |

Some directions conflict with general clinical guidance. The survey is cross-sectional and vulnerable to confounding and measurement error. The model therefore uses non-causal wording and never says that changing a habit will change one person's blood pressure.

## Per-prediction explanations

The runtime adds the two largest absolute feature contributions to the existing recommendation `message`. Each is a calibrated log-odds difference from the weighted training reference profile and is described as model points, not percentage points. Any displayed contribution based on a missing input is labelled as missing information rather than as behaviour; the overall estimate also names every defaulted field. The 95% range is a PSU-bootstrap model uncertainty interval; a range crossing zero is called uncertain. Each draw resamples training PSUs for the classifier and validation PSUs for calibration, while keeping the fitted age-spline and scaling transform fixed. The range therefore captures training-coefficient and validation-calibration sampling variation, but not all preprocessing uncertainty. These values are not causal effects, Shapley values, or complete predictive intervals, and they do not explain the patient's reading.

## Runtime and safety contract

The runtime reads the artefact once, verifies the digest of those exact bytes, and unpickles only the verified payload. It validates the bundle's exact version, build environment, features, input domains, labels, thresholds, calibration, contribution arrays, effects, and provenance hashes. Loading and validation happen during application startup so the first request does not pay the one-time artefact cost. A missing, corrupt, or incompatible artefact silently degrades to deterministic readings/lifestyle guidance and logs the failure internally.

Low or very-high readings in the current recommendation window always use safety wording only. No model estimate or lifestyle advice is attached. The public band remains `high`; the internal very-high boundary is systolic at least 180 mmHg or diastolic at least 110 mmHg. A very-high value takes precedence over a conflicting low value. Patient-facing recommendation output never contains a diagnosis or any medication/drug/dose content, medication or treatment timing, treatment start/stop instructions, or treatment-change advice. A real loopback Uvicorn HTTP gate checks that both the first request and p95 remain below 300 ms without an LLM.

There is no external LLM and no third-party inference. The local model and template-based guidance are deterministic; the API response shape is unchanged.

## Limits to keep in mind

- The estimate is a **population probability used as context**, not a diagnosis or an individual clinical prediction.
- STEPS is cross-sectional: association at one moment, not proof that changing a habit changes a given person's blood pressure.
- Survey questions differ from HyperSync's daily logs. Treat the feature mapping as approximate; each field's missingness is tracked independently.
- Activity minutes are capped at 240/day and disclosed. Population estimates are omitted outside ages 18–29 even though the survey itself covers ages 18–69.
- Medication use may lower measured blood pressure among some respondents. Medication is not a model feature.
- Missing profile or lifestyle inputs use recorded training defaults, and the estimate names the defaulted fields.
- The PSU-cluster interval is not a complete three-stage survey-design variance estimate.
- The model is a research prototype and has not received clinical sign-off.
