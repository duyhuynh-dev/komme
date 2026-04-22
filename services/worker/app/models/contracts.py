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
    venue_name: str
    neighborhood: str
    title: str
    starts_at: str
    latitude: float
    longitude: float
    min_price: float | None = None
    max_price: float | None = None
    source_confidence: float = 0.7
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

