"""Single source of truth for blood-pressure classification.

The same thresholds are mirrored in the frontend (src/utils/bpStatus.js)
so the live preview on the "Log reading" screen agrees with the status
the API assigns once the reading is saved.
"""

LOW_SYSTOLIC = 90
LOW_DIASTOLIC = 60
HIGH_SYSTOLIC = 150
HIGH_DIASTOLIC = 90
# A separate safety boundary. The application keeps the public band as "high",
# but recommendation routing must treat readings at or above this boundary as
# very high and must not attach lifestyle advice.
VERY_HIGH_SYSTOLIC = 180
VERY_HIGH_DIASTOLIC = 110
ELEVATED_SYSTOLIC = 135
ELEVATED_DIASTOLIC = 85

CONTROLLED = "controlled"
ELEVATED = "elevated"
HIGH = "high"
LOW = "low"
NO_DATA = "no_data"


def is_very_high_bp(systolic: float, diastolic: float) -> bool:
    """Whether a reading crosses the internal urgent safety boundary."""
    return systolic >= VERY_HIGH_SYSTOLIC or diastolic >= VERY_HIGH_DIASTOLIC


def classify_bp(systolic: float, diastolic: float) -> str:
    """Classify a reading or average. Either value crossing a band sets the band.

    A very-high value takes precedence over a conflicting low value. The public
    band remains ``high``, so an acute very-high reading cannot be presented to
    a patient or clinician as a low reading.
    """
    if is_very_high_bp(systolic, diastolic):
        return HIGH
    if systolic < LOW_SYSTOLIC or diastolic < LOW_DIASTOLIC:
        return LOW
    if systolic >= HIGH_SYSTOLIC or diastolic >= HIGH_DIASTOLIC:
        return HIGH
    if systolic >= ELEVATED_SYSTOLIC or diastolic >= ELEVATED_DIASTOLIC:
        return ELEVATED
    return CONTROLLED
