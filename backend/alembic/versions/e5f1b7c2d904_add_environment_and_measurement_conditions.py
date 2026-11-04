"""capture the physical environment and how each reading was taken

* environmental_factors.temperature_feel / noise_level: the day's surroundings.
* bp_readings.rested_before / stimulant_before: whether the reading was taken
  after resting, and without caffeine, smoking or exercise just before.

All columns are nullable, so existing rows are untouched ("not recorded").

Revision ID: e5f1b7c2d904
Revises: d4e8a1b6f203
Create Date: 2026-11-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f1b7c2d904'
down_revision: Union[str, Sequence[str], None] = 'd4e8a1b6f203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plain SQL for the enum types so the migration also works with `--sql`.
    op.execute("CREATE TYPE temperaturefeel AS ENUM ('cold', 'comfortable', 'hot')")
    op.execute("CREATE TYPE noiselevel AS ENUM ('quiet', 'moderate', 'loud')")

    op.add_column(
        'environmental_factors',
        sa.Column('temperature_feel', postgresql.ENUM(name='temperaturefeel', create_type=False), nullable=True),
    )
    op.add_column(
        'environmental_factors',
        sa.Column('noise_level', postgresql.ENUM(name='noiselevel', create_type=False), nullable=True),
    )
    op.add_column('bp_readings', sa.Column('rested_before', sa.Boolean(), nullable=True))
    op.add_column('bp_readings', sa.Column('stimulant_before', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('bp_readings', 'stimulant_before')
    op.drop_column('bp_readings', 'rested_before')
    op.drop_column('environmental_factors', 'noise_level')
    op.drop_column('environmental_factors', 'temperature_feel')
    op.execute("DROP TYPE noiselevel")
    op.execute("DROP TYPE temperaturefeel")
