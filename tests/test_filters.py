"""Noise rejection: what gets dropped, what must survive, and on which shapes.

Coordinates are synthetic throughout — see ``synthetic.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from synthetic import BASE_LAT, BASE_LON, FAR_LAT, FAR_LON, Trackpoint, straight_track

from gpxkit import exceeds_physical_speed, filter_high_quality_points, strip_teleport_runs


def _p(**kwargs):
    return SimpleNamespace(**kwargs)


def _ts(seconds_offset: float) -> datetime:
    base = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(seconds=seconds_offset)


class TestFieldDrivenGates:
    """HDOP and reported speed — only fire when the point carries the field."""

    def test_drops_high_hdop(self):
        points = [
            _p(hdop=1.2, speed_mps=10.0, time=_ts(0)),
            _p(hdop=8.5, speed_mps=10.0, time=_ts(2)),
            _p(hdop=2.0, speed_mps=10.0, time=_ts(4)),
        ]
        out = filter_high_quality_points(points, max_hdop=3.0)
        assert [p.hdop for p in out] == [1.2, 2.0]

    def test_drops_stationary_jitter(self):
        points = [
            _p(hdop=1.0, speed_mps=10.0, time=_ts(0)),
            _p(hdop=1.0, speed_mps=0.2, time=_ts(2)),
            _p(hdop=1.0, speed_mps=12.0, time=_ts(4)),
        ]
        out = filter_high_quality_points(points, min_speed_mps=1.0)
        assert [p.speed_mps for p in out] == [10.0, 12.0]

    def test_bare_speed_field_is_also_read(self):
        points = [
            _p(speed=10.0, time=_ts(0)),
            _p(speed=0.1, time=_ts(2)),
        ]
        assert len(filter_high_quality_points(points, min_speed_mps=1.0)) == 1

    def test_unparseable_field_never_drops_a_point(self):
        # A garbage value is not evidence of a bad fix.
        points = [_p(hdop="n/a", speed_mps="fast", time=_ts(0)), _p(hdop=1.0, time=_ts(5))]
        assert len(filter_high_quality_points(points)) == 2

    def test_missing_fields_keep_the_point(self):
        points = [_p(time=_ts(0)), _p(time=_ts(5))]
        assert len(filter_high_quality_points(points)) == 2

    def test_gates_are_inert_on_a_shape_with_no_such_fields(self):
        # A GPX-style trackpoint carries neither HDOP nor speed. Even with
        # absurd thresholds it must not be rejected for fields it cannot have.
        pts = [
            Trackpoint(lat=BASE_LAT, lon=BASE_LON, timestamp=0.0),
            Trackpoint(lat=BASE_LAT + 0.001, lon=BASE_LON, timestamp=5.0),
        ]
        out = filter_high_quality_points(pts, max_hdop=0.1, min_speed_mps=1000.0)
        assert len(out) == 2


class TestNullIsland:
    def test_drops_null_island_points(self):
        points = [
            _p(lat=BASE_LAT, lon=BASE_LON, time=_ts(0)),
            _p(lat=0.0, lon=0.0, time=_ts(2)),
            _p(lat=BASE_LAT + 0.03, lon=BASE_LON + 0.04, time=_ts(4)),
        ]
        out = filter_high_quality_points(points)
        assert 0.0 not in [p.lat for p in out]
        assert len(out) == 2

    def test_all_null_island_returns_empty(self):
        points = [_p(lat=0.0, lon=0.0, time=_ts(i)) for i in range(5)]
        assert filter_high_quality_points(points) == []

    def test_a_genuine_zero_on_one_axis_survives(self):
        # Only (0, 0) is the sentinel. The equator and the prime meridian are
        # real places and a fix on either must not be discarded.
        on_the_equator = [
            _p(lat=0.0, lon=10.0, time=_ts(0)),
            _p(lat=0.0, lon=10.001, time=_ts(5)),
        ]
        on_the_meridian = [
            _p(lat=10.0, lon=0.0, time=_ts(0)),
            _p(lat=10.001, lon=0.0, time=_ts(5)),
        ]
        assert len(filter_high_quality_points(on_the_equator)) == 2
        assert len(filter_high_quality_points(on_the_meridian)) == 2


class TestSubSecondDuplicates:
    def test_dedupes_sub_second_points(self):
        points = [
            _p(hdop=1.0, speed_mps=10.0, time=_ts(0.0)),
            _p(hdop=1.0, speed_mps=10.0, time=_ts(0.3)),
            _p(hdop=1.0, speed_mps=10.0, time=_ts(0.7)),
            _p(hdop=1.0, speed_mps=10.0, time=_ts(1.5)),
        ]
        assert len(filter_high_quality_points(points, min_gap_sec=1.0)) == 2

    def test_points_with_no_time_are_never_deduped(self):
        points = [_p(lat=BASE_LAT, lon=BASE_LON) for _ in range(4)]
        assert len(filter_high_quality_points(points, min_gap_sec=1.0)) == 4

    def test_a_clean_one_hertz_track_survives_intact(self):
        points = [_p(hdop=1.0, speed_mps=15.0, time=_ts(i)) for i in range(0, 20, 2)]
        assert len(filter_high_quality_points(points)) == len(points)


class TestSpatialOutliers:
    def test_drops_a_fix_far_from_the_cluster(self):
        cluster = [
            _p(lat=BASE_LAT + i * 0.01, lon=BASE_LON + i * 0.01, time=_ts(i * 2))
            for i in range(20)
        ]
        wrong_lock = _p(lat=FAR_LAT, lon=FAR_LON, time=_ts(100))
        out = filter_high_quality_points(cluster + [wrong_lock])
        assert FAR_LAT not in [p.lat for p in out]
        assert len(out) == 20

    def test_a_long_legitimate_journey_is_not_split(self):
        # Two legs ~540 km apart, joined by five hours of driving. Neither the
        # radius test nor the speed test may decide half the journey is noise.
        leg_a = [
            _p(lat=BASE_LAT + i * 0.05, lon=BASE_LON + i * 0.02, time=_ts(i * 60))
            for i in range(10)
        ]
        leg_b = [
            _p(lat=49.0 + i * 0.01, lon=-94.0 + i * 0.01, time=_ts(20_000 + i * 60))
            for i in range(10)
        ]
        assert len(filter_high_quality_points(leg_a + leg_b)) == 20

    def test_radius_is_configurable(self):
        # 111 km out, reached slowly enough that the speed test has no opinion.
        # The default radius keeps it; a tight one does not — proof the default
        # is a choice, not a constant baked into the algorithm.
        cluster = [
            _p(lat=BASE_LAT + i * 0.001, lon=BASE_LON, time=_ts(i * 10)) for i in range(20)
        ]
        far = _p(lat=BASE_LAT + 1.0, lon=BASE_LON, time=_ts(1000))
        assert len(filter_high_quality_points(cluster + [far])) == 21
        assert len(filter_high_quality_points(cluster + [far], spatial_outlier_km=50.0)) == 20

    def test_points_without_coordinates_are_left_alone(self):
        pts = [
            _p(lat=BASE_LAT, lon=BASE_LON, time=_ts(0)),
            _p(time=_ts(5)),  # no position at all
            _p(lat=BASE_LAT + 0.001, lon=BASE_LON, time=_ts(10)),
        ]
        assert len(filter_high_quality_points(pts)) == 3


class TestTeleportRuns:
    """The test a per-point outlier rule cannot express."""

    def _head_and_body(self, seam_dt_sec: float):
        # Three identical stale fixes, then 120 real ones 55 km to the south.
        # Only the time gap across the seam differs between the two cases.
        head = [(float(t), BASE_LAT + 0.5, BASE_LON) for t in (0.0, 1.0, 2.0)]
        body = straight_track(120, start_t=2.0 + seam_dt_sec)
        return head, body

    def test_impossible_seam_strips_the_leading_run(self):
        head, body = self._head_and_body(seam_dt_sec=1.0)  # 55 km in one second
        out = filter_high_quality_points(head + body)
        assert out == body

    def test_the_same_jump_after_a_long_dropout_survives(self):
        # 55 km over 20 minutes is 167 km/h — a tunnel, a ferry, or a receiver
        # that simply stopped logging. Identical distance, opposite verdict.
        head, body = self._head_and_body(seam_dt_sec=1200.0)
        out = filter_high_quality_points(head + body)
        assert len(out) == len(head) + len(body)

    def test_the_radius_test_alone_would_have_kept_the_stale_run(self):
        # The stale run sits ~55 km out — nowhere near the 500 km radius. Turn
        # the seam test off (by raising its floor out of reach) and every stale
        # fix survives, which is exactly why the seam test has to exist.
        head, body = self._head_and_body(seam_dt_sec=1.0)
        out = filter_high_quality_points(head + body, teleport_jump_floor_km=1e9)
        assert len(out) == len(head) + len(body)

    def test_interior_anomalies_are_never_removed(self):
        # A single impossible fix in the middle of the track is left in place:
        # gpxkit does not guess whether you want it interpolated or split.
        before = straight_track(60)
        after = straight_track(60, start_t=61.0)
        spike = (60.0, BASE_LAT + 0.5, BASE_LON)
        out = filter_high_quality_points(before + [spike] + after)
        assert spike in out

    def test_never_strips_below_two_points(self):
        assert len(strip_teleport_runs([(0.0, BASE_LAT, BASE_LON)])) == 1
        two = [(0.0, BASE_LAT, BASE_LON), (1.0, BASE_LAT + 0.5, BASE_LON)]
        assert strip_teleport_runs(two) == two

    def test_a_track_with_no_readable_positions_is_returned_unchanged(self):
        pts = [_p(time=_ts(i)) for i in range(5)]
        assert strip_teleport_runs(pts) == pts

    def test_ceiling_is_configurable(self):
        # Lower the ceiling below the seam's implied speed and the previously
        # legitimate dropout becomes a teleport.
        head, body = self._head_and_body(seam_dt_sec=1200.0)  # ~167 km/h
        out = filter_high_quality_points(head + body, teleport_speed_ceiling_kmh=100.0)
        assert out == body

    def test_jump_floor_protects_short_hops(self):
        # Raise the floor above the seam distance and the seam stops counting,
        # however impossible its speed.
        head, body = self._head_and_body(seam_dt_sec=1.0)
        out = filter_high_quality_points(head + body, teleport_jump_floor_km=500.0)
        assert len(out) == len(head) + len(body)


class TestExceedsPhysicalSpeed:
    def test_instant_jump_is_impossible(self):
        assert exceeds_physical_speed(400.0, 1.0) is True

    def test_long_dropout_is_plausible(self):
        assert exceeds_physical_speed(25.0, 600.0) is False

    def test_unknown_spacing_cannot_prove_a_teleport(self):
        assert exceeds_physical_speed(10_000.0, None) is False
        assert exceeds_physical_speed(10_000.0, 0.0) is False
        assert exceeds_physical_speed(10_000.0, -5.0) is False

    def test_ceiling_is_a_strict_greater_than(self):
        # Exactly 1000 km/h is not "exceeds".
        assert exceeds_physical_speed(1000.0, 3600.0) is False
        assert exceeds_physical_speed(1000.1, 3600.0) is True


class TestPointShapesShareTheSameGates:
    """Positional tuples and plain objects must not be second-class inputs."""

    def test_null_island_tuple_dropped(self):
        pts = [(0.0, 0.0, 0.0), (2.0, BASE_LAT, BASE_LON), (4.0, BASE_LAT + 0.1, BASE_LON - 0.1)]
        out = filter_high_quality_points(pts)
        assert (0.0, 0.0, 0.0) not in out
        assert len(out) == 2

    def test_bare_two_tuple_null_island_dropped(self):
        pts = [(0.0, 0.0), (BASE_LAT, BASE_LON), (BASE_LAT + 0.1, BASE_LON - 0.1)]
        assert (0.0, 0.0) not in filter_high_quality_points(pts)

    def test_sub_second_tuple_deduped(self):
        pts = [
            (0.0, BASE_LAT, BASE_LON),
            (0.4, BASE_LAT, BASE_LON),
            (3.0, BASE_LAT + 0.1, BASE_LON - 0.1),
        ]
        out = filter_high_quality_points(pts, min_gap_sec=1.0)
        assert [p[0] for p in out] == [0.0, 3.0]

    def test_spatial_outlier_tuple_dropped(self):
        pts = [
            (0.0, BASE_LAT, BASE_LON),
            (1.0, BASE_LAT + 0.01, BASE_LON - 0.01),
            (2.0, BASE_LAT + 0.02, BASE_LON - 0.02),
            (3.0, FAR_LAT, FAR_LON),
        ]
        out = filter_high_quality_points(pts)
        assert (3.0, FAR_LAT, FAR_LON) not in out
        assert len(out) == 3

    def test_teleport_head_stripped_on_the_tuple_path(self):
        body = [(float(100 + i), BASE_LAT + i * 0.001, BASE_LON) for i in range(8)]
        head = (99.0, BASE_LAT + 1.0, BASE_LON)  # 111 km in one second
        out = filter_high_quality_points([head] + body)
        assert out == body

    def test_null_island_object_dropped(self):
        pts = [
            Trackpoint(lat=0.0, lon=0.0, timestamp=0.0),
            Trackpoint(lat=BASE_LAT, lon=BASE_LON, elevation=310.0, timestamp=2.0),
            Trackpoint(lat=BASE_LAT + 0.1, lon=BASE_LON - 0.1, elevation=311.0, timestamp=4.0),
        ]
        out = filter_high_quality_points(pts)
        assert all(not (p.lat == 0.0 and p.lon == 0.0) for p in out)
        assert len(out) == 2

    def test_spatial_outlier_object_dropped(self):
        pts = [
            Trackpoint(lat=BASE_LAT, lon=BASE_LON, timestamp=0.0),
            Trackpoint(lat=BASE_LAT + 0.01, lon=BASE_LON - 0.01, timestamp=1.0),
            Trackpoint(lat=BASE_LAT + 0.02, lon=BASE_LON - 0.02, timestamp=2.0),
            Trackpoint(lat=FAR_LAT, lon=FAR_LON, timestamp=3.0),
        ]
        assert len(filter_high_quality_points(pts)) == 3

    def test_sub_second_object_deduped(self):
        pts = [
            Trackpoint(lat=BASE_LAT, lon=BASE_LON, timestamp=0.0),
            Trackpoint(lat=BASE_LAT, lon=BASE_LON, timestamp=0.3),
            Trackpoint(lat=BASE_LAT + 0.1, lon=BASE_LON - 0.1, timestamp=3.0),
        ]
        assert len(filter_high_quality_points(pts, min_gap_sec=1.0)) == 2

    def test_dict_null_island_dropped(self):
        pts = [
            {"time": 0.0, "lat": 0.0, "lon": 0.0},
            {"time": 2.0, "lat": BASE_LAT, "lon": BASE_LON},
        ]
        assert len(filter_high_quality_points(pts)) == 1

    def test_dict_hdop_gate_fires(self):
        pts = [
            {"time": 0.0, "lat": BASE_LAT, "lon": BASE_LON, "hdop": 9.0},
            {"time": 5.0, "lat": BASE_LAT + 0.1, "lon": BASE_LON, "hdop": 1.0},
        ]
        out = filter_high_quality_points(pts, max_hdop=3.0)
        assert [p["hdop"] for p in out] == [1.0]

    def test_mixed_shapes_in_one_track(self):
        pts = [
            {"time": 0.0, "lat": 0.0, "lon": 0.0},
            (2.0, BASE_LAT, BASE_LON),
            Trackpoint(lat=BASE_LAT + 0.01, lon=BASE_LON, timestamp=4.0),
            _p(lat=BASE_LAT + 0.02, lon=BASE_LON, time=6.0),
        ]
        assert len(filter_high_quality_points(pts)) == 3


class TestEmptyAndDegenerate:
    @pytest.mark.parametrize("empty", [[], None, ()])
    def test_empty_input(self, empty):
        assert filter_high_quality_points(empty) == []

    def test_single_point_passes_through(self):
        pts = [(0.0, BASE_LAT, BASE_LON)]
        assert filter_high_quality_points(pts) == pts

    def test_input_list_is_not_mutated(self):
        pts = [(0.0, 0.0, 0.0), (2.0, BASE_LAT, BASE_LON), (4.0, BASE_LAT + 0.1, BASE_LON)]
        original = list(pts)
        filter_high_quality_points(pts)
        assert pts == original

    def test_surviving_objects_are_the_originals_not_copies(self):
        a = _p(lat=BASE_LAT, lon=BASE_LON, time=_ts(0))
        out = filter_high_quality_points([a])
        assert out[0] is a
