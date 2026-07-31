"""Restrict a track to the ranges that survived an edit.

If the recording a track accompanies has been cut — sections removed, a
highlight reel assembled, a multi-day trip split into legs — then the raw
track no longer describes what is left. Statistics computed over it will
include the roads you cut out.

:func:`trim_gps_to_clip_timeline` takes the ranges that *survived*, in the
original track's clock, and returns only the fixes inside them.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Sequence

__all__ = ["trim_gps_to_clip_timeline"]


def _default_time_accessor(point: Any) -> float:
    """Seconds for a point, or ``TypeError`` naming the way out.

    Handles ``(t, ...)`` sequences and objects exposing ``t``,
    ``timestamp_sec``, ``time_sec`` or ``source_sec``. Anything else — notably
    ``datetime`` timestamps, which have no single correct origin — must be
    projected by the caller through ``time_key``.
    """
    if isinstance(point, (tuple, list)) and point:
        return float(point[0])
    for attr in ("t", "timestamp_sec", "time_sec", "source_sec"):
        if hasattr(point, attr):
            return float(getattr(point, attr))
    raise TypeError(
        f"Cannot extract a time from {type(point).__name__}; "
        "pass time_key= to trim_gps_to_clip_timeline()."
    )


def trim_gps_to_clip_timeline(
    gps_points: Optional[Iterable[Any]],
    included_segments: Optional[Sequence[tuple]],
    *,
    time_key: Optional[Callable[[Any], float]] = None,
) -> list:
    """Return the points whose time falls inside any of ``included_segments``.

    Args:
        gps_points: Any iterable of points. ``None`` yields ``[]``.
        included_segments: ``(start, end)`` pairs, inclusive at both ends, in
            the same clock as the points. They need not be sorted or disjoint;
            a point in two overlapping ranges is still returned once. ``None``
            means "no edit happened" and returns every point; an **empty list**
            means "nothing survived" and returns none — the distinction is the
            whole reason this takes ``Optional``.
        time_key: Projection from a point to a number, for shapes the default
            accessor cannot read. For ``datetime`` waypoints measured from a
            known start::

                time_key=lambda wp: (wp.timestamp - start).total_seconds()

    Returns:
        A new list, in input order, of the original point objects.

    >>> track = [(0.0, 45.0, -99.0), (5.0, 45.1, -99.1), (30.0, 45.2, -99.2)]
    >>> [p[0] for p in trim_gps_to_clip_timeline(track, [(4.0, 11.0)])]
    [5.0]
    """
    if gps_points is None:
        return []
    if included_segments is None:
        return list(gps_points)
    ranges = [(float(s), float(e)) for s, e in included_segments]
    if not ranges:
        return []
    accessor = time_key or _default_time_accessor
    kept: list = []
    for pt in gps_points:
        t = float(accessor(pt))
        for start, end in ranges:
            if start <= t <= end:
                kept.append(pt)
                break
    return kept
