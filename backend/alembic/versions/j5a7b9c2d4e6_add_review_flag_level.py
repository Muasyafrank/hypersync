"""snapshot the treatment-review severity with each clinician review

Revision ID: j5a7b9c2d4e6
Revises: i4e6f8a2b3c5
Create Date: 2026-11-25 10:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "j5a7b9c2d4e6"
down_revision: str | Sequence[str] | None = "i4e6f8a2b3c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "treatment_reviews",
        sa.Column("flag_level", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("treatment_reviews", "flag_level")
