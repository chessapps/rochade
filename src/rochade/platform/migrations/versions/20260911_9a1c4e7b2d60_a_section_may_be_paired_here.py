"""a section may be paired here

Revision ID: 9a1c4e7b2d60
Revises: 7d2f4a8c1e55
Create Date: 2026-09-11 00:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a1c4e7b2d60"
down_revision: str | None = "7d2f4a8c1e55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # What a player line needs that a manager's export never gave us, and the
    # one thing that happens to a player mid-event that no import can express.
    op.add_column(
        "section_player",
        sa.Column("sex", sa.String(length=1), server_default="", nullable=False),
    )
    op.add_column(
        "section_player",
        sa.Column("birth_date", sa.String(length=10), server_default="", nullable=False),
    )
    op.add_column("section_player", sa.Column("withdrawn_from_round", sa.Integer(), nullable=True))
    op.add_column("section", sa.Column("top_board_colour", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("section", "top_board_colour")
    op.drop_column("section_player", "withdrawn_from_round")
    op.drop_column("section_player", "birth_date")
    op.drop_column("section_player", "sex")
