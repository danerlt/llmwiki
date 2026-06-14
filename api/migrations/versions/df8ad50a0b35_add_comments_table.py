"""add comments table

Revision ID: df8ad50a0b35
Revises: e92b82749b50
"""
from alembic import op
import sqlalchemy as sa


revision = 'df8ad50a0b35'
down_revision = 'e92b82749b50'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_page_id", "comments", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_page_id", table_name="comments")
    op.drop_table("comments")
