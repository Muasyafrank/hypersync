"""add cascade delete to user foreign keys

Revision ID: 443e06b28f84
Revises: 83fdc0faf63b
Create Date: 2026-08-16 21:12:22.033460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '443e06b28f84'
down_revision: Union[str, Sequence[str], None] = '83fdc0faf63b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.drop_constraint('patient_profiles_user_id_fkey', 'patient_profiles', type_='foreignkey')
    op.create_foreign_key(
        'patient_profiles_user_id_fkey', 'patient_profiles', 'users',
        ['user_id'], ['user_id'], ondelete='CASCADE'
    )

    op.drop_constraint('bp_readings_patient_id_fkey', 'bp_readings', type_='foreignkey')
    op.create_foreign_key(
        'bp_readings_patient_id_fkey', 'bp_readings', 'users',
        ['patient_id'], ['user_id'], ondelete='CASCADE'
    )

    op.drop_constraint('refresh_tokens_user_id_fkey', 'refresh_tokens', type_='foreignkey')
    op.create_foreign_key(
        'refresh_tokens_user_id_fkey', 'refresh_tokens', 'users',
        ['user_id'], ['user_id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('patient_profiles_user_id_fkey', 'patient_profiles', type_='foreignkey')
    op.create_foreign_key('patient_profiles_user_id_fkey', 'patient_profiles', 'users', ['user_id'], ['user_id'])

    op.drop_constraint('bp_readings_patient_id_fkey', 'bp_readings', type_='foreignkey')
    op.create_foreign_key('bp_readings_patient_id_fkey', 'bp_readings', 'users', ['patient_id'], ['user_id'])

    op.drop_constraint('refresh_tokens_user_id_fkey', 'refresh_tokens', type_='foreignkey')
    op.create_foreign_key('refresh_tokens_user_id_fkey', 'refresh_tokens', 'users', ['user_id'], ['user_id'])