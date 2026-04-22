from pydantic import BaseModel


class MapTokenResponse(BaseModel):
    token: str

