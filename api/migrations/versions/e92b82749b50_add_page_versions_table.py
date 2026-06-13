"""add page_versions table

Revision ID: e92b82749b50
Revises: 1245f96cd622
"""
from alembic import op
import sqlalchemy as sa


revision = 'e92b82749b50'
down_revision = '1245f96cd622'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("page_type", sa.String(length=32), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("edited_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"]),
        sa.ForeignKeyConstraint(["edited_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "version_no", name="uq_pageversion_page_no"),
    )
    op.create_index("ix_page_versions_page_id", "page_versions", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_page_versions_page_id", table_name="page_versions")
    op.drop_table("page_versions")
