"""promotion requests

Revision ID: 0d0abccd011f
Revises: 3aa55dd6fe75
"""
from alembic import op
import sqlalchemy as sa


revision = '0d0abccd011f'
down_revision = '3aa55dd6fe75'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promotion_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("page_id", sa.Uuid(), sa.ForeignKey("wiki_pages.id"), nullable=False),
        sa.Column("to_kb_id", sa.Uuid(), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_promotion_requests_status", "promotion_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_promotion_requests_status", "promotion_requests")
    op.drop_table("promotion_requests")
