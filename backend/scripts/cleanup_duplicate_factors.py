"""Inspect and safely clean legacy duplicate daily lifestyle check-ins.

Older HyperSync versions allowed more than one lifestyle row for the same
patient and calendar day. The current database constraint prevents that, but a
migration cannot guess which legacy row contains the intended observations.

This command is therefore a dry-run by default. It prints every non-null answer
in every duplicate group. With ``--apply --keep earliest`` or
``--apply --keep latest`` it merges complementary answers into the retained row
and deletes only rows whose remaining values are proven redundant.

If duplicate rows disagree about the same field, the command refuses to delete
anything until the conflict is resolved explicitly in a JSON file::

    {
      "<patient-uuid>/2026-11-25": {
        "sleep_hours": 8,
        "medication_taken": false
      }
    }

Pass that file with ``--resolutions path.json``. Every conflicting field for
every affected group must be present. The command validates the file before it
changes the database.

Run it from ``backend/`` with the same environment used by the application,
then run ``alembic upgrade head`` again. The ``latest`` and ``earliest``
rules use each row's creation time, with the row ID as a deterministic tie
breaker.
"""

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import delete, inspect, select, update

sys.path.append(os.getcwd())

from app.core.database import SessionLocal  # noqa: E402
from app.models.environmental_factor import (  # noqa: E402
    EnvironmentalFactor,
    IntakeLevel,
    NoiseLevel,
    StressLevel,
    TemperatureFeel,
)

ANSWER_FIELDS = (
    "stress_level",
    "sleep_hours",
    "diet_adherence",
    "medication_prescribed",
    "medication_taken",
    "salt_intake",
    "caffeine_intake",
    "alcohol_consumed",
    "smoked",
    "physical_activity_minutes",
    "temperature_feel",
    "noise_level",
)
ROW_FIELDS = (
    "factor_id",
    "patient_id",
    "logged_date",
    "created_at",
    *ANSWER_FIELDS,
)

_ENUM_VALUES = {
    "stress_level": {item.value for item in StressLevel},
    "salt_intake": {item.value for item in IntakeLevel},
    "caffeine_intake": {item.value for item in IntakeLevel},
    "temperature_feel": {item.value for item in TemperatureFeel},
    "noise_level": {item.value for item in NoiseLevel},
}
_BOOLEAN_FIELDS = {
    "diet_adherence",
    "medication_prescribed",
    "medication_taken",
    "alcohol_consumed",
    "smoked",
}
_INTEGER_FIELDS = {"physical_activity_minutes"}
_FLOAT_FIELDS = {"sleep_hours"}


def _row_order(row):
    created_at = row.created_at.isoformat() if row.created_at else ""
    return (created_at, str(row.factor_id))


def _choose_rows(group, keep):
    ordered = sorted(group, key=_row_order)
    return ordered[-1] if keep == "latest" else ordered[0]


def _group_key(group) -> str:
    return f"{group[0].patient_id}/{group[0].logged_date.isoformat()}"


def _plain_value(value):
    return value.value if hasattr(value, "value") else value


def _answer(row, field: str):
    """Read an answer, treating a not-yet-migrated column as unanswered."""
    return getattr(row, field, None)


def _coerce_resolution(field: str, value):
    """Validate one explicit conflict-resolution value for a database column."""
    if value is None:
        return None
    if field in _BOOLEAN_FIELDS:
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be true or false")
        return value
    if field in _INTEGER_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field} must be an integer")
        if not 0 <= value <= 1440:
            raise ValueError(f"{field} must be between 0 and 1440")
        return value
    if field in _FLOAT_FIELDS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a number")
        if not math.isfinite(value) or not 0 <= value <= 24:
            raise ValueError(f"{field} must be a finite number between 0 and 24")
        return float(value)
    if field in _ENUM_VALUES:
        if not isinstance(value, str) or value not in _ENUM_VALUES[field]:
            allowed = ", ".join(sorted(_ENUM_VALUES[field]))
            raise ValueError(f"{field} must be one of: {allowed}")
        enum_type = {
            "stress_level": StressLevel,
            "salt_intake": IntakeLevel,
            "caffeine_intake": IntakeLevel,
            "temperature_feel": TemperatureFeel,
            "noise_level": NoiseLevel,
        }[field]
        return enum_type(value)
    raise ValueError(f"unknown lifestyle field: {field}")


def _load_resolutions(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None:
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read resolutions file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("the resolutions file must contain a JSON object")

    resolutions = {}
    for group_key, values in raw.items():
        if not isinstance(group_key, str) or not isinstance(values, dict):
            raise ValueError("each resolution must map a patient/date key to an object")
        resolved = {}
        for field, value in values.items():
            if field not in ANSWER_FIELDS:
                raise ValueError(f"unknown lifestyle field in resolutions: {field}")
            resolved[field] = _coerce_resolution(field, value)
        resolutions[group_key] = resolved
    return resolutions


def _merge_plan(group, resolutions):
    """Return merged values and any unresolved same-field conflicts."""
    merged = {}
    conflicts = {}
    group_resolutions = resolutions.get(_group_key(group), {})

    for field in ANSWER_FIELDS:
        observations = [(row.factor_id, _answer(row, field)) for row in group if _answer(row, field) is not None]
        if not observations:
            continue
        distinct = {_plain_value(value) for _, value in observations}
        if len(distinct) == 1:
            merged[field] = observations[0][1]
            continue

        if field not in group_resolutions:
            conflicts[field] = observations
            continue
        merged[field] = group_resolutions[field]

    return merged, conflicts


def _print_group(group) -> None:
    print(f"\nPatient {group[0].patient_id}, logged date {group[0].logged_date}:")
    for row in sorted(group, key=_row_order):
        print(f"  {row.factor_id}  created {row.created_at}")
        answers = [
            f"{field}={_plain_value(_answer(row, field))}" for field in ANSWER_FIELDS if _answer(row, field) is not None
        ]
        print("    " + (", ".join(answers) if answers else "(no answers)"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="merge and delete duplicate rows (otherwise only report them)"
    )
    parser.add_argument("--keep", choices=["earliest", "latest"], help="which row to retain when --apply is used")
    parser.add_argument("--patient-id", type=UUID, help="limit the report and cleanup to one patient")
    parser.add_argument(
        "--resolutions",
        type=Path,
        help="JSON file with explicit values for conflicting fields, keyed by patient-uuid/YYYY-MM-DD",
    )
    args = parser.parse_args()

    if args.apply and not args.keep:
        parser.error("--apply requires an explicit --keep earliest or --keep latest choice")
    if args.resolutions and not args.apply:
        parser.error("--resolutions is only used with --apply")

    try:
        resolutions = _load_resolutions(args.resolutions)
    except ValueError as exc:
        parser.error(str(exc))

    db = SessionLocal()
    try:
        # The cleanup must work at the revision where the duplicate constraint
        # failed. That revision may not yet have every newer answer column, so
        # select only columns that actually exist instead of loading the full
        # current ORM model.
        available_columns = {column["name"] for column in inspect(db.get_bind()).get_columns("environmental_factors")}
        selected_fields = [field for field in ROW_FIELDS if field in available_columns]
        query = select(*(getattr(EnvironmentalFactor, field) for field in selected_fields)).select_from(
            EnvironmentalFactor
        )
        if args.patient_id:
            query = query.where(EnvironmentalFactor.patient_id == args.patient_id)
        query = query.order_by(
            EnvironmentalFactor.patient_id,
            EnvironmentalFactor.logged_date,
            EnvironmentalFactor.created_at,
            EnvironmentalFactor.factor_id,
        )
        rows = [
            SimpleNamespace(**dict(zip(selected_fields, values, strict=True))) for values in db.execute(query).all()
        ]

        groups = defaultdict(list)
        for row in rows:
            groups[(row.patient_id, row.logged_date)].append(row)
        duplicates = [group for group in groups.values() if len(group) > 1]

        if not duplicates:
            print("No duplicate daily lifestyle check-ins found.")
            return 0

        print(f"Found {len(duplicates)} duplicate patient/day groups:")
        for group in duplicates:
            _print_group(group)

        if not args.apply:
            print("\nDry run only. Review every answer above before applying a cleanup.")
            return 0

        plans = []
        unresolved = []
        used_resolution_keys = set()
        for group in duplicates:
            merged, conflicts = _merge_plan(group, resolutions)
            key = _group_key(group)
            if key in resolutions:
                used_resolution_keys.add(key)
            if conflicts:
                unresolved.append((group, conflicts))
            plans.append((group, merged))

        unknown_keys = set(resolutions) - used_resolution_keys
        if unknown_keys:
            parser.error(f"resolution keys do not match a duplicate group: {', '.join(sorted(unknown_keys))}")

        if unresolved:
            print("\nNo rows were changed because some same-field answers conflict:")
            for group, conflicts in unresolved:
                print(f"\n  {_group_key(group)}")
                for field, observations in conflicts.items():
                    rendered = ", ".join(f"{row_id}={_plain_value(value)}" for row_id, value in observations)
                    print(f"    {field}: {rendered}")
            print(
                "\nCreate a JSON resolution file with every conflicting field, then rerun with --resolutions. "
                'Example: {"<patient-uuid>/YYYY-MM-DD": {"field": value}}.'
            )
            return 2

        removed = 0
        for group, merged in plans:
            keeper = _choose_rows(group, args.keep)
            if merged:
                db.execute(
                    update(EnvironmentalFactor)
                    .where(EnvironmentalFactor.factor_id == keeper.factor_id)
                    .values(**merged)
                )
            for row in group:
                if row.factor_id != keeper.factor_id:
                    db.execute(delete(EnvironmentalFactor).where(EnvironmentalFactor.factor_id == row.factor_id))
                    removed += 1
        db.commit()
        print(f"\nRemoved {removed} duplicate rows and kept the {args.keep} row in every group.")
        print("Run `alembic upgrade head` to install the one-check-in-per-day constraint.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
