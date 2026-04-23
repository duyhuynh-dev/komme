from pydantic import BaseModel


class OkResponse(BaseModel):
    ok: bool = True


class SupplySyncResponse(BaseModel):
    ok: bool = True
    candidateCount: int = 0
    accepted: int = 0
    sourcesCreated: int = 0
    venuesCreated: int = 0
    eventsCreated: int = 0
    occurrencesCreated: int = 0
    status: str = "synced"
