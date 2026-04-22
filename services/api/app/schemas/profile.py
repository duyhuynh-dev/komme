from pydantic import BaseModel, Field


class InterestTopic(BaseModel):
    id: str
    label: str
    confidence: float
    sourceSignals: list[str] = Field(default_factory=list)
    boosted: bool = False
    muted: bool = False


class InterestListResponse(BaseModel):
    topics: list[InterestTopic]


class InterestListUpdate(BaseModel):
    topics: list[InterestTopic]


class UserConstraintPayload(BaseModel):
    city: str = "New York City"
    neighborhood: str | None = None
    zipCode: str | None = None
    radiusMiles: int = 8
    budgetLevel: str = "under_75"
    preferredDays: list[str] = Field(default_factory=lambda: ["Thursday", "Friday", "Saturday"])
    socialMode: str = "either"


class AnchorPayload(BaseModel):
    neighborhood: str | None = None
    zipCode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source: str

