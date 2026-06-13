"""sources wiki_pages page_links

Revision ID: 56b57887b971
Revises: 0002_org_kb
"""
from alembic import op
import sqlalchemy as sa


revision = '56b57887b971'
down_revision = '0002_org_kb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kb_id", sa.Uuid(), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("job_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sources_kb_id", "sources", ["kb_id"])
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kb_id", sa.Uuid(), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("slug", sa.String(512), nullable=False),
        sa.Column("page_type", sa.String(32), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("frontmatter", sa.JSON(), nullable=True),
        sa.Column("source_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("kb_id", "slug", name="uq_wiki_kb_slug"),
    )
    op.create_index("ix_wiki_pages_kb_id", "wiki_pages", ["kb_id"])
    op.create_table(
        "page_links",
        sa.Column("from_page_id", sa.Uuid(), sa.ForeignKey("wiki_pages.id"), primary_key=True),
        sa.Column("to_slug", sa.String(512), primary_key=True),
        sa.Column("to_page_id", sa.Uuid(), sa.ForeignKey("wiki_pages.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("page_links")
    op.drop_index("ix_wiki_pages_kb_id", "wiki_pages")
    op.drop_table("wiki_pages")
    op.drop_index("ix_sources_kb_id", "sources")
    op.drop_table("sources")
