from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.core.factor_insights import (
    DESCRIPTIONS,
    LABELS,
    MODEL_FEATURE,
    RISK_PREDICATES,
    RULE_MESSAGES,
    RULE_ORDER,
    TIPS,
    build_advice,
    coverage_message,
    flagged_fields,
    group_patterns,
    measurement_advice,
    personal_patterns,
    summarize_log,
)

DAY0 = date(2026, 10, 1)


def day(n):
    return DAY0 + timedelta(days=n)


def entry(n, **answers):
    fields = dict.fromkeys(RISK_PREDICATES)
    fields.update(answers)
    return SimpleNamespace(logged_date=day(n), **fields)


def test_every_loggable_habit_has_a_risk_rule_and_a_tip():
    assert set(RISK_PREDICATES) == set(TIPS)  # nothing captured but never advised on (caffeine used to be)


def test_every_habit_is_fully_wired_up():
    """A new loggable habit must be advised on, described in patterns and named in summaries."""
    for name in RISK_PREDICATES:
        assert name in DESCRIPTIONS, name
        assert name in LABELS, name
        assert name in MODEL_FEATURE or name in RULE_MESSAGES, name  # a message from somewhere
        if name not in MODEL_FEATURE:
            assert name in RULE_ORDER, name


@pytest.mark.parametrize(
    ("field", "risky", "fine"),
    [
        ("salt_intake", "high", "low"),
        ("alcohol_consumed", True, False),
        ("smoked", True, False),
        ("physical_activity_minutes", 5, 45),
        ("diet_adherence", False, True),
        ("sleep_hours", 4.5, 8),
        ("stress_level", "high", "moderate"),
        ("caffeine_intake", "high", "moderate"),
        ("medication_taken", False, True),
        ("temperature_feel", "cold", "comfortable"),
        ("noise_level", "loud", "moderate"),
    ],
)
def test_risk_predicates(field, risky, fine):
    assert RISK_PREDICATES[field](risky)
    assert not RISK_PREDICATES[field](fine)


class TestFlagging:
    def test_one_good_day_cannot_hide_a_week_of_bad_ones(self):
        log = [entry(n, sleep_hours=4) for n in range(5)] + [entry(5, sleep_hours=8)]
        assert "sleep_hours" in flagged_fields(summarize_log(log), day(0))

    def test_a_single_old_slip_is_not_a_habit(self):
        log = [entry(0, smoked=True), entry(1, smoked=False), entry(2, smoked=False)]
        assert "smoked" not in flagged_fields(summarize_log(log), day(0))

    def test_a_risky_latest_answer_is_flagged_even_once(self):
        log = [entry(0, smoked=False), entry(3, smoked=True)]
        assert "smoked" in flagged_fields(summarize_log(log), day(0))

    def test_entries_before_the_window_do_not_count(self):
        log = [entry(n, sleep_hours=4) for n in range(3)]
        assert flagged_fields(summarize_log(log), day(10)) == set()

    def test_unanswered_questions_are_ignored(self):
        assert flagged_fields(summarize_log([entry(0)]), day(0)) == set()


class TestPersonalPatterns:
    def _log(self, bad_days, all_days, **bad):
        good = {k: (not v if isinstance(v, bool) else v) for k, v in bad.items()}
        return [entry(n, **(bad if n in bad_days else good)) for n in all_days]

    def test_finds_a_habit_that_tracks_higher_readings(self):
        log = self._log({0, 2, 4}, range(6), smoked=True)
        systolic = {day(n): (165.0 if n in {0, 2, 4} else 120.0) for n in range(6)}
        [pattern] = personal_patterns(summarize_log(log), systolic)
        assert pattern.field == "smoked"
        assert (pattern.risky_days, pattern.safe_days) == (3, 3)
        assert pattern.difference == pytest.approx(45)

    def test_ignores_a_gap_that_is_within_normal_variation(self):
        log = self._log({0, 2, 4}, range(6), smoked=True)
        systolic = {day(n): (124.0 if n in {0, 2, 4} else 120.0) for n in range(6)}
        assert personal_patterns(summarize_log(log), systolic) == []

    def test_needs_enough_days_on_both_sides(self):
        log = self._log({0}, range(4), smoked=True)  # only one risky day
        systolic = {day(n): (170.0 if n == 0 else 120.0) for n in range(4)}
        assert personal_patterns(summarize_log(log), systolic) == []

    def test_days_without_a_reading_are_not_compared(self):
        log = self._log({0, 1}, range(4), smoked=True)
        assert personal_patterns(summarize_log(log), {}) == []

    def test_habits_on_identical_days_are_reported_together(self):
        bad = {0, 2, 4}
        log = [entry(n, sleep_hours=4 if n in bad else 8, salt_intake="high" if n in bad else "low") for n in range(6)]
        systolic = {day(n): (170.0 if n in bad else 120.0) for n in range(6)}
        groups = group_patterns(personal_patterns(summarize_log(log), systolic))
        assert len(groups) == 1
        assert {p.field for p in groups[0]} == {"sleep_hours", "salt_intake"}


class TestBuildAdvice:
    def test_nothing_flagged_means_no_advice(self):
        assert build_advice([entry(0, smoked=False)], {}, day(0), None, limit=5) == []

    def test_every_flagged_habit_gets_actionable_advice(self):
        log = [entry(0, caffeine_intake="high", sleep_hours=4, stress_level="high")]
        advice = build_advice(log, {}, day(0), None, limit=5)
        text = " ".join(a["message"] for a in advice)
        for field in ("caffeine_intake", "sleep_hours", "stress_level"):
            assert TIPS[field] in text

    def test_smoking_and_missed_medication_are_never_the_ones_cut(self):
        everything = dict(
            salt_intake="high", alcohol_consumed=True, smoked=True, physical_activity_minutes=0,
            diet_adherence=False, sleep_hours=3, stress_level="high", caffeine_intake="high", medication_taken=False,
        )  # fmt: skip
        advice = build_advice([entry(0, **everything)], {}, day(0), None, limit=3)
        text = " ".join(a["message"] for a in advice)
        assert "smoking" in text.lower()
        assert "medication" in text.lower()

    def test_anything_cut_for_space_is_named_not_dropped(self):
        everything = dict(
            salt_intake="high", alcohol_consumed=True, smoked=True, physical_activity_minutes=0,
            diet_adherence=False, sleep_hours=3, stress_level="high", caffeine_intake="high", medication_taken=False,
        )  # fmt: skip
        advice = build_advice([entry(0, **everything)], {}, day(0), None, limit=3)
        assert advice[-1]["message"].startswith("Also worth attention")
        for label in ("stress", "sleep", "coffee or tea"):
            assert label in advice[-1]["message"]

    def test_a_personal_pattern_comes_first_and_replaces_the_generic_line(self):
        bad = {0, 2, 4}
        log = [entry(n, sleep_hours=4 if n in bad else 8) for n in range(6)]
        systolic = {day(n): (165.0 if n in bad else 120.0) for n in range(6)}
        advice = build_advice(log, systolic, day(0), None, limit=5)
        assert advice[0]["source"] == "pattern"
        assert "45 mmHg higher" in advice[0]["message"]
        assert "not proof of cause" in advice[0]["message"]
        assert sum("6 hours" in a["message"] for a in advice) == 1  # not repeated as a generic line

    def test_survey_supported_habits_are_labelled_and_sourced(self):
        effects = {"alcohol_consumed": {"odds_ratio": 1.5, "ci_low": 1.1, "ci_high": 2.0}}
        advice = build_advice([entry(0, alcohol_consumed=True)], {}, day(0), effects, limit=5)
        assert advice[0]["source"] == "model"
        assert "survey data" in advice[0]["message"]


def reading(systolic, rested=None, stimulant=None):
    return SimpleNamespace(systolic=systolic, rested_before=rested, stimulant_before=stimulant)


class TestMeasurementConditions:
    def test_a_single_hurried_reading_is_not_worth_a_lecture(self):
        assert measurement_advice([reading(150, rested=False), reading(120, True, False)]) is None

    def test_unanswered_conditions_are_not_assumed_bad(self):
        assert measurement_advice([reading(150), reading(150), reading(150)]) is None

    def test_properly_taken_readings_raise_nothing(self):
        assert measurement_advice([reading(150, True, False)] * 4) is None

    def test_several_hurried_readings_get_technique_advice(self):
        advice = measurement_advice(
            [reading(150, rested=False), reading(150, stimulant=True), reading(150, True, False)]
        )
        assert advice["source"] == "rule"
        assert "2 of your 3 readings" in advice["message"]
        assert "5 minutes" in advice["message"] and "30 minutes" in advice["message"]

    def test_shows_how_much_higher_the_hurried_readings_were(self):
        readings = [reading(152, rested=False)] * 2 + [reading(120, True, False)] * 3
        advice = measurement_advice(readings)
        assert advice["source"] == "pattern"
        assert "32 mmHg higher" in advice["message"]
        assert "the 3 you took properly rested" in advice["message"]

    def test_a_small_gap_is_not_reported_as_a_pattern(self):
        readings = [reading(124, rested=False)] * 2 + [reading(120, True, False)] * 3
        assert measurement_advice(readings)["source"] == "rule"

    def test_it_leads_the_advice_even_when_no_habit_is_flagged(self):
        readings = [reading(150, rested=False)] * 2
        advice = build_advice([entry(0, smoked=False)], {}, day(0), None, limit=5, readings=readings)
        assert [a["kind"] for a in advice] == ["measurement"]


class TestCoverage:
    def test_says_how_many_days_are_still_needed(self):
        message = coverage_message([entry(0, sleep_hours=8)], {day(0): 150.0, day(1): 150.0})
        assert "4 days" in message and "You have 1 so far" in message

    def test_days_without_a_reading_do_not_count(self):
        assert "You have 0 so far" in coverage_message([entry(0, sleep_hours=8)], {day(5): 150.0})

    def test_quiet_once_there_is_enough_to_compare(self):
        log = [entry(n, sleep_hours=8) for n in range(4)]
        assert coverage_message(log, {day(n): 130.0 for n in range(4)}) is None
