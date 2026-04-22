import httpx

from app.core.config import get_settings
from app.models.contracts import CandidateEvent, RetrievalQuery


class TicketmasterConnector:
    source_name = "ticketmaster"

    async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
        settings = get_settings()
        if not settings.ticketmaster_api_key:
            return []

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params={
                    "apikey": settings.ticketmaster_api_key,
                    "keyword": query.query,
                    "city": "New York",
                    "size": 10,
                },
            )
            response.raise_for_status()
            payload = response.json()

        events = []
        for item in payload.get("_embedded", {}).get("events", []):
            venue = item.get("_embedded", {}).get("venues", [{}])[0]
            location = venue.get("location", {})
            events.append(
                CandidateEvent(
                    source=self.source_name,
                    venue_name=venue.get("name", "Unknown venue"),
                    neighborhood="NYC",
                    title=item.get("name", "Untitled event"),
                    starts_at=item.get("dates", {}).get("start", {}).get("dateTime", ""),
                    latitude=float(location.get("latitude", 0.0)),
                    longitude=float(location.get("longitude", 0.0)),
                    min_price=(item.get("priceRanges") or [{}])[0].get("min"),
                    max_price=(item.get("priceRanges") or [{}])[0].get("max"),
                    source_confidence=0.92,
                    tags=[query.category, query.query],
                )
            )
        return events

