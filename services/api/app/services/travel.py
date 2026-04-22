from math import atan2, cos, radians, sin, sqrt


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_miles = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_miles * c


def estimate_travel_bands(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> list[dict[str, int | str]]:
    distance = haversine_miles(
        origin_latitude,
        origin_longitude,
        destination_latitude,
        destination_longitude,
    )
    walk_minutes = max(5, round(distance * 22))
    transit_minutes = max(10, round(distance * 12 + 8))

    return [
        {
            "mode": "walk",
            "label": f"{walk_minutes} min walk",
            "minutes": walk_minutes,
        },
        {
            "mode": "transit",
            "label": f"{transit_minutes} min transit",
            "minutes": transit_minutes,
        },
    ]

