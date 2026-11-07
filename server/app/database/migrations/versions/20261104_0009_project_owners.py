"""project owners

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-04 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('project_owner_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_projects_project_owner_id'), ['project_owner_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_projects_project_owner_id_users'), 'users', ['project_owner_id'], ['id'], ondelete='SET NULL')

    # Until now a project belonged to whoever created it.
    op.execute('UPDATE projects SET project_owner_id = created_by_id')


def downgrade() -> None:
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_projects_project_owner_id_users'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_projects_project_owner_id'))
        batch_op.drop_column('project_owner_id')
