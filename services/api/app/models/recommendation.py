from sqlalchemy import JSON, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

DIGEST_CLICK_FEEDBACK_ACTION = "digest_click"
DIGEST_SECURITY_CLICK_FEEDBACK_ACTION = "digest_security_click"
PLANNER_COMMIT_FEEDBACK_ACTION = "planner_commit"
PLANNER_SWAP_FEEDBACK_ACTION = "planner_swap"


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


class DigestDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "digest_deliveries"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recommendation_run_id: Mapped[str] = mapped_column(
        ForeignKey("recommendation_runs.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), default="resend")
    status: Mapped[str] = mapped_column(String(32), default="queued")
