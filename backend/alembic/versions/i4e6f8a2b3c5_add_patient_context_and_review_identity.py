"""add patient timezone, medication context and immutable reviewer name

Revision ID: i4e6f8a2b3c5
Revises: g7b3d9e4f126
Create Date: 2026-11-25 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "i4e6f8a2b3c5"
down_revision: str | Sequence[str] | None = "g7b3d9e4f126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "patient_profiles",
        sa.Column("timezone", sa.String(), nullable=False, server_default="Africa/Nairobi"),
    )
    op.add_column(
        "environmental_factors",
        sa.Column("medication_prescribed", sa.Boolean(), nullable=True),
    )
    # Existing medication answers mean the patient said they take prescribed
    # medication. New rows can explicitly record that no medication is taken.
    op.execute(
        """
        UPDATE environmental_factors
        SET medication_prescribed = TRUE
        WHERE medication_taken IS NOT NULL
        """
    )
    op.add_column(
        "treatment_reviews",
        sa.Column("clinician_name", sa.String(), nullable=True),
    )
    # Preserve attribution for existing reviews before future account changes.
    op.execute(
        """
        UPDATE treatment_reviews AS treatment_review
        SET clinician_name = clinician.full_name
        FROM users AS clinician
        WHERE treatment_review.clinician_id = clinician.user_id
        """
    )


def downgrade() -> None:
    op.drop_column("treatment_reviews", "clinician_name")
    op.drop_column("environmental_factors", "medication_prescribed")
    op.drop_column("patient_profiles", "timezone")
