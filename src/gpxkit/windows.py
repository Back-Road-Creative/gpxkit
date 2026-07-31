"""Questions you can ask about a slice of a track.

Every function here takes a track and a window and returns one number (or
``None`` when the answer is genuinely unmeasurable). They are the measurements
you reach for once :mod:`gpxkit.filters` has removed the noise: *did this
stretch actually have GPS?*, *were we moving?*, *how close did we pass to this
place?*

**Two rules govern all of them.**

*Same clock.* The window bounds and the points' timestamps must be in the same
unit and the same origin. ``gpxkit`` cannot detect a mismatch — epoch seconds
compared against seconds-into-a-recording will silently produce ``0.0``.

*Unmeasurable is ``None``, never a default.* When there are too few fixes to
compute an answer, these functions return ``None`` instead of ``0.0`` or
``1.0``. A caller that treats "no data" as "passed" builds a gate that opens
widest exactly when it knows least.

Every point you pass is counted as a real fix. If you want noise excluded,
run :func:`gpxkit.filter_high_quality_points` first — that separation is
deliberate, because "how much of this window had usable GPS" and "what counts
as usable" are two different decisions and you should own the second one.
"""

from __future__ import annotations

import statistics
from typing import Any, Optional, Sequence

from .geo import haversine_km
from .points import point_lat, point_lon, point_seconds

__all__ = [
    "locked_gps_coverage",
    "locked_gps_duration_coverage",
    "trace_time_window",
    "window_median_speed_mps",
    "window_stationary_fraction",
    "nearest_trace_distance_km",
]


def _in_window_coords(
    gps_points: Optional[Sequence[Any]], w0: float, w1: float
) -> list[tuple[float, float, float]]:
    """``[(t, lat, lon), ...]`` for fixes with usable time and position in ``[w0, w1]``."""
    out: list[tuple[float, float, float]] = []
    for p in gps_points or []:
        t, lat, lon = point_seconds(p), point_lat(p), point_lon(p)
        if t is None or lat is None or lon is None or t < w0 or t > w1:
            continue
        try:
            out.append((float(t), float(lat), float(lon)))
        except (TypeError, ValueError):
            continue
    return out


def _consecutive_speeds_mps(
    gps_points: Optional[Sequence[Any]], w0: float, w1: float
) -> list[float]:
    """Ground speed (m/s) between each pair of consecutive in-window fixes.

    Derived from position and time, never from a reported speed channel — a
    parsed GPX track usually has no speed field at all, and where one exists it
    is often the receiver's own smoothed estimate rather than a measurement.
    """
    pts = sorted(_in_window_coords(gps_points, w0, w1))
    return [
        haversine_km(la0, lo0, la1, lo1) * 1000.0 / (t1 - t0)
        for (t0, la0, lo0), (t1, la1, lo1) in zip(pts, pts[1:])
        if t1 > t0
    ]


def locked_gps_coverage(
    gps_points: Optional[Sequence[Any]],
    window_start_sec: float,
    window_end_sec: float,
    *,
    expected_hz: float = 1.0,
) -> float:
    """Fraction (0.0–1.0) of ``[window_start_sec, window_end_sec]`` carrying a fix.

    The window is divided into buckets ``1 / expected_hz`` seconds wide, and the
    result is the share of buckets containing at least one point. Bucketing
    rather than counting makes the answer robust in both directions: an
    over-sampled trace saturates at 1.0 instead of exceeding it, and a dead or
    sparse stretch lowers it in proportion to how long it lasted.

    Returns ``0.0`` for an empty track or a zero-length / inverted window.
    Raises ``ValueError`` if ``expected_hz`` is not positive.

    >>> track = [(float(t), 45.0, -99.0) for t in range(11)]
    >>> locked_gps_coverage(track, 0.0, 10.0)
    1.0
    >>> locked_gps_coverage(track[:6], 0.0, 10.0)   # second half is dead
    0.6
    """
    if expected_hz <= 0:
        raise ValueError("expected_hz must be positive")
    if window_end_sec <= window_start_sec:
        return 0.0
    span = window_end_sec - window_start_sec
    expected = max(1, round(span * expected_hz))
    bucket_sec = 1.0 / expected_hz
    covered: set[int] = set()
    for p in gps_points or []:
        t = point_seconds(p)
        if t is None or t < window_start_sec or t > window_end_sec:
            continue
        idx = int((t - window_start_sec) / bucket_sec)
        covered.add(min(idx, expected - 1))
    return min(1.0, len(covered) / expected)


def locked_gps_duration_coverage(
    gps_points: Optional[Sequence[Any]],
    duration_sec: float,
    *,
    expected_hz: float = 1.0,
) -> float:
    """Coverage measured against a *duration* instead of a window.

    Use this when the material you are describing is not contiguous in any
    single clock — a recording with sections cut out of it, a track stitched
    from several files, or points timestamped in one clock while the length you
    care about is measured in another.

    :func:`locked_gps_coverage` would count every removed section as dead GPS,
    because a single start-to-end window spans the gaps. This function does not
    look at the window at all: the numerator is the number of distinct
    ``expected_hz`` buckets among the supplied points' own timestamps (so the
    clock's origin is irrelevant), and the denominator is ``duration_sec``. A
    dead run at either end, or a real dropout in the middle, still lowers the
    result; time that was deliberately removed cannot, because its fixes were
    never supplied.

    Returns ``0.0`` for a non-positive duration. Raises ``ValueError`` if
    ``expected_hz`` is not positive.
    """
    if expected_hz <= 0:
        raise ValueError("expected_hz must be positive")
    if duration_sec <= 0:
        return 0.0
    expected = max(1, round(duration_sec * expected_hz))
    covered = {
        int(t * expected_hz) for t in (point_seconds(p) for p in gps_points or []) if t is not None
    }
    return min(1.0, len(covered) / expected)


def trace_time_window(gps_points: Optional[Sequence[Any]]) -> Optional[tuple[float, float]]:
    """``(earliest, latest)`` timestamp in the track, or ``None`` under two fixes.

    The window a track implies about itself, for when the caller has no window
    of its own to supply.
    """
    ts = [t for t in (point_seconds(p) for p in gps_points or []) if t is not None]
    return (min(ts), max(ts)) if len(ts) >= 2 else None


def window_median_speed_mps(
    gps_points: Optional[Sequence[Any]], w0: float, w1: float
) -> Optional[float]:
    """Median ground speed in m/s over the window, or ``None`` if unmeasurable.

    Median rather than mean: one surviving bad fix would drag a mean anywhere,
    while the median needs half the intervals to be wrong before it moves.
    """
    speeds = _consecutive_speeds_mps(gps_points, w0, w1)
    return statistics.median(speeds) if speeds else None


def window_stationary_fraction(
    gps_points: Optional[Sequence[Any]],
    w0: float,
    w1: float,
    *,
    stop_speed_mps: float,
) -> Optional[tuple[float, int]]:
    """``(stationary_fraction, interval_count)``, or ``None`` if unmeasurable.

    The share of consecutive in-window intervals whose ground speed is below
    ``stop_speed_mps``, plus how many intervals that share was computed from —
    so a caller can refuse to act on a fraction derived from three intervals.

    This is the per-interval companion to :func:`window_median_speed_mps`. Use
    it when your threshold is not "half" — a median can only ever answer "is
    the middle interval stopped?", whereas this answers "what share of the time
    were we stopped?" against any cut-off you choose.

    ``None`` means fewer than two usable in-window fixes. Do not read that as
    "moving".
    """
    speeds = _consecutive_speeds_mps(gps_points, w0, w1)
    if not speeds:
        return None
    stopped = sum(1 for s in speeds if s < stop_speed_mps)
    return stopped / len(speeds), len(speeds)


def nearest_trace_distance_km(
    lat: float,
    lon: float,
    gps_points: Optional[Sequence[Any]],
    w0: float,
    w1: float,
) -> Optional[float]:
    """Distance in km from ``(lat, lon)`` to the closest in-window fix, or ``None``.

    Distance to the nearest *sampled point*, not to the path between them, so a
    sparse track reports a larger number than a dense one over the same route.
    At 1 Hz and highway speed the difference is under 15 m; at one fix a minute
    it is kilometres.
    """
    ds = [haversine_km(lat, lon, la, lo) for _t, la, lo in _in_window_coords(gps_points, w0, w1)]
    return min(ds) if ds else None
