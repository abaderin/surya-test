"""add detection task type and boxes table

Revision ID: 0003_detection_tasks_and_boxes
Revises: 0002_task_deleted_flag
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_detection_tasks_and_boxes"
down_revision = "0002_task_deleted_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE task_type ADD VALUE IF NOT EXISTS 'detection'")

    op.create_table(
        "detection_boxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pages.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("bbox_px", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bbox_norm", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("polygon_px", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("raw_surya", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_detection_boxes_page_order", "detection_boxes", ["page_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_detection_boxes_page_order", table_name="detection_boxes")
    op.drop_table("detection_boxes")
