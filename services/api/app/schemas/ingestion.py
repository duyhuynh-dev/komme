from pydantic import BaseModel, Field


class IngestCandidateItem(BaseModel):
    source: str
    source_kind: str = "connector"
    source_event_key: str
    title: str
    summary: str | None = None
    category: str = "culture"
    starts_at: str
    ends_at: str | None = None
    venue_name: str
    neighborhood: str = "NYC"
    address: str
    city: str = "New York City"
    state: str = "NY"
    postal_code: str | None = None
    latitude: float
    longitude: float
    apple_place_id: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    ticket_url: str | None = None
    source_confidence: float = 0.7
    topic_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CandidateIngestPayload(BaseModel):
    items: list[IngestCandidateItem] = Field(default_factory=list)


class CandidateIngestResponse(BaseModel):
    accepted: int = 0
    sources_created: int = 0
    venues_created: int = 0
    events_created: int = 0
    occurrences_created: int = 0
