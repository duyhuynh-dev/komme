from typing import Protocol

from app.models.contracts import CandidateEvent, RetrievalQuery


class EventConnector(Protocol):
    source_name: str

    async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
        ...

