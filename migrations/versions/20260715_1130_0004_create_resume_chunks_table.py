"""create resume chunks table

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-15 11:30:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("keywords_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resume_id",
            "chunk_index",
            name="uq_resume_chunks_resume_index",
        ),
    )
    op.create_index(op.f("ix_resume_chunks_resume_id"), "resume_chunks", ["resume_id"], unique=False)
    op.create_index(op.f("ix_resume_chunks_user_id"), "resume_chunks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_resume_chunks_user_id"), table_name="resume_chunks")
    op.drop_index(op.f("ix_resume_chunks_resume_id"), table_name="resume_chunks")
    op.drop_table("resume_chunks")
