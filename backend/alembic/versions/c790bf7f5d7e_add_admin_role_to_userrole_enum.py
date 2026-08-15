"""add admin role to userrole enum

Revision ID: c790bf7f5d7e
Revises: f736d935c113
Create Date: 2026-08-10 17:45:46.620674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c790bf7f5d7e'
down_revision: Union[str, Sequence[str], None] = 'f736d935c113'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'admin'")
   



def downgrade() -> None:
    """Downgrade schema."""
    pass
