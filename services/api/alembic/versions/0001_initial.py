"""initial baseline

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The FastAPI service also creates metadata on startup to keep local greenfield setup simple.
    # This migration is intentionally lightweight scaffolding for future schema evolution.
    pass


def downgrade() -> None:
    pass
