"""device tokens do not expire

Revision ID: 3b7c1d2e9f40
Revises: e9579aa47141
Create Date: 2026-09-08 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3b7c1d2e9f40"
down_revision: str | None = "e9579aa47141"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A poster on the wall has to keep working on day three. Whatever had
    # lapsed by the clock is live again; the arbiter revokes what should stop.
    op.drop_column("device", "expires_at")
    # `EventAction` gains DEVICE_REMOVED: VARCHAR without a check constraint,
    # so nothing to do here.


def downgrade() -> None:
    op.add_column(
        "device",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now() + interval '14 hours'"),
        ),
    )
    op.alter_column("device", "expires_at", server_default=None)
