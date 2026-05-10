from pydantic import BaseModel, Field


class OkResponse(BaseModel):
    ok: bool = True


class SupplySyncResponse(BaseModel):
    ok: bool = True
    candidateCount: int = 0
    realEventCount: int = 0
    ticketUrlCount: int = 0
    accepted: int = 0
    sourcesCreated: int = 0
    venuesCreated: int = 0
    eventsCreated: int = 0
    occurrencesCreated: int = 0
    sourceCounts: dict[str, int] = Field(default_factory=dict)
    rejectedCounts: dict[str, int] = Field(default_factory=dict)
    fallbackUsed: bool = False
    status: str = "synced"
