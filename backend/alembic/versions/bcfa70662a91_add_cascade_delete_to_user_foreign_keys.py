"""add cascade delete to user foreign keys

Revision ID: bcfa70662a91
Revises: 443e06b28f84
Create Date: 2026-08-19 12:26:13.830242

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bcfa70662a91'
down_revision: Union[str, Sequence[str], None] = '443e06b28f84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
