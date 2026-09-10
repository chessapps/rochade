"""a tournament chooses its pairing program

Revision ID: 7d2f4a8c1e55
Revises: 5c2e7a9d1b04
Create Date: 2026-09-10 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d2f4a8c1e55"
down_revision: str | None = "5c2e7a9d1b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tournament",
        sa.Column("manager", sa.String(length=32), server_default="vega", nullable=False),
    )
    # A tournament that already holds sections was run on whatever program
    # those sections came from; the first one decides.
    op.execute(
        """
        UPDATE tournament SET manager = first.manager
        FROM (
            SELECT DISTINCT ON (tournament_id) tournament_id, manager
            FROM section ORDER BY tournament_id, created_at, name
        ) AS first
        WHERE first.tournament_id = tournament.id
        """
    )


def downgrade() -> None:
    op.drop_column("tournament", "manager")
