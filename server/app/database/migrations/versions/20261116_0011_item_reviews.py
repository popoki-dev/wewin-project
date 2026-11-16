"""reviews of expected revenue, co-developers and payments

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-16 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing items start out unreviewed, so their projects show the review badge.
    with op.batch_alter_table('project_revenue_forecasts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('leader_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('leader_reviewed_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('owner_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('owner_reviewed_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_project_revenue_forecasts_leader_reviewed_by_id_users'), 'users', ['leader_reviewed_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key(batch_op.f('fk_project_revenue_forecasts_owner_reviewed_by_id_users'), 'users', ['owner_reviewed_by_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('project_codevelopers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('leader_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('leader_reviewed_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('owner_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('owner_reviewed_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_project_codevelopers_leader_reviewed_by_id_users'), 'users', ['leader_reviewed_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key(batch_op.f('fk_project_codevelopers_owner_reviewed_by_id_users'), 'users', ['owner_reviewed_by_id'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('project_payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('leader_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('leader_reviewed_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('owner_reviewed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('owner_reviewed_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_project_payments_leader_reviewed_by_id_users'), 'users', ['leader_reviewed_by_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key(batch_op.f('fk_project_payments_owner_reviewed_by_id_users'), 'users', ['owner_reviewed_by_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('project_payments', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_project_payments_owner_reviewed_by_id_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_project_payments_leader_reviewed_by_id_users'), type_='foreignkey')
        batch_op.drop_column('owner_reviewed_by_id')
        batch_op.drop_column('owner_reviewed_at')
        batch_op.drop_column('leader_reviewed_by_id')
        batch_op.drop_column('leader_reviewed_at')

    with op.batch_alter_table('project_codevelopers', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_project_codevelopers_owner_reviewed_by_id_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_project_codevelopers_leader_reviewed_by_id_users'), type_='foreignkey')
        batch_op.drop_column('owner_reviewed_by_id')
        batch_op.drop_column('owner_reviewed_at')
        batch_op.drop_column('leader_reviewed_by_id')
        batch_op.drop_column('leader_reviewed_at')

    with op.batch_alter_table('project_revenue_forecasts', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_project_revenue_forecasts_owner_reviewed_by_id_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_project_revenue_forecasts_leader_reviewed_by_id_users'), type_='foreignkey')
        batch_op.drop_column('owner_reviewed_by_id')
        batch_op.drop_column('owner_reviewed_at')
        batch_op.drop_column('leader_reviewed_by_id')
        batch_op.drop_column('leader_reviewed_at')
