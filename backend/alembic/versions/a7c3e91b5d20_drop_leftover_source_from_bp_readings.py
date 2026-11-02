"""drop leftover source column from bp_readings

Revision ID: a7c3e91b5d20
Revises: 1cc28f2d4580
Create Date: 2026-09-28 10:05:00.000000

Migration 280618c66655 ("remove source from bp readings") was generated
with an empty upgrade(), so on any database built from scratch the
NOT NULL `source` column was never dropped. The BPReading model doesn't
define it, so every INSERT failed with a NotNullViolation.

This drops it for real. IF EXISTS keeps it safe on databases where the
column was already removed by hand.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c3e91b5d20'
down_revision: Union[str, Sequence[str], None] = '1cc28f2d4580'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE bp_readings DROP COLUMN IF EXISTS source")


def downgrade() -> None:
    # Nullable on purpose: re-adding it as NOT NULL would fail on any
    # table that already has rows.
    op.execute("ALTER TABLE bp_readings ADD COLUMN IF NOT EXISTS source VARCHAR")
