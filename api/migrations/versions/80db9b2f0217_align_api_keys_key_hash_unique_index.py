"""align api_keys key_hash unique index

Revision ID: 80db9b2f0217
Revises: 63fd001eaa4d
"""
from alembic import op
import sqlalchemy as sa


revision = '80db9b2f0217'
down_revision = '63fd001eaa4d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 模型 ApiKey.key_hash 声明 unique=True, index=True（期望唯一索引），
    # 但原迁移 b991ece5479a 建的是唯一约束 uq_api_keys_key_hash —— 对齐为唯一索引以消除漂移。
    op.drop_constraint(op.f("uq_api_keys_key_hash"), "api_keys", type_="unique")
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.create_unique_constraint(op.f("uq_api_keys_key_hash"), "api_keys", ["key_hash"])
