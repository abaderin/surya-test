"""add cancelled statuses for files and tasks

Revision ID: 0004_cancelled_statuses
Revises: 0003_detection_tasks_and_boxes
Create Date: 2026-05-23
"""

from alembic import op

revision = "0004_cancelled_statuses"
down_revision = "0003_detection_tasks_and_boxes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE file_status ADD VALUE IF NOT EXISTS 'cancelling'")
    op.execute("ALTER TYPE file_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.execute("ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL enums do not support dropping values safely in-place.
    pass
