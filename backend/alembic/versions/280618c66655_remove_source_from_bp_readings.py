"""remove source from bp readings

Revision ID: 280618c66655
Revises: bcfa70662a91
Create Date: 2026-08-20 15:13:10.082861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '280618c66655'
down_revision: Union[str, Sequence[str], None] = 'bcfa70662a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
