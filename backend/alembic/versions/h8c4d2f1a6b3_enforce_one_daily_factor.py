"""enforce one lifestyle check-in per patient per local day

The daily check-in is one observation of a day's habits. Allowing repeated
rows for the same date made medication adherence look like several missed
days and allowed one request to change current advice more than once.

Revision ID: h8c4d2f1a6b3
Revises: j5a7b9c2d4e6
Create Date: 2026-11-24 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "h8c4d2f1a6b3"
down_revision: str | Sequence[str] | None = "j5a7b9c2d4e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "uq_environmental_factors_patient_logged_date"


def upgrade() -> None:
    """Refuse to guess which legacy duplicate should be kept."""
    if context.is_offline_mode():
        # Offline SQL generation has no database to inspect. Emit the final
        # constraint for a clean target; the online preflight remains the
        # safety check for databases that may contain legacy duplicates.
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            "environmental_factors",
            ["patient_id", "logged_date"],
        )
        return

    existing_constraints = {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("environmental_factors")
    }
    if CONSTRAINT_NAME in existing_constraints:
        # Some development databases installed the constraint before their
        # Alembic version table was advanced. Treat that state as complete.
        return

    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                """
            SELECT patient_id, logged_date, COUNT(*) AS entry_count
            FROM environmental_factors
            GROUP BY patient_id, logged_date
            HAVING COUNT(*) > 1
            LIMIT 1
            """
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot enforce one daily lifestyle check-in while duplicate rows exist. "
            "Run `python -m scripts.cleanup_duplicate_factors` to review every saved answer in the affected "
            "patient/day groups. Complementary answers are merged; same-field conflicts require the helper's "
            "explicit --resolutions file. Then rerun it with an explicit --keep earliest or --keep latest choice. "
            "After the cleanup, run alembic upgrade head again."
        )

    op.create_unique_constraint(
        CONSTRAINT_NAME,
        "environmental_factors",
        ["patient_id", "logged_date"],
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "environmental_factors", type_="unique")
