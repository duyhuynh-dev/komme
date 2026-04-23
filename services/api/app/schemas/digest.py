from pydantic import BaseModel, Field

from app.schemas.recommendations import VenueRecommendationCard


class DigestPreviewResponse(BaseModel):
    recipientEmail: str
    subject: str
    preheader: str
    html: str
    text: str
    generatedAt: str
    items: list[VenueRecommendationCard] = Field(default_factory=list)


class DigestSendResponse(BaseModel):
    ok: bool = True
    recipientEmail: str
    provider: str = "resend"
    status: str = "sent"


class DigestBatchResponse(BaseModel):
    ok: bool = True
    processedUsers: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    status: str = "completed"
