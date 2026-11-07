"""co-developer contact details

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-03 23:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('project_codevelopers', schema=None) as batch_op:
        # Optional; existing co-developers have none recorded.
        batch_op.add_column(sa.Column('contact', sa.String(length=300), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('project_codevelopers', schema=None) as batch_op:
        batch_op.drop_column('contact')
