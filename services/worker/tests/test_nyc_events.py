from app.connectors.nyc_events import _candidate_from_nyc_event, _event_items
from app.models.contracts import RetrievalQuery


def test_event_items_accepts_common_collection_shapes() -> None:
    assert _event_items({"events": [{"id": "1"}]}) == [{"id": "1"}]
    assert _event_items({"results": [{"id": "2"}]}) == [{"id": "2"}]
    assert _event_items([{"id": "3"}]) == [{"id": "3"}]


def test_candidate_from_nyc_event_maps_open_data_payload() -> None:
    item = {
        "event_id": "parks-1",
        "event_name": "SummerStage Community Concert",
        "park_name": "Central Park",
        "address": "Rumsey Playfield, New York, NY",
        "start_date": "2026-06-25",
        "start_time": "7:00 PM",
        "latitude": "40.7727",
        "longitude": "-73.9712",
        "event_url": "https://www.nycgovparks.org/events/parks-1",
        "description": "Free outdoor music.",
        "category": "community",
    }

    candidate = _candidate_from_nyc_event(
        item,
        RetrievalQuery(query="free parks culture", source="nyc_events", category="community"),
        source_base_url="https://data.cityofnewyork.us/resource/events.json",
    )

    assert candidate is not None
    assert candidate.source == "nyc_events"
    assert candidate.source_event_key == "nyc_events:parks-1"
    assert candidate.venue_name == "Central Park"
    assert candidate.ticket_url == "https://www.nycgovparks.org/events/parks-1"
    assert candidate.starts_at == "2026-06-25T23:00:00+00:00"
