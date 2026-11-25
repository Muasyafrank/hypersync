"""Published filenames, versions and checksum files for trained model bundles.

Keeping this contract separate from the training code means ordinary application
and test environments do not need to import the ML-only plotting stack.
"""

RUNTIME_MODEL_VERSION = "3.0.1-steps-logit-aligned"
RUNTIME_MODEL_SHA256 = "917eab9781483939230306f82d8aa4fe7fd206c3de6b77424c923998f0b49094"
RUNTIME_MODEL_FEATURES = (
    "age",
    "sex",
    "smoked",
    "alcohol_consumed",
    "salt_score",
    "activity_minutes",
    "diet_adherence",
)
RUNTIME_MODEL_LABELS = ("at_risk", "not_at_risk")
RUNTIME_MODEL_EFFECT_UNITS = {
    "age": "per 10 years",
    "sex": "male vs female",
    "salt_score": "per +1 salt level (0-3)",
    "alcohol_consumed": "alcohol in last 30 days",
    "activity_minutes": "per 30 active min/day",
    "diet_adherence": "meets fruit/veg target",
    "smoked": "currently smokes",
}
MODEL_AGE_RANGE = (18, 100)
MODEL_ACTIVITY_MAX_MINUTES = 240
MODEL_SALT_SCORE_RANGE = (0, 3)

MODEL_VERSIONS = {
    "current": RUNTIME_MODEL_VERSION,
    "bmi": "3.0.1-steps-logit-aligned-bmi-experimental",
}
MODEL_FILENAMES = {
    "current": "bp_status_model.joblib",
    "bmi": "bp_status_model_bmi.joblib",
}
CHECKSUM_FILENAMES = {
    "current": "SHA256SUMS",
    "bmi": "SHA256SUMS.bmi",
}
