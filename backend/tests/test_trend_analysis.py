from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.core.bp_classification import NO_DATA
from app.core.trend_analysis import summarize_readings


def reading(day: int, systolic: int, diastolic: int, heart_rate: int | None = None, hour: int = 9):
    return SimpleNamespace(
        recorded_at=datetime(2026, 10, day, hour, 0, tzinfo=UTC),
        systolic=systolic,
        diastolic=diastolic,
        heart_rate=heart_rate,
    )


def test_no_readings_is_no_data():
    trend = summarize_readings([], period_days=7)
    assert trend.status == NO_DATA
    assert trend.reading_count == 0
    assert trend.daily_breakdown == []
    assert trend.avg_systolic is None


def test_averages_and_overall_status():
    trend = summarize_readings([reading(1, 140, 90), reading(2, 160, 100)], period_days=7)
    assert (trend.avg_systolic, trend.avg_diastolic) == (150.0, 95.0)
    assert trend.status == "high"


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((89, 80), (90, 80), "low"),  # 89.5 systolic is below 90
        ((120, 59), (120, 60), "low"),  # 59.5 diastolic is below 60
        ((149, 80), (150, 80), "elevated"),  # 149.5 systolic is below 150
        ((120, 89), (120, 90), "elevated"),  # 89.5 diastolic is below 90
        ((90, 60), (90, 60), "controlled"),
        ((150, 90), (150, 90), "high"),
        ((135, 85), (135, 85), "elevated"),
    ],
)
def test_fractional_averages_are_classified_without_rounding(first, second, expected):
    readings = [
        reading(1, first[0], first[1], hour=8),
        reading(1, second[0], second[1], hour=20),
    ]

    trend = summarize_readings(readings, period_days=7)

    assert trend.status == expected
    assert trend.daily_breakdown[0].status == expected


def test_status_agrees_with_the_one_decimal_average_shown_to_the_user():
    readings = [reading(1, 150, 80, hour=8)] * 24 + [reading(1, 149, 80, hour=20)]
    trend = summarize_readings(readings, period_days=7)
    assert trend.avg_systolic == 150.0
    assert trend.status == "high"
    assert trend.daily_breakdown[0].avg_systolic == 150.0
    assert trend.daily_breakdown[0].status == "high"


def test_same_day_readings_collapse_into_one_daily_average():
    trend = summarize_readings([reading(1, 120, 80, hour=8), reading(1, 130, 90, hour=20), reading(2, 118, 78)], 7)
    assert [d.reading_count for d in trend.daily_breakdown] == [2, 1]
    assert trend.daily_breakdown[0].avg_systolic == 125.0


def test_heart_rate_average_ignores_readings_without_one():
    trend = summarize_readings([reading(1, 120, 80, heart_rate=60), reading(2, 120, 80, heart_rate=None)], 7)
    assert trend.avg_heart_rate == 60


def test_heart_rate_average_is_none_when_never_logged():
    assert summarize_readings([reading(1, 120, 80)], 7).avg_heart_rate is None


@pytest.mark.parametrize("period", [7, 30, 90])
def test_period_is_echoed_back(period):
    assert summarize_readings([], period_days=period).period_days == period


def test_days_are_taken_in_the_callers_timezone():
    late = reading(1, 120, 80, hour=22)  # 22:00 UTC = 01:00 next day in Nairobi
    utc_day = summarize_readings([late], 7).daily_breakdown[0].date
    nairobi_day = summarize_readings([late], 7, ZoneInfo("Africa/Nairobi")).daily_breakdown[0].date
    assert (utc_day.day, nairobi_day.day) == (1, 2)


def test_a_naive_timestamp_is_treated_as_utc():
    naive = SimpleNamespace(recorded_at=datetime(2026, 10, 1, 22, 0), systolic=120, diastolic=80, heart_rate=None)
    nairobi_day = summarize_readings([naive], 7, ZoneInfo("Africa/Nairobi")).daily_breakdown[0].date
    assert nairobi_day.day == 2
