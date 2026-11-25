"""The rules behind the clinician-only treatment-review flag."""

import re
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.core.bp_classification import NO_DATA
from app.core.treatment_review import (
    MIN_READINGS_PER_WEEK,
    PRIORITY,
    ROUTINE,
    SNOOZE_DAYS,
    SUSTAINED_ELEVATED_HIGH,
    SUSTAINED_LOW,
    assess,
    judge_adherence,
    judge_measurement,
    weekly_summaries,
)

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)  # a Monday, midday UTC

CONTROLLED, ELEVATED, HIGH, LOW = (118, 76), (142, 88), (162, 100), (86, 54)


def readings_for(weeks, per_week=7, **conditions):
    """weeks: oldest first, each a (systolic, diastolic) tuple or None for 'no readings that week'."""
    out = []
    for index, week in enumerate(reversed(weeks)):  # index 0 = the most recent week
        if week is None:
            continue
        for day in range(per_week):
            out.append(
                SimpleNamespace(
                    recorded_at=NOW - timedelta(days=7 * index + day, hours=4),
                    systolic=week[0],
                    diastolic=week[1],
                    rested_before=conditions.get("rested_before"),
                    stimulant_before=conditions.get("stimulant_before"),
                )
            )
    return out


def meds(taken, missed, days_ago_start=0):
    """Medication log entries: `taken` days taken then `missed` days missed."""
    answers = [True] * taken + [False] * missed
    return [
        SimpleNamespace(
            logged_date=(NOW - timedelta(days=days_ago_start + i)).date(), **blank_entry(medication_taken=a)
        )
        for i, a in enumerate(answers)
    ]


def blank_entry(**answers):
    fields = dict.fromkeys(
        [
            "stress_level",
            "sleep_hours",
            "diet_adherence",
            "medication_taken",
            "salt_intake",
            "caffeine_intake",
            "alcohol_consumed",
            "smoked",
            "physical_activity_minutes",
            "temperature_feel",
            "noise_level",
        ]  # fmt: skip
    )
    fields.update(answers)
    return fields


class TestWhoIsFlagged:
    def test_three_elevated_or_high_weeks_including_the_latest_is_flagged(self):
        a = assess(readings_for([CONTROLLED, ELEVATED, ELEVATED, ELEVATED]), [], NOW)
        assert a.flagged and a.active
        assert a.kind == SUSTAINED_ELEVATED_HIGH
        assert a.weeks_in_flagged_band == 3

    def test_two_elevated_or_high_weeks_is_not_enough(self):
        a = assess(readings_for([CONTROLLED, CONTROLLED, ELEVATED, ELEVATED]), [], NOW)
        assert not a.flagged

    def test_a_patient_who_has_already_improved_is_not_flagged(self):
        a = assess(readings_for([ELEVATED, ELEVATED, ELEVATED, CONTROLLED]), [], NOW)
        assert not a.flagged

    def test_a_patient_who_stopped_measuring_is_not_flagged(self):
        a = assess(readings_for([ELEVATED, ELEVATED, ELEVATED, None]), [], NOW)
        assert not a.flagged  # no recent data: the flag cannot say anything about now

    def test_weeks_with_too_few_readings_are_not_trusted(self):
        sparse = readings_for([ELEVATED] * 4, per_week=MIN_READINGS_PER_WEEK - 1)
        assert not assess(sparse, [], NOW).flagged
        assert all(w.status == NO_DATA for w in assess(sparse, [], NOW).weeks)

    def test_three_weeks_of_data_is_enough_to_judge(self):
        a = assess(readings_for([None, ELEVATED, ELEVATED, ELEVATED]), [], NOW)
        assert a.flagged

    def test_controlled_patients_are_never_flagged(self):
        assert not assess(readings_for([CONTROLLED] * 4), [], NOW).flagged

    def test_readings_older_than_four_weeks_are_ignored(self):
        old = readings_for([HIGH] * 4)
        for r in old:
            r.recorded_at -= timedelta(days=60)
        assert not assess(old, [], NOW).flagged


class TestLevelAndDirection:
    def test_sustained_high_band_is_priority(self):
        a = assess(readings_for([HIGH, HIGH, HIGH, ELEVATED]), [], NOW)
        assert a.level == PRIORITY

    def test_elevated_only_is_routine(self):
        a = assess(readings_for([ELEVATED] * 4), [], NOW)
        assert a.level == ROUTINE

    def test_sustained_low_is_flagged_without_assuming_over_treatment(self):
        a = assess(readings_for([CONTROLLED, LOW, LOW, LOW]), [], NOW)
        assert a.kind == SUSTAINED_LOW and a.level == ROUTINE
        assert "low band" in a.headline
        assert "over-treatment" not in a.headline
        assert "above target" not in a.headline

    def test_a_single_low_week_is_not_flagged(self):
        assert not assess(readings_for([CONTROLLED, CONTROLLED, CONTROLLED, LOW]), [], NOW).flagged


class TestWhatToConfirmFirst:
    @pytest.mark.parametrize(
        ("taken", "missed", "status", "phrase"),
        [
            (9, 1, "good", "does not rule out other causes"),
            (6, 4, "poor", "explore adherence support and other causes"),
            (2, 1, "unknown", "confirm what medication, if any, the patient takes"),
        ],
    )
    def test_the_headline_reflects_adherence(self, taken, missed, status, phrase):
        a = assess(readings_for([ELEVATED] * 4), meds(taken, missed), NOW)
        assert a.adherence.status == status
        assert phrase in a.headline

    def test_adherence_thresholds(self):
        assert judge_adherence([True] * 4).status == "unknown"  # too few answers to judge
        assert judge_adherence([True] * 9 + [False]).status == "good"  # 10% missed
        assert judge_adherence([True] * 8 + [False] * 2).status == "poor"  # 20% missed

    def test_days_without_prescribed_medication_are_not_adherence_misses(self):
        no_medication = [
            SimpleNamespace(
                logged_date=(NOW - timedelta(days=i)).date(),
                **blank_entry(medication_prescribed=False, medication_taken=None),
            )
            for i in range(5)
        ]
        a = assess(readings_for([ELEVATED] * 4), no_medication, NOW)
        assert a.adherence.answered == 0
        assert a.adherence.missed == 0
        assert a.adherence.status == "unknown"

    def test_duplicate_rows_on_one_date_count_as_one_day(self):
        day = NOW.date()
        duplicate_misses = [SimpleNamespace(logged_date=day, **blank_entry(medication_taken=False)) for _ in range(5)]
        a = assess(readings_for([ELEVATED] * 4), duplicate_misses, NOW)
        assert a.adherence.answered == 1
        assert a.adherence.missed == 1
        assert a.adherence.status == "unknown"
        assert "fewer than 5 answers" in a.headline

    def test_hurried_readings_cast_doubt_on_the_numbers(self):
        hurried = readings_for([ELEVATED] * 4, rested_before=False)
        a = assess(hurried, meds(9, 1), NOW)
        assert a.measurement.caution
        assert "confirm technique" in a.headline

    def test_properly_taken_readings_raise_no_doubt(self):
        proper = readings_for([ELEVATED] * 4, rested_before=True, stimulant_before=False)
        assert not judge_measurement(proper).caution

    def test_future_readings_do_not_change_measurement_statistics(self):
        future = SimpleNamespace(
            recorded_at=NOW + timedelta(days=1),
            systolic=120,
            diastolic=80,
            rested_before=True,
            stimulant_before=False,
        )
        a = assess(readings_for([ELEVATED] * 4) + [future], [], NOW)
        assert a.measurement.total == 28

    def test_contributors_come_from_the_lifestyle_log(self):
        log = [SimpleNamespace(logged_date=(NOW - timedelta(days=i)).date(), **blank_entry(salt_intake="high"))
               for i in range(3)]  # fmt: skip
        a = assess(readings_for([ELEVATED] * 4), log, NOW)
        assert a.contributors == ["salt"]
        assert any("salt" in line for line in a.confirm_first)

    def test_it_always_lists_all_three_checks(self):
        a = assess(readings_for([ELEVATED] * 4), [], NOW)
        topics = [line.split(":")[0] for line in a.confirm_first]
        assert topics == ["Medication use", "Measurement", "Lifestyle"]


class TestReviewPause:
    def reviewed(self, days_ago):
        return assess(readings_for([ELEVATED] * 4), [], NOW, last_reviewed_at=NOW - timedelta(days=days_ago))

    def test_a_recent_review_pauses_the_flag_but_keeps_the_facts(self):
        a = self.reviewed(10)
        assert a.flagged and not a.active
        assert a.snoozed_until == NOW - timedelta(days=10) + timedelta(days=SNOOZE_DAYS)

    def test_the_flag_returns_once_the_pause_has_passed(self):
        assert self.reviewed(SNOOZE_DAYS + 1).active

    def test_never_reviewed_means_active(self):
        assert assess(readings_for([ELEVATED] * 4), [], NOW).active

    def test_a_review_from_an_earlier_episode_does_not_pause_a_relapse(self):
        # The current four weeks contain three elevated weeks but the latest
        # run began after the old review, so this is a new episode.
        readings = readings_for([ELEVATED, ELEVATED, ELEVATED, CONTROLLED, ELEVATED])
        a = assess(
            readings,
            [],
            NOW,
            last_reviewed_at=NOW - timedelta(days=10),
            last_reviewed_kind=SUSTAINED_ELEVATED_HIGH,
            last_reviewed_level=ROUTINE,
        )
        assert a.flagged and a.active
        assert a.snoozed_until is None

    def test_a_routine_review_does_not_pause_a_priority_escalation(self):
        a = assess(
            readings_for([HIGH, HIGH, HIGH, ELEVATED]),
            [],
            NOW,
            last_reviewed_at=NOW - timedelta(days=1),
            last_reviewed_kind=SUSTAINED_ELEVATED_HIGH,
            last_reviewed_level=ROUTINE,
        )
        assert a.level == PRIORITY and a.active
        assert a.snoozed_until is None


class TestSafetyOfTheWording:
    def test_it_never_talks_about_doses_or_drugs(self):
        for weeks in ([ELEVATED] * 4, [LOW] * 4):
            for log in (meds(9, 1), meds(5, 5), []):
                a = assess(readings_for(weeks), log, NOW)
                text = " ".join([a.headline, *a.confirm_first])
                assert not re.search(
                    r"\b(dose|doses|mg|prescrib\w*|titrat\w*|uptitrat\w*|increase|double)\b", text, re.I
                )


class TestWeeklyBins:
    def test_four_contiguous_weeks_ending_today_oldest_first(self):
        weeks = weekly_summaries([], date(2026, 11, 16))
        assert [(w.start, w.end) for w in weeks] == [
            (date(2026, 10, 20), date(2026, 10, 26)),
            (date(2026, 10, 27), date(2026, 11, 2)),
            (date(2026, 11, 3), date(2026, 11, 9)),
            (date(2026, 11, 10), date(2026, 11, 16)),
        ]

    def test_days_follow_the_users_timezone(self):
        # 22:30 UTC on 15 Nov is already 16 Nov in Nairobi, so it belongs in the most recent week there.
        late = [SimpleNamespace(recorded_at=datetime(2026, 11, 9, 22, 30, tzinfo=UTC), systolic=140, diastolic=90,
                                rested_before=None, stimulant_before=None) for _ in range(3)]  # fmt: skip
        nairobi = weekly_summaries(late, date(2026, 11, 16), ZoneInfo("Africa/Nairobi"))
        utc = weekly_summaries(late, date(2026, 11, 16), UTC)
        assert nairobi[-1].reading_count == 3 and utc[-1].reading_count == 0
