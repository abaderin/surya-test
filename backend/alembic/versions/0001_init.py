"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    file_status = postgresql.ENUM(
        "new",
        "validation",
        "validation_failed",
        "in_progress",
        "failed",
        "done",
        name="file_status",
        create_type=False,
    )
    task_status = postgresql.ENUM("new", "in_progress", "failed", "done", name="task_status", create_type=False)
    task_type = postgresql.ENUM(
        "validation",
        "render_page",
        "layout",
        "ocr",
        "image_extraction",
        "meta_extraction",
        name="task_type",
        create_type=False,
    )
    page_status = postgresql.ENUM("new", "in_progress", "failed", "done", name="page_status", create_type=False)

    bind = op.get_bind()
    file_status.create(bind, checkfirst=True)
    task_status.create(bind, checkfirst=True)
    task_type.create(bind, checkfirst=True)
    page_status.create(bind, checkfirst=True)

    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("status", file_status, nullable=False),
        sa.Column("pages_count", sa.Integer(), nullable=True),
        sa.Column("progress_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cover_path", sa.String(length=1024), nullable=True),
        sa.Column("source_path", sa.String(length=1024), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column("image_path", sa.String(length=1024), nullable=True),
        sa.Column("status", page_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pages.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("bbox_px", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bbox_norm", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("polygon_px", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("color_key", sa.String(length=64), nullable=False),
        sa.Column("raw_surya", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("artifact_path", sa.String(length=1024), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pages.id"), nullable=True),
        sa.Column("type", task_type, nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_files_status_created_at", "files", ["status", "created_at"])
    op.create_index("ix_pages_file_number", "pages", ["file_id", "page_number"], unique=True)
    op.create_index("ix_tasks_status_created_at", "tasks", ["status", "created_at"])
    op.create_index("ix_tasks_file_status", "tasks", ["file_id", "status"])
    op.create_index("ix_blocks_page_order", "blocks", ["page_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_blocks_page_order", table_name="blocks")
    op.drop_index("ix_tasks_file_status", table_name="tasks")
    op.drop_index("ix_tasks_status_created_at", table_name="tasks")
    op.drop_index("ix_pages_file_number", table_name="pages")
    op.drop_index("ix_files_status_created_at", table_name="files")
    op.drop_table("tasks")
    op.drop_table("blocks")
    op.drop_table("pages")
    op.drop_table("files")

    bind = op.get_bind()
    postgresql.ENUM(name="page_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="task_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="task_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="file_status").drop(bind, checkfirst=True)
