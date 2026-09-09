"""a tournament may hold a join code

Revision ID: e9579aa47141
Revises: e89c5e8380ff
Create Date: 2026-09-07 22:12:21.502839
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9579aa47141"
down_revision: str | None = "e89c5e8380ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tournament", sa.Column("join_code", sa.String(length=12), nullable=True))
    # Named, so the downgrade has something to drop and every backend agrees.
    op.create_unique_constraint("uq_tournament_join_code", "tournament", ["join_code"])
    # `PrincipalKind` gains ANONYMOUS in the same change and needs nothing here:
    # these enums are VARCHAR without a check constraint, by SQLAlchemy default.


def downgrade() -> None:
    op.drop_constraint("uq_tournament_join_code", "tournament", type_="unique")
    op.drop_column("tournament", "join_code")
