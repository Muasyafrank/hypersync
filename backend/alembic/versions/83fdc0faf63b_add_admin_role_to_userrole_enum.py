"""add admin role to userrole enum

Revision ID: 83fdc0faf63b
Revises: c790bf7f5d7e
Create Date: 2026-08-10 18:18:45.947240

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83fdc0faf63b'
down_revision: Union[str, Sequence[str], None] = 'c790bf7f5d7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
