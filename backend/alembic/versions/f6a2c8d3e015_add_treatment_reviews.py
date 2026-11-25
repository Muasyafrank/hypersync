"""add treatment_reviews: a dated record that a clinician reviewed a patient

Revision ID: f6a2c8d3e015
Revises: e5f1b7c2d904
Create Date: 2026-11-16 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6a2c8d3e015'
down_revision: Union[str, Sequence[str], None] = 'e5f1b7c2d904'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'treatment_reviews',
        sa.Column('review_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('clinician_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('note', sa.String(), nullable=True),
        sa.Column('flag_kind', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinician_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('review_id'),
    )
    op.create_index(op.f('ix_treatment_reviews_patient_id'), 'treatment_reviews', ['patient_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_treatment_reviews_patient_id'), table_name='treatment_reviews')
    op.drop_table('treatment_reviews')
