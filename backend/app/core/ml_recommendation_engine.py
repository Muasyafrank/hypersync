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
   API response's "source" field ("model" vs "rule" vs "system").

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

import os
from datetime import UTC, date, datetime, timedelta, tzinfo

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.core.factor_insights import build_advice, coverage_message
from app.core.reading_window import ReadingWindow
from app.core.trend_analysis import compute_trend, latest_reading_time, local_day
from app.models.environmental_factor import EnvironmentalFactor
from app.models.reading import BPReading
from app.models.user import PatientProfile

# A systolic swing smaller than this between periods reads as noise, not
# a real trend, so it's reported as "holding steady" rather than up/down.
DIRECTION_NOISE_THRESHOLD_MMHG = 3


def _readings_noun(count: int) -> str:
    return "reading" if count == 1 else "readings"


_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "models", "bp_status_model.joblib")
_bundle = None


def _load_model():
    global _bundle
    if _bundle is None:
        if not os.path.exists(_MODEL_PATH):
            raise RuntimeError(
                "BP status model not found. Run `python -m ml.train_model` "
                "from the backend/ directory (with the STEPS .sav file in data/)."
            )
        _bundle = joblib.load(_MODEL_PATH)
    return _bundle


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


def _build_model_features(recent, age: int, sex: int) -> dict:
    """
    Maps a patient's HyperSync-logged environmental factor entry onto the
    same feature space the model was trained on. Missing values fall back
    to population-neutral defaults, not zeros.
    """
    salt = SALT_SCORE_MAP.get(_enum_val(recent.salt_intake) if recent else None, 1)
    return {
        "age": age,
        "sex": sex,
        "smoked": int(recent.smoked) if recent and recent.smoked is not None else 0,
        "alcohol_consumed": int(recent.alcohol_consumed) if recent and recent.alcohol_consumed is not None else 0,
        "salt_score": salt,
        "activity_minutes": recent.physical_activity_minutes
        if recent and recent.physical_activity_minutes is not None
        else 25,
        "diet_adherence": int(recent.diet_adherence) if recent and recent.diet_adherence is not None else 1,
    }


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
    window_start = today - timedelta(days=period_days)  # no upper bound: newer lifestyle logs still count
    entries = (
        db.query(EnvironmentalFactor)
        .filter(
            EnvironmentalFactor.patient_id == patient_id,
            EnvironmentalFactor.logged_date >= today - timedelta(days=PATTERN_LOOKBACK_DAYS),
        )
        .order_by(EnvironmentalFactor.logged_date.desc(), EnvironmentalFactor.created_at.desc())
        .all()
    )
    effects = _load_model().get("effects")

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
        # Prevention: controlled today does not mean the habits logged are harmless.
        out.extend(advice(MAX_ADVICE_CONTROLLED))
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
        return out

    # Elevated or high: the survey-trained model gives the population context.
    in_window = [e for e in entries if e.logged_date >= window_start]
    recent = in_window[0] if in_window else None

    bundle = _load_model()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    profile = db.query(PatientProfile).filter(PatientProfile.user_id == patient_id).first()
    age = 38
    if profile and profile.date_of_birth:
        age = _age_in_years(profile.date_of_birth)
    sex = 1 if profile and profile.sex and _enum_val(profile.sex) == "Male" else 0

    feat_dict = _build_model_features(recent, age, sex)
    # Features the app does not collect yet (e.g. bmi in a model trained with
    # --features bmi) fall back to the training-population median.
    medians = bundle.get("feature_medians", {})
    row = {c: feat_dict.get(c, medians.get(c)) for c in feature_columns}
    X = pd.DataFrame([row], columns=feature_columns)

    proba = model.predict_proba(X)[0]
    at_risk_idx = list(model.classes_).index("at_risk")
    overall_risk_proba = float(proba[at_risk_idx])

    out = [
        {
            "message": (
                f"Your average blood pressure {window.phrase} is {trend.status} "
                f"at {trend.avg_systolic}/{trend.avg_diastolic} mmHg across {trend.reading_count} "
                f"{_readings_noun(trend.reading_count)}. In a national Kenyan health survey, about "
                f"{round(overall_risk_proba * 100)}% of people with your age, sex and logged habits had elevated "
                f"or high blood pressure. This is a population figure, not a diagnosis.{window.nudge}"
            ),
            "based_on_trend": trend.status,
            "confidence": round(overall_risk_proba, 3),
            "source": "model",
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
                    "The habits you've logged recently look healthy, so they don't explain these readings. "
                    "Keep logging, and discuss the readings with your clinician: medication, family history "
                    "and how you measure at home can all matter."
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
