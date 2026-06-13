"""add user token_version

Revision ID: 1245f96cd622
Revises: 28cb56cf183a
"""
from alembic import op
import sqlalchemy as sa


revision = '1245f96cd622'
down_revision = '28cb56cf183a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default="0" 让存量行回填为 0；NOT NULL 与模型一致
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
