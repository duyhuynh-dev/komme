import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.taste.contracts import CachedActivityEnvelope, NormalizedRedditActivity

SCHEMA_VERSION = "v1"


class FileActivityCache:
    def __init__(self, cache_dir: Path, ttl_hours: int = 24, schema_version: str = SCHEMA_VERSION):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        self.schema_version = schema_version

    def load(self, source: str, source_key: str) -> NormalizedRedditActivity | None:
        cache_path = self._cache_path(source, source_key)
        if not cache_path.exists():
            return None

        envelope = CachedActivityEnvelope.model_validate_json(cache_path.read_text())
        if envelope.schema_version != self.schema_version:
            return None

        if datetime.now(UTC) - envelope.saved_at > self.ttl:
            return None

        return envelope.activity

    def store(self, source: str, source_key: str, activity: NormalizedRedditActivity) -> Path:
        cache_path = self._cache_path(source, source_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        envelope = CachedActivityEnvelope(
            schema_version=self.schema_version,
            saved_at=datetime.now(UTC),
            activity=activity,
        )
        cache_path.write_text(envelope.model_dump_json(indent=2))
        return cache_path

    def _cache_path(self, source: str, source_key: str) -> Path:
        normalized_key = re.sub(r"[^a-zA-Z0-9._-]+", "_", source_key.strip().lower()).strip("_") or "unknown"
        return self.cache_dir / f"{source}__{normalized_key}__{self.schema_version}.json"

