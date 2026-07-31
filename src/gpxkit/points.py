"""Duck-typed accessors for "a GPS point", whatever shape yours is.

Every other module in ``gpxkit`` reads coordinates and times through these four
functions and nothing else. That is the whole reason the library works on your
data without an adapter layer: there is no ``gpxkit.Point`` class you must
convert to, and no schema you must match.

Supported shapes, all simultaneously, in one list if you like:

=========================  ==========================================
shape                      example
=========================  ==========================================
mapping                    ``{"time": 12.0, "lat": 45.1, "lon": -99.4}``
3-tuple / 3-list           ``(12.0, 45.1, -99.4)``  → ``(t, lat, lon)``
2-tuple / 2-list           ``(45.1, -99.4)``        → ``(lat, lon)``, no time
object with attributes     ``obj.lat`` / ``obj.latitude`` …
=========================  ==========================================

Field-name aliases are checked in order, so both the short names most parsers
emit (``lat`` / ``lon`` / ``time``) and the long names the GPX schema uses
(``latitude`` / ``longitude`` / ``timestamp``) resolve. Anything unreadable
returns ``None`` rather than raising — a filter that cannot see a field must
skip that test, not reject the point.

**Positional-tuple convention.** A 3-element sequence is ``(t, lat, lon)``, not
``(lat, lon, t)``. Time first is the ordering that sorts chronologically for
free, which is what most track code wants. A 2-element sequence is ``(lat,
lon)`` and carries no time.
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "get_field",
    "point_lat",
    "point_lon",
    "point_time",
    "point_seconds",
]


def get_field(point: Any, *names: str, default: Any = None) -> Any:
    """Return the first present, non-``None`` key or attribute named in ``names``.

    Mappings are read by key, everything else by attribute, so the same call
    site serves dicts, dataclasses, namedtuples, ORM rows and
    ``SimpleNamespace`` objects.

    >>> get_field({"speed": 12.0}, "speed_mps", "speed")
    12.0
    >>> get_field(object(), "hdop", default=1.0)
    1.0
    """
    for name in names:
        if isinstance(point, dict):
            if name in point and point[name] is not None:
                return point[name]
        else:
            val = getattr(point, name, None)
            if val is not None:
                return val
    return default


def point_lat(point: Any) -> Any:
    """Latitude of a point, or ``None`` if it has none this module can see."""
    if isinstance(point, (tuple, list)):
        if len(point) >= 3:
            return point[1]
        if len(point) == 2:
            return point[0]
        return None
    return get_field(point, "lat", "latitude")


def point_lon(point: Any) -> Any:
    """Longitude of a point, or ``None`` if it has none this module can see."""
    if isinstance(point, (tuple, list)):
        if len(point) >= 3:
            return point[2]
        if len(point) == 2:
            return point[1]
        return None
    return get_field(point, "lon", "lng", "longitude")


def point_time(point: Any) -> Any:
    """Raw time value of a point — seconds, a ``datetime``, or ``None``.

    No conversion happens here; use :func:`point_seconds` when you want a
    number you can subtract.
    """
    if isinstance(point, (tuple, list)):
        return point[0] if len(point) >= 3 else None
    return get_field(point, "time", "timestamp")


def point_seconds(point: Any) -> Optional[float]:
    """Time of a point as a float, or ``None`` if it is missing or unreadable.

    A ``datetime`` is converted through its ``.timestamp()`` (so a naive
    datetime is interpreted in the local zone — pass aware datetimes if that
    matters to you). Anything else is coerced with ``float()``.

    The unit is whatever unit your track uses. ``gpxkit`` only ever subtracts
    two of these, so epoch seconds, seconds-since-track-start and
    seconds-into-a-video all work — as long as one track does not mix them.
    """
    ts = point_time(point)
    if ts is None:
        return None
    if hasattr(ts, "timestamp"):
        try:
            return float(ts.timestamp())
        except Exception:  # noqa: BLE001 - a broken .timestamp() is just "no time"
            return None
    try:
        return float(ts)
    except (TypeError, ValueError):
        return None
