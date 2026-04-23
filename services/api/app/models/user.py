from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")

    oauth_connections = relationship("OAuthConnection", back_populates="user", cascade="all, delete-orphan")
    constraints = relationship("UserConstraint", back_populates="user", cascade="all, delete-orphan")
    anchors = relationship("UserAnchorLocation", back_populates="user", cascade="all, delete-orphan")
    email_preferences = relationship("EmailPreference", back_populates="user", cascade="all, delete-orphan")


class OAuthConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    provider_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_csv: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="oauth_connections")


class UserConstraint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_constraints"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_constraints_user"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    city: Mapped[str] = mapped_column(String(128), default="New York City")
    neighborhood: Mapped[str | None] = mapped_column(String(128), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    radius_miles: Mapped[int] = mapped_column(Integer, default=8)
    budget_level: Mapped[str] = mapped_column(String(32), default="under_75")
    preferred_days_csv: Mapped[str] = mapped_column(Text, default="Thursday,Friday,Saturday")
    social_mode: Mapped[str] = mapped_column(String(32), default="either")

    user = relationship("User", back_populates="constraints")


class UserAnchorLocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_anchor_locations"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(32), default="zip")
    neighborhood: Mapped[str | None] = mapped_column(String(128), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_session_only: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="anchors")


class EmailPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "email_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_email_preferences_user"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    weekly_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_day: Mapped[str] = mapped_column(String(32), default="Tuesday")
    digest_time_local: Mapped[str] = mapped_column(String(16), default="09:00")

    user = relationship("User", back_populates="email_preferences")
