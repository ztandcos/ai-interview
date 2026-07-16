"""create interview tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-15 16:30:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("focus", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interviews_resume_id"), "interviews", ["resume_id"], unique=False)
    op.create_index(op.f("ix_interviews_status"), "interviews", ["status"], unique=False)
    op.create_index(op.f("ix_interviews_user_id"), "interviews", ["user_id"], unique=False)

    op.create_table(
        "interview_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_messages_interview_id"),
        "interview_messages",
        ["interview_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interview_messages_message_type"),
        "interview_messages",
        ["message_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interview_messages_user_id"),
        "interview_messages",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "interview_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths_json", sa.Text(), nullable=False),
        sa.Column("weaknesses_json", sa.Text(), nullable=False),
        sa.Column("suggestions_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interview_id"),
    )
    op.create_index(
        op.f("ix_interview_reports_user_id"),
        "interview_reports",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_reports_user_id"), table_name="interview_reports")
    op.drop_table("interview_reports")
    op.drop_index(op.f("ix_interview_messages_user_id"), table_name="interview_messages")
    op.drop_index(op.f("ix_interview_messages_message_type"), table_name="interview_messages")
    op.drop_index(op.f("ix_interview_messages_interview_id"), table_name="interview_messages")
    op.drop_table("interview_messages")
    op.drop_index(op.f("ix_interviews_user_id"), table_name="interviews")
    op.drop_index(op.f("ix_interviews_status"), table_name="interviews")
    op.drop_index(op.f("ix_interviews_resume_id"), table_name="interviews")
    op.drop_table("interviews")
