"""add favorites table

Revision ID: 4b50a583db74
Revises: aa979a660c35
"""
from alembic import op
import sqlalchemy as sa


revision = '4b50a583db74'
down_revision = 'aa979a660c35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["page_id"], ["wiki_pages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "page_id", name="uq_favorite_user_page"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorites_page_id", "favorites", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_favorites_page_id", table_name="favorites")
    op.drop_index("ix_favorites_user_id", table_name="favorites")
    op.drop_table("favorites")
