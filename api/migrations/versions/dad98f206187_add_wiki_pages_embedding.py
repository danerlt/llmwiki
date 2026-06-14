"""add wiki_pages embedding

Revision ID: dad98f206187
Revises: 89753ef103f3
"""
from alembic import op
import sqlalchemy as sa


revision = 'dad98f206187'
down_revision = '89753ef103f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wiki_pages", sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("wiki_pages", "embedding")
