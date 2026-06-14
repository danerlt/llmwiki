"""add answer_feedback table

Revision ID: aa979a660c35
Revises: b17ca4b2da9b
"""
from alembic import op
import sqlalchemy as sa


revision = 'aa979a660c35'
down_revision = 'b17ca4b2da9b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("vote", sa.String(length=8), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_answer_feedback_vote", "answer_feedback", ["vote"])


def downgrade() -> None:
    op.drop_index("ix_answer_feedback_vote", table_name="answer_feedback")
    op.drop_table("answer_feedback")
