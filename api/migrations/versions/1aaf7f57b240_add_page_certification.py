"""add page certification

Revision ID: 1aaf7f57b240
Revises: d33d15cb9d99
"""
from alembic import op
import sqlalchemy as sa


revision = '1aaf7f57b240'
down_revision = 'd33d15cb9d99'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wiki_pages", sa.Column("verified_by", sa.Uuid(), nullable=True))
    op.add_column("wiki_pages", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_wiki_pages_verified_by", "wiki_pages", "users", ["verified_by"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_wiki_pages_verified_by", "wiki_pages", type_="foreignkey")
    op.drop_column("wiki_pages", "verified_at")
    op.drop_column("wiki_pages", "verified_by")
