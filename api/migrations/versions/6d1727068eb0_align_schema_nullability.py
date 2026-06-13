"""align schema nullability

Revision ID: 6d1727068eb0
Revises: 264d68a888c5
"""
from alembic import op
import sqlalchemy as sa


revision = '6d1727068eb0'
down_revision = '264d68a888c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 收敛漂移：模型推断这些列为 NOT NULL，但建表迁移里遗留为 nullable=True。
    # 先回填历史 NULL，确保 SET NOT NULL 在已有数据上安全；JSON 列回填为空容器。
    op.execute("UPDATE sources SET created_at = now() WHERE created_at IS NULL")
    op.execute("UPDATE wiki_pages SET created_at = now() WHERE created_at IS NULL")
    op.execute("UPDATE wiki_pages SET updated_at = now() WHERE updated_at IS NULL")
    op.execute("UPDATE wiki_pages SET frontmatter = '{}' WHERE frontmatter IS NULL")
    op.execute("UPDATE wiki_pages SET source_ids = '[]' WHERE source_ids IS NULL")
    op.execute("UPDATE promotion_requests SET created_at = now() WHERE created_at IS NULL")
    op.execute("UPDATE audit_events SET created_at = now() WHERE created_at IS NULL")

    op.alter_column(
        "sources", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
    op.alter_column(
        "wiki_pages", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
    op.alter_column(
        "wiki_pages", "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
    op.alter_column("wiki_pages", "frontmatter", existing_type=sa.JSON(), nullable=False)
    op.alter_column("wiki_pages", "source_ids", existing_type=sa.JSON(), nullable=False)
    op.alter_column(
        "promotion_requests", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )
    op.alter_column(
        "audit_events", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        "audit_events", "created_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.alter_column(
        "promotion_requests", "created_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.alter_column("wiki_pages", "source_ids", existing_type=sa.JSON(), nullable=True)
    op.alter_column("wiki_pages", "frontmatter", existing_type=sa.JSON(), nullable=True)
    op.alter_column(
        "wiki_pages", "updated_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.alter_column(
        "wiki_pages", "created_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.alter_column(
        "sources", "created_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
