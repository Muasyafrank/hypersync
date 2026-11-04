"""make bp_readings.heart_rate nullable

Pulse is optional in the API schema (``heart_rate: int | None``) and on the
"Log reading" form, but migration 8371df067ab9 had made the column NOT NULL, so
saving a reading without a pulse failed with an IntegrityError (HTTP 500).

Revision ID: d4e8a1b6f203
Revises: a7c3e91b5d20
Create Date: 2026-10-29 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8a1b6f203'
down_revision: Union[str, Sequence[str], None] = 'a7c3e91b5d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow readings to be saved without a pulse."""
    op.alter_column('bp_readings', 'heart_rate', existing_type=sa.INTEGER(), nullable=True)


def downgrade() -> None:
    """Restore NOT NULL.

    Fails if any reading has no pulse: inventing a value for those rows would
    corrupt the data, so they have to be dealt with deliberately first.
    """
    op.alter_column('bp_readings', 'heart_rate', existing_type=sa.INTEGER(), nullable=False)
