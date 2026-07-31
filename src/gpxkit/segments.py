"""Reduce a segment timeline to the few segments worth naming.

A track matched against a road network turns into a long list of named
segments, most of which are noise: the forty metres of a side street you used
to turn around, the slip road, the roundabout counted as its own way. Naming
all of them is useless; naming the longest one is usually too little.

:func:`select_significant_roads` keeps the segments that are long enough *and*
lasted long enough to be worth mentioning, caps the count, and hands them back
in the order they were travelled.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .points import get_field

__all__ = ["select_significant_roads"]


def select_significant_roads(
    road_segments: Optional[Sequence[Any]],
    *,
    min_duration_sec: float = 30.0,
    min_length_m: float = 1000.0,
    max_count: int = 3,
) -> list:
    """Return the significant segments of a timeline, in chronological order.

    Args:
        road_segments: Segment records in travel order. Each is read
            duck-typed, like everything in ``gpxkit``: a ``name``, a duration
            from ``duration_sec`` or ``duration``, and a length from
            ``length_m`` or ``length``. Dicts and objects both work.
        min_duration_sec: Segments shorter in time than this are dropped.
        min_length_m: Segments shorter in distance than this are dropped.
        max_count: At most this many survive; the longest-*duration* ones win.

    Returns:
        A new list of the original records, in input order.

    Unnamed segments are dropped outright — an anonymous segment cannot be
    mentioned, so its size is irrelevant. Both thresholds must be cleared:
    length alone would keep a motorway you were on for eight seconds, and
    duration alone would keep the traffic light you sat at.

    Selection ranks by **duration** but returns in **input order**, so a caller
    building a phrase gets the roads in the order they were driven rather than
    in rank order.

    >>> segs = [
    ...     {"name": "Route 9",  "duration_sec": 600.0, "length_m": 20000.0},
    ...     {"name": "Mill Ln",  "duration_sec": 5.0,   "length_m": 100.0},
    ...     {"name": "Route 12", "duration_sec": 300.0, "length_m": 10000.0},
    ... ]
    >>> [s["name"] for s in select_significant_roads(segs)]
    ['Route 9', 'Route 12']
    """
    if not road_segments:
        return []

    prefiltered: list[tuple[int, Any]] = []
    for i, r in enumerate(road_segments):
        if not get_field(r, "name"):
            continue
        duration = get_field(r, "duration_sec", "duration", default=0.0)
        length = get_field(r, "length_m", "length", default=0.0)
        try:
            if float(duration) < min_duration_sec:
                continue
            if float(length) < min_length_m:
                continue
        except (TypeError, ValueError):
            continue
        prefiltered.append((i, r))

    if len(prefiltered) <= max_count:
        return [r for _, r in prefiltered]

    def _duration(entry: tuple[int, Any]) -> float:
        try:
            return float(get_field(entry[1], "duration_sec", "duration", default=0.0))
        except (TypeError, ValueError):
            return 0.0

    top = sorted(prefiltered, key=_duration, reverse=True)[:max_count]
    top.sort(key=lambda entry: entry[0])
    return [r for _, r in top]
