"""add wiki_pages tags

Revision ID: b17ca4b2da9b
Revises: df8ad50a0b35
"""
from alembic import op
import sqlalchemy as sa


revision = 'b17ca4b2da9b'
down_revision = 'df8ad50a0b35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOT NULL + server_default '[]' 回填存量行，避免 NULL
    op.add_column(
        "wiki_pages",
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("wiki_pages", "tags")
