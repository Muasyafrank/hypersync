"""recommendations.position: keep the order in which a batch was shown

A batch of recommendations is written in one transaction, so all its rows share
one created_at. Reading it back "newest first" therefore returned them in an
arbitrary order. `position` records the order explicitly.

Revision ID: g7b3d9e4f126
Revises: f6a2c8d3e015
Create Date: 2026-11-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7b3d9e4f126'
down_revision: Union[str, Sequence[str], None] = 'f6a2c8d3e015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recommendations', sa.Column('position', sa.Integer(), server_default='0', nullable=False))
    # Legacy rows have no record of their original display order. Give each
    # batch a deterministic order so reads are reproducible; the live endpoint
    # will replace the batch if its content/order differs from newly generated
    # advice.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                recommendation_id,
                ROW_NUMBER() OVER (
                    PARTITION BY patient_id, created_at
                    ORDER BY recommendation_id
                ) - 1 AS batch_position
            FROM recommendations
        )
        UPDATE recommendations AS recommendation
        SET position = ranked.batch_position
        FROM ranked
        WHERE recommendation.recommendation_id = ranked.recommendation_id
        """
    )


def downgrade() -> None:
    op.drop_column('recommendations', 'position')
