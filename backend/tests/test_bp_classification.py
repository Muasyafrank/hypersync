import pytest

from app.core.bp_classification import CONTROLLED, ELEVATED, HIGH, LOW, classify_bp


@pytest.mark.parametrize(
    ("systolic", "diastolic", "expected"),
    [
        (120, 80, CONTROLLED),
        (134, 84, CONTROLLED),  # just under both elevated thresholds
        (135, 80, ELEVATED),  # systolic alone crosses into elevated
        (120, 85, ELEVATED),  # diastolic alone crosses into elevated
        (149, 89, ELEVATED),  # just under both high thresholds
        (150, 80, HIGH),
        (120, 90, HIGH),
        (89, 70, LOW),  # low systolic
        (110, 59, LOW),  # low diastolic
        (90, 60, CONTROLLED),  # the low bands are exclusive of 90/60
    ],
)
def test_thresholds(systolic, diastolic, expected):
    assert classify_bp(systolic, diastolic) == expected


def test_low_takes_precedence_over_high():
    # Either value crossing a band sets the band, and "low" is checked first.
    assert classify_bp(160, 55) == LOW
