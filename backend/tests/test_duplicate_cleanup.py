"""Legacy duplicate cleanup must preserve complementary observations."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from scripts.cleanup_duplicate_factors import ANSWER_FIELDS, _coerce_resolution, _merge_plan


def _row(**answers):
    values = {field: None for field in ANSWER_FIELDS}
    values.update(answers)
    patient_id = values.pop("patient_id", uuid4())
    return SimpleNamespace(
        factor_id=uuid4(),
        patient_id=patient_id,
        logged_date=date(2026, 11, 25),
        created_at=datetime(2026, 11, 25, 8, tzinfo=UTC),
        **values,
    )


def test_columns_added_after_a_legacy_row_are_treated_as_unanswered():
    patient_id = uuid4()
    legacy_row = SimpleNamespace(
        factor_id=uuid4(),
        patient_id=patient_id,
        logged_date=date(2026, 11, 25),
        created_at=datetime(2026, 11, 25, 8, tzinfo=UTC),
        sleep_hours=8,
    )

    merged, conflicts = _merge_plan([legacy_row], {})

    assert merged == {"sleep_hours": 8}
    assert conflicts == {}


def test_complementary_answers_are_merged_without_a_conflict():
    patient_id = uuid4()
    first = _row(medication_taken=False, patient_id=patient_id)
    second = _row(sleep_hours=8, patient_id=patient_id)
    group = [first, second]

    merged, conflicts = _merge_plan(group, {})

    assert merged["medication_taken"] is False
    assert merged["sleep_hours"] == 8
    assert conflicts == {}


def test_disagreeing_answers_require_an_explicit_resolution():
    patient_id = uuid4()
    first = _row(medication_taken=False, sleep_hours=4, patient_id=patient_id)
    second = _row(medication_taken=True, sleep_hours=8, patient_id=patient_id)
    group = [first, second]
    key = f"{patient_id}/2026-11-25"

    merged, conflicts = _merge_plan(group, {})

    assert set(conflicts) == {"medication_taken", "sleep_hours"}
    assert "medication_taken" not in merged

    merged, conflicts = _merge_plan(
        group,
        {key: {"medication_taken": False, "sleep_hours": 8}},
    )

    assert conflicts == {}
    assert merged["medication_taken"] is False
    assert merged["sleep_hours"] == 8


def test_resolution_values_are_validated_for_the_target_column():
    assert _coerce_resolution("medication_taken", False) is False
    assert _coerce_resolution("sleep_hours", 7) == 7.0
    assert _coerce_resolution("physical_activity_minutes", 30) == 30


def test_resolution_values_cannot_bypass_api_ranges():
    for field, value in (
        ("sleep_hours", -1),
        ("sleep_hours", float("nan")),
        ("sleep_hours", 25),
        ("physical_activity_minutes", -1),
        ("physical_activity_minutes", 1441),
    ):
        try:
            _coerce_resolution(field, value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{field}={value!r} should have been rejected")
