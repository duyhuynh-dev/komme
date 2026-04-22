from app.services.recommendations import _price_label
from app.services.travel import estimate_travel_bands, haversine_miles


def test_haversine_distance_stays_positive() -> None:
    miles = haversine_miles(40.7315, -73.9897, 40.7063, -73.9232)
    assert miles > 0


def test_travel_bands_return_walk_and_transit() -> None:
    bands = estimate_travel_bands(40.7315, -73.9897, 40.7063, -73.9232)
    assert [band["mode"] for band in bands] == ["walk", "transit"]
    assert bands[0]["minutes"] < bands[1]["minutes"]


def test_price_label_formats_ranges() -> None:
    assert _price_label(20, 35) == "$20-$35"
    assert _price_label(25, 25) == "$25"
    assert _price_label(None, 40) == "Up to $40"

