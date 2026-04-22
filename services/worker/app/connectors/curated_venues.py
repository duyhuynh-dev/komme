from app.models.contracts import CandidateEvent, RetrievalQuery


class CuratedVenueConnector:
    source_name = "curated_venues"

    async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
        # The MVP starts with a curated NYC venue list to complement sparse API coverage.
        demo_candidates = [
            CandidateEvent(
                source=self.source_name,
                venue_name="Elsewhere",
                neighborhood="Bushwick",
                title="Late-night warehouse textures",
                starts_at="2026-04-25T23:30:00+00:00",
                latitude=40.7063,
                longitude=-73.9232,
                min_price=32,
                max_price=40,
                source_confidence=0.84,
                tags=["underground dance", "brooklyn"],
            ),
            CandidateEvent(
                source=self.source_name,
                venue_name="Public Records",
                neighborhood="Gowanus",
                title="Ambient listening room session",
                starts_at="2026-04-27T00:00:00+00:00",
                latitude=40.6784,
                longitude=-73.9896,
                min_price=20,
                max_price=28,
                source_confidence=0.8,
                tags=["listening room", "culture"],
            ),
        ]
        lowered_query = query.query.lower()
        return [
            candidate
            for candidate in demo_candidates
            if any(term in " ".join(candidate.tags + [candidate.title.lower()]) for term in lowered_query.split())
        ] or demo_candidates[:1]

