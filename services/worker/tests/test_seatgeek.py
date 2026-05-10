from app.connectors.seatgeek import _candidate_from_seatgeek, _normalize_seatgeek_datetime
from app.models.contracts import RetrievalQuery


def test_normalize_seatgeek_datetime_to_utc() -> None:
    assert _normalize_seatgeek_datetime("2026-06-25T23:30:00") == "2026-06-25T23:30:00+00:00"


def test_candidate_from_seatgeek_maps_event_and_venue_payload() -> None:
    item = {
        "id": 123,
        "title": "Indie Night at Brooklyn Steel",
        "datetime_utc": "2026-06-25T23:30:00Z",
        "url": "https://seatgeek.com/indie-night-tickets",
        "venue": {
            "name": "Brooklyn Steel",
            "address": "319 Frost St",
            "city": "Brooklyn",
            "state": "NY",
            "postal_code": "11222",
            "location": {"lat": 40.7194, "lon": -73.9385},
        },
        "stats": {"lowest_price": 32, "highest_price": 80},
        "taxonomies": [{"name": "concert"}],
        "performers": [{"name": "Test Band"}],
    }

    candidate = _candidate_from_seatgeek(item, RetrievalQuery(query="indie", source="seatgeek"))

    assert candidate is not None
    assert candidate.source == "seatgeek"
    assert candidate.source_event_key == "seatgeek:123"
    assert candidate.venue_name == "Brooklyn Steel"
    assert candidate.ticket_url == "https://seatgeek.com/indie-night-tickets"
    assert candidate.min_price == 32
    assert candidate.max_price == 80
