"""gpxkit — GPS noise rejection and track-window analytics, with no dependencies.

Everything here works on *your* point type. There is no ``gpxkit.Point`` to
convert to: coordinates and times are read through duck-typed accessors that
understand mappings, ``(t, lat, lon)`` tuples, ``(lat, lon)`` tuples, and any
object with ``lat`` / ``latitude`` style attributes — mixed together in one
list if that is what you have. See :mod:`gpxkit.points`.

Typical use::

    from gpxkit import filter_high_quality_points, window_median_speed_mps

    clean = filter_high_quality_points(raw_track)
    speed = window_median_speed_mps(clean, 0.0, 600.0)

Modules:

* :mod:`gpxkit.points` — the duck-typed accessors everything else reads through
* :mod:`gpxkit.geo` — great-circle distance
* :mod:`gpxkit.filters` — noise rejection
* :mod:`gpxkit.windows` — measurements over a slice of a track
* :mod:`gpxkit.segments` — picking the segments worth naming
* :mod:`gpxkit.trim` — restricting a track to the ranges that survived an edit
"""

from __future__ import annotations

from .filters import (
    SPATIAL_OUTLIER_KM,
    TELEPORT_JUMP_FLOOR_KM,
    TELEPORT_SPEED_CEILING_KMH,
    TELEPORT_STEP_MULTIPLE,
    exceeds_physical_speed,
    filter_high_quality_points,
    strip_teleport_runs,
)
from .geo import EARTH_RADIUS_KM, haversine_km
from .points import get_field, point_lat, point_lon, point_seconds, point_time
from .segments import select_significant_roads
from .trim import trim_gps_to_clip_timeline
from .windows import (
    locked_gps_coverage,
    locked_gps_duration_coverage,
    nearest_trace_distance_km,
    trace_time_window,
    window_median_speed_mps,
    window_stationary_fraction,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # points
    "get_field",
    "point_lat",
    "point_lon",
    "point_time",
    "point_seconds",
    # geo
    "EARTH_RADIUS_KM",
    "haversine_km",
    # filters
    "SPATIAL_OUTLIER_KM",
    "TELEPORT_SPEED_CEILING_KMH",
    "TELEPORT_JUMP_FLOOR_KM",
    "TELEPORT_STEP_MULTIPLE",
    "exceeds_physical_speed",
    "filter_high_quality_points",
    "strip_teleport_runs",
    # windows
    "locked_gps_coverage",
    "locked_gps_duration_coverage",
    "trace_time_window",
    "window_median_speed_mps",
    "window_stationary_fraction",
    "nearest_trace_distance_km",
    # segments
    "select_significant_roads",
    # trim
    "trim_gps_to_clip_timeline",
]
