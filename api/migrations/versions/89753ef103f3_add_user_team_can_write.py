"""add user_team can_write

Revision ID: 89753ef103f3
Revises: 1aaf7f57b240
"""
from alembic import op
import sqlalchemy as sa


revision = '89753ef103f3'
down_revision = '1aaf7f57b240'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_teams",
        sa.Column("can_write", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("user_teams", "can_write")
