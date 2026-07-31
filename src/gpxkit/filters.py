"""Noise rejection for consumer GPS traces.

A consumer receiver does not fail by going quiet. It fails by lying
confidently: it reports ``(0, 0)`` before it has a fix, it locks onto a stale
almanac and reports a position hundreds of kilometres away, it jitters a metre
back and forth while you sit at a red light, and it emits four fixes in the
same second when you only asked for one.

:func:`filter_high_quality_points` removes those, in one pass, in this order:

1. **Null island.** Exactly ``(0.0, 0.0)`` is the no-lock sentinel, not a spot
   in the Gulf of Guinea.
2. **HDOP ceiling.** Drop fixes whose reported horizontal dilution of precision
   is worse than ``max_hdop``. Points with no HDOP field are kept.
3. **Speed floor.** Drop fixes whose *reported* speed is below
   ``min_speed_mps`` — stationary jitter. Points with no speed field are kept.
4. **Sub-second duplicates.** Of two fixes closer together than ``min_gap_sec``,
   drop the later one.
5. **Spatial outliers.** Drop fixes further than ``spatial_outlier_km`` from the
   median of the surviving cluster.
6. **Teleport runs.** Strip a leading or trailing *run* of fixes joined to the
   body of the track by a seam whose implied speed is physically impossible.

Steps 2 and 3 are field-driven and are honestly inert on point shapes that
carry no HDOP or speed channel — a bare ``(t, lat, lon)`` tuple, or a GPX
trackpoint. That is deliberate: a missing field is not evidence of a bad fix,
so it never causes a drop. Steps 1, 4, 5 and 6 need only latitude, longitude
and time, so they apply to every shape :mod:`gpxkit.points` can read.

Why steps 5 and 6 are both needed is the interesting part; see the README.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any, Optional, Sequence

from .geo import haversine_km
from .points import get_field, point_lat, point_lon, point_seconds

__all__ = [
    "SPATIAL_OUTLIER_KM",
    "TELEPORT_SPEED_CEILING_KMH",
    "TELEPORT_JUMP_FLOOR_KM",
    "TELEPORT_STEP_MULTIPLE",
    "exceeds_physical_speed",
    "filter_high_quality_points",
    "strip_teleport_runs",
]

logger = logging.getLogger(__name__)

# Radius from the median of the surviving cluster beyond which a fix is an
# outlier. Generous on purpose: a single day's drive can legitimately cover
# several hundred kilometres, and this test must never split a long journey in
# half. It is the coarse net; the teleport test below is the fine one.
SPATIAL_OUTLIER_KM = 500.0

# Implied-speed ceiling for the teleport test. A jump between consecutive
# fixes is a teleport only when ``km / hours`` exceeds this — never on raw
# kilometres alone. 25 km after a ten-minute tunnel or ferry dropout is
# ~150 km/h and legitimate; the same 25 km in one second is ~90,000 km/h and
# is a stale lock. 1000 km/h sits far above any ground or ferry travel and far
# below an instantaneous jump, so the two cases separate cleanly.
TELEPORT_SPEED_CEILING_KMH = 1000.0

# A seam must clear BOTH an absolute floor and a multiple of the track's own
# median step before the speed test is even applied, so ordinary fast-fix noise
# in a dense trace can never trip the strip.
TELEPORT_JUMP_FLOOR_KM = 25.0
TELEPORT_STEP_MULTIPLE = 20.0

# Never strip more than this fraction of the track from either end. A filter
# that can eat an arbitrary amount of your data is worse than the noise.
_MAX_STRIP_FRACTION = 0.05


def exceeds_physical_speed(
    km: float,
    dt_sec: Optional[float],
    *,
    ceiling_kmh: float = TELEPORT_SPEED_CEILING_KMH,
) -> bool:
    """Return ``True`` iff covering ``km`` in ``dt_sec`` implies an impossible speed.

    ``dt_sec`` of ``None`` or ``<= 0`` means the spacing is unknown, and the
    answer is ``False``: you cannot prove a teleport without a clock. Callers
    that care must apply their own spatial guard as well.

    >>> exceeds_physical_speed(400.0, 1.0)      # 400 km in a second
    True
    >>> exceeds_physical_speed(25.0, 600.0)     # 25 km after a 10-minute dropout
    False
    """
    if dt_sec is None or dt_sec <= 0:
        return False
    return (km / (dt_sec / 3600.0)) > ceiling_kmh


def filter_high_quality_points(
    gps_points: Optional[Sequence[Any]],
    *,
    max_hdop: float = 3.0,
    min_speed_mps: float = 1.0,
    min_gap_sec: float = 1.0,
    spatial_outlier_km: float = SPATIAL_OUTLIER_KM,
    teleport_speed_ceiling_kmh: float = TELEPORT_SPEED_CEILING_KMH,
    teleport_jump_floor_km: float = TELEPORT_JUMP_FLOOR_KM,
    teleport_step_multiple: float = TELEPORT_STEP_MULTIPLE,
) -> list:
    """Return the points of ``gps_points`` that survive every noise test.

    Args:
        gps_points: Any sequence of point-like objects — see :mod:`gpxkit.points`
            for the shapes understood. Mixed shapes in one list are fine.
        max_hdop: Drop points whose ``hdop`` field exceeds this. Points with no
            ``hdop`` are kept.
        min_speed_mps: Drop points whose ``speed_mps`` / ``speed`` field is
            below this. Points with no speed field are kept.
        min_gap_sec: Drop the later of any two points less than this many
            seconds apart.
        spatial_outlier_km: Drop points further than this from the median of
            the cluster.
        teleport_speed_ceiling_kmh: Implied speed above which a seam is a
            teleport rather than a dropout.
        teleport_jump_floor_km: A seam under this many kilometres is never a
            teleport, however short the time gap.
        teleport_step_multiple: A seam under this multiple of the track's median
            step is never a teleport, however long the jump.

    Returns:
        A new list of the surviving points, in input order. The point objects
        themselves are returned unchanged — ``gpxkit`` never copies or rewrites
        your data.

    The defaults are tuned for ground vehicles at roughly 1 Hz. Walking,
    cycling, sailing and flight all want different numbers; every threshold is
    a keyword argument for exactly that reason.
    """
    if not gps_points:
        return []

    survivors: list = []
    last_ts: float | None = None

    for p in gps_points:
        # (1) Null island: the no-lock sentinel a receiver emits before it has
        # acquired satellites.
        lat_raw = point_lat(p)
        lon_raw = point_lon(p)
        if lat_raw is not None and lon_raw is not None:
            try:
                if float(lat_raw) == 0.0 and float(lon_raw) == 0.0:
                    continue
            except (TypeError, ValueError):
                pass

        # (2) HDOP ceiling. A missing or unparseable field is not a rejection.
        hdop = get_field(p, "hdop")
        if hdop is not None:
            try:
                if float(hdop) > max_hdop:
                    continue
            except (TypeError, ValueError):
                pass

        # (3) Speed floor — stationary jitter, when the receiver reports speed.
        speed = get_field(p, "speed_mps", "speed")
        if speed is not None:
            try:
                if float(speed) < min_speed_mps:
                    continue
            except (TypeError, ValueError):
                pass

        # (4) Sub-second duplicates. Points with no readable time never
        # advance the clock and are never dropped for it.
        ts_sec = point_seconds(p)
        if ts_sec is not None and last_ts is not None and (ts_sec - last_ts) < min_gap_sec:
            continue
        if ts_sec is not None:
            last_ts = ts_sec

        survivors.append(p)

    survivors = _strip_spatial_outliers(survivors, spatial_outlier_km)
    survivors = strip_teleport_runs(
        survivors,
        ceiling_kmh=teleport_speed_ceiling_kmh,
        jump_floor_km=teleport_jump_floor_km,
        step_multiple=teleport_step_multiple,
    )
    return survivors


def _strip_spatial_outliers(survivors: list, radius_km: float) -> list:
    """Drop fixes further than ``radius_km`` from the cluster's median position.

    The reference is the median latitude and the median longitude taken
    *independently*, which is cheap, robust to a minority of wild fixes, and
    good enough because the radius is deliberately coarse. Points whose
    coordinates cannot be read are kept — this test has no opinion about them.
    """
    if len(survivors) < 2:
        return survivors

    lats: list[float] = []
    lons: list[float] = []
    for p in survivors:
        lat_v, lon_v = point_lat(p), point_lon(p)
        if lat_v is None or lon_v is None:
            continue
        try:
            lats.append(float(lat_v))
            lons.append(float(lon_v))
        except (TypeError, ValueError):
            pass
    if not lats:
        return survivors

    med_lat = statistics.median(lats)
    med_lon = statistics.median(lons)
    kept: list = []
    for p in survivors:
        lat_v, lon_v = point_lat(p), point_lon(p)
        if lat_v is None or lon_v is None:
            kept.append(p)
            continue
        try:
            dist = haversine_km(float(lat_v), float(lon_v), med_lat, med_lon)
        except (TypeError, ValueError):
            kept.append(p)
            continue
        if dist <= radius_km:
            kept.append(p)
        else:
            logger.debug(
                "spatial outlier dropped: lat=%.4f lon=%.4f dist=%.0f km from median",
                float(lat_v),
                float(lon_v),
                dist,
            )
    return kept


def strip_teleport_runs(
    points: list,
    *,
    ceiling_kmh: float = TELEPORT_SPEED_CEILING_KMH,
    jump_floor_km: float = TELEPORT_JUMP_FLOOR_KM,
    step_multiple: float = TELEPORT_STEP_MULTIPLE,
) -> list:
    """Strip a leading or trailing run joined to the track by an impossible seam.

    This is the test that a per-point outlier rule cannot express. A stale lock
    is not one bad fix, it is a *run* of consecutive bad fixes that agree with
    each other; every point in the run looks fine next to its neighbours, and
    only the seam where the run meets the real track is anomalous.

    A seam qualifies only when all three hold:

    * it is longer than ``jump_floor_km`` in absolute terms,
    * it is longer than ``step_multiple`` times the track's own median step, and
    * its implied speed exceeds ``ceiling_kmh``.

    Interior points are never removed — a mid-track anomaly is a different
    problem with different correct answers (interpolate? split the track?) and
    guessing on your behalf would be wrong. At least two points always survive,
    and at most 5 % of the track is stripped from either end.
    """
    n = len(points)
    if n < 3:
        return points

    coords: list[Optional[tuple[float, float, Optional[float]]]] = []
    for p in points:
        lat_v, lon_v = point_lat(p), point_lon(p)
        if lat_v is None or lon_v is None:
            coords.append(None)
            continue
        try:
            coords.append((float(lat_v), float(lon_v), point_seconds(p)))
        except (TypeError, ValueError):
            coords.append(None)

    step_km: list[Optional[float]] = []
    for i in range(n - 1):
        a, b = coords[i], coords[i + 1]
        step_km.append(None if a is None or b is None else haversine_km(a[0], a[1], b[0], b[1]))
    known = sorted(s for s in step_km if s is not None)
    if not known:
        return points

    # Upper-middle element rather than a true median: with an even number of
    # steps the average of the two middles could sit between a dense cluster
    # and a sparse one, and the threshold should follow the sparser reality.
    median_step = known[len(known) // 2]
    seam_threshold = max(jump_floor_km, step_multiple * median_step)

    def _is_seam(i: int) -> bool:
        a, b = coords[i], coords[i + 1]
        km = step_km[i]
        if a is None or b is None or km is None or km <= seam_threshold:
            return False
        dt = None if a[2] is None or b[2] is None else (b[2] - a[2])
        return exceeds_physical_speed(km, dt, ceiling_kmh=ceiling_kmh)

    max_strip = max(1, int(n * _MAX_STRIP_FRACTION))
    start = 0
    for i in range(min(max_strip, n - 1)):
        if _is_seam(i):
            start = i + 1
            break
    end = n
    for j in range(min(max_strip, n - 1)):
        if _is_seam(n - 2 - j):
            end = n - 1 - j
            break

    if start == 0 and end == n:
        return points
    if end - start < 2:
        return points
    logger.debug("teleport strip: dropped %d leading + %d trailing point(s)", start, n - end)
    return points[start:end]
