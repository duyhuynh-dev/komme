"""add planner sessions

Revision ID: 0002_planner_sessions
Revises: 0001_initial
Create Date: 2026-04-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_planner_sessions"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "planner_sessions",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("recommendation_run_id", sa.String(), nullable=True),
        sa.Column("recommendation_context_hash", sa.String(length=64), nullable=True),
        sa.Column("initial_route_snapshot", sa.JSON(), nullable=False),
        sa.Column("active_stop_event_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("budget_level", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_run_id"], ["recommendation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_planner_sessions_active_stop_event_id"), "planner_sessions", ["active_stop_event_id"])
    op.create_index(op.f("ix_planner_sessions_recommendation_context_hash"), "planner_sessions", ["recommendation_context_hash"])
    op.create_index(op.f("ix_planner_sessions_recommendation_run_id"), "planner_sessions", ["recommendation_run_id"])
    op.create_index(op.f("ix_planner_sessions_status"), "planner_sessions", ["status"])
    op.create_index(op.f("ix_planner_sessions_user_id"), "planner_sessions", ["user_id"])

    op.create_table(
        "planner_session_events",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("recommendation_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["planner_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_planner_session_events_created_at"), "planner_session_events", ["created_at"])
    op.create_index(op.f("ix_planner_session_events_event_type"), "planner_session_events", ["event_type"])
    op.create_index(op.f("ix_planner_session_events_recommendation_id"), "planner_session_events", ["recommendation_id"])
    op.create_index(op.f("ix_planner_session_events_session_id"), "planner_session_events", ["session_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_planner_session_events_session_id"), table_name="planner_session_events")
    op.drop_index(op.f("ix_planner_session_events_recommendation_id"), table_name="planner_session_events")
    op.drop_index(op.f("ix_planner_session_events_event_type"), table_name="planner_session_events")
    op.drop_index(op.f("ix_planner_session_events_created_at"), table_name="planner_session_events")
    op.drop_table("planner_session_events")

    op.drop_index(op.f("ix_planner_sessions_user_id"), table_name="planner_sessions")
    op.drop_index(op.f("ix_planner_sessions_status"), table_name="planner_sessions")
    op.drop_index(op.f("ix_planner_sessions_recommendation_run_id"), table_name="planner_sessions")
    op.drop_index(op.f("ix_planner_sessions_recommendation_context_hash"), table_name="planner_sessions")
    op.drop_index(op.f("ix_planner_sessions_active_stop_event_id"), table_name="planner_sessions")
    op.drop_table("planner_sessions")
