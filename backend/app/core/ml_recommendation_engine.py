"""
ML-based recommendation engine, trained on real Kenya STEPS 2015 NCD risk
factor survey data (see ml/steps_pipeline.py and ml/train_model.py).

DESIGN NOTES (worth restating in the project report)
------------------------------------------------------
1. The trained model predicts AT-RISK vs NOT-AT-RISK using age, sex, and
   five lifestyle features. Age and sex are included because they
   materially improve predictive accuracy (age in particular dominates
   feature importance, consistent with the hypertension literature), but
   they are NEVER surfaced as "recommendations" since a patient cannot
   act on their age or sex. Only the five MODIFIABLE lifestyle features
   (activity, salt, alcohol, smoking, diet) are ranked and shown.

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

4. Per-patient factor ranking combines the model's GLOBAL feature
   importance (empirically learned from real data) with the PATIENT'S
   OWN logged value for that factor: a factor only surfaces as a
   recommendation if the model found it generally predictive AND the
   patient's own logged behaviour is in the risk-associated direction.
"""
import os
import joblib
import numpy as np
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.core.trend_analysis import compute_trend
from app.models.environmental_factor import EnvironmentalFactor
from app.models.user import PatientProfile

_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "ml", "models", "bp_status_model.joblib"
)
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


# Modifiable lifestyle features the app can generate recommendations for.
# age/sex are deliberately excluded — see module docstring, point 1.
MODIFIABLE_FEATURES = ["activity_minutes", "salt_score", "alcohol_consumed", "smoked", "diet_adherence"]

MESSAGES = {
    "activity_minutes": "Your logged physical activity has been low. In the population data this system is trained on, low activity is one of the strongest lifestyle factors associated with higher blood pressure — regular moderate activity, like brisk walking, may help.",
    "salt_score": "Your logged salt intake has been high. High salt intake is strongly associated with elevated blood pressure in the population data this system is trained on — try reducing added salt and processed foods.",
    "alcohol_consumed": "You've logged alcohol consumption recently. This is associated with higher blood pressure in the population data this system is trained on — reducing intake may help.",
    "smoked": "You've logged smoking recently. Smoking is associated with elevated blood pressure and broader cardiovascular risk — consider support resources for quitting.",
    "diet_adherence": "You've logged not meeting the recommended fruit and vegetable intake. This is associated with higher blood pressure in the population data this system is trained on — consider increasing your daily servings.",
}

# Rule-based factors: no equivalent question in the training data, so
# these are plain threshold checks, not model output.
RULE_MESSAGES = {
    "poor_sleep": "You've logged under 6 hours of sleep recently. Poor sleep is linked to higher blood pressure in clinical guidance, though this system's trained model does not cover sleep directly.",
    "high_stress": "You've logged high stress recently. Stress can raise blood pressure — short relaxation breaks may help. (Based on general clinical guidance, not the trained model.)",
    "missed_medication": "You've logged a missed medication dose. Missing doses can contribute to elevated readings. (Based on general clinical guidance, not the trained model.)",
}

MAX_FACTOR_MESSAGES = 3
SALT_SCORE_MAP = {"none": 0, "low": 1, "moderate": 2, "high": 3}


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
        "activity_minutes": recent.physical_activity_minutes if recent and recent.physical_activity_minutes is not None else 25,
        "diet_adherence": int(recent.diet_adherence) if recent and recent.diet_adherence is not None else 1,
    }


def _is_risk_direction(feature: str, value) -> bool:
    if feature == "activity_minutes":
        return value < 20
    if feature == "salt_score":
        return value >= 2
    if feature == "alcohol_consumed":
        return bool(value)
    if feature == "smoked":
        return bool(value)
    if feature == "diet_adherence":
        return not bool(value)
    return False


def generate_recommendations_ml(db: Session, patient_id, period_days: int = 7) -> list[dict]:
    trend = compute_trend(db, patient_id, period_days)

    if trend.status == "no_data":
        return [{
            "message": "You haven't logged any readings recently. Record your blood pressure at a consistent time each day for more reliable trends.",
            "based_on_trend": None, "confidence": None, "source": "system",
        }]

    if trend.status == "controlled":
        return [{
            "message": f"Your blood pressure has been controlled over the last {period_days} days. Keep up your current routine.",
            "based_on_trend": "controlled", "confidence": None, "source": "system",
        }]

    if trend.status == "low":
        return [{
            "message": "Your average blood pressure is on the low side. If you feel dizzy or unwell, contact your clinician.",
            "based_on_trend": "low", "confidence": None, "source": "system",
        }]

    cutoff = date.today() - timedelta(days=period_days)
    recent = (
        db.query(EnvironmentalFactor)
        .filter(EnvironmentalFactor.patient_id == patient_id, EnvironmentalFactor.logged_date >= cutoff)
        .order_by(EnvironmentalFactor.logged_date.desc())
        .first()
    )

    bundle = _load_model()
    model = bundle["model"]
    feature_columns = bundle["feature_columns"]

    profile = db.query(PatientProfile).filter(PatientProfile.user_id == patient_id).first()
    age = 38
    if profile and profile.date_of_birth:
        age = date.today().year - profile.date_of_birth.year
    sex = 1 if profile and profile.sex and _enum_val(profile.sex) == "Male" else 0

    feat_dict = _build_model_features(recent, age, sex)
    X = np.array([[feat_dict[c] for c in feature_columns]])

    proba = model.predict_proba(X)[0]
    at_risk_idx = list(model.classes_).index("at_risk")
    overall_risk_proba = float(proba[at_risk_idx])

    importances = dict(zip(feature_columns, model.feature_importances_))

    scored = []
    for feature in MODIFIABLE_FEATURES:
        value = feat_dict[feature]
        if _is_risk_direction(feature, value):
            scored.append((feature, importances.get(feature, 0.0)))
    scored.sort(key=lambda x: x[1], reverse=True)

    total_importance = sum(importances[f] for f in MODIFIABLE_FEATURES) or 1.0

    out = [{
        "message": (
            f"Your average blood pressure over the last {period_days} days is {trend.status}. "
            f"Based on a model trained on Kenya NCD survey data, your estimated risk profile is "
            f"{round(overall_risk_proba * 100)}%. The factors below are the most likely contributors."
        ),
        "based_on_trend": trend.status,
        "confidence": round(overall_risk_proba, 3),
        "source": "model",
    }]

    added = 0
    for feature, importance in scored:
        if added >= MAX_FACTOR_MESSAGES:
            break
        relative_confidence = importance / total_importance
        out.append({
            "message": MESSAGES[feature],
            "based_on_trend": trend.status,
            "confidence": round(relative_confidence, 3),
            "source": "model",
        })
        added += 1

    if recent:
        if recent.sleep_hours is not None and recent.sleep_hours < 6:
            out.append({"message": RULE_MESSAGES["poor_sleep"], "based_on_trend": trend.status, "confidence": None, "source": "rule"})
        if _enum_val(recent.stress_level) == "high":
            out.append({"message": RULE_MESSAGES["high_stress"], "based_on_trend": trend.status, "confidence": None, "source": "rule"})
        if recent.medication_taken is False:
            out.append({"message": RULE_MESSAGES["missed_medication"], "based_on_trend": trend.status, "confidence": None, "source": "rule"})

    if added == 0 and recent is None:
        out.append({
            "message": "Log your stress, sleep, diet, and medication on the Lifestyle page — this lets the system identify what may be driving your readings.",
            "based_on_trend": trend.status, "confidence": None, "source": "system",
        })

    return out
