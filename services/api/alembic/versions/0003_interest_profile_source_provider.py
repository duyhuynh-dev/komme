"""add interest profile source provider

Revision ID: 0003_interest_profile_source_provider
Revises: 0002_planner_sessions
Create Date: 2026-04-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_interest_profile_source_provider"
down_revision: str | None = "0002_planner_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_interest_profiles",
        sa.Column("source_provider", sa.String(length=64), server_default="unknown", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_interest_profiles", "source_provider")
