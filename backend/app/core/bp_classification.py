"""Single source of truth for blood-pressure classification.

The same thresholds are mirrored in the frontend (src/utils/bpStatus.js)
so the live preview on the "Log reading" screen agrees with the status
the API assigns once the reading is saved.
"""

LOW_SYSTOLIC = 90
LOW_DIASTOLIC = 60
HIGH_SYSTOLIC = 150
HIGH_DIASTOLIC = 90
ELEVATED_SYSTOLIC = 135
ELEVATED_DIASTOLIC = 85

CONTROLLED = "controlled"
ELEVATED = "elevated"
HIGH = "high"
LOW = "low"
NO_DATA = "no_data"


def classify_bp(systolic: int, diastolic: int) -> str:
    """Classify a single reading. Either value crossing a band sets the band."""
    if systolic < LOW_SYSTOLIC or diastolic < LOW_DIASTOLIC:
        return LOW
    if systolic >= HIGH_SYSTOLIC or diastolic >= HIGH_DIASTOLIC:
        return HIGH
    if systolic >= ELEVATED_SYSTOLIC or diastolic >= ELEVATED_DIASTOLIC:
        return ELEVATED
    return CONTROLLED
