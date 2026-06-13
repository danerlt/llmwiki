"""drop redundant users email unique constraint

Revision ID: 28cb56cf183a
Revises: 6d1727068eb0
"""
from alembic import op
import sqlalchemy as sa


revision = '28cb56cf183a'
down_revision = '6d1727068eb0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 迁移 0002 给 users.email 同时建了列级 UNIQUE 约束(users_email_key)和唯一索引(ix_users_email)，
    # 同一列两套唯一性冗余。模型只声明唯一索引，故删掉冗余约束，唯一性仍由 ix_users_email 保证。
    op.drop_constraint("users_email_key", "users", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("users_email_key", "users", ["email"])
