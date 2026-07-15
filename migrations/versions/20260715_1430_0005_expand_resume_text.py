"""expand resume extracted text

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-15 14:30:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "resumes",
        "extracted_text",
        existing_type=sa.Text(),
        type_=mysql.MEDIUMTEXT(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "resumes",
        "extracted_text",
        existing_type=mysql.MEDIUMTEXT(),
        type_=sa.Text(),
        existing_nullable=False,
    )
