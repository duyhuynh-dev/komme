from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.events import CanonicalEvent, EventOccurrence, EventSource, Venue, VenueGeocode
from app.models.profile import ProfileRun, RedditActivity, UserInterestProfile
from app.models.recommendation import RecommendationRun, VenueRecommendation
from app.models.user import EmailPreference, User, UserAnchorLocation, UserConstraint
from app.services.travel import estimate_travel_bands


async def seed_demo_state(session: AsyncSession, only_missing: bool = False) -> None:
    settings = get_settings()
    user = await session.scalar(select(User).where(User.email == settings.default_user_email))
    if user is None:
        user = User(email=settings.default_user_email, display_name="Pulse Beta User")
        session.add(user)
        await session.flush()

    if not only_missing:
        constraint = UserConstraint(
            user_id=user.id,
            city="New York City",
            neighborhood="East Village",
            zip_code="10003",
            radius_miles=8,
            budget_level="under_75",
            preferred_days_csv="Thursday,Friday,Saturday",
            social_mode="either",
        )
        anchor = UserAnchorLocation(
            user_id=user.id,
            source="zip",
            neighborhood="East Village",
            zip_code="10003",
            latitude=40.7315,
            longitude=-73.9897,
            is_session_only=False,
        )
        email_preference = EmailPreference(user_id=user.id)
        profile_run = ProfileRun(
            user_id=user.id,
            summary_json={"summary": "Demo interest profile built from Reddit signals."},
        )
        session.add_all([constraint, anchor, email_preference, profile_run])

        topics = [
            UserInterestProfile(
                user_id=user.id,
                topic_key="underground_dance",
                label="Underground dance",
                confidence=0.94,
                source_signals_json=["r/aves", "saved venue lineups", "commented on DJ threads"],
                boosted=True,
                muted=False,
            ),
            UserInterestProfile(
                user_id=user.id,
                topic_key="indie_live_music",
                label="Indie live music",
                confidence=0.88,
                source_signals_json=["r/indieheads", "Brooklyn venue threads"],
            ),
            UserInterestProfile(
                user_id=user.id,
                topic_key="gallery_nights",
                label="Gallery nights",
                confidence=0.72,
                source_signals_json=["saved art-weekend posts", "commented on openings"],
            ),
        ]
        session.add_all(topics)

        session.add_all(
            [
                RedditActivity(
                    user_id=user.id,
                    activity_type="comment",
                    subreddit="aves",
                    title="Warehouse set recommendations",
                    body="Looking for darker late-night sets in Brooklyn",
                    occurred_at=datetime.now(tz=UTC).isoformat(),
                ),
                RedditActivity(
                    user_id=user.id,
                    activity_type="saved",
                    subreddit="indieheads",
                    title="Tour calendar in NYC",
                    body="Shortlist of intimate room shows",
                    occurred_at=datetime.now(tz=UTC).isoformat(),
                ),
            ]
        )

        source = EventSource(kind="curated", name="Pulse Demo Source", base_url="https://pulse.local")
        session.add(source)
        await session.flush()

        venues = [
            Venue(
                name="Elsewhere",
                neighborhood="Bushwick",
                address="599 Johnson Ave, Brooklyn, NY",
                postal_code="11237",
                latitude=40.7063,
                longitude=-73.9232,
                apple_place_id="elsewhere-demo",
            ),
            Venue(
                name="Knockdown Center",
                neighborhood="Maspeth",
                address="52-19 Flushing Ave, Queens, NY",
                postal_code="11378",
                latitude=40.7144,
                longitude=-73.9180,
                apple_place_id="knockdown-demo",
            ),
            Venue(
                name="Le Poisson Rouge",
                neighborhood="Greenwich Village",
                address="158 Bleecker St, New York, NY",
                postal_code="10012",
                latitude=40.7285,
                longitude=-74.0005,
                apple_place_id="lpr-demo",
            ),
        ]
        session.add_all(venues)
        await session.flush()

        session.add_all(
            [
                VenueGeocode(venue_id=venue.id, provider_place_id=venue.apple_place_id or venue.id)
                for venue in venues
            ]
        )

        starts = [
            datetime.now(tz=UTC) + timedelta(days=2, hours=6),
            datetime.now(tz=UTC) + timedelta(days=3, hours=7),
            datetime.now(tz=UTC) + timedelta(days=4, hours=5),
        ]

        event_specs = [
            ("after-hours techno showcase", "Live music", "A late-night lineup of warehouse-leaning selectors."),
            ("hybrid club night and visual installation", "Culture", "Dance floor energy with projection-heavy visuals."),
            ("intimate alt-pop performance", "Live music", "Small-room set with strong songwriting and crowd energy."),
        ]
        occurrences: list[EventOccurrence] = []
        for index, (venue, starts_at, event_spec) in enumerate(zip(venues, starts, event_specs, strict=True)):
            event = CanonicalEvent(
                source_id=source.id,
                source_event_key=f"pulse-demo-{index}",
                title=event_spec[0].title(),
                category=event_spec[1],
                summary=event_spec[2],
            )
            session.add(event)
            await session.flush()
            occurrence = EventOccurrence(
                event_id=event.id,
                venue_id=venue.id,
                starts_at=starts_at.isoformat(),
                ends_at=(starts_at + timedelta(hours=5)).isoformat(),
                min_price=25 + index * 10,
                max_price=35 + index * 15,
                ticket_url="https://pulse.local/tickets",
                metadata_json={"sourceConfidence": 0.93 - index * 0.05},
            )
            session.add(occurrence)
            occurrences.append(occurrence)

        await session.flush()

        run = RecommendationRun(
            user_id=user.id,
            viewport_json={
                "latitude": 40.73061,
                "longitude": -73.935242,
                "latitudeDelta": 0.24,
                "longitudeDelta": 0.24,
            },
        )
        session.add(run)
        await session.flush()

        reasons = [
            [
                {"title": "Taste overlap", "detail": "Your Reddit activity heavily leans toward warehouse techno and after-hours bookings."},
                {"title": "Practical fit", "detail": "This venue stays inside your current NYC radius and mid-range budget."},
            ],
            [
                {"title": "Scene proximity", "detail": "The lineup matches your underground dance profile but broadens into visual art programming."},
                {"title": "Novelty balance", "detail": "This is a stretch pick that still sits close to your saved culture-night signals."},
            ],
            [
                {"title": "Songwriting signal", "detail": "Indie live-music threads and saved intimate-room posts point toward this type of room."},
                {"title": "Easy night out", "detail": "Shorter travel time and earlier start make this a lower-friction midweek option."},
            ],
        ]

        origin = (40.7315, -73.9897)
        for rank, (venue, occurrence, rationale) in enumerate(zip(venues, occurrences, reasons, strict=True), start=1):
            session.add(
                VenueRecommendation(
                    run_id=run.id,
                    venue_id=venue.id,
                    event_occurrence_id=occurrence.id,
                    rank=rank,
                    score=0.96 - rank * 0.08,
                    score_band="high" if rank == 1 else "medium",
                    reasons_json=rationale,
                    travel_json=estimate_travel_bands(origin[0], origin[1], venue.latitude, venue.longitude),
                    secondary_events_json=[],
                )
            )

    await session.commit()
