from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EventSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_sources"

    kind: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128), unique=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Venue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "venues"
    __table_args__ = (UniqueConstraint("name", "address", name="uq_venues_name_address"),)

    name: Mapped[str] = mapped_column(String(255))
    neighborhood: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(128), default="New York City")
    state: Mapped[str] = mapped_column(String(64), default="NY")
    postal_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    apple_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    geocodes = relationship("VenueGeocode", back_populates="venue", cascade="all, delete-orphan")


class VenueGeocode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "venue_geocodes"

    venue_id: Mapped[str] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="apple")
    provider_place_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_response_json: Mapped[dict] = mapped_column(JSON, default=dict)

    venue = relationship("Venue", back_populates="geocodes")


class CanonicalEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "canonical_events"

    source_id: Mapped[str] = mapped_column(ForeignKey("event_sources.id", ondelete="CASCADE"), index=True)
    source_event_key: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class EventOccurrence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_occurrences"

    event_id: Mapped[str] = mapped_column(ForeignKey("canonical_events.id", ondelete="CASCADE"), index=True)
    venue_id: Mapped[str] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[str] = mapped_column(String(64), index=True)
    ends_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    ticket_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
