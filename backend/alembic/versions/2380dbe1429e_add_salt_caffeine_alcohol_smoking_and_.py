"""add salt, caffeine, alcohol, smoking, and activity to environmental_factors

Revision ID: 2380dbe1429e
Revises: db1602290668
Create Date: 2026-09-09 15:10:55.583812
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2380dbe1429e"
down_revision: Union[str, Sequence[str], None] = "db1602290668"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create PostgreSQL enum type
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'intakelevel'
            ) THEN
                CREATE TYPE intakelevel AS ENUM (
                    'none',
                    'low',
                    'moderate',
                    'high'
                );
            END IF;
        END
        $$;
    """)

    # Add columns
    op.add_column(
        "environmental_factors",
        sa.Column(
            "salt_intake",
            sa.Enum(
                "none",
                "low",
                "moderate",
                "high",
                name="intakelevel",
                create_type=False
            ),
            nullable=True
        )
    )

    op.add_column(
        "environmental_factors",
        sa.Column(
            "caffeine_intake",
            sa.Enum(
                "none",
                "low",
                "moderate",
                "high",
                name="intakelevel",
                create_type=False
            ),
            nullable=True
        )
    )

    op.add_column(
        "environmental_factors",
        sa.Column(
            "alcohol_consumed",
            sa.Boolean(),
            nullable=True
        )
    )

    op.add_column(
        "environmental_factors",
        sa.Column(
            "smoked",
            sa.Boolean(),
            nullable=True
        )
    )

    op.add_column(
        "environmental_factors",
        sa.Column(
            "physical_activity_minutes",
            sa.Integer(),
            nullable=True
        )
    )


def downgrade() -> None:
    # Drop columns first
    op.drop_column(
        "environmental_factors",
        "physical_activity_minutes"
    )

    op.drop_column(
        "environmental_factors",
        "smoked"
    )

    op.drop_column(
        "environmental_factors",
        "alcohol_consumed"
    )

    op.drop_column(
        "environmental_factors",
        "caffeine_intake"
    )

    op.drop_column(
        "environmental_factors",
        "salt_intake"
    )

    # Drop enum type
    op.execute("""
        DROP TYPE IF EXISTS intakelevel;
    """)