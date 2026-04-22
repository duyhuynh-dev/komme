from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import CanonicalEvent, EventOccurrence, Venue
from app.models.recommendation import RecommendationRun, VenueRecommendation
from app.models.user import User, UserAnchorLocation, UserConstraint
from app.schemas.recommendations import (
    ArchiveResponse,
    MapVenuePin,
    RecommendationsMapResponse,
    RecommendationReason,
    TravelEstimate,
    VenueRecommendationCard,
)
from app.services.travel import estimate_travel_bands


async def _latest_run(session: AsyncSession, user_id: str) -> RecommendationRun | None:
    return await session.scalar(
        select(RecommendationRun)
        .where(RecommendationRun.user_id == user_id)
        .order_by(desc(RecommendationRun.created_at))
        .limit(1)
    )


async def _user_anchor(session: AsyncSession, user_id: str) -> UserAnchorLocation | None:
    return await session.scalar(
        select(UserAnchorLocation)
        .where(UserAnchorLocation.user_id == user_id)
        .order_by(desc(UserAnchorLocation.created_at))
        .limit(1)
    )


async def _user_constraints(session: AsyncSession, user_id: str) -> UserConstraint | None:
    return await session.scalar(select(UserConstraint).where(UserConstraint.user_id == user_id).limit(1))


def _anchor_coordinates(anchor: UserAnchorLocation | None) -> tuple[float, float]:
    if anchor and anchor.latitude is not None and anchor.longitude is not None:
        return anchor.latitude, anchor.longitude

    zip_to_coordinate = {
        "10003": (40.7315, -73.9897),
        "11211": (40.7176, -73.9533),
        "10014": (40.7347, -74.0060),
    }
    if anchor and anchor.zip_code and anchor.zip_code in zip_to_coordinate:
        return zip_to_coordinate[anchor.zip_code]

    return (40.73061, -73.935242)


async def get_map_recommendations(
    session: AsyncSession,
    user: User,
) -> RecommendationsMapResponse:
    run = await _latest_run(session, user.id)
    if run is None:
        return RecommendationsMapResponse(
            viewport={"latitude": 40.73061, "longitude": -73.935242, "latitudeDelta": 0.22, "longitudeDelta": 0.22},
            pins=[],
            cards={},
            generatedAt="",
            userConstraint={},
        )

    anchor = await _user_anchor(session, user.id)
    constraints = await _user_constraints(session, user.id)
    origin_latitude, origin_longitude = _anchor_coordinates(anchor)

    recommendation_rows = (
        await session.scalars(
            select(VenueRecommendation)
            .where(VenueRecommendation.run_id == run.id)
            .order_by(VenueRecommendation.rank.asc())
        )
    ).all()

    pins: list[MapVenuePin] = []
    cards: dict[str, VenueRecommendationCard] = {}

    for index, recommendation in enumerate(recommendation_rows):
        venue = await session.get(Venue, recommendation.venue_id)
        occurrence = await session.get(EventOccurrence, recommendation.event_occurrence_id)
        event = await session.get(CanonicalEvent, occurrence.event_id if occurrence else None)
        if not venue or not occurrence or not event:
            continue

        travel = estimate_travel_bands(
            origin_latitude,
            origin_longitude,
            venue.latitude,
            venue.longitude,
        )
        reasons = [
            RecommendationReason(title=item["title"], detail=item["detail"])
            for item in recommendation.reasons_json
        ]

        cards[venue.id] = VenueRecommendationCard(
            venueId=venue.id,
            venueName=venue.name,
            neighborhood=venue.neighborhood or "NYC",
            address=venue.address,
            eventTitle=event.title,
            eventId=occurrence.id,
            startsAt=occurrence.starts_at,
            priceLabel=_price_label(occurrence.min_price, occurrence.max_price),
            scoreBand=recommendation.score_band,
            score=recommendation.score,
            travel=[TravelEstimate(**item) for item in travel],
            reasons=reasons,
            secondaryEvents=recommendation.secondary_events_json or [],
        )
        pins.append(
            MapVenuePin(
                venueId=venue.id,
                venueName=venue.name,
                latitude=venue.latitude,
                longitude=venue.longitude,
                scoreBand=recommendation.score_band,
                selected=index == 0,
            )
        )

    return RecommendationsMapResponse(
        viewport=run.viewport_json,
        pins=pins,
        cards=cards,
        generatedAt=run.created_at.isoformat(),
        userConstraint={
            "city": constraints.city if constraints else "New York City",
            "neighborhood": constraints.neighborhood if constraints else None,
            "zipCode": constraints.zip_code if constraints else None,
            "radiusMiles": constraints.radius_miles if constraints else 8,
            "budgetLevel": constraints.budget_level if constraints else "under_75",
            "preferredDays": constraints.preferred_days_csv.split(",") if constraints else ["Thursday", "Friday", "Saturday"],
            "socialMode": constraints.social_mode if constraints else "either",
        },
    )


async def get_archive(session: AsyncSession, user: User) -> ArchiveResponse:
    map_response = await get_map_recommendations(session, user)
    items = sorted(map_response.cards.values(), key=lambda item: item.score, reverse=True)
    return ArchiveResponse(items=items)


def _price_label(min_price: float | None, max_price: float | None) -> str:
    if min_price is None and max_price is None:
        return "Price varies"
    if min_price is not None and max_price is not None and min_price == max_price:
        return f"${min_price:.0f}"
    if min_price is None:
        return f"Up to ${max_price:.0f}"
    if max_price is None:
        return f"From ${min_price:.0f}"
    return f"${min_price:.0f}-${max_price:.0f}"

