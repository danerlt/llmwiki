"""add search_misses table

Revision ID: 63fd001eaa4d
Revises: dad98f206187
"""
from alembic import op
import sqlalchemy as sa


revision = '63fd001eaa4d'
down_revision = 'dad98f206187'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_misses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_misses_query", "search_misses", ["query"])


def downgrade() -> None:
    op.drop_index("ix_search_misses_query", table_name="search_misses")
    op.drop_table("search_misses")
