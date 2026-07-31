"""Great-circle geometry helpers.

Deliberately tiny and dependency-free: one distance function, on the sphere.
``gpxkit`` never needs ellipsoidal accuracy — every decision it makes is a
threshold comparison (is this jump bigger than 25 km? is this fix further than
500 km from the cluster?), and the haversine/WGS-84 disagreement of ~0.5 % is
three orders of magnitude below those thresholds.
"""

from __future__ import annotations

import math

__all__ = ["EARTH_RADIUS_KM", "haversine_km"]

# Mean Earth radius. Using the mean rather than the equatorial radius keeps the
# worst-case sphere-vs-ellipsoid error under ~0.5 % anywhere on the globe.
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two ``(lat, lon)`` points.

    Latitudes and longitudes are decimal degrees. The result is always
    non-negative and is symmetric in its arguments.

    >>> round(haversine_km(45.0, -100.0, 45.0, -101.0), 1)
    78.6
    """
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    # ``min(a, 1.0)`` guards asin() against a float overshoot past 1.0 for
    # antipodal points, which would otherwise raise ValueError.
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(a, 1.0)))
