from sqlalchemy import JSON, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RedditActivity(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reddit_activities"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    activity_type: Mapped[str] = mapped_column(String(32), index=True)
    subreddit: Mapped[str] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(nullable=True)
    occurred_at: Mapped[str] = mapped_column(String(64))


class ProfileRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profile_runs"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="gemini")
    model_name: Mapped[str] = mapped_column(String(128), default="gemini-2.5-flash")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)


class UserInterestProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_interest_profiles"
    __table_args__ = (UniqueConstraint("user_id", "topic_key", name="uq_user_interest_topic"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_key: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_signals_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    boosted: Mapped[bool] = mapped_column(default=False)
    muted: Mapped[bool] = mapped_column(default=False)


class UserInterestOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_interest_overrides"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_key: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(32), default="mute")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
