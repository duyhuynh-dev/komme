from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

DIGEST_CLICK_FEEDBACK_ACTION = "digest_click"
DIGEST_SECURITY_CLICK_FEEDBACK_ACTION = "digest_security_click"
PLANNER_COMMIT_FEEDBACK_ACTION = "planner_commit"
PLANNER_SWAP_FEEDBACK_ACTION = "planner_swap"
PLANNER_ATTENDED_FEEDBACK_ACTION = "planner_attended"
PLANNER_SKIPPED_FEEDBACK_ACTION = "planner_skipped"


class RecommendationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendation_runs"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="gemini")
    model_name: Mapped[str] = mapped_column(String(128), default="gemini-2.5-flash")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    viewport_json: Mapped[dict] = mapped_column(JSON, default=dict)


class VenueRecommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "venue_recommendations"
    __table_args__ = (UniqueConstraint("run_id", "venue_id", name="uq_run_venue"),)

    run_id: Mapped[str] = mapped_column(ForeignKey("recommendation_runs.id", ondelete="CASCADE"), index=True)
    venue_id: Mapped[str] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), index=True)
    event_occurrence_id: Mapped[str] = mapped_column(
        ForeignKey("event_occurrences.id", ondelete="CASCADE"),
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float] = mapped_column(Float)
    score_band: Mapped[str] = mapped_column(String(32), default="medium")
    reasons_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    travel_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    secondary_events_json: Mapped[list[dict]] = mapped_column(JSON, default=list)


class FeedbackEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feedback_events"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(32))
    reasons_json: Mapped[list[dict]] = mapped_column(JSON, default=list)


class PlannerSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planner_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recommendation_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recommendation_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    initial_route_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    active_stop_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    budget_level: Mapped[str] = mapped_column(String(32), default="under_75")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")


class PlannerSessionEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "planner_session_events"

    session_id: Mapped[str] = mapped_column(ForeignKey("planner_sessions.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class DigestDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digest_deliveries"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recommendation_run_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_runs.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), default="resend")
    status: Mapped[str] = mapped_column(String(32), default="queued")
