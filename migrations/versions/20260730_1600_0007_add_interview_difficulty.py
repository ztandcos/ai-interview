"""add interview difficulty

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-30 16:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column(
            "difficulty",
            sa.String(length=20),
            server_default="medium",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("interviews", "difficulty")
