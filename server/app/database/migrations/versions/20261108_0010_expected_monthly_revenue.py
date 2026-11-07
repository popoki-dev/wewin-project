"""expected monthly revenue

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-08 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('project_revenue_forecasts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('year', sa.SmallInteger(), nullable=False),
    sa.Column('month', sa.SmallInteger(), nullable=False),
    sa.Column('amount_cents', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_revenue_forecasts_project_id_projects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_project_revenue_forecasts')),
    sa.UniqueConstraint('project_id', 'year', 'month', name=op.f('uq_project_revenue_forecasts_project_id'))
    )
    with op.batch_alter_table('project_revenue_forecasts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_project_revenue_forecasts_project_id'), ['project_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('project_revenue_forecasts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_project_revenue_forecasts_project_id'))

    op.drop_table('project_revenue_forecasts')
