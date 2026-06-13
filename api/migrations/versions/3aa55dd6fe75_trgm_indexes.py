"""trgm indexes

Revision ID: 3aa55dd6fe75
Revises: 56b57887b971
"""
from alembic import op
import sqlalchemy as sa


revision = '3aa55dd6fe75'
down_revision = '56b57887b971'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pg_trgm 扩展已在 0001 基线启用；此处为标题/正文建 GIN trgm 索引加速 LIKE 子串检索
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_wiki_title_trgm "
        "ON wiki_pages USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_wiki_content_trgm "
        "ON wiki_pages USING gin (content_md gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_wiki_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_wiki_title_trgm")
