from pydantic import BaseModel


class MapTokenResponse(BaseModel):
    enabled: bool
    token: str | None = None
