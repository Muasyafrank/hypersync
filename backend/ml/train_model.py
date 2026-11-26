"""Train and evaluate HyperSync's survey-aware population model.

The published v4 model uses the Kenya STEPS 2015 NCD Risk Factor Survey
(KNBS/MoH/WHO). It is a cross-sectional population model, not a patient-level
forecasting model and not a clinical decision rule.

The build is deliberately locked:

* ``wstep2`` is the measurement weight for the blood-pressure/physical-measure
  target;
* primary sampling units (PSUs) stay inside one train/validation/test split;
* the committed PSU assignment file is authoritative;
* the regularisation strength is selected by PSU-grouped CV inside training;
* Platt calibration is learned on validation and assessed once on test; and
* contribution intervals come from a stratified PSU bootstrap.

Run from ``backend/`` with the separately obtained raw survey file::

    python -m ml.train_model --features current

The command verifies the raw-file digest, reads the committed split lock and
rewrites the versioned runtime artefact, checksum and evaluation reports.
"""

import argparse
import hashlib
import json
import os
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

# Keep numerical libraries single-threaded so a rebuild is reproducible on the
# same pinned environment. These must be set before numpy/sklearn are imported;
# inherited values are overridden rather than silently changing the build.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from app.core.bp_classification import (
    ELEVATED_DIASTOLIC,
    ELEVATED_SYSTOLIC,
    HIGH_DIASTOLIC,
    HIGH_SYSTOLIC,
    LOW_DIASTOLIC,
    LOW_SYSTOLIC,
    VERY_HIGH_DIASTOLIC,
    VERY_HIGH_SYSTOLIC,
)
from ml.model_contract import (
    CHECKSUM_FILENAMES,
    MODEL_ESTIMATE_AGE_RANGE,
    MODEL_FILENAMES,
    MODEL_VERSIONS,
    RUNTIME_MODEL_BOOTSTRAP_REPLICATES,
    RUNTIME_MODEL_BUILD_PLATFORM,
    RUNTIME_MODEL_BUILD_PYTHON,
    RUNTIME_MODEL_EFFECT_UNITS,
    RUNTIME_MODEL_FEATURES,
    RUNTIME_MODEL_INPUT_FEATURES,
    RUNTIME_MODEL_RAW_SHA256,
    RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256,
    RUNTIME_MODEL_SHA256,
    RUNTIME_MODEL_SPLIT_FILENAME,
    RUNTIME_MODEL_SPLIT_SHA256,
    RUNTIME_MODEL_TRAINING_DATA_SHA256,
    RUNTIME_MODEL_WEIGHT_VARIABLE,
)
from ml.steps_pipeline import BMI_FEATURE_COLUMNS, FEATURE_COLUMNS, MODEL_INPUT_COLUMNS, build_dataset

MODEL_DIR = Path("ml/models")
ARTIFACT_DIR = Path("ml/artifacts")
DATA_PATH = Path("data/2015_STEPS_Data.sav")
REQUIREMENTS_LOCK_PATH = Path("ml/requirements-lock.txt")
SPLIT_LOCK_PATH = ARTIFACT_DIR / RUNTIME_MODEL_SPLIT_FILENAME

SEED = 20261125
SPLIT_SEED = 20261125
CLASSIFICATION_LABEL_ORDER = ["not_at_risk", "at_risk"]
CLASSIFICATION_THRESHOLDS = {
    "low_systolic": LOW_SYSTOLIC,
    "low_diastolic": LOW_DIASTOLIC,
    "high_systolic": HIGH_SYSTOLIC,
    "high_diastolic": HIGH_DIASTOLIC,
    "very_high_systolic": VERY_HIGH_SYSTOLIC,
    "very_high_diastolic": VERY_HIGH_DIASTOLIC,
    "elevated_systolic": ELEVATED_SYSTOLIC,
    "elevated_diastolic": ELEVATED_DIASTOLIC,
}
CONTINUOUS = {"age", "activity_minutes", "salt_score", "bmi", "pulse"}
C_GRID = (0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
N_BOOTSTRAP = RUNTIME_MODEL_BOOTSTRAP_REPLICATES
N_TEST_BOOTSTRAP = 2000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_build_environment() -> None:
    """Refuse a build that cannot reproduce the published runtime identity."""
    python_version = platform.python_version()
    if python_version != RUNTIME_MODEL_BUILD_PYTHON:
        raise RuntimeError(
            f"the published model requires Python {RUNTIME_MODEL_BUILD_PYTHON}; current version is {python_version}"
        )
    operating_system = platform.system().lower()
    if operating_system != RUNTIME_MODEL_BUILD_PLATFORM:
        raise RuntimeError(
            f"the published model requires {RUNTIME_MODEL_BUILD_PLATFORM}; current platform is {operating_system}"
        )
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("the reproducible model build requires PYTHONHASHSEED=0 before Python starts")
    if not REQUIREMENTS_LOCK_PATH.is_file():
        raise FileNotFoundError(f"dependency lock not found: {REQUIREMENTS_LOCK_PATH}")
    lock_digest = _sha256(REQUIREMENTS_LOCK_PATH)
    if lock_digest != RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256:
        raise RuntimeError(
            f"dependency lock SHA-256 is {lock_digest}, expected {RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256}"
        )


def _weighted_mode(values: pd.Series, weights: pd.Series) -> float:
    """Most common non-missing value under survey weights; ties use the lower value."""
    valid = values.notna() & weights.gt(0)
    if not valid.any():
        raise ValueError("cannot calculate a weighted mode without valid weighted values")
    totals = (
        values[valid]
        .groupby(values[valid])
        .apply(lambda group: float(weights[valid][group.index].sum()), include_groups=False)
    )
    return float(totals[totals == totals.max()].index.min())


def _weighted_median(values: pd.Series, weights: pd.Series) -> float:
    """Weighted median used for a continuous training-population default."""
    valid = values.notna() & weights.gt(0)
    if not valid.any():
        raise ValueError("cannot calculate a weighted median without valid weighted values")
    pairs = pd.DataFrame({"value": values[valid].astype(float), "weight": weights[valid].astype(float)}).sort_values(
        "value"
    )
    midpoint = pairs["weight"].sum() / 2
    cumulative = pairs["weight"].cumsum()
    return float(pairs.loc[cumulative.ge(midpoint), "value"].iloc[0])


def training_defaults(df: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    """Survey-weighted representative defaults learned from the training split."""
    weights = df[RUNTIME_MODEL_WEIGHT_VARIABLE]
    defaults: dict[str, float] = {}
    for column in columns:
        if column in {"age", "activity_minutes", "bmi"}:
            defaults[column] = _weighted_median(df[column], weights)
        else:
            defaults[column] = _weighted_mode(df[column], weights)
    return defaults


def apply_defaults(frame: pd.DataFrame, defaults: dict[str, float]) -> pd.DataFrame:
    """Apply training-split defaults while retaining explicit missingness flags."""
    filled = frame.copy()
    for column, default in defaults.items():
        if column in filled:
            filled[column] = filled[column].fillna(default)
    return filled


def build_model(input_columns: list[str], c_value: float) -> Pipeline:
    """Regularised logistic baseline with a smooth age curve.

    The caller has already applied training-split defaults. Missingness is
    represented by explicit indicator columns, so no fitted imputer can leak
    information from validation or test rows.
    """
    semantic = [column for column in input_columns if not column.endswith("_missing")]
    missing = [column for column in input_columns if column.endswith("_missing")]
    continuous = [column for column in semantic if column in CONTINUOUS and column != "age"]
    binary = [column for column in semantic if column not in CONTINUOUS]

    preprocessor = ColumnTransformer(
        [
            ("age", SplineTransformer(n_knots=5, degree=3), ["age"]),
            ("continuous", StandardScaler(), continuous),
            ("binary", "passthrough", binary),
            ("missing", "passthrough", missing),
        ],
        remainder="drop",
    )
    classifier = LogisticRegression(
        C=c_value,
        solver="lbfgs",
        max_iter=5000,
        random_state=SEED,
    )
    return Pipeline([("preprocess", preprocessor), ("classifier", classifier)])


def _normalised_weights(weights: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(weights, dtype=float)
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("survey weights must be finite and positive")
    return values / values.mean()


def _at_risk_coefficients(classifier, at_risk_class) -> np.ndarray:
    """Return binary-logistic coefficients on the at-risk log-odds scale.

    sklearn fits a positive coefficient toward ``classes_[1]``. The point model
    uses string labels, whose sorted order is ``["at_risk", "not_at_risk"]``;
    bootstrap models use numeric labels ``[0, 1]``. This helper removes that
    otherwise easy-to-miss orientation difference.
    """
    classes = list(classifier.classes_)
    if len(classes) != 2:
        raise ValueError("the at-risk coefficient helper expects a binary classifier")
    at_risk_index = classes.index(at_risk_class)
    coefficients = np.asarray(classifier.coef_[0], dtype=float)
    return coefficients if at_risk_index == 1 else -coefficients


def _calibration_points(y, probability, weights, edges=None) -> tuple[list[dict], float]:
    """Weighted calibration points and expected calibration error."""
    y = np.asarray(y, dtype=int)
    probability = np.asarray(probability, dtype=float)
    weights = _normalised_weights(weights)
    if edges is None:
        edges = np.quantile(probability, np.linspace(0, 1, 11))
    bins = np.clip(np.digitize(probability, np.asarray(edges)[1:-1]), 0, len(edges) - 2)
    points = []
    absolute_error = 0.0
    for bin_index in range(len(edges) - 1):
        mask = bins == bin_index
        if not mask.any():
            # Keep the complete frozen-bin series in metrics and charts. An
            # empty test bin contributes nothing to ECE, but it must not be
            # silently omitted from the published curve.
            points.append(
                {
                    "bin": bin_index + 1,
                    "n": 0,
                    "weight": 0.0,
                    "mean_predicted": None,
                    "observed": None,
                }
            )
            continue
        bin_weight = weights[mask].sum()
        mean_prediction = float(np.average(probability[mask], weights=weights[mask]))
        observed = float(np.average(y[mask], weights=weights[mask]))
        points.append(
            {
                "bin": bin_index + 1,
                "n": int(mask.sum()),
                "weight": float(bin_weight),
                "mean_predicted": mean_prediction,
                "observed": observed,
            }
        )
        absolute_error += float(bin_weight * abs(mean_prediction - observed))
    # ``_normalised_weights`` makes the mean weight 1, so the weights sum to
    # the number of observations. ECE is a probability-scale quantity and must
    # be divided by that total rather than accumulated as a raw weighted sum.
    ece = absolute_error / float(weights.sum())
    return points, ece


def _weighted_metrics(y, probability, weights, calibration_edges=None) -> dict:
    y_array = np.asarray(y, dtype=int)
    probability = np.asarray(probability, dtype=float)
    weights = _normalised_weights(weights)
    clipped = np.clip(probability, 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1e6, solver="lbfgs", max_iter=5000).fit(logit, y_array, sample_weight=weights)
    prevalence = float(np.average(y_array, weights=weights))
    mean_prediction = float(np.average(probability, weights=weights))
    baseline_brier = float(np.average((y_array - prevalence) ** 2, weights=weights))
    _curve, ece = _calibration_points(y_array, probability, weights, edges=calibration_edges)
    return {
        "n": int(len(y_array)),
        "weighted_prevalence": prevalence,
        "mean_prediction": mean_prediction,
        "calibration_in_the_large": prevalence - mean_prediction,
        "expected_calibration_error": ece,
        "auroc": float(roc_auc_score(y_array, probability, sample_weight=weights)),
        "pr_auc": float(average_precision_score(y_array, probability, sample_weight=weights)),
        "brier": float(brier_score_loss(y_array, probability, sample_weight=weights)),
        "log_loss": float(log_loss(y_array, probability, labels=[0, 1], sample_weight=weights)),
        "prevalence_baseline_brier": baseline_brier,
        "brier_skill_score": float(1 - brier_score_loss(y_array, probability, sample_weight=weights) / baseline_brier),
        "calibration_slope": float(calibrator.coef_[0][0]),
        "calibration_intercept": float(calibrator.intercept_[0]),
    }


def _unweighted_metrics(y, probability) -> dict:
    y_array = np.asarray(y, dtype=int)
    probability = np.asarray(probability, dtype=float)
    prevalence = float(y_array.mean())
    baseline_brier = float(np.mean((y_array - prevalence) ** 2))
    return {
        "n": int(len(y_array)),
        "prevalence": prevalence,
        "mean_prediction": float(probability.mean()),
        "auroc": float(roc_auc_score(y_array, probability)),
        "pr_auc": float(average_precision_score(y_array, probability)),
        "brier": float(brier_score_loss(y_array, probability)),
        "log_loss": float(log_loss(y_array, probability, labels=[0, 1])),
        "prevalence_baseline_brier": baseline_brier,
    }


def _fit_calibrator(y, base_probability, weights):
    clipped = np.clip(np.asarray(base_probability, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1e6, solver="lbfgs", max_iter=5000).fit(
        logit, np.asarray(y, dtype=int), sample_weight=_normalised_weights(weights)
    )
    return float(calibrator.coef_[0][0]), float(calibrator.intercept_[0])


def _apply_calibration(probability, slope: float, intercept: float):
    clipped = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1 - clipped))
    return 1 / (1 + np.exp(-(slope * logit + intercept)))


def create_split_assignment(df: pd.DataFrame) -> pd.DataFrame:
    """Create a deterministic 60/20/20 PSU split within each stratum."""
    assignments = []
    for stratum in sorted(df["stratum"].dropna().unique()):
        psus = np.array(sorted(df.loc[df["stratum"] == stratum, "psu"].dropna().unique()), dtype=int)
        rng = np.random.default_rng(SPLIT_SEED + int(stratum))
        shuffled = rng.permutation(psus)
        n_test = int(round(len(psus) * 0.20))
        n_validation = int(round(len(psus) * 0.20))
        for psu in shuffled[:n_test]:
            assignments.append((int(psu), int(stratum), "test"))
        for psu in shuffled[n_test : n_test + n_validation]:
            assignments.append((int(psu), int(stratum), "validation"))
        for psu in shuffled[n_test + n_validation :]:
            assignments.append((int(psu), int(stratum), "train"))
    return pd.DataFrame(assignments, columns=["psu", "stratum", "split"]).sort_values("psu").reset_index(drop=True)


def write_split_lock(df: pd.DataFrame) -> Path:
    assignment = create_split_assignment(df)
    SPLIT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    assignment.to_csv(SPLIT_LOCK_PATH, index=False, lineterminator="\n")
    return SPLIT_LOCK_PATH


def load_split_lock(df: pd.DataFrame) -> pd.DataFrame:
    """Read and validate the committed PSU lock; never silently regenerate it."""
    if not SPLIT_LOCK_PATH.exists():
        raise FileNotFoundError(
            f"split lock {SPLIT_LOCK_PATH} is missing; run with --write-split-lock and commit the result"
        )
    digest = _sha256(SPLIT_LOCK_PATH)
    if not RUNTIME_MODEL_SPLIT_SHA256.startswith("PENDING_") and digest != RUNTIME_MODEL_SPLIT_SHA256:
        raise ValueError(f"split lock SHA-256 is {digest}, expected {RUNTIME_MODEL_SPLIT_SHA256}")

    assignment = pd.read_csv(SPLIT_LOCK_PATH)
    if list(assignment.columns) != ["psu", "stratum", "split"]:
        raise ValueError("split lock must contain exactly psu,stratum,split")
    if assignment["psu"].duplicated().any():
        raise ValueError("split lock assigns a PSU more than once")
    if not set(assignment["split"]).issubset({"train", "validation", "test"}):
        raise ValueError("split lock contains an unknown split name")

    observed = df[["psu", "stratum"]].dropna().drop_duplicates()
    if len(observed) != len(assignment):
        raise ValueError("split lock does not cover every PSU in the cleaned data")
    comparison = observed.merge(assignment, on="psu", how="outer", suffixes=("_data", "_lock"), indicator=True)
    if not comparison["_merge"].eq("both").all():
        raise ValueError("split lock and cleaned data contain different PSU sets")
    if not comparison["stratum_data"].eq(comparison["stratum_lock"]).all():
        raise ValueError("split lock changes a PSU's survey stratum")

    merged = df.merge(assignment[["psu", "split"]], on="psu", how="left", validate="many_to_one")
    if merged["split"].isna().any():
        raise ValueError("split lock did not assign every model row")
    return merged


def _tune_c(train_df: pd.DataFrame, input_columns: list[str]) -> tuple[float, list[dict]]:
    """Select regularisation by five-fold PSU-grouped CV inside training only."""
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    x = train_df[input_columns]
    y = train_df["y"].to_numpy()
    groups = train_df["psu"].to_numpy()
    results = []

    for c_value in C_GRID:
        fold_losses = []
        fold_briers = []
        fold_aucs = []
        for fold_train, fold_validation in splitter.split(x, y, groups):
            fold_train_df = train_df.iloc[fold_train]
            fold_validation_df = train_df.iloc[fold_validation]
            defaults = training_defaults(fold_train_df, FEATURE_COLUMNS)
            x_train = apply_defaults(fold_train_df[input_columns], defaults)
            x_validation = apply_defaults(fold_validation_df[input_columns], defaults)
            weights = _normalised_weights(fold_train_df[RUNTIME_MODEL_WEIGHT_VARIABLE])
            model = build_model(input_columns, c_value).fit(
                x_train,
                fold_train_df["y"].map({0: "not_at_risk", 1: "at_risk"}),
                classifier__sample_weight=weights,
            )
            probability = model.predict_proba(x_validation)[:, list(model.classes_).index("at_risk")]
            validation_weights = _normalised_weights(fold_validation_df[RUNTIME_MODEL_WEIGHT_VARIABLE])
            fold_losses.append(
                log_loss(
                    fold_validation_df["y"],
                    probability,
                    labels=[0, 1],
                    sample_weight=validation_weights,
                )
            )
            fold_briers.append(brier_score_loss(fold_validation_df["y"], probability, sample_weight=validation_weights))
            fold_aucs.append(roc_auc_score(fold_validation_df["y"], probability, sample_weight=validation_weights))
        results.append(
            {
                "c": c_value,
                "mean_log_loss": float(np.mean(fold_losses)),
                "mean_brier": float(np.mean(fold_briers)),
                "mean_auroc": float(np.mean(fold_aucs)),
                "fold_log_loss": [float(value) for value in fold_losses],
            }
        )
        print(
            f"  C={c_value:<4} weighted CV log loss {results[-1]['mean_log_loss']:.5f}  "
            f"Brier {results[-1]['mean_brier']:.5f}  AUROC {results[-1]['mean_auroc']:.4f}"
        )

    best = min(results, key=lambda result: (result["mean_log_loss"], result["c"]))
    return float(best["c"]), results


def _feature_groups(feature_names: list[str]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for feature in RUNTIME_MODEL_FEATURES:
        indices = []
        for index, name in enumerate(feature_names):
            if feature == "age" and name.startswith("age__"):
                indices.append(index)
            elif name in {f"binary__{feature}", f"continuous__{feature}"}:
                indices.append(index)
            elif name == f"missing__{feature}_missing":
                indices.append(index)
        groups[feature] = indices
    covered = [index for indices in groups.values() for index in indices]
    if sorted(covered) != list(range(len(feature_names))):
        raise ValueError("feature groups do not cover every transformed model feature exactly once")
    return groups


def _psu_clusters(frame: pd.DataFrame) -> dict[int, dict[int, list[int]]]:
    """Map stratum and PSU to row positions within one split."""
    clusters: dict[int, dict[int, list[int]]] = {}
    for position, row in enumerate(frame.itertuples(index=False)):
        clusters.setdefault(int(row.stratum), {}).setdefault(int(row.psu), []).append(position)
    return clusters


def _resample_psu_positions(clusters: dict[int, dict[int, list[int]]], rng) -> np.ndarray:
    """Resample PSUs with replacement within each stratum."""
    positions = []
    for stratum in sorted(clusters):
        psus = np.array(sorted(clusters[stratum]), dtype=int)
        selected = rng.choice(psus, size=len(psus), replace=True)
        for psu in selected:
            positions.extend(clusters[stratum][int(psu)])
    return np.asarray(positions, dtype=int)


def _bootstrap_coefficients(
    z_train,
    y_train,
    weights_train,
    z_validation,
    y_validation,
    weights_validation,
    train_df,
    validation_df,
    c_value: float,
    replicates: int,
):
    """Stratified PSU bootstrap of training fits and validation calibration.

    Training and validation PSUs are both resampled within strata. Original
    survey weights are repeated with their selected PSU, so each draw reflects
    cluster sampling variation in both model fitting and calibration.
    """
    rng = np.random.default_rng(SEED + 991)
    train_clusters = _psu_clusters(train_df)
    validation_clusters = _psu_clusters(validation_df)

    coefficient_draws = []
    calibration_slopes = []
    for replicate in range(replicates):
        positions = _resample_psu_positions(train_clusters, rng)
        draw_weights = _normalised_weights(weights_train[positions])
        classifier = LogisticRegression(
            C=c_value,
            solver="lbfgs",
            max_iter=5000,
            random_state=SEED + replicate,
        ).fit(z_train[positions], y_train[positions], sample_weight=draw_weights)
        # Numeric 0/1 labels put the at-risk class at index 1. The helper keeps
        # this draw on exactly the same at-risk scale as the point model.
        coefficient_draws.append(_at_risk_coefficients(classifier, 1))

        validation_positions = _resample_psu_positions(validation_clusters, rng)
        validation_probability = classifier.predict_proba(z_validation[validation_positions])[:, 1]
        slope, _intercept = _fit_calibrator(
            y_validation[validation_positions],
            validation_probability,
            weights_validation[validation_positions],
        )
        calibration_slopes.append(slope)
        if (replicate + 1) % 25 == 0 or replicate + 1 == replicates:
            print(f"  PSU bootstrap {replicate + 1}/{replicates}")

    return np.asarray(coefficient_draws), np.asarray(calibration_slopes)


def _bootstrap_test_metrics(test_df, probability, replicates: int, calibration_edges=None) -> dict:
    """PSU-cluster bootstrap intervals for fixed locked-test predictions.

    PSUs are sampled with replacement within each stratum. Respondent rows are
    not duplicated: each sampled PSU's multiplicity is applied to its original
    survey weight. These are PSU-cluster intervals, not a complete three-stage
    survey-design bootstrap.
    """
    rng = np.random.default_rng(SEED + 1771)
    y = test_df["y"].to_numpy()
    weights = test_df[RUNTIME_MODEL_WEIGHT_VARIABLE].to_numpy()
    psu = test_df["psu"].to_numpy()
    stratum = test_df["stratum"].to_numpy()
    draws = []

    for _replicate in range(replicates):
        multiplicities = {}
        for stratum_value in sorted(np.unique(stratum)):
            psus = np.array(sorted(np.unique(psu[stratum == stratum_value])), dtype=int)
            selected = rng.choice(psus, size=len(psus), replace=True)
            for selected_psu in selected:
                multiplicities[int(selected_psu)] = multiplicities.get(int(selected_psu), 0) + 1
        multiplicities_by_row = np.asarray([multiplicities.get(int(row_psu), 0) for row_psu in psu], dtype=int)
        sampled = multiplicities_by_row > 0
        replicate_weights = multiplicities_by_row[sampled] * weights[sampled]
        draws.append(
            _weighted_metrics(
                y[sampled],
                probability[sampled],
                replicate_weights,
                calibration_edges=calibration_edges,
            )
        )

    result = {}
    point = _weighted_metrics(y, probability, weights, calibration_edges=calibration_edges)
    for name in (
        "auroc",
        "pr_auc",
        "brier",
        "log_loss",
        "calibration_slope",
        "calibration_intercept",
        "calibration_in_the_large",
        "expected_calibration_error",
    ):
        values = np.asarray([draw[name] for draw in draws], dtype=float)
        low, high = np.quantile(values, [0.025, 0.975])
        result[name] = {
            "estimate": float(point[name]),
            "ci_low": float(low),
            "ci_high": float(high),
        }
    return {
        "method": "stratified PSU-cluster bootstrap of fixed locked-test predictions",
        "replicates": replicates,
        "interval": "percentile 95% interval",
        "scope": "PSU-cluster uncertainty only; not a full three-stage survey-design interval",
        "metrics": result,
    }


def _global_effects(coefficients, feature_names, groups, age_contrasts, scales):
    """Adjusted odds ratios on the model's original feature scales."""
    sex_index = groups["sex"][0]
    salt_index = next(index for index in groups["salt_score"] if feature_names[index] == "continuous__salt_score")
    activity_index = next(
        index for index in groups["activity_minutes"] if feature_names[index] == "continuous__activity_minutes"
    )

    def binary_odds(feature: str) -> float:
        index = next(index for index in groups[feature] if feature_names[index] == f"binary__{feature}")
        return float(np.exp(coefficients[index]))

    age_log_odds = float(np.mean(age_contrasts @ coefficients[groups["age"]]))
    return {
        "age": float(np.exp(age_log_odds)),
        "sex": float(np.exp(coefficients[sex_index])),
        "salt_score": float(np.exp(coefficients[salt_index] / scales["salt_score"])),
        "alcohol_consumed": binary_odds("alcohol_consumed"),
        "activity_minutes": float(np.exp(coefficients[activity_index] / scales["activity_minutes"] * 30)),
        "diet_adherence": binary_odds("diet_adherence"),
        "smoked": binary_odds("smoked"),
    }


def _save_charts(
    effects,
    test_probability,
    test_y,
    test_weights,
    output_dir: Path,
    calibration_edges=None,
):
    names = list(effects)
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(names) + 1.6))
    for index, name in enumerate(names):
        effect = effects[name]
        clear = effect["ci_low"] > 1 or effect["ci_high"] < 1
        colour = "#0D9488" if clear else "#94A3B8"
        ax.plot([effect["ci_low"], effect["ci_high"]], [index, index], color=colour, lw=2)
        ax.plot(effect["odds_ratio"], index, "o", color=colour)
    ax.axvline(1, color="#334155", ls="--", lw=1)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([f"{name}  ({effects[name]['unit']})" for name in names], fontsize=8)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("Survey-weighted adjusted odds ratio (95% PSU-bootstrap interval)")
    ax.set_title("Adjusted effects, Kenya STEPS 2015")
    fig.tight_layout()
    fig.savefig(output_dir / "effects.png", dpi=160)
    plt.close(fig)

    weights = _normalised_weights(test_weights)
    edges = np.asarray(
        calibration_edges if calibration_edges is not None else np.quantile(test_probability, np.linspace(0, 1, 11)),
        dtype=float,
    )
    curve, _ece = _calibration_points(test_y, test_probability, weights, edges=edges)
    predicted = [point["mean_predicted"] if point["mean_predicted"] is not None else np.nan for point in curve]
    observed = [point["observed"] if point["observed"] is not None else np.nan for point in curve]
    fig, ax = plt.subplots(figsize=(5.2, 5))
    ax.plot([0, 1], [0, 1], "--", color="#94A3B8")
    ax.plot(predicted, observed, "o-", color="#0D9488")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed weighted share at risk")
    ax.set_title("Locked-test calibration (validation-frozen bins)")
    fig.tight_layout()
    fig.savefig(output_dir / "calibration.png", dpi=160)
    plt.close(fig)

    threshold = float(np.average(test_y, weights=weights))
    predicted_class = (test_probability >= threshold).astype(int)
    matrix = confusion_matrix(test_y, predicted_class, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.imshow(matrix, cmap="Greens")
    ax.set_xticks(range(2), CLASSIFICATION_LABEL_ORDER, rotation=45)
    ax.set_yticks(range(2), CLASSIFICATION_LABEL_ORDER)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Locked-test confusion matrix at weighted prevalence")
    for row in range(2):
        for column in range(2):
            ax.text(
                column,
                row,
                matrix[row, column],
                ha="center",
                va="center",
                color="white" if matrix[row, column] > np.max(matrix) / 2 else "black",
            )
    fig.tight_layout()
    fig.savefig(output_dir / "confusion_matrix.png", dpi=160)
    plt.close(fig)


def _library_versions() -> dict[str, str]:
    packages = [
        "joblib",
        "matplotlib",
        "numpy",
        "pandas",
        "pyreadstat",
        "scikit-learn",
        "scipy",
    ]
    versions = {"python": platform.python_version()}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _training_data_hash(df: pd.DataFrame) -> str:
    columns = [
        "respondent_id",
        *RUNTIME_MODEL_FEATURES,
        *RUNTIME_MODEL_INPUT_FEATURES[len(RUNTIME_MODEL_FEATURES) :],
        "y",
        RUNTIME_MODEL_WEIGHT_VARIABLE,
        "psu",
        "stratum",
        "split",
    ]
    canonical = df[columns].sort_values("respondent_id").to_csv(index=False, float_format="%.15g", lineterminator="\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", choices=["current", "bmi"], default="current")
    parser.add_argument(
        "--write-split-lock",
        action="store_true",
        help="write the deterministic PSU assignment, then stop without training",
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=N_BOOTSTRAP)
    args = parser.parse_args()
    if args.bootstrap_replicates < 50:
        raise ValueError("at least 50 bootstrap replicates are required")
    _validate_build_environment()

    columns = FEATURE_COLUMNS if args.features == "current" else BMI_FEATURE_COLUMNS
    input_columns = list(MODEL_INPUT_COLUMNS if args.features == "current" else columns)
    if args.features == "bmi":
        input_columns += ["bmi_missing"]

    model_dir = MODEL_DIR
    artifact_dir = ARTIFACT_DIR / ("bmi" if args.features == "bmi" else "")
    model_filename = MODEL_FILENAMES[args.features]
    checksum_filename = CHECKSUM_FILENAMES[args.features]
    model_version = MODEL_VERSIONS[args.features]
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    print("Loading and cleaning Kenya STEPS 2015 data...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"raw survey file not found: {DATA_PATH}")
    raw_digest = _sha256(DATA_PATH)
    if raw_digest != RUNTIME_MODEL_RAW_SHA256:
        raise ValueError(f"raw survey SHA-256 is {raw_digest}, expected {RUNTIME_MODEL_RAW_SHA256}")
    df = build_dataset(str(DATA_PATH))

    if args.write_split_lock:
        path = write_split_lock(df)
        print(f"Wrote split lock -> {path}")
        print(f"Split lock SHA-256 -> {_sha256(path)}")
        return

    exclusion_counts = dict(df.attrs.get("exclusion_counts", {}))
    known_pregnant_count = int(df["pregnant"].eq(1).sum())
    unknown_pregnancy_count = int(df["pregnant"].isna().sum())
    # Pregnancy can change blood pressure. Exclude known pregnancy and an
    # unknown pregnancy status rather than assuming that an unanswered status
    # means "not pregnant".
    df = df[df["pregnant"].eq(0)].copy()
    zero_weight_count = int(df[RUNTIME_MODEL_WEIGHT_VARIABLE].le(0).sum())
    df = df[df[RUNTIME_MODEL_WEIGHT_VARIABLE].gt(0)].copy()
    df = load_split_lock(df)
    df["y"] = df["bp_status"].isin(["elevated", "high"]).astype(int)
    if args.features == "bmi":
        df["bmi_missing"] = df["bmi"].isna().astype(int)

    print(
        f"Model rows: {len(df)}; weighted elevated/high share "
        f"{np.average(df['y'], weights=df[RUNTIME_MODEL_WEIGHT_VARIABLE]):.3f}; "
        f"zero-weight rows excluded: {zero_weight_count}"
    )

    train_df = df[df["split"] == "train"].copy()
    validation_df = df[df["split"] == "validation"].copy()
    test_df = df[df["split"] == "test"].copy()
    for name, part in (("train", train_df), ("validation", validation_df), ("test", test_df)):
        print(
            f"  {name:10s} rows={len(part):4d} PSUs={part['psu'].nunique():3d} "
            f"weighted prevalence={np.average(part['y'], weights=part[RUNTIME_MODEL_WEIGHT_VARIABLE]):.3f}"
        )

    print("\nSelecting regularisation by PSU-grouped CV inside training only...")
    best_c, cv_grid = _tune_c(train_df, input_columns)

    defaults = training_defaults(train_df, columns)
    x_train = apply_defaults(train_df[input_columns], defaults)
    x_validation = apply_defaults(validation_df[input_columns], defaults)
    x_test = apply_defaults(test_df[input_columns], defaults)
    x_test_all_missing = x_test.copy()
    for feature in RUNTIME_MODEL_FEATURES:
        x_test_all_missing[feature] = defaults[feature]
    for feature in RUNTIME_MODEL_FEATURES:
        x_test_all_missing[f"{feature}_missing"] = 1
    train_weights = _normalised_weights(train_df[RUNTIME_MODEL_WEIGHT_VARIABLE])
    validation_weights = _normalised_weights(validation_df[RUNTIME_MODEL_WEIGHT_VARIABLE])
    test_weights = _normalised_weights(test_df[RUNTIME_MODEL_WEIGHT_VARIABLE])

    final = build_model(input_columns, best_c).fit(
        x_train,
        train_df["y"].map({0: "not_at_risk", 1: "at_risk"}),
        classifier__sample_weight=train_weights,
    )
    base_validation = final.predict_proba(x_validation)[:, list(final.classes_).index("at_risk")]
    calibration_slope, calibration_intercept = _fit_calibrator(validation_df["y"], base_validation, validation_weights)
    base_test = final.predict_proba(x_test)[:, list(final.classes_).index("at_risk")]
    calibrated_test = _apply_calibration(base_test, calibration_slope, calibration_intercept)
    all_missing_base = final.predict_proba(x_test_all_missing)[:, list(final.classes_).index("at_risk")]
    all_missing_calibrated = _apply_calibration(all_missing_base, calibration_slope, calibration_intercept)

    validation_calibrated = _apply_calibration(base_validation, calibration_slope, calibration_intercept)
    # Freeze calibration bins on validation before looking at the test set.
    # Every published ECE and calibration curve then uses these same edges.
    validation_curve_edges = np.quantile(validation_calibrated, np.linspace(0, 1, 11))
    weighted_test = _weighted_metrics(
        test_df["y"], calibrated_test, test_weights, calibration_edges=validation_curve_edges
    )
    unweighted_test = _unweighted_metrics(test_df["y"], calibrated_test)
    uncalibrated_test = _weighted_metrics(
        test_df["y"], base_test, test_weights, calibration_edges=validation_curve_edges
    )
    validation_metrics = _weighted_metrics(
        validation_df["y"], validation_calibrated, validation_weights, calibration_edges=validation_curve_edges
    )
    test_calibration_curve, test_ece = _calibration_points(
        test_df["y"], calibrated_test, test_weights, edges=validation_curve_edges
    )
    third_test_target = test_df["bp_status_third"].isin(["elevated", "high"]).astype(int)
    third_target_metrics = _weighted_metrics(
        third_test_target, calibrated_test, test_weights, calibration_edges=validation_curve_edges
    )
    print(
        f"\nLocked test: weighted AUROC {weighted_test['auroc']:.3f}, PR-AUC {weighted_test['pr_auc']:.3f}, "
        f"Brier {weighted_test['brier']:.4f}, calibration slope {weighted_test['calibration_slope']:.3f}"
    )
    print(f"Building {N_TEST_BOOTSTRAP}-replicate PSU-cluster test interval...")
    test_uncertainty = _bootstrap_test_metrics(
        test_df,
        calibrated_test,
        N_TEST_BOOTSTRAP,
        calibration_edges=validation_curve_edges,
    )

    subgroups = {}
    subgroup_definitions = {
        "female": df["sex"].eq(0),
        "male": df["sex"].eq(1),
        "age_18_39": df["age"].between(18, 39),
        "age_40_59": df["age"].between(40, 59),
        "age_60_69": df["age"].between(60, 69),
        "age_18_29": df["age"].between(18, 29),
        "age_30_44": df["age"].between(30, 44),
        "age_45_59": df["age"].between(45, 59),
        "rural": df["stratum"].eq(1),
        "urban": df["stratum"].eq(2),
    }
    for name, definition in subgroup_definitions.items():
        mask = definition.loc[test_df.index].to_numpy()
        subgroup = test_df.loc[mask]
        events = int(subgroup["y"].sum())
        denominators = {
            "n": int(len(subgroup)),
            "events": events,
            "non_events": int(len(subgroup) - events),
            "psus": int(subgroup["psu"].nunique()),
            "weighted_denominator": float(subgroup[RUNTIME_MODEL_WEIGHT_VARIABLE].sum()),
        }
        if len(subgroup) == 0 or len(np.unique(subgroup["y"].to_numpy())) < 2:
            subgroups[name] = {**denominators, "metrics": None}
            continue
        subgroups[name] = {
            **denominators,
            "metrics": _weighted_metrics(
                subgroup["y"].to_numpy(),
                calibrated_test[mask],
                test_weights[mask],
                calibration_edges=validation_curve_edges,
            ),
        }

    preprocessor = final.named_steps["preprocess"]
    classifier = final.named_steps["classifier"]
    z_train = preprocessor.transform(x_train)
    z_validation = preprocessor.transform(x_validation)
    feature_names = list(preprocessor.get_feature_names_out())
    groups = _feature_groups(feature_names)
    # The string labels sort as ["at_risk", "not_at_risk"], so sklearn's
    # positive class-1 coefficient points toward "not_at_risk". The helper
    # expresses every contribution on the at-risk log-odds scale used by the
    # probability.
    point_coefficients = _at_risk_coefficients(classifier, "at_risk")

    reference = {feature: defaults[feature] for feature in columns}
    for feature in RUNTIME_MODEL_INPUT_FEATURES:
        if feature.endswith("_missing"):
            reference[feature] = 0
    age_contrasts = []
    for age in range(18, 60):
        first = reference.copy()
        second = reference.copy()
        first["age"] = age
        second["age"] = age + 10
        first_z = preprocessor.transform(pd.DataFrame([first], columns=input_columns))[0]
        second_z = preprocessor.transform(pd.DataFrame([second], columns=input_columns))[0]
        age_contrasts.append(second_z[groups["age"]] - first_z[groups["age"]])
    age_contrasts = np.asarray(age_contrasts)

    continuous_transformer = preprocessor.named_transformers_["continuous"]
    scales = {
        "salt_score": float(continuous_transformer.scale_[0]),
        "activity_minutes": float(continuous_transformer.scale_[1]),
    }

    print(f"\nBuilding {args.bootstrap_replicates}-replicate stratified PSU bootstrap...")
    bootstrap_coefficients, bootstrap_slopes = _bootstrap_coefficients(
        z_train,
        train_df["y"].to_numpy(),
        train_df[RUNTIME_MODEL_WEIGHT_VARIABLE].to_numpy(),
        z_validation,
        validation_df["y"].to_numpy(),
        validation_df[RUNTIME_MODEL_WEIGHT_VARIABLE].to_numpy(),
        train_df,
        validation_df,
        best_c,
        args.bootstrap_replicates,
    )

    point_effects = _global_effects(point_coefficients, feature_names, groups, age_contrasts, scales)
    bootstrap_effects = [
        _global_effects(coefficients, feature_names, groups, age_contrasts, scales)
        for coefficients in bootstrap_coefficients
    ]
    effects = {}
    for feature in RUNTIME_MODEL_FEATURES:
        draws = np.asarray([result[feature] for result in bootstrap_effects])
        low, high = np.quantile(draws, [0.025, 0.975])
        effects[feature] = {
            "odds_ratio": float(point_effects[feature]),
            "ci_low": float(low),
            "ci_high": float(high),
            "unit": RUNTIME_MODEL_EFFECT_UNITS[feature],
        }

    split_counts = {}
    for split_name, part in (("train", train_df), ("validation", validation_df), ("test", test_df)):
        split_counts[split_name] = {
            "rows": int(len(part)),
            "psus": int(part["psu"].nunique()),
            "weighted_prevalence": float(np.average(part["y"], weights=part[RUNTIME_MODEL_WEIGHT_VARIABLE])),
        }

    training_data_sha256 = _training_data_hash(df)
    if (
        not RUNTIME_MODEL_TRAINING_DATA_SHA256.startswith("PENDING_")
        and training_data_sha256 != RUNTIME_MODEL_TRAINING_DATA_SHA256
    ):
        raise ValueError(
            f"training-data SHA-256 is {training_data_sha256}, expected {RUNTIME_MODEL_TRAINING_DATA_SHA256}"
        )

    metrics = {
        "data_source": "Kenya STEPS NCD Risk Factor Survey 2015 (KNBS/MoH/WHO)",
        "model_version": model_version,
        "feature_set": args.features,
        "build_environment": {
            "python": RUNTIME_MODEL_BUILD_PYTHON,
            "platform": RUNTIME_MODEL_BUILD_PLATFORM,
            "requirements_lock_sha256": RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256,
        },
        "features": list(RUNTIME_MODEL_FEATURES),
        "model_input_features": input_columns,
        "runtime_estimate_age_range": list(MODEL_ESTIMATE_AGE_RANGE),
        "classification_thresholds": CLASSIFICATION_THRESHOLDS,
        "raw_data_sha256": raw_digest,
        "training_data_sha256": training_data_sha256,
        "split_lock_sha256": _sha256(SPLIT_LOCK_PATH),
        "seed": SEED,
        "split_seed": SPLIT_SEED,
        "n_total": int(len(df)),
        "exclusion_counts": {
            **exclusion_counts,
            "known_pregnant_excluded_after_core_filters": known_pregnant_count,
            "unknown_pregnancy_excluded_after_core_filters": unknown_pregnancy_count,
            "analytic_zero_weight_rows_remaining": zero_weight_count,
        },
        "n_zero_weight_excluded": zero_weight_count,
        "at_risk_share": float(df["y"].mean()),
        "weighted_at_risk_share": float(np.average(df["y"], weights=df[RUNTIME_MODEL_WEIGHT_VARIABLE])),
        "survey": {
            "weight_variable": RUNTIME_MODEL_WEIGHT_VARIABLE,
            "weight_normalisation": "weights divided by their split mean for fitting and evaluation",
            "weight_min": float(df[RUNTIME_MODEL_WEIGHT_VARIABLE].min()),
            "weight_max": float(df[RUNTIME_MODEL_WEIGHT_VARIABLE].max()),
            "weight_mean": float(df[RUNTIME_MODEL_WEIGHT_VARIABLE].mean()),
            "effective_sample_size": float(
                df[RUNTIME_MODEL_WEIGHT_VARIABLE].sum() ** 2 / (df[RUNTIME_MODEL_WEIGHT_VARIABLE] ** 2).sum()
            ),
            "psu_count": int(df["psu"].nunique()),
            "strata": sorted(int(value) for value in df["stratum"].unique()),
        },
        "split": {
            "seed": SPLIT_SEED,
            "lock_file": f"backend/ml/artifacts/{RUNTIME_MODEL_SPLIT_FILENAME}",
            "lock_sha256": _sha256(SPLIT_LOCK_PATH),
            "method": "60/20/20 PSU split within each residence stratum",
            "counts": split_counts,
        },
        "missingness": {
            column: int(df[column].sum()) for column in RUNTIME_MODEL_INPUT_FEATURES if column.endswith("_missing")
        },
        "hyperparameters": {
            "selected_c": best_c,
            "selection_metric": "mean PSU-grouped CV weighted log loss",
            "cv_grid": cv_grid,
            "classifier": "LogisticRegression(solver=lbfgs, max_iter=5000)",
            "age_representation": "five-knot cubic spline",
        },
        "calibration": {
            "method": "Platt calibration on the locked validation split",
            "slope": calibration_slope,
            "intercept": calibration_intercept,
            "validation": validation_metrics,
            "test_uncalibrated": uncalibrated_test,
            "test_calibrated": weighted_test,
            "bin_definition": "10 equal-count bins frozen from locked validation calibrated probabilities",
            "frozen_validation_bin_edges": [float(value) for value in validation_curve_edges],
            "test_calibration_curve": test_calibration_curve,
            "test_expected_calibration_error": test_ece,
        },
        "test": {
            "weighted": weighted_test,
            "unweighted": unweighted_test,
            "threshold": float(np.average(test_df["y"], weights=test_weights)),
            "confusion_matrix": confusion_matrix(
                test_df["y"],
                (calibrated_test >= np.average(test_df["y"], weights=test_weights)).astype(int),
                labels=[0, 1],
            ).tolist(),
            "psu_cluster_bootstrap_uncertainty": test_uncertainty,
        },
        "missing_data_sensitivity": {
            "scenario": "all seven model inputs replaced by survey-weighted training defaults with every missingness flag set",
            "weighted_test": _weighted_metrics(
                test_df["y"],
                all_missing_calibrated,
                test_weights,
                calibration_edges=validation_curve_edges,
            ),
        },
        "target_sensitivity": {
            "primary": "mean of second and third BP readings; both readings required",
            "alternate": "third BP reading only; the same frozen model is evaluated with alternate labels",
            "primary_test": weighted_test,
            "alternate_test": third_target_metrics,
            "all_rows_primary_at_risk_share": float(df["y"].mean()),
            "all_rows_alternate_at_risk_share": float(df["bp_status_third"].isin(["elevated", "high"]).mean()),
            "all_rows_changed_binary_label": int(
                (df["y"] != df["bp_status_third"].isin(["elevated", "high"]).astype(int)).sum()
            ),
        },
        "subgroups": subgroups,
        "effects": effects,
        "contribution_uncertainty": {
            "method": "stratified PSU bootstrap of training fits and validation calibration",
            "replicates": args.bootstrap_replicates,
            "interval": "percentile 95% interval",
            "scale": "calibrated log-odds difference from the weighted training reference profile",
            "sampled_splits": ["train", "validation"],
            "fixed_components": ["fitted age spline", "fitted scaling transform"],
        },
        "feature_defaults": defaults,
        "library_versions": _library_versions(),
        "numerical_environment": {
            "platform": platform.platform(),
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
            "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        },
        "training_command": f"PYTHONHASHSEED=0 python -m ml.train_model --features {args.features}",
    }

    contribution = {
        "method": "stratified_psu_bootstrap",
        "replicates": args.bootstrap_replicates,
        "interval": "percentile_95",
        "sampled_splits": ["train", "validation"],
        "fixed_components": ["fitted age spline", "fitted scaling transform"],
        "scale": "calibrated_log_odds_difference_from_reference",
        "feature_names": feature_names,
        "groups": groups,
        "reference_profile": reference,
        "point_coefficients": point_coefficients,
        "bootstrap_coefficients": bootstrap_coefficients,
        "point_calibration_slope": calibration_slope,
        "bootstrap_calibration_slopes": bootstrap_slopes,
    }

    # The full evaluation report keeps the exact host platform for audit.
    # The runtime bundle omits that volatile kernel string while retaining
    # the pinned Python patch, OS family and dependency-lock digest, so an
    # identical rebuild has an identical runtime identity.
    runtime_metrics = {
        **metrics,
        "numerical_environment": {
            key: value for key, value in metrics["numerical_environment"].items() if key != "platform"
        },
    }

    bundle = {
        "model": final,
        "model_type": "logistic",
        "feature_columns": list(RUNTIME_MODEL_FEATURES),
        "model_input_columns": input_columns,
        "feature_defaults": defaults,
        "effects": effects,
        "calibration": {
            "method": "platt_logit",
            "slope": calibration_slope,
            "intercept": calibration_intercept,
        },
        "contribution": contribution,
        "label_order": [str(label) for label in final.classes_],
        "metrics": runtime_metrics,
        "build_environment": metrics["build_environment"],
        "data_source": "Kenya STEPS NCD Risk Factor Survey 2015",
        "raw_data_sha256": raw_digest,
        "training_data_sha256": training_data_sha256,
        "split_lock_sha256": _sha256(SPLIT_LOCK_PATH),
        "training_command": f"PYTHONHASHSEED=0 python -m ml.train_model --features {args.features}",
        "pipeline": "ml/steps_pipeline.py",
        "version": model_version,
    }

    model_path = model_dir / model_filename
    staged_model_path = model_path.with_name(f"{model_path.name}.tmp")
    staged_model_path.unlink(missing_ok=True)
    joblib.dump(bundle, staged_model_path, compress=3)
    digest = hashlib.sha256(staged_model_path.read_bytes()).hexdigest()

    # The runtime accepts one versioned digest. Stage the rebuild first and
    # refuse to publish a current-model artefact that does not match that
    # contract; an intentional new model must update model_contract.py first.
    expected_digest = RUNTIME_MODEL_SHA256 if args.features == "current" else None
    if expected_digest and not expected_digest.startswith("PENDING_") and digest != expected_digest:
        staged_model_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"rebuilt model SHA-256 is {digest}, expected {expected_digest}; "
            "update backend/ml/model_contract.py only for an intentional versioned change"
        )

    with open(artifact_dir / "metrics.json", "w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2, sort_keys=True, allow_nan=False)
        file.write("\n")
    with open(artifact_dir / "classification_report.txt", "w", encoding="utf-8") as file:
        file.write(f"Kenya STEPS 2015, weighted model rows={len(df)}, features={list(RUNTIME_MODEL_FEATURES)}\n\n")
        file.write(f"Selected C: {best_c}\n")
        file.write(
            f"Locked weighted test: AUROC {weighted_test['auroc']:.4f}, "
            f"PR-AUC {weighted_test['pr_auc']:.4f}, Brier {weighted_test['brier']:.4f}\n"
        )
        file.write(
            f"Calibration slope {weighted_test['calibration_slope']:.4f}, "
            f"intercept {weighted_test['calibration_intercept']:.4f}\n\n"
        )
        for name, result in subgroups.items():
            if result["metrics"]:
                file.write(
                    f"{name:12s} n={result['n']:3d} AUROC {result['metrics']['auroc']:.4f} "
                    f"PR-AUC {result['metrics']['pr_auc']:.4f} Brier {result['metrics']['brier']:.4f}\n"
                )

    _save_charts(
        effects,
        calibrated_test,
        test_df["y"].to_numpy(),
        test_weights,
        artifact_dir,
        calibration_edges=validation_curve_edges,
    )

    checksum_path = model_dir / checksum_filename
    staged_checksum_path = checksum_path.with_name(f"{checksum_path.name}.tmp")
    staged_checksum_path.write_text(f"{digest}  {model_filename}\n", encoding="utf-8")
    # Both publication files are prepared before either replaces its live
    # counterpart, so a staging failure cannot publish a model without its
    # matching checksum.
    os.replace(staged_model_path, model_path)
    os.replace(staged_checksum_path, checksum_path)
    print(f"\nSaved model   -> {model_path}")
    print(f"SHA-256       -> {digest}")
    print(f"Training data -> {training_data_sha256}")
    print(f"Saved reports -> {artifact_dir}/ (metrics.json and charts)")


if __name__ == "__main__":
    main()
