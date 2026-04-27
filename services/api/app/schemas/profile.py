from pydantic import BaseModel, Field
from app.schemas.common import OkResponse
from app.schemas.recommendations import MapContext


class InterestTopic(BaseModel):
    id: str
    label: str
    confidence: float
    sourceProvider: str = "unknown"
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


class AnchorSaveResponse(OkResponse):
    mapContext: MapContext = Field(default_factory=MapContext)


class EmailPreferenceResponse(BaseModel):
    weeklyDigestEnabled: bool = True
    digestDay: str = "Tuesday"
    digestTimeLocal: str = "09:00"
    timezone: str = "America/New_York"


class EmailPreferencePayload(BaseModel):
    weeklyDigestEnabled: bool = True
    digestDay: str = "Tuesday"
    digestTimeLocal: str = "09:00"
    timezone: str | None = None
