from pydantic import BaseModel, Field


class InterestEvidence(BaseModel):
    subreddit: str
    activity_type: str
    text: str


class InterestTopic(BaseModel):
    key: str
    label: str
    confidence: float
    signals: list[str] = Field(default_factory=list)


class InterestExtractionResult(BaseModel):
    topics: list[InterestTopic] = Field(default_factory=list)


class RetrievalQuery(BaseModel):
    query: str
    source: str
    city: str = "New York City"
    category: str = "culture"


class RetrievalPlan(BaseModel):
    queries: list[RetrievalQuery] = Field(default_factory=list)


class CandidateEvent(BaseModel):
    source: str
    source_kind: str = "connector"
    source_event_key: str
    venue_name: str
    neighborhood: str
    address: str
    city: str = "New York City"
    state: str = "NY"
    postal_code: str | None = None
    title: str
    summary: str | None = None
    category: str = "culture"
    starts_at: str
    ends_at: str | None = None
    latitude: float
    longitude: float
    apple_place_id: str | None = None
    ticket_url: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    source_confidence: float = 0.7
    topic_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class RankedCandidate(BaseModel):
    venue_name: str
    title: str
    score: float
    score_band: str
    reasons: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class RankedCandidateList(BaseModel):
    items: list[RankedCandidate] = Field(default_factory=list)


class RecommendationReasons(BaseModel):
    reasons: list[str] = Field(default_factory=list)
