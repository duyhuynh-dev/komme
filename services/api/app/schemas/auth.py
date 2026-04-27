from pydantic import BaseModel, Field


class ConnectedSourceHealth(BaseModel):
    connected: bool = False
    latestRunStatus: str | None = None
    latestRunAt: str | None = None
    stale: bool = False
    currentlyInfluencingRanking: bool = False
    healthReason: str | None = None


class AuthViewerResponse(BaseModel):
    userId: str
    email: str
    displayName: str | None = None
    isAuthenticated: bool
    isDemo: bool
    authMethod: str = "demo"
    redditConnected: bool
    redditConnectionMode: str = "none"
    spotifyConnected: bool = False
    spotifyTasteHealth: ConnectedSourceHealth = Field(default_factory=ConnectedSourceHealth)


class RedditConnectStartResponse(BaseModel):
    authorizeUrl: str


class SpotifyConnectStartResponse(BaseModel):
    authorizeUrl: str
