"""Synthetic tracks and point types for the test suite.

Every coordinate in this suite is invented. The tracks are generated from round
numbers in an empty stretch of the northern plains and correspond to no journey
anyone took; nothing here is a captured trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Anchor for every synthetic track. Chosen for arithmetic convenience, not
# because anything happened here.
BASE_LAT = 45.0
BASE_LON = -99.0

# A stand-in "wrong satellite cluster" position roughly 1700 km from the
# anchor, for the stale-almanac fix a cold receiver reports.
FAR_LAT = 30.0
FAR_LON = -88.0


@dataclass
class Trackpoint:
    """A minimal GPX-style trackpoint: position, elevation, time. No HDOP, no speed.

    Stands in for the many parser output types that carry only what a GPX file
    actually contains, so the suite can prove the field-driven gates stay inert
    on them rather than silently rejecting every point.
    """

    lat: float
    lon: float
    elevation: Optional[float] = None
    timestamp: Optional[float] = None


def straight_track(
    n: int,
    *,
    start_t: float = 0.0,
    step_sec: float = 1.0,
    step_deg: float = 0.001,
    lat: float = BASE_LAT,
    lon: float = BASE_LON,
) -> list[tuple[float, float, float]]:
    """``n`` fixes as ``(t, lat, lon)`` tuples heading north-east from an anchor."""
    return [(start_t + i * step_sec, lat + i * step_deg, lon + i * step_deg) for i in range(n)]
