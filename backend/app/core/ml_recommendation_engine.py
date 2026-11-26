"""
ML-based recommendation engine, trained on real Kenya STEPS 2015 NCD risk
factor survey data (see ml/steps_pipeline.py and ml/train_model.py).

DESIGN NOTES (worth restating in the project report)
------------------------------------------------------
1. The trained model predicts AT-RISK vs NOT-AT-RISK from age, sex and five
   lifestyle features. Age and sex are included because they matter most for
   accuracy, but they are NEVER surfaced as recommendations since a patient
   cannot act on them. Only the five modifiable lifestyle features are
   considered for advice (see app/core/lifestyle_factors.py).

2. STEPS does not measure sleep, caffeine, or perceived stress, so these
   three HyperSync-collected factors are NOT part of the trained model.
   They are handled separately as plainly-labelled threshold rules below,
   clearly distinguished from the model-derived recommendations in the
   API response's "source" field ("model" for survey-supported lifestyle guidance, "population_model" for the survey estimate, and "rule" or "system" for the other guidance).

3. Medication adherence is retained for clinician-only treatment review, not
   patient recommendations, and is not a trained feature. STEPS only asks about
   antihypertensive medication of respondents already diagnosed with
   hypertension (~11% of the sample), so training on it would either gut the
   dataset or leak diagnosis status into the model.

4. Which habits to mention is decided in factor_insights (see its docstring), which
   builds on lifestyle_factors.rank_factors for the five survey-covered ones:
   a factor is only considered when the PATIENT'S OWN logged value points the
   unhealthy way. Factors whose adjusted effect interval supports the harmful
   direction are listed first and say so; the rest are worded as general
   clinical guidance and ordered by guideline priority. The model's built-in
   feature importance is deliberately NOT used: it overstated physical
   activity (second only to age) when held-out data showed almost no effect.
   See ml/README.md.

5. The model itself never sees the patient's actual BP readings — it
   can't: STEPS is a one-time cross-sectional survey with a mean of the second
   and third measurements per respondent, so there's no reading *history* in
   the training data to learn a relationship from. Rather than fabricate one
   by blending the model's lifestyle-based probability with an invented
   "reading risk score" (which would mix two incomparable scales and
   imply a rigor that isn't there), the patient's own reading history is
   used directly and separately: source="readings" below reports their
   actual average, the direction of change versus the prior period, and
   how many logged days were elevated/high — computed straight from
   their BPReading rows, with no model involved. It's shown alongside,
   not blended into, the model's lifestyle-based estimate.

6. Low or very-high readings in the current recommendation window use safety
   wording only. They never receive a population estimate or lifestyle advice.
"""

import hashlib
import io
import logging
import math
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path
from threading import Lock

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

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
from app.core.factor_insights import build_advice, coverage_message
from app.core.localtime import local_day, resolve_timezone
from app.core.reading_window import ReadingWindow
from app.core.safety_messages import LOW_SAFETY_GUIDANCE, VERY_HIGH_SAFETY_GUIDANCE
from app.core.trend_analysis import compute_trend, summarize_readings
from app.models.environmental_factor import EnvironmentalFactor
from app.models.reading import BPReading
from app.models.user import PatientProfile
from ml.model_contract import (
    MODEL_ACTIVITY_MAX_MINUTES,
    MODEL_AGE_RANGE,
    MODEL_ESTIMATE_AGE_RANGE,
    MODEL_FILENAMES,
    MODEL_SALT_SCORE_RANGE,
    RUNTIME_MODEL_BOOTSTRAP_REPLICATES,
    RUNTIME_MODEL_BUILD_PLATFORM,
    RUNTIME_MODEL_BUILD_PYTHON,
    RUNTIME_MODEL_EFFECT_UNITS,
    RUNTIME_MODEL_EXPLANATION_FEATURES,
    RUNTIME_MODEL_FEATURES,
    RUNTIME_MODEL_INPUT_FEATURES,
    RUNTIME_MODEL_LABELS,
    RUNTIME_MODEL_RAW_SHA256,
    RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256,
    RUNTIME_MODEL_SHA256,
    RUNTIME_MODEL_SPLIT_SHA256,
    RUNTIME_MODEL_TRAINING_DATA_SHA256,
    RUNTIME_MODEL_VERSION,
)

# A systolic swing smaller than this between periods reads as noise, not
# a real trend, so it's reported as "holding steady" rather than up/down.
DIRECTION_NOISE_THRESHOLD_MMHG = 3

logger = logging.getLogger(__name__)


def _readings_noun(count: int) -> str:
    return "reading" if count == 1 else "readings"


_MODEL_DIR = Path(__file__).resolve().parents[2] / "ml" / "models"
_MODEL_PATH = _MODEL_DIR / MODEL_FILENAMES["current"]
_bundle = None
_model_load_attempted = False
_model_load_lock = Lock()


def _validate_model_file(path) -> bytes:
    """Verify and return the exact artefact bytes that may be unpickled."""
    payload = Path(path).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != RUNTIME_MODEL_SHA256:
        raise ValueError(f"model artifact SHA-256 is {digest}, expected {RUNTIME_MODEL_SHA256}")
    return payload


def _expected_contribution_groups(feature_names: list[str]) -> dict[str, list[int]]:
    """Map each semantic model input to its transformed design columns."""
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
    return groups


def _validate_model_bundle(bundle) -> None:
    """Raise ValueError when an artefact cannot satisfy the runtime contract.

    The file digest is checked before unpickling. These checks then make the
    unpacked bundle's identity, features, input domains, labels, thresholds,
    calibration and contribution-uncertainty metadata explicit. A malformed
    bundle fails closed: it never reaches the patient-facing recommendation
    path.
    """
    if not isinstance(bundle, dict):
        raise ValueError("model bundle must be a dictionary")
    if bundle.get("version") != RUNTIME_MODEL_VERSION:
        raise ValueError(f"model bundle version must be {RUNTIME_MODEL_VERSION}")
    if bundle.get("model_type") != "logistic":
        raise ValueError("model bundle type must be logistic")

    model = bundle.get("model")
    if model is None or not callable(getattr(model, "predict_proba", None)):
        raise ValueError("model bundle has no usable predict_proba model")

    feature_columns = bundle.get("feature_columns")
    if feature_columns != list(RUNTIME_MODEL_FEATURES):
        raise ValueError(f"model bundle features must be {list(RUNTIME_MODEL_FEATURES)}")
    input_columns = bundle.get("model_input_columns")
    if input_columns != list(RUNTIME_MODEL_INPUT_FEATURES):
        raise ValueError(f"model bundle model inputs must be {list(RUNTIME_MODEL_INPUT_FEATURES)}")
    model_features = getattr(model, "feature_names_in_", None)
    if model_features is not None and list(model_features) != list(RUNTIME_MODEL_INPUT_FEATURES):
        raise ValueError("model bundle estimator features do not match the published input contract")

    defaults = bundle.get("feature_defaults")
    if not isinstance(defaults, dict) or set(defaults) != set(RUNTIME_MODEL_FEATURES):
        raise ValueError("model bundle must contain training defaults for exactly the published features")
    for column, value in defaults.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"model bundle has an invalid training default for {column}")

    minimum_age, maximum_age = MODEL_AGE_RANGE
    minimum_activity = 0
    maximum_activity = MODEL_ACTIVITY_MAX_MINUTES
    minimum_salt, maximum_salt = MODEL_SALT_SCORE_RANGE
    default_domains = {
        "age": (minimum_age, maximum_age),
        "sex": (0, 1),
        "smoked": (0, 1),
        "alcohol_consumed": (0, 1),
        "salt_score": (minimum_salt, maximum_salt),
        "activity_minutes": (minimum_activity, maximum_activity),
        "diet_adherence": (0, 1),
    }
    for column, (minimum, maximum) in default_domains.items():
        if not minimum <= defaults[column] <= maximum:
            raise ValueError(f"model bundle has an out-of-domain training default for {column}")

    classes = list(getattr(model, "classes_", []))
    if classes != list(RUNTIME_MODEL_LABELS):
        raise ValueError(f"model bundle classes must be {list(RUNTIME_MODEL_LABELS)}")
    if bundle.get("label_order") != classes:
        raise ValueError("model bundle label order does not match its model classes")

    metrics = bundle.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("model bundle metrics must be a dictionary")
    if metrics.get("model_version") != RUNTIME_MODEL_VERSION:
        raise ValueError("model bundle metrics version does not match the runtime contract")
    if metrics.get("feature_set") != "current":
        raise ValueError("model bundle metrics feature set does not match the runtime contract")
    if metrics.get("features") != list(RUNTIME_MODEL_FEATURES):
        raise ValueError("model bundle metrics features do not match the runtime contract")
    if metrics.get("model_input_features") != list(RUNTIME_MODEL_INPUT_FEATURES):
        raise ValueError("model bundle metrics model inputs do not match the runtime contract")
    if metrics.get("runtime_estimate_age_range") != list(MODEL_ESTIMATE_AGE_RANGE):
        raise ValueError("model bundle metrics estimate age range do not match the runtime contract")

    expected_build_environment = {
        "python": RUNTIME_MODEL_BUILD_PYTHON,
        "platform": RUNTIME_MODEL_BUILD_PLATFORM,
        "requirements_lock_sha256": RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256,
    }
    if bundle.get("build_environment") != expected_build_environment:
        raise ValueError("model bundle build environment does not match the runtime contract")
    if metrics.get("build_environment") != expected_build_environment:
        raise ValueError("model bundle metrics build environment do not match the runtime contract")
    numerical_environment = metrics.get("numerical_environment")
    expected_numerical_environment = {
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "PYTHONHASHSEED": "0",
    }
    if numerical_environment != expected_numerical_environment:
        raise ValueError("model bundle numerical environment does not match the runtime contract")

    expected_thresholds = {
        "low_systolic": LOW_SYSTOLIC,
        "low_diastolic": LOW_DIASTOLIC,
        "high_systolic": HIGH_SYSTOLIC,
        "high_diastolic": HIGH_DIASTOLIC,
        "very_high_systolic": VERY_HIGH_SYSTOLIC,
        "very_high_diastolic": VERY_HIGH_DIASTOLIC,
        "elevated_systolic": ELEVATED_SYSTOLIC,
        "elevated_diastolic": ELEVATED_DIASTOLIC,
    }
    if metrics.get("classification_thresholds") != expected_thresholds:
        raise ValueError("model bundle classification thresholds do not match the application contract")

    calibration = bundle.get("calibration")
    if not isinstance(calibration, dict) or calibration.get("method") != "platt_logit":
        raise ValueError("model bundle must contain the published Platt calibration")
    slope = calibration.get("slope")
    intercept = calibration.get("intercept")
    if (
        not isinstance(slope, (int, float))
        or isinstance(slope, bool)
        or not math.isfinite(slope)
        or slope <= 0
        or not isinstance(intercept, (int, float))
        or isinstance(intercept, bool)
        or not math.isfinite(intercept)
    ):
        raise ValueError("model bundle calibration parameters are invalid")
    metrics_calibration = metrics.get("calibration")
    if not isinstance(metrics_calibration, dict):
        raise ValueError("model bundle metrics calibration is missing")
    expected_bin_definition = "10 equal-count bins frozen from locked validation calibrated probabilities"
    if metrics_calibration.get("bin_definition") != expected_bin_definition:
        raise ValueError("model bundle calibration bin definition does not match the runtime contract")
    metrics_slope = metrics_calibration.get("slope")
    metrics_intercept = metrics_calibration.get("intercept")
    if (
        not isinstance(metrics_slope, (int, float))
        or isinstance(metrics_slope, bool)
        or not math.isfinite(metrics_slope)
        or not isinstance(metrics_intercept, (int, float))
        or isinstance(metrics_intercept, bool)
        or not math.isfinite(metrics_intercept)
    ):
        raise ValueError("model bundle published calibration metrics are invalid")
    if not math.isclose(metrics_slope, slope, rel_tol=1e-12, abs_tol=1e-12) or not math.isclose(
        metrics_intercept, intercept, rel_tol=1e-12, abs_tol=1e-12
    ):
        raise ValueError("model bundle runtime calibration does not match the published metrics")
    frozen_edges = metrics_calibration.get("frozen_validation_bin_edges")
    if (
        not isinstance(frozen_edges, list)
        or len(frozen_edges) != 11
        or any(
            not isinstance(edge, (int, float)) or isinstance(edge, bool) or not math.isfinite(edge)
            for edge in frozen_edges
        )
        or any(left >= right for left, right in zip(frozen_edges, frozen_edges[1:], strict=False))
        or frozen_edges[0] < 0
        or frozen_edges[-1] > 1
    ):
        raise ValueError("model bundle must contain eleven ordered frozen validation calibration edges")
    test_metrics = metrics.get("test")
    weighted_test_metrics = test_metrics.get("weighted") if isinstance(test_metrics, dict) else None
    headline_ece = (
        weighted_test_metrics.get("expected_calibration_error") if isinstance(weighted_test_metrics, dict) else None
    )
    curve_ece = metrics_calibration.get("test_expected_calibration_error")
    if (
        not isinstance(headline_ece, (int, float))
        or isinstance(headline_ece, bool)
        or not math.isfinite(headline_ece)
        or not isinstance(curve_ece, (int, float))
        or isinstance(curve_ece, bool)
        or not math.isfinite(curve_ece)
        or not math.isclose(headline_ece, curve_ece, rel_tol=1e-12, abs_tol=1e-12)
    ):
        raise ValueError("model bundle calibration curve and headline ECE do not agree")

    named_steps = getattr(model, "named_steps", None)
    if not isinstance(named_steps, dict):
        raise ValueError("model bundle model does not expose its fitted pipeline steps")
    preprocessor = named_steps.get("preprocess")
    classifier = named_steps.get("classifier")
    if preprocessor is None or classifier is None:
        raise ValueError("model bundle model does not expose the fitted preprocessor and classifier")
    try:
        fitted_feature_names = list(preprocessor.get_feature_names_out())
    except Exception as exc:
        raise ValueError("model bundle fitted feature names cannot be verified") from exc

    contribution = bundle.get("contribution")
    if not isinstance(contribution, dict) or contribution.get("method") != "stratified_psu_bootstrap":
        raise ValueError("model bundle must contain PSU-bootstrap contribution metadata")
    if contribution.get("sampled_splits") != ["train", "validation"]:
        raise ValueError("model bundle contribution bootstrap must sample both training and validation PSUs")
    if contribution.get("fixed_components") != ["fitted age spline", "fitted scaling transform"]:
        raise ValueError("model bundle contribution bootstrap fixed-component contract is invalid")
    replicates = contribution.get("replicates")
    if replicates != RUNTIME_MODEL_BOOTSTRAP_REPLICATES:
        raise ValueError("model bundle contribution bootstrap replicate count does not match the runtime contract")
    feature_names = contribution.get("feature_names")
    if (
        not isinstance(feature_names, list)
        or not feature_names
        or len(set(feature_names)) != len(feature_names)
        or not all(isinstance(name, str) for name in feature_names)
    ):
        raise ValueError("model bundle contribution feature names are invalid")
    if feature_names != fitted_feature_names:
        raise ValueError("model bundle contribution feature names do not match the fitted preprocessor")
    groups = contribution.get("groups")
    if not isinstance(groups, dict) or set(groups) != set(RUNTIME_MODEL_FEATURES):
        raise ValueError("model bundle contribution groups do not match the feature contract")
    covered = []
    for feature, indices in groups.items():
        if (
            not isinstance(indices, list)
            or not indices
            or not all(isinstance(index, int) and not isinstance(index, bool) for index in indices)
            or any(index < 0 or index >= len(feature_names) for index in indices)
        ):
            raise ValueError(f"model bundle contribution group is invalid for {feature}")
        covered.extend(indices)
    if sorted(covered) != list(range(len(feature_names))):
        raise ValueError("model bundle contribution groups do not cover transformed features exactly once")
    expected_groups = _expected_contribution_groups(feature_names)
    if groups != expected_groups:
        raise ValueError("model bundle contribution groups do not match the fitted feature semantics")

    point_coefficients = np.asarray(contribution.get("point_coefficients"), dtype=float)
    bootstrap_coefficients = np.asarray(contribution.get("bootstrap_coefficients"), dtype=float)
    bootstrap_slopes = np.asarray(contribution.get("bootstrap_calibration_slopes"), dtype=float)
    if point_coefficients.shape != (len(feature_names),) or not np.isfinite(point_coefficients).all():
        raise ValueError("model bundle point contribution coefficients are invalid")
    if (
        bootstrap_coefficients.shape != (replicates, len(feature_names))
        or not np.isfinite(bootstrap_coefficients).all()
    ):
        raise ValueError("model bundle bootstrap contribution coefficients are invalid")
    if (
        bootstrap_slopes.shape != (replicates,)
        or not np.isfinite(bootstrap_slopes).all()
        or np.any(bootstrap_slopes <= 0)
    ):
        raise ValueError("model bundle bootstrap calibration slopes are invalid")
    classifier_classes = list(getattr(classifier, "classes_", []))
    classifier_coefficients = np.asarray(getattr(classifier, "coef_", []), dtype=float)
    if (
        classifier_classes != list(RUNTIME_MODEL_LABELS)
        or classifier_coefficients.shape != (1, len(feature_names))
        or not np.isfinite(classifier_coefficients).all()
    ):
        raise ValueError("model bundle fitted classifier coefficients are invalid")
    fitted_at_risk_coefficients = (
        classifier_coefficients[0] if classifier_classes.index("at_risk") == 1 else -classifier_coefficients[0]
    )
    if not np.allclose(point_coefficients, fitted_at_risk_coefficients, rtol=1e-9, atol=1e-12):
        raise ValueError("model bundle contribution coefficients do not match the fitted classifier")
    if not np.any(np.abs(bootstrap_coefficients) > 1e-12) or not np.any(np.std(bootstrap_coefficients, axis=0) > 1e-12):
        raise ValueError("model bundle bootstrap contribution coefficients contain no model variation")
    if not np.any(np.std(bootstrap_slopes) > 1e-12):
        raise ValueError("model bundle bootstrap calibration slopes contain no model variation")
    if not math.isclose(float(contribution.get("point_calibration_slope")), float(slope), rel_tol=1e-9):
        raise ValueError("model bundle point and published calibration slopes do not agree")

    reference = contribution.get("reference_profile")
    if not isinstance(reference, dict) or set(reference) != set(RUNTIME_MODEL_INPUT_FEATURES):
        raise ValueError("model bundle contribution reference profile does not match the input contract")
    for feature in RUNTIME_MODEL_FEATURES:
        if not math.isclose(float(reference[feature]), float(defaults[feature]), rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(f"model bundle contribution reference differs from the training default for {feature}")
    for feature in RUNTIME_MODEL_INPUT_FEATURES:
        if feature.endswith("_missing") and reference[feature] != 0:
            raise ValueError("model bundle contribution reference must contain complete inputs")

    effects = bundle.get("effects")
    if not isinstance(effects, dict) or set(effects) != set(RUNTIME_MODEL_FEATURES):
        raise ValueError("model bundle must contain effect metadata for exactly the published features")
    effect_fields = {"odds_ratio", "ci_low", "ci_high", "unit"}
    for name, effect in effects.items():
        if not isinstance(effect, dict) or set(effect) != effect_fields:
            raise ValueError(f"model bundle has incomplete effect metadata for {name}")
        if not all(
            isinstance(effect[key], (int, float))
            and not isinstance(effect[key], bool)
            and math.isfinite(effect[key])
            and effect[key] > 0
            for key in ("odds_ratio", "ci_low", "ci_high")
        ):
            raise ValueError(f"model bundle has invalid effect metadata for {name}")
        if not effect["ci_low"] <= effect["odds_ratio"] <= effect["ci_high"]:
            raise ValueError(f"model bundle effect interval does not contain its estimate for {name}")
        if effect["unit"] != RUNTIME_MODEL_EFFECT_UNITS[name]:
            raise ValueError(f"model bundle effect unit does not match the runtime contract for {name}")
    if metrics.get("effects") != effects:
        raise ValueError("model bundle metrics effects do not match its effect metadata")

    expected_hashes = {
        "raw_data_sha256": RUNTIME_MODEL_RAW_SHA256,
        "split_lock_sha256": RUNTIME_MODEL_SPLIT_SHA256,
        "training_data_sha256": RUNTIME_MODEL_TRAINING_DATA_SHA256,
    }
    for field, expected in expected_hashes.items():
        if not expected.startswith("PENDING_") and bundle.get(field) != expected:
            raise ValueError(f"model bundle {field} does not match the published contract")
        if metrics.get(field) != bundle.get(field):
            raise ValueError(f"model bundle metrics {field} do not match the bundle")
    published_contribution = metrics.get("contribution_uncertainty")
    expected_contribution_metadata = {
        "method": "stratified PSU bootstrap of training fits and validation calibration",
        "replicates": replicates,
        "interval": "percentile 95% interval",
        "scale": "calibrated log-odds difference from the weighted training reference profile",
        "sampled_splits": ["train", "validation"],
        "fixed_components": ["fitted age spline", "fitted scaling transform"],
    }
    if published_contribution != expected_contribution_metadata:
        raise ValueError("model bundle metrics contribution metadata do not match the runtime contract")


def _load_model():
    """Load the versioned model bundle, or return None if it is unavailable.

    The model supplies population context; it is not required for the patient's
    own readings, lifestyle rules or measurement guidance. A missing, corrupt or
    incompatible artifact must therefore degrade the estimate, not turn the
    recommendation endpoint into a 500. The lock prevents one concurrent
    request from seeing a temporary "not attempted yet" state while another is
    still validating the artefact.
    """
    global _bundle, _model_load_attempted
    if _bundle is not None:
        return _bundle

    with _model_load_lock:
        if _bundle is not None:
            return _bundle
        if _model_load_attempted:
            return None
        _model_load_attempted = True

        if not Path(_MODEL_PATH).exists():
            logger.warning("BP status model not found at %s; continuing without the population estimate", _MODEL_PATH)
            return None

        try:
            # Hash and unpickle the same in-memory bytes. Reading the path
            # again after hashing would leave a time-of-check/time-of-use gap.
            payload = _validate_model_file(_MODEL_PATH)
            loaded = joblib.load(io.BytesIO(payload))
            _validate_model_bundle(loaded)
        except Exception as exc:
            logger.warning(
                "BP status model at %s could not be loaded or does not match the runtime contract (%s); "
                "continuing without the population estimate",
                _MODEL_PATH,
                exc,
            )
            return None

        _bundle = loaded
        return _bundle


def preload_model() -> None:
    """Load and validate the optional model bundle outside the request path.

    Application startup calls this so the first recommendation request does
    not pay the one-time joblib validation cost. Loading remains best-effort:
    a missing or invalid artefact is logged and the deterministic
    recommendation path continues without the population estimate.
    """
    _load_model()


def _model_frame(bundle: dict, row: dict) -> pd.DataFrame:
    """Build the exact model input frame, including missingness indicators."""
    columns = bundle.get("model_input_columns", bundle.get("feature_columns", []))
    defaults = bundle.get("feature_defaults", {})
    values = {
        column: row.get(column, defaults.get(column, 0 if column.endswith("_missing") else np.nan))
        for column in columns
    }
    return pd.DataFrame([values], columns=columns)


def _calibrated_probability(bundle: dict, base_probability: float) -> float:
    clipped = min(max(float(base_probability), 1e-6), 1 - 1e-6)
    calibration = bundle["calibration"]
    calibrated_logit = calibration["slope"] * math.log(clipped / (1 - clipped)) + calibration["intercept"]
    return float(1 / (1 + math.exp(-calibrated_logit)))


def _prediction_contributions(bundle: dict, frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Per-prediction log-odds contributions with PSU-bootstrap intervals.

    Each contribution is the calibrated log-odds difference from the weighted
    training reference profile. The interval reflects model-fitting and
    validation-calibration-slope variation in the PSU bootstrap; it is not a
    causal interval or a complete predictive interval.
    """
    contribution = bundle["contribution"]
    model = bundle["model"]
    preprocessor = model.named_steps.get("preprocess")
    classifier = model.named_steps.get("classifier")
    if preprocessor is None or classifier is None:
        raise ValueError("model pipeline does not expose contribution components")

    row = preprocessor.transform(frame)[0]
    reference = contribution["reference_profile"]
    reference_frame = pd.DataFrame([reference], columns=bundle["model_input_columns"])
    reference_row = preprocessor.transform(reference_frame)[0]
    delta = row - reference_row

    point_coefficients = np.asarray(contribution["point_coefficients"], dtype=float)
    bootstrap_coefficients = np.asarray(contribution["bootstrap_coefficients"], dtype=float)
    bootstrap_slopes = np.asarray(contribution["bootstrap_calibration_slopes"], dtype=float)
    point_slope = float(contribution["point_calibration_slope"])

    result = {}
    input_values = frame.iloc[0]
    for feature in RUNTIME_MODEL_EXPLANATION_FEATURES:
        indices = contribution["groups"][feature]
        feature_delta = delta[indices]
        point = point_slope * float(np.dot(feature_delta, point_coefficients[indices]))
        draws = bootstrap_slopes * (bootstrap_coefficients[:, indices] @ feature_delta)
        low, high = np.quantile(draws, [0.025, 0.975])
        result[feature] = {
            "point": float(point),
            "ci_low": float(low),
            "ci_high": float(high),
            "missing": bool(input_values[f"{feature}_missing"]),
        }
    return result


def _predict_with_explanation(bundle: dict, row: dict) -> dict | None:
    """Return calibrated probability and honest per-prediction contributions."""
    try:
        frame = _model_frame(bundle, row)
        probabilities = bundle["model"].predict_proba(frame)[0]
        at_risk_index = list(bundle["model"].classes_).index("at_risk")
        base_probability = float(probabilities[at_risk_index])
        probability = _calibrated_probability(bundle, base_probability)
        if not 0 <= probability <= 1:
            return None
        return {
            "probability": probability,
            "contributions": _prediction_contributions(bundle, frame),
        }
    except Exception as exc:
        logger.warning("BP status model prediction failed (%s); continuing without the population estimate", exc)
        return None


def _predict_at_risk_probability(bundle: dict, row: dict) -> float | None:
    """Return the calibrated at-risk probability, or None if prediction fails."""
    result = _predict_with_explanation(bundle, row)
    return result["probability"] if result is not None else None


# How many pieces of lifestyle advice to show alongside the blood-pressure summary.
MAX_ADVICE_ELEVATED = 5
MAX_ADVICE_CONTROLLED = 3  # preventive: keep it short when readings are already fine

# How far back to look when comparing the patient's habits with their own readings.
PATTERN_LOOKBACK_DAYS = 30
SALT_SCORE_MAP = {"none": 0, "low": 1, "moderate": 2, "high": 3}


def _age_in_years(born: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _enum_val(v):
    return v.value if hasattr(v, "value") else v


def _lifestyle_value(recent, name: str):
    """Read one lifestyle value from a snapshot or a model-like object."""
    if recent is None:
        return None
    if isinstance(recent, dict):
        return recent.get(name)
    return getattr(recent, name, None)


def _latest_lifestyle_values(entries) -> dict:
    """Use the newest available answer for each lifestyle field independently.

    A partial check-in must not erase an answer to a different question that
    the patient supplied on an earlier day in the same window. The entries are
    ordered newest-first, and each field keeps its own most recent non-null
    value.
    """
    values = {
        "smoked": None,
        "alcohol_consumed": None,
        "salt_intake": None,
        "physical_activity_minutes": None,
        "diet_adherence": None,
    }
    for entry in entries:
        for name in values:
            if values[name] is None:
                value = getattr(entry, name, None)
                if value is not None:
                    values[name] = value
    return values


def _build_model_features(recent, age: int, sex: int, defaults: dict) -> dict:
    """Map app inputs onto the v4 model space with explicit missingness flags.

    Missing lifestyle answers use the survey-weighted training default stored
    in the versioned model bundle. The corresponding indicator remains set so
    the model and its contribution intervals can account for the gap.
    """
    salt_value = _enum_val(_lifestyle_value(recent, "salt_intake"))
    salt_known = salt_value in SALT_SCORE_MAP
    salt = SALT_SCORE_MAP.get(salt_value, defaults.get("salt_score", 1))
    smoked = _lifestyle_value(recent, "smoked")
    alcohol = _lifestyle_value(recent, "alcohol_consumed")
    activity = _lifestyle_value(recent, "physical_activity_minutes")
    diet = _lifestyle_value(recent, "diet_adherence")
    smoked_known = smoked is not None
    alcohol_known = alcohol is not None
    activity_known = activity is not None
    diet_known = diet is not None

    features = {
        "age": age,
        "sex": sex,
        "smoked": int(smoked) if smoked_known else int(defaults.get("smoked", 0)),
        "alcohol_consumed": int(alcohol) if alcohol_known else int(defaults.get("alcohol_consumed", 0)),
        "salt_score": salt,
        "activity_minutes": max(0, min(activity, MODEL_ACTIVITY_MAX_MINUTES))
        if activity_known
        else defaults.get("activity_minutes", 0),
        "diet_adherence": int(diet) if diet_known else int(defaults.get("diet_adherence", 0)),
        "age_missing": 0,
        "sex_missing": 0,
        "smoked_missing": int(not smoked_known),
        "alcohol_consumed_missing": int(not alcohol_known),
        "salt_score_missing": int(not salt_known),
        "activity_minutes_missing": int(not activity_known),
        "diet_adherence_missing": int(not diet_known),
    }
    return features


MISSING_INPUT_LABELS = {
    "age": "age",
    "sex": "sex",
    "smoked": "smoking status",
    "alcohol_consumed": "alcohol use",
    "salt_intake": "salt intake",
    "physical_activity_minutes": "physical activity",
    "diet_adherence": "diet",
}


def _missing_model_inputs(profile, recent) -> list[str]:
    """Which model inputs are absent rather than genuinely supplied.

    Missing values are filled with training-population defaults for prediction,
    but the patient-facing estimate must say when that happened. In particular,
    an unspecified sex must never be described as the patient's own sex.
    """
    missing = []
    if profile is None or profile.date_of_birth is None:
        missing.append("age")
    if profile is None or profile.sex is None or _enum_val(profile.sex) == "Other":
        missing.append("sex")

    lifestyle_values = {
        "smoked": _lifestyle_value(recent, "smoked"),
        "alcohol_consumed": _lifestyle_value(recent, "alcohol_consumed"),
        "salt_intake": _lifestyle_value(recent, "salt_intake"),
        "physical_activity_minutes": _lifestyle_value(recent, "physical_activity_minutes"),
        "diet_adherence": _lifestyle_value(recent, "diet_adherence"),
    }
    missing.extend(name for name, value in lifestyle_values.items() if value is None)
    return missing


def _missing_input_phrase(missing_inputs: list[str]) -> str:
    """Patient-readable names for the fields that use population defaults."""
    labels = [MISSING_INPUT_LABELS[name] for name in missing_inputs if name in MISSING_INPUT_LABELS]
    if not labels:
        return ""
    if len(labels) == 1:
        joined = labels[0]
    elif len(labels) == 2:
        joined = f"{labels[0]} and {labels[1]}"
    else:
        joined = f"{', '.join(labels[:-1])} and {labels[-1]}"
    return f"your {joined}"


def _previous_period_average(db: Session, patient_id, period_days: int, end: datetime | None = None):
    """Average systolic/diastolic for the window immediately BEFORE the
    current one, so the current average has something real to compare
    against. Returns None rather than a zeroed average when the patient
    has no readings that far back, so callers can tell "no prior data"
    apart from "no change"."""
    now = end or datetime.now(UTC)
    window_end = now - timedelta(days=period_days)
    window_start = now - timedelta(days=period_days * 2)
    readings = (
        db.query(BPReading)
        .filter(
            BPReading.patient_id == patient_id,
            BPReading.recorded_at >= window_start,
            BPReading.recorded_at < window_end,
        )
        .all()
    )
    if not readings:
        return None
    avg_sys = sum(r.systolic for r in readings) / len(readings)
    avg_dia = sum(r.diastolic for r in readings) / len(readings)
    return avg_sys, avg_dia, len(readings)


def _reading_trend_entry(
    db: Session, patient_id, trend, period_days: int, window: ReadingWindow, end: datetime | None = None
) -> dict | None:
    """A recommendation built directly from the patient's own logged BP
    readings: their real average, the direction of change against the
    prior period, and how many logged days were elevated/high. No model
    involved — see module docstring, point 5. Returns None only when
    there is nothing meaningful to say (a single reading with no prior
    period to compare against).
    """
    elevated_or_high_days = sum(1 for d in trend.daily_breakdown if d.status in ("elevated", "high"))
    total_days = len(trend.daily_breakdown)

    direction_clause = ""
    previous = _previous_period_average(db, patient_id, period_days, end)
    if previous:
        prev_sys, prev_dia, _prev_count = previous
        delta = trend.avg_systolic - prev_sys
        if delta >= DIRECTION_NOISE_THRESHOLD_MMHG:
            direction_clause = (
                f" That's up from {round(prev_sys)}/{round(prev_dia)} mmHg the period before "
                f"— systolic has risen about {round(delta)} mmHg."
            )
        elif delta <= -DIRECTION_NOISE_THRESHOLD_MMHG:
            direction_clause = (
                f" That's down from {round(prev_sys)}/{round(prev_dia)} mmHg the period before "
                f"— a drop of about {round(-delta)} mmHg."
            )
        else:
            direction_clause = (
                f" That's holding steady compared with {round(prev_sys)}/{round(prev_dia)} mmHg the period before."
            )

    day_clause = ""
    if total_days > 1:
        day_clause = f" {elevated_or_high_days} of {total_days} logged days were elevated or high."

    if not direction_clause and not day_clause:
        return None

    return {
        "message": (
            f"From your own {trend.reading_count} logged {_readings_noun(trend.reading_count)} in {window.period_label}: average "
            f"{trend.avg_systolic}/{trend.avg_diastolic} mmHg.{direction_clause}{day_clause}"
        ),
        "based_on_trend": trend.status,
        "confidence": None,
        "source": "readings",
    }


def _utc_datetime(moment: datetime) -> datetime:
    """Treat a naive database timestamp as UTC, as the rest of the app does."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _recommendation_window(
    db: Session, patient_id, period_days: int, now: datetime
) -> tuple[list[BPReading], datetime, bool]:
    """Materialise the recommendation window once for trend and safety use.

    A fresh window deliberately has no upper bound, so legacy future-timestamp
    clock skew is included. If it is empty, all history is loaded once and the
    most recent period is selected in memory. Trend summarisation and safety
    routing then use exactly the same reading objects.
    """
    cutoff = now - timedelta(days=period_days)
    fresh = (
        db.query(BPReading)
        .filter(BPReading.patient_id == patient_id, BPReading.recorded_at >= cutoff)
        .order_by(BPReading.recorded_at.asc())
        .all()
    )
    if fresh:
        return fresh, now, False
    all_readings = (
        db.query(BPReading).filter(BPReading.patient_id == patient_id).order_by(BPReading.recorded_at.asc()).all()
    )
    if not all_readings:
        return [], now, False
    latest = max(_utc_datetime(reading.recorded_at) for reading in all_readings)
    stale_cutoff = latest - timedelta(days=period_days)
    stale = [reading for reading in all_readings if stale_cutoff <= _utc_datetime(reading.recorded_at) <= latest]
    return stale, latest, True


def _is_very_high(systolic: float, diastolic: float) -> bool:
    return systolic >= VERY_HIGH_SYSTOLIC or diastolic >= VERY_HIGH_DIASTOLIC


def _is_low(systolic: float, diastolic: float) -> bool:
    return systolic < LOW_SYSTOLIC or diastolic < LOW_DIASTOLIC


CONTRIBUTION_LABELS = {
    "salt_score": "salt intake",
    "alcohol_consumed": "alcohol use",
    "activity_minutes": "physical activity",
    "diet_adherence": "diet",
    "smoked": "smoking",
}


def _contribution_explanation(contributions: dict[str, dict[str, float]]) -> str:
    """Plain-language explanation of the largest patient-specific contributions."""
    ranked = [
        item
        for item in sorted(contributions.items(), key=lambda item: abs(item[1]["point"]), reverse=True)
        if abs(item[1]["point"]) > 1e-12
    ][:2]
    if not ranked:
        return (
            "Model explanation: No single lifestyle factor moved the model score much. "
            "This explains the population estimate only, not the blood pressure reading."
        )
    sentences = []
    for feature, values in ranked:
        point = values["point"]
        low = values["ci_low"]
        high = values["ci_high"]
        direction = "up" if point >= 0 else "down"
        subject = (
            f"Missing {CONTRIBUTION_LABELS[feature]} information"
            if values.get("missing")
            else CONTRIBUTION_LABELS[feature].capitalize()
        )
        sentences.append(
            f"{subject} moved the model score {direction} by {abs(point):.2f} model points. "
            f"The model's 95% range was {low:.2f} to {high:.2f} model points."
        )
        if low <= 0 <= high:
            sentences.append("The range crosses zero, so the direction is uncertain.")
    sentences.append("These are model points, not percentage points.")
    sentences.append("These model results do not prove that changing a habit will change one person's blood pressure.")
    sentences.append("This explains the population estimate only, not the blood pressure reading.")
    return "Model explanation: " + " ".join(sentences)


def _safety_route(trend, readings) -> str | None:
    """Safety takes precedence over every model and lifestyle message."""
    if _is_very_high(trend.avg_systolic, trend.avg_diastolic) or any(
        _is_very_high(reading.systolic, reading.diastolic) for reading in readings
    ):
        return "very_high"
    if trend.status == "low" or any(_is_low(reading.systolic, reading.diastolic) for reading in readings):
        return "low"
    return None


def _safety_recommendation(kind: str, trend, window) -> dict:
    average = f"{trend.avg_systolic}/{trend.avg_diastolic} mmHg"
    if kind == "very_high":
        message = (
            f"At least one blood pressure reading {window.phrase} was very high. Your average was {average}. "
            f"{VERY_HIGH_SAFETY_GUIDANCE}"
        )
    else:
        message = (
            f"At least one blood pressure reading {window.phrase} was low. Your average was {average}. "
            f"{LOW_SAFETY_GUIDANCE}"
        )
    return {
        "message": message,
        "based_on_trend": trend.status,
        "confidence": None,
        "source": "system",
    }


def _lifestyle_advice(*, entries, readings, daily_systolic, window_start, trend_status, effects, limit):
    """Advice from the patient's lifestyle log, tied to their own readings where the data allow."""
    return [
        {**item, "based_on_trend": trend_status, "confidence": None}
        for item in build_advice(entries, daily_systolic, window_start, effects, limit, readings)
    ]


def generate_recommendations_ml(db: Session, patient_id, period_days: int = 7, tz: tzinfo = UTC) -> list[dict]:
    now = datetime.now(UTC)
    period_readings, window_end, stale = _recommendation_window(db, patient_id, period_days, now)
    trend = summarize_readings(period_readings, period_days, tz)
    window = ReadingWindow(period_days)
    if stale:
        window = ReadingWindow(
            period_days,
            stale_days=max((now - window_end).days, 0),
            first_day=trend.daily_breakdown[0].date,
            last_day=trend.daily_breakdown[-1].date,
        )

    if trend.status == "no_data":
        return [
            {
                "message": "You haven't logged any readings recently. Record your blood pressure at a consistent time each day for more reliable trends.",
                "based_on_trend": None,
                "confidence": None,
                "source": "system",
            }
        ]

    # Lifestyle log: the look-back for patterns; the period itself decides which habits are "current".
    today = local_day(window_end, tz)
    # Date-only check-ins use the same number of local calendar days as the
    # recommendation period. For a seven-day period this is today through six
    # days ago, not the eight inclusive dates produced by a raw seven-day
    # subtraction.
    window_start = today - timedelta(days=max(period_days - 1, 0))
    entries = (
        db.query(EnvironmentalFactor)
        .filter(
            EnvironmentalFactor.patient_id == patient_id,
            EnvironmentalFactor.logged_date >= today - timedelta(days=PATTERN_LOOKBACK_DAYS),
            EnvironmentalFactor.logged_date <= today,
        )
        .order_by(EnvironmentalFactor.logged_date.desc(), EnvironmentalFactor.created_at.desc())
        .all()
    )
    bundle = _load_model()
    effects = bundle.get("effects", {}) if bundle else {}

    # Daily average systolic over the look-back, in the patient's local days, to set against the log.
    daily = compute_trend(
        db, patient_id, PATTERN_LOOKBACK_DAYS, end=window_end if stale else None, tz=tz
    ).daily_breakdown
    daily_systolic = {d.date: d.avg_systolic for d in daily}
    safety_kind = _safety_route(trend, period_readings)
    if safety_kind:
        return [_safety_recommendation(safety_kind, trend, window)]

    def advice(limit, readings=()):
        return _lifestyle_advice(
            entries=entries,
            readings=readings,
            daily_systolic=daily_systolic,
            window_start=window_start,
            trend_status=trend.status,
            effects=effects,
            limit=limit,
        )

    if trend.status == "controlled":
        out = [
            {
                "message": (
                    f"Your blood pressure has been controlled {window.phrase}, "
                    f"averaging {trend.avg_systolic}/{trend.avg_diastolic} mmHg across "
                    f"{trend.reading_count} {_readings_noun(trend.reading_count)}. Keep up your current routine.{window.nudge}"
                ),
                "based_on_trend": "controlled",
                "confidence": None,
                "source": "system",
            }
        ]
        reading_entry = _reading_trend_entry(db, patient_id, trend, period_days, window, window_end)
        if reading_entry:
            out.append(reading_entry)
        # Prevention: controlled today does not mean the habits logged are harmless,
        # and hurried readings can still distort an otherwise controlled average.
        out.extend(
            advice(
                MAX_ADVICE_CONTROLLED,
                period_readings,
            )
        )
        return out

    if trend.status == "low":
        # Defensive duplicate of the earlier safety gate. Low readings never
        # receive lifestyle advice.
        return [_safety_recommendation("low", trend, window)]

    # Elevated or high: the survey-trained model gives the population context.
    in_window = [e for e in entries if e.logged_date >= window_start]
    recent = _latest_lifestyle_values(in_window)

    summary = (
        f"Your average blood pressure {window.phrase} is {trend.status} "
        f"at {trend.avg_systolic}/{trend.avg_diastolic} mmHg across {trend.reading_count} "
        f"{_readings_noun(trend.reading_count)}."
    )

    overall_risk_proba = None
    contribution_explanation = ""
    estimate_unavailable_reason = None
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == patient_id).first()
    if bundle:
        try:
            defaults = bundle.get("feature_defaults", {})
            input_columns = bundle["model_input_columns"]

            age = None
            age_missing = 1
            if profile and profile.date_of_birth:
                profile_tz = resolve_timezone(profile.timezone) if profile and profile.timezone else tz
                calculated_age = _age_in_years(profile.date_of_birth, local_day(now, profile_tz))
                minimum_age, maximum_age = MODEL_AGE_RANGE
                if minimum_age <= calculated_age <= maximum_age:
                    age = calculated_age
                    age_missing = 0
                    estimate_minimum_age, estimate_maximum_age = MODEL_ESTIMATE_AGE_RANGE
                    if not estimate_minimum_age <= calculated_age <= estimate_maximum_age:
                        # The survey includes these ages, but the locked test
                        # results for the older granular age bands were weak
                        # or reversed. Do not generalise the overall result.
                        estimate_unavailable_reason = "the locked test results were too weak for your age group"
                else:
                    # The survey universe was 18-69. Do not extrapolate a
                    # population estimate beyond that supported age range.
                    estimate_unavailable_reason = (
                        f"your profile age is outside the model's supported {minimum_age}–{maximum_age} range"
                    )

            if age is None:
                age = defaults.get("age", 35)

            profile_sex = _enum_val(profile.sex) if profile and profile.sex else None
            sex_missing = 1
            if profile_sex == "Male":
                sex = 1
                sex_missing = 0
            elif profile_sex == "Female":
                sex = 0
                sex_missing = 0
            else:
                # The binary training model has no representation for an
                # unspecified or "Other" sex. Use the weighted training default
                # and disclose the gap.
                sex = defaults.get("sex", 0)

            features = _build_model_features(recent, age, sex, defaults)
            features["age_missing"] = age_missing
            features["sex_missing"] = sex_missing
            row = {column: features.get(column, defaults.get(column)) for column in input_columns}
            if estimate_unavailable_reason is None:
                prediction = _predict_with_explanation(bundle, row)
                if prediction is not None:
                    overall_risk_proba = prediction["probability"]
                    contribution_explanation = _contribution_explanation(prediction["contributions"])
        except Exception as exc:
            logger.warning("BP status model input preparation failed (%s); continuing without the estimate", exc)
            overall_risk_proba = None
            contribution_explanation = ""
            estimate_unavailable_reason = None

    if overall_risk_proba is not None:
        caveats = ["The app uses brief versions of the survey questions, so this is only an approximate comparison."]
        if age_missing == 0:
            caveats.append("Performance was only modest for your age group, so treat this as broad context.")
        missing_inputs = _missing_model_inputs(profile, recent)
        if missing_inputs:
            population_phrase = "people with a similar survey profile"
            caveats.append(
                f"The estimate is missing {_missing_input_phrase(missing_inputs)}, so default values from "
                "the training population are used for those fields and it is not fully personalised."
            )
        else:
            population_phrase = "people with a similar age, sex and logged habits"
        activity = _lifestyle_value(recent, "physical_activity_minutes")
        if activity is not None and activity > MODEL_ACTIVITY_MAX_MINUTES:
            caveats.append(
                f"The physical activity value is capped at {MODEL_ACTIVITY_MAX_MINUTES} minutes per day for this estimate."
            )
        input_caveat = f" {' '.join(caveats)}" if caveats else ""
        explanation_clause = f" {contribution_explanation}" if contribution_explanation else ""

        out = [
            {
                "message": (
                    f"{summary} Using 2015 Kenya STEPS survey data, the model estimates that about "
                    f"{round(overall_risk_proba * 100)}% of {population_phrase} had elevated or high blood "
                    f"pressure. This is a population estimate and does not assess your blood pressure."
                    f"{input_caveat}{explanation_clause}{window.nudge}"
                ),
                "based_on_trend": trend.status,
                "confidence": round(overall_risk_proba, 3),
                "source": "population_model",
            }
        ]
    else:
        reason_clause = (
            f" A survey estimate is not shown because {estimate_unavailable_reason}."
            if estimate_unavailable_reason
            else ""
        )
        out = [
            {
                "message": f"{summary}{reason_clause}{window.nudge}",
                "based_on_trend": trend.status,
                "confidence": None,
                "source": "system",
            }
        ]

    reading_entry = _reading_trend_entry(db, patient_id, trend, period_days, window, window_end)
    if reading_entry:
        out.append(reading_entry)

    lifestyle = advice(MAX_ADVICE_ELEVATED, period_readings)
    out.extend(lifestyle)

    if not in_window:
        out.append(
            {
                "message": "Log your stress, sleep, diet, salt, alcohol, smoking, and activity on the Lifestyle page. This helps the system match your habits with your readings.",
                "based_on_trend": trend.status,
                "confidence": None,
                "source": "system",
            }
        )
    elif not [item for item in lifestyle if item.get("kind") != "measurement"]:
        out.append(
            {
                "message": (
                    "No risky pattern is visible in the lifestyle answers you have logged so far; unanswered "
                    "questions and other factors may still matter. Keep logging, and discuss the readings with "
                    "your clinician. Other health factors and measurement conditions may also matter."
                ),
                "based_on_trend": trend.status,
                "confidence": None,
                "source": "system",
            }
        )

    # Tell a sparse logger exactly what is missing for their own patterns to appear.
    coverage = coverage_message(entries, daily_systolic) if in_window else None
    if coverage:
        out.append({"message": coverage, "based_on_trend": trend.status, "confidence": None, "source": "system"})
    return out
