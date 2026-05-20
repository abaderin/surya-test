"""add deleted flag to tasks

Revision ID: 0002_task_deleted_flag
Revises: 0001_init
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_task_deleted_flag"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("tasks", "deleted", server_default=None)


def downgrade() -> None:
    op.drop_column("tasks", "deleted")
