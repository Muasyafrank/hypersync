# HyperSync risk model: what the data can and cannot do

Trained on Kenya STEPS 2015 (n = 4,500; 4,282 usable). Target: elevated or high
blood pressure (same thresholds as `app/core/bp_classification.py`).
Retrain with `python -m ml.train_model` (see the docstring for options).

All figures below come from repeated 5-fold cross-validation (3 repeats,
identical folds for every model). A single 20% test split (884 rows) has a
standard error of about 0.018 AUC, bigger than most differences between models.

## 1. The model is at the ceiling of its inputs

| Features | Random forest | Gradient boosting | Logistic + age curve |
|---|---|---|---|
| age + sex only | 0.640 | 0.651 | 0.654 |
| **current 7 features** | 0.658 | 0.655 | 0.657 |
| current + BMI | **0.692** | 0.682 | 0.686 |
| current + BMI + waist | 0.694 | 0.685 | 0.689 |

(AUC, 4,147 identical rows. 0.5 is a coin flip.)

- The five lifestyle questions add almost nothing over age and sex.
- Tuning the forest (depth, leaf size, class weights) moved AUC between 0.688
  and 0.692. Swapping algorithms changes nothing. Only new information helps.
- BMI is the one big gain (+0.03). Waist adds almost nothing beyond BMI.
- Resting pulse adds about +0.013 on top of BMI (0.688 to 0.701).
  Urban/rural, wealth and education add nothing.
- The previously saved figure (0.667 AUC in metrics.json) came from one lucky split. Cross-validation
  puts the same model at 0.656-0.658.

## 2. Why the deployed model is now logistic regression

Same accuracy, but calibrated. The old forest used `class_weight="balanced"`,
so its probabilities were inflated: mean prediction 48% against 42% observed.
That number was shown to patients as their "estimated risk".

| Model | Mean predicted | Observed | Calibration slope (ideal 1) |
|---|---|---|---|
| Random forest, balanced | 48.3% | 41.8% | 1.17 |
| Logistic regression | 41.8% | 41.8% | 0.99 |

## 3. Why factor ranking no longer uses feature importance

The forest's built-in importance ranked physical activity second (0.20), behind
only age. On held-out data, shuffling activity barely changed accuracy:

| Feature | Built-in importance | Held-out permutation (AUC drop) |
|---|---|---|
| age | 0.625 | +0.143 +/- 0.021 |
| activity_minutes | 0.204 | +0.009 +/- 0.005 |
| salt_score | 0.068 | +0.002 +/- 0.004 |
| alcohol_consumed | 0.035 | +0.006 +/- 0.004 |
| smoked | 0.018 | -0.002 +/- 0.001 |
| diet_adherence | 0.014 | +0.001 +/- 0.001 |

Built-in importance favours continuous variables, so activity looked far more
important than it is. Adjusted effects (odds ratio, 95% bootstrap CI, one model
holding the others fixed):

| Factor | OR | Clear effect? |
|---|---|---|
| +10 years of age | 1.52 (1.45-1.60) | yes |
| +5 BMI points (separate run) | 1.56 (1.42-1.67) | yes |
| alcohol in last 30 days | 1.46 (1.21-1.74) | yes |
| +30 active min/day | 0.97 (0.95-0.99) | yes, but small |
| salt level +1 | 0.96 (0.91-1.02) | no |
| currently smokes | 0.85 (0.64-1.09) | no |
| meets fruit/veg target | 1.08 (0.85-1.34) | no |

"No clear effect" does not mean salt or diet do not matter. Trials show they
do. It means these single survey questions are too crude to detect them. So
`lifestyle_factors.rank_factors` credits a factor to the survey only when its
interval excludes "no effect", and words everything else as general clinical
guidance.

## 4. Limits to keep in mind

- STEPS is cross-sectional: association at one moment, not proof that changing a
  habit changes a given person's blood pressure.
- The questions differ from what the app logs. STEPS asks about the last 30
  days and "how often do you add salt"; HyperSync logs a daily entry. Treat the
  mapping in `_build_model_features` as approximate.
- 11% of respondents were on blood pressure medication, which hides their risk.
- Defaults are used when a lifestyle field is missing, so a thin log produces a
  near-generic estimate.

## 5. Next step with the largest payoff

Collect height (once, on the profile) and weight (in the Lifestyle log), compute
BMI, then run `python -m ml.train_model --features bmi`. The engine already fills
any feature the app does not collect with the training median, so the switch is
a retrain plus the data-collection change.
