"""Published filenames, versions and checksum files for trained model bundles.

Keeping this contract separate from the training code means ordinary application
and test environments do not need to import the ML-only plotting stack.
"""

RUNTIME_MODEL_VERSION = "4.0.1-steps-survey-calibrated"
RUNTIME_MODEL_SHA256 = "45c7adf6df1a707e0560cf110be9cd82da51c73ade610391436f3237fd331652"

# The exact build environment is part of the published artefact identity.
# The dependency lock is fully hashed; this Python patch is pinned so a
# rebuild cannot silently create a different runtime bundle.
RUNTIME_MODEL_BUILD_PYTHON = "3.13.14"
RUNTIME_MODEL_BUILD_PLATFORM = "linux"
RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256 = "2d720d57fcd8c60110f8437f8035b42168fff3a1fbe8f75f5dade54ba4183892"

RUNTIME_MODEL_FEATURES = (
    "age",
    "sex",
    "smoked",
    "alcohol_consumed",
    "salt_score",
    "activity_minutes",
    "diet_adherence",
)
RUNTIME_MODEL_MISSING_FEATURES = tuple(f"{feature}_missing" for feature in RUNTIME_MODEL_FEATURES)
RUNTIME_MODEL_INPUT_FEATURES = RUNTIME_MODEL_FEATURES + RUNTIME_MODEL_MISSING_FEATURES
RUNTIME_MODEL_LABELS = ("at_risk", "not_at_risk")
RUNTIME_MODEL_EFFECT_UNITS = {
    "age": "per 10 years (mean contrast)",
    "sex": "male vs female",
    "salt_score": "per +1 salt level (0-3)",
    "alcohol_consumed": "alcohol in last 30 days",
    "activity_minutes": "per 30 active min/day",
    "diet_adherence": "meets fruit/veg target",
    "smoked": "currently smokes",
}
RUNTIME_MODEL_EXPLANATION_FEATURES = (
    "salt_score",
    "alcohol_consumed",
    "activity_minutes",
    "diet_adherence",
    "smoked",
)

# The survey includes ages 18–69, but the locked test does not support a
# patient-facing percentage for every age band. The granular age 30–44,
# 45–59, and 60–69 results are near-random or worse. Withhold the estimate
# outside the conservative 18–29 band rather than generalising weak subgroup
# performance; the deterministic reading and lifestyle guidance still runs.
MODEL_AGE_RANGE = (18, 69)
MODEL_ESTIMATE_AGE_RANGE = (18, 29)
MODEL_ACTIVITY_MAX_MINUTES = 240
MODEL_SALT_SCORE_RANGE = (0, 3)

# The Kenya STEPS 2015 measurement weight is the appropriate weight for the
# blood-pressure/physical-measurement target. PSU and stratum retain the
# survey design used by the locked split and bootstrap uncertainty estimates.
RUNTIME_MODEL_WEIGHT_VARIABLE = "wstep2"
RUNTIME_MODEL_PSU_VARIABLE = "psu"
RUNTIME_MODEL_STRATUM_VARIABLE = "stratum"
RUNTIME_MODEL_SPLIT_FILENAME = "split_assignments.csv"
RUNTIME_MODEL_SPLIT_SHA256 = "c3a7dacdb7b265f110e1c79c7782b3601511c3c336dcd23461d0bfc1452cd609"
RUNTIME_MODEL_RAW_SHA256 = "081b3cbf4be2b7f840af1f6b3c7c731c6187d3eebf3591e08b4743879b1c5b12"
RUNTIME_MODEL_TRAINING_DATA_SHA256 = "8242dd85710f0bff917f59b0fbda4fce4116ec836b3a883b9ad19379ae1ffc40"
RUNTIME_MODEL_BOOTSTRAP_REPLICATES = 200

MODEL_VERSIONS = {
    "current": RUNTIME_MODEL_VERSION,
    "bmi": "4.0.0-steps-survey-calibrated-bmi-experimental",
}
MODEL_FILENAMES = {
    "current": "bp_status_model.joblib",
    "bmi": "bp_status_model_bmi.joblib",
}
CHECKSUM_FILENAMES = {
    "current": "SHA256SUMS",
    "bmi": "SHA256SUMS.bmi",
}
