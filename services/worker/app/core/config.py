from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_PATH = Path(__file__).resolve()
SERVICE_ROOT = CONFIG_PATH.parents[2]
REPO_ROOT = CONFIG_PATH.parents[4] if len(CONFIG_PATH.parents) > 4 else SERVICE_ROOT


class Settings(BaseSettings):
    env: Literal["development", "staging", "production"] = "development"
    api_base_url: str = "http://localhost:8000"
    gemini_api_key: str = ""
    gemini_model: str = "google-gla:gemini-2.5-flash"
    inngest_app_id: str = "pulse-worker"
    ticketmaster_api_key: str = ""
    seatgeek_client_id: str = ""
    seatgeek_client_secret: str = ""
    nyc_events_api_url: str = ""
    nyc_events_api_key: str = ""
    internal_ingest_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(SERVICE_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
