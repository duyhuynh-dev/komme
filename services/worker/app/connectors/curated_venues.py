from app.models.contracts import CandidateEvent, RetrievalQuery


class CuratedVenueConnector:
    source_name = "curated_venues"

    async def search(self, query: RetrievalQuery) -> list[CandidateEvent]:
        # The MVP starts with a curated NYC venue list to complement sparse API coverage.
        demo_candidates = [
            CandidateEvent(
                source=self.source_name,
                source_kind="curated_feed",
                source_event_key="curated:elsewhere-late-night-textures",
                venue_name="Elsewhere",
                neighborhood="Bushwick",
                address="599 Johnson Ave, Brooklyn, NY",
                city="New York City",
                state="NY",
                postal_code="11237",
                title="Late-night warehouse textures",
                summary="A deeper late-night lineup with warehouse techno energy and visual atmosphere.",
                category="live music",
                starts_at="2026-04-25T23:30:00+00:00",
                ends_at="2026-04-26T05:00:00+00:00",
                latitude=40.7063,
                longitude=-73.9232,
                ticket_url="https://www.elsewherebrooklyn.com/events",
                min_price=32,
                max_price=40,
                source_confidence=0.84,
                topic_keys=["underground_dance"],
                tags=["underground dance", "brooklyn"],
            ),
            CandidateEvent(
                source=self.source_name,
                source_kind="curated_feed",
                source_event_key="curated:public-records-listening-room",
                venue_name="Public Records",
                neighborhood="Gowanus",
                address="233 Butler St, Brooklyn, NY",
                city="New York City",
                state="NY",
                postal_code="11217",
                title="Ambient listening room session",
                summary="A seated, art-forward listening-room program with light visuals and experimental sets.",
                category="culture",
                starts_at="2026-04-27T00:00:00+00:00",
                ends_at="2026-04-27T03:00:00+00:00",
                latitude=40.6784,
                longitude=-73.9896,
                ticket_url="https://publicrecords.nyc/calendar",
                min_price=20,
                max_price=28,
                source_confidence=0.8,
                topic_keys=["gallery_nights"],
                tags=["listening room", "culture"],
            ),
            CandidateEvent(
                source=self.source_name,
                source_kind="curated_feed",
                source_event_key="curated:lpr-intimate-alt-pop",
                venue_name="Le Poisson Rouge",
                neighborhood="Greenwich Village",
                address="158 Bleecker St, New York, NY",
                city="New York City",
                state="NY",
                postal_code="10012",
                title="Intimate alt-pop songwriter night",
                summary="A small-room performance built around indie songwriting and close crowd energy.",
                category="live music",
                starts_at="2026-04-28T00:30:00+00:00",
                ends_at="2026-04-28T03:00:00+00:00",
                latitude=40.7285,
                longitude=-74.0005,
                ticket_url="https://lpr.com/",
                min_price=30,
                max_price=45,
                source_confidence=0.82,
                topic_keys=["indie_live_music"],
                tags=["indie live music", "songwriter"],
            ),
        ]
        lowered_query = query.query.lower()
        return [
            candidate
            for candidate in demo_candidates
            if any(term in " ".join(candidate.tags + [candidate.title.lower()]) for term in lowered_query.split())
        ] or demo_candidates[:1]
