"""org and kb tables

Revision ID: 0002_org_kb
Revises: 0001_baseline
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_org_kb"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("departments.id"), nullable=True),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id"), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "user_teams",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.id"), primary_key=True),
    )
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("scope_ref_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.UniqueConstraint("scope_type", "scope_ref_id", name="uq_kb_scope"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_bases")
    op.drop_table("user_teams")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    op.drop_table("teams")
    op.drop_table("departments")
