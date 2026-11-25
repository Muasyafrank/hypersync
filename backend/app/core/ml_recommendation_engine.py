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

3. Medication adherence is also handled as a rule, not a trained feature,
   because STEPS only asks about antihypertensive medication of
   respondents already diagnosed with hypertension (~11% of the sample) —
   training on it would have either gutted the dataset or leaked
   diagnosis status into the model.

4. Which habits to mention is decided in factor_insights (see its docstring), which
   builds on lifestyle_factors.rank_factors for the five survey-covered ones:
   a factor is only considered when the PATIENT'S OWN logged value points the
   unhealthy way. Factors whose adjusted effect in the survey data is clearly
   different from "no effect" (95% CI) are listed first and say so; the rest
   are worded as general clinical guidance and ordered by guideline priority.
   The model's built-in feature importance is deliberately NOT used: it
   overstated physical activity (second only to age) when held-out data showed
   almost no effect. See ml/README.md.

5. The model itself never sees the patient's actual BP readings — it
   can't: STEPS is a one-time cross-sectional survey with a single BP
   measurement per respondent, so there's no reading *history* in the
   training data to learn a relationship from. Rather than fabricate one
   by blending the model's lifestyle-based probability with an invented
   "reading risk score" (which would mix two incomparable scales and
   imply a rigor that isn't there), the patient's own reading history is
   used directly and separately: source="readings" below reports their
   actual average, the direction of change versus the prior period, and
   how many logged days were elevated/high — computed straight from
   their BPReading rows, with no model involved. It's shown alongside,
   not blended into, the model's lifestyle-based estimate.
"""

import hashlib
import logging
import math
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path
from threading import Lock

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.core.bp_classification import (
    ELEVATED_DIASTOLIC,
    ELEVATED_SYSTOLIC,
    HIGH_DIASTOLIC,
    HIGH_SYSTOLIC,
    LOW_DIASTOLIC,
    LOW_SYSTOLIC,
)
from app.core.factor_insights import build_advice, coverage_message
from app.core.localtime import local_day, resolve_timezone
from app.core.reading_window import ReadingWindow
from app.core.trend_analysis import compute_trend, latest_reading_time
from app.models.environmental_factor import EnvironmentalFactor
from app.models.reading import BPReading
from app.models.user import PatientProfile
from ml.model_contract import (
    MODEL_ACTIVITY_MAX_MINUTES,
    MODEL_AGE_RANGE,
    MODEL_FILENAMES,
    MODEL_SALT_SCORE_RANGE,
    RUNTIME_MODEL_EFFECT_UNITS,
    RUNTIME_MODEL_FEATURES,
    RUNTIME_MODEL_LABELS,
    RUNTIME_MODEL_SHA256,
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


def _validate_model_file(path) -> None:
    """Verify the published digest before unpickling a model artefact."""
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != RUNTIME_MODEL_SHA256:
        raise ValueError(f"model artifact SHA-256 is {digest}, expected {RUNTIME_MODEL_SHA256}")


def _validate_model_bundle(bundle) -> None:
    """Raise ValueError when an artefact cannot satisfy the runtime contract.

    The file digest is checked before unpickling. These checks then make the
    unpacked bundle's identity, features, input domains, labels, thresholds and
    effect metadata explicit. A malformed bundle fails closed: it never
    reaches the patient-facing recommendation path.
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
    model_features = getattr(model, "feature_names_in_", None)
    if model_features is not None and list(model_features) != list(RUNTIME_MODEL_FEATURES):
        raise ValueError("model bundle estimator features do not match the published feature contract")

    medians = bundle.get("feature_medians")
    if not isinstance(medians, dict) or set(medians) != set(RUNTIME_MODEL_FEATURES):
        raise ValueError("model bundle must contain training medians for exactly the published features")
    for column, value in medians.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"model bundle has an invalid training median for {column}")

    minimum_age, maximum_age = MODEL_AGE_RANGE
    minimum_activity = 0
    maximum_activity = MODEL_ACTIVITY_MAX_MINUTES
    minimum_salt, maximum_salt = MODEL_SALT_SCORE_RANGE
    median_domains = {
        "age": (minimum_age, maximum_age),
        "sex": (0, 1),
        "smoked": (0, 1),
        "alcohol_consumed": (0, 1),
        "salt_score": (minimum_salt, maximum_salt),
        "activity_minutes": (minimum_activity, maximum_activity),
        "diet_adherence": (0, 1),
    }
    for column, (minimum, maximum) in median_domains.items():
        if not minimum <= medians[column] <= maximum:
            raise ValueError(f"model bundle has an out-of-domain training median for {column}")

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

    expected_thresholds = {
        "low_systolic": LOW_SYSTOLIC,
        "low_diastolic": LOW_DIASTOLIC,
        "high_systolic": HIGH_SYSTOLIC,
        "high_diastolic": HIGH_DIASTOLIC,
        "elevated_systolic": ELEVATED_SYSTOLIC,
        "elevated_diastolic": ELEVATED_DIASTOLIC,
    }
    if metrics.get("classification_thresholds") != expected_thresholds:
        raise ValueError("model bundle classification thresholds do not match the application contract")

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
            # Check the published digest before unpickling anything.
            _validate_model_file(_MODEL_PATH)
            loaded = joblib.load(_MODEL_PATH)
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


def _predict_at_risk_probability(bundle: dict, row: dict) -> float | None:
    """Return the model's at-risk probability, or None if prediction fails."""
    try:
        feature_columns = bundle["feature_columns"]
        frame = pd.DataFrame([row], columns=feature_columns)
        probabilities = bundle["model"].predict_proba(frame)[0]
        at_risk_index = list(bundle["model"].classes_).index("at_risk")
        probability = float(probabilities[at_risk_index])
    except Exception as exc:
        logger.warning("BP status model prediction failed (%s); continuing without the population estimate", exc)
        return None
    return probability if 0 <= probability <= 1 else None


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


def _build_model_features(recent, age: int, sex: int, medians: dict) -> dict:
    """Map the app's inputs onto the model's training feature space.

    Missing lifestyle answers use the training-population median stored in
    the versioned model bundle. Keeping those defaults in one place prevents
    the API and the model card from claiming a fallback that the code does
    not actually use.
    """
    salt = SALT_SCORE_MAP.get(
        _enum_val(recent.salt_intake) if recent else None,
        medians.get("salt_score", 1),
    )
    return {
        "age": age,
        "sex": sex,
        "smoked": int(recent.smoked) if recent and recent.smoked is not None else int(medians.get("smoked", 0)),
        "alcohol_consumed": int(recent.alcohol_consumed)
        if recent and recent.alcohol_consumed is not None
        else int(medians.get("alcohol_consumed", 0)),
        "salt_score": salt,
        "activity_minutes": max(
            0,
            min(
                recent.physical_activity_minutes,
                MODEL_ACTIVITY_MAX_MINUTES,
            ),
        )
        if recent and recent.physical_activity_minutes is not None
        else medians.get("activity_minutes", 0),
        "diet_adherence": int(recent.diet_adherence)
        if recent and recent.diet_adherence is not None
        else int(medians.get("diet_adherence", 0)),
    }


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
        "smoked": getattr(recent, "smoked", None),
        "alcohol_consumed": getattr(recent, "alcohol_consumed", None),
        "salt_intake": getattr(recent, "salt_intake", None),
        "physical_activity_minutes": getattr(recent, "physical_activity_minutes", None),
        "diet_adherence": getattr(recent, "diet_adherence", None),
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


def _period_readings(db: Session, patient_id, period_days: int, window_end: datetime, stale: bool) -> list[BPReading]:
    """The readings behind the current average (same window as compute_trend)."""
    query = db.query(BPReading).filter(
        BPReading.patient_id == patient_id,
        BPReading.recorded_at >= window_end - timedelta(days=period_days),
    )
    if stale:
        query = query.filter(BPReading.recorded_at <= window_end)
    return query.all()


def _lifestyle_advice(*, entries, readings, daily_systolic, window_start, trend_status, effects, limit):
    """Advice from the patient's lifestyle log, tied to their own readings where the data allow."""
    return [
        {**item, "based_on_trend": trend_status, "confidence": None}
        for item in build_advice(entries, daily_systolic, window_start, effects, limit, readings)
    ]


def generate_recommendations_ml(db: Session, patient_id, period_days: int = 7, tz: tzinfo = UTC) -> list[dict]:
    now = datetime.now(UTC)
    trend = compute_trend(db, patient_id, period_days, tz=tz)
    window = ReadingWindow(period_days)
    window_end = now
    stale = False

    if trend.status == "no_data":
        # Nothing in the last `period_days`. Rather than pretend the patient
        # has no history, describe their most recent readings and say how old
        # they are.
        latest = latest_reading_time(db, patient_id)
        if latest is not None:
            window_end = latest
            stale = True
            trend = compute_trend(db, patient_id, period_days, end=latest, tz=tz)
            window = ReadingWindow(
                period_days,
                stale_days=max((now - latest).days, 0),
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
    window_start = today - timedelta(days=period_days)
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
                _period_readings(db, patient_id, period_days, window_end, stale),
            )
        )
        return out

    if trend.status == "low":
        out = [
            {
                "message": (
                    f"Your average blood pressure {window.phrase} is on the low side at {trend.avg_systolic}/"
                    f"{trend.avg_diastolic} mmHg across {trend.reading_count} {_readings_noun(trend.reading_count)}. If you feel "
                    f"dizzy or unwell, contact your clinician.{window.nudge}"
                ),
                "based_on_trend": "low",
                "confidence": None,
                "source": "system",
            }
        ]
        reading_entry = _reading_trend_entry(db, patient_id, trend, period_days, window, window_end)
        if reading_entry:
            out.append(reading_entry)
        # A low average does not make smoking, medication-not-taken or poor sleep
        # harmless. Keep the same concrete, actionable habit guidance used for
        # other bands.
        out.extend(advice(MAX_ADVICE_CONTROLLED, _period_readings(db, patient_id, period_days, window_end, stale)))
        return out

    # Elevated or high: the survey-trained model gives the population context.
    in_window = [e for e in entries if e.logged_date >= window_start]
    recent = in_window[0] if in_window else None

    summary = (
        f"Your average blood pressure {window.phrase} is {trend.status} "
        f"at {trend.avg_systolic}/{trend.avg_diastolic} mmHg across {trend.reading_count} "
        f"{_readings_noun(trend.reading_count)}."
    )

    overall_risk_proba = None
    estimate_unavailable_reason = None
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == patient_id).first()
    if bundle:
        try:
            feature_columns = bundle["feature_columns"]
            medians = bundle.get("feature_medians", {})

            age = None
            if profile and profile.date_of_birth:
                profile_tz = resolve_timezone(profile.timezone) if profile and profile.timezone else tz
                calculated_age = _age_in_years(profile.date_of_birth, local_day(now, profile_tz))
                minimum_age, maximum_age = MODEL_AGE_RANGE
                if minimum_age <= calculated_age <= maximum_age:
                    age = calculated_age
                else:
                    # The training population was 18–100. Do not extrapolate a
                    # population estimate beyond that supported age range.
                    estimate_unavailable_reason = (
                        "the age in your profile is outside the model's supported 18–100 range"
                    )

            if age is None:
                age = medians.get("age", 35)
            profile_sex = _enum_val(profile.sex) if profile and profile.sex else None
            if profile_sex == "Male":
                sex = 1
            elif profile_sex == "Female":
                sex = 0
            else:
                # The binary training model has no representation for an unspecified
                # or "Other" sex, so use its population median and disclose the gap.
                sex = medians.get("sex", 0)

            feat_dict = _build_model_features(recent, age, sex, medians)
            # Features the app does not collect yet (e.g. bmi in a model trained with
            # --features bmi) fall back to the training-population median.
            row = {c: feat_dict.get(c, medians.get(c)) for c in feature_columns}
            if estimate_unavailable_reason is None:
                overall_risk_proba = _predict_at_risk_probability(bundle, row)
        except Exception as exc:
            logger.warning("BP status model input preparation failed (%s); continuing without the estimate", exc)
            overall_risk_proba = None
            estimate_unavailable_reason = None

    if overall_risk_proba is not None:
        caveats = []
        missing_inputs = _missing_model_inputs(profile, recent)
        if missing_inputs:
            population_phrase = "people with a similar survey profile"
            caveats.append(
                f"The estimate is missing {_missing_input_phrase(missing_inputs)}, so default values from "
                "the training population are used for those fields and it is not fully personalised."
            )
        else:
            population_phrase = "people with a similar age, sex and logged habits"
        if (
            recent is not None
            and recent.physical_activity_minutes is not None
            and recent.physical_activity_minutes > MODEL_ACTIVITY_MAX_MINUTES
        ):
            caveats.append(
                f"The physical activity value is capped at {MODEL_ACTIVITY_MAX_MINUTES} minutes per day for this estimate."
            )
        input_caveat = f" {' '.join(caveats)}" if caveats else ""

        out = [
            {
                "message": (
                    f"{summary} In a national Kenyan health survey, about "
                    f"{round(overall_risk_proba * 100)}% of {population_phrase} had elevated or high blood "
                    f"pressure. This is a population figure, not a diagnosis.{input_caveat}{window.nudge}"
                ),
                "based_on_trend": trend.status,
                "confidence": round(overall_risk_proba, 3),
                "source": "population_model",
            }
        ]
    else:
        unavailable = f" for {estimate_unavailable_reason}" if estimate_unavailable_reason else " right now"
        out = [
            {
                "message": (
                    f"{summary} The survey-based population estimate is not available{unavailable}, so the "
                    f"advice below still uses your readings and daily log.{window.nudge}"
                ),
                "based_on_trend": trend.status,
                "confidence": None,
                "source": "system",
            }
        ]

    reading_entry = _reading_trend_entry(db, patient_id, trend, period_days, window, window_end)
    if reading_entry:
        out.append(reading_entry)

    lifestyle = advice(MAX_ADVICE_ELEVATED, _period_readings(db, patient_id, period_days, window_end, stale))
    out.extend(lifestyle)

    if not in_window:
        out.append(
            {
                "message": "Log your stress, sleep, diet, and medication on the Lifestyle page — this lets the system identify what may be driving your readings.",
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
                    "your clinician: medication, family history and how you measure at home can all contribute."
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
