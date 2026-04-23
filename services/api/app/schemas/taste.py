from pydantic import BaseModel, Field


class ThemeCatalogItemResponse(BaseModel):
    id: str
    label: str
    description: str


class ThemeCatalogResponse(BaseModel):
    items: list[ThemeCatalogItemResponse] = Field(default_factory=list)


class ThemeEvidenceCountResponse(BaseModel):
    key: str
    count: int


class ThemeEvidenceSnippetResponse(BaseModel):
    type: str
    subreddit: str | None = None
    snippet: str
    permalink: str | None = None


class ThemeEvidenceResponse(BaseModel):
    matchedSubreddits: list[ThemeEvidenceCountResponse] = Field(default_factory=list)
    matchedKeywords: list[ThemeEvidenceCountResponse] = Field(default_factory=list)
    topExamples: list[ThemeEvidenceSnippetResponse] = Field(default_factory=list)
    providerNotes: list[str] = Field(default_factory=list)


class TasteThemeResponse(BaseModel):
    id: str
    label: str
    confidence: int
    confidenceLabel: str
    evidence: ThemeEvidenceResponse


class TasteProfileResponse(BaseModel):
    source: str
    sourceKey: str
    username: str | None = None
    generatedAt: str
    themes: list[TasteThemeResponse] = Field(default_factory=list)
    unmatchedActivity: dict = Field(default_factory=dict)


class ManualTastePayload(BaseModel):
    selectedThemeIds: list[str] = Field(default_factory=list, min_length=1)
