"""add user is_active

Revision ID: 8bfe1d1cf0fa
Revises: ff5e58059194
"""
from alembic import op
import sqlalchemy as sa


revision = '8bfe1d1cf0fa'
down_revision = 'ff5e58059194'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
