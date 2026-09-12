"""a tournament may be published

Revision ID: b4e8c2d1f7a3
Revises: 9a1c4e7b2d60
Create Date: 2026-09-11 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4e8c2d1f7a3"
down_revision: str | None = "9a1c4e7b2d60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Off for every tournament that exists: nothing becomes public by upgrading.
    op.add_column(
        "tournament",
        sa.Column("published", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("tournament", sa.Column("slug", sa.String(length=80), nullable=True))
    op.create_unique_constraint("uq_tournament_slug", "tournament", ["slug"])


def downgrade() -> None:
    op.drop_constraint("uq_tournament_slug", "tournament", type_="unique")
    op.drop_column("tournament", "slug")
    op.drop_column("tournament", "published")
