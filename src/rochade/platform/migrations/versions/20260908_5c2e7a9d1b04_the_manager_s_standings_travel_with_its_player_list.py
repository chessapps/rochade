"""the manager's standings travel with its player list

Revision ID: 5c2e7a9d1b04
Revises: 3b7c1d2e9f40
Create Date: 2026-09-08 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5c2e7a9d1b04"
down_revision: str | None = "3b7c1d2e9f40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("section", sa.Column("standings_after_round", sa.Integer(), nullable=True))
    op.add_column(
        "section",
        sa.Column("tiebreak_names", JSON, nullable=False, server_default="[]"),
    )
    op.add_column("section_player", sa.Column("points", sa.Float(), nullable=True))
    op.add_column(
        "section_player",
        sa.Column("tiebreaks", JSON, nullable=False, server_default="[]"),
    )
    op.add_column("section_player", sa.Column("rank", sa.Integer(), nullable=True))
    # `EventAction` gains STANDINGS_IMPORTED: VARCHAR without a check
    # constraint, so nothing to do here.


def downgrade() -> None:
    op.drop_column("section_player", "rank")
    op.drop_column("section_player", "tiebreaks")
    op.drop_column("section_player", "points")
    op.drop_column("section", "tiebreak_names")
    op.drop_column("section", "standings_after_round")
