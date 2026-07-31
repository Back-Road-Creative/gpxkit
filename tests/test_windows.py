"""Measurements over a slice of a track."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from synthetic import BASE_LAT, BASE_LON, Trackpoint

from gpxkit import (
    locked_gps_coverage,
    locked_gps_duration_coverage,
    nearest_trace_distance_km,
    trace_time_window,
    window_median_speed_mps,
    window_stationary_fraction,
)


def _dicts(times):
    return [{"lat": BASE_LAT, "lon": BASE_LON, "time": float(t)} for t in times]


class TestLockedGpsCoverage:
    def test_a_fix_every_second_is_full_coverage(self):
        assert locked_gps_coverage(_dicts(range(11)), 0.0, 10.0) == 1.0

    def test_a_dead_second_half_is_about_half(self):
        assert locked_gps_coverage(_dicts(range(6)), 0.0, 10.0) == pytest.approx(0.6)

    def test_points_outside_the_window_do_not_count(self):
        pts = _dicts(range(11)) + _dicts([100.0, 101.0])
        assert locked_gps_coverage(pts, 100.0, 110.0) == pytest.approx(0.2)

    def test_oversampling_saturates_rather_than_overflowing(self):
        five_hz = _dicts(t * 0.2 for t in range(51))
        assert locked_gps_coverage(five_hz, 0.0, 10.0) == 1.0

    def test_expected_hz_changes_the_bucket_width(self):
        # One fix every two seconds is full coverage at 0.5 Hz and half at 1 Hz.
        every_two_sec = _dicts(range(0, 11, 2))
        assert locked_gps_coverage(every_two_sec, 0.0, 10.0, expected_hz=0.5) == 1.0
        assert locked_gps_coverage(every_two_sec, 0.0, 10.0, expected_hz=1.0) == pytest.approx(0.6)

    def test_all_point_shapes_are_understood(self):
        objs = [Trackpoint(BASE_LAT, BASE_LON, None, float(t)) for t in range(11)]
        tuples = [(float(t), BASE_LAT, BASE_LON) for t in range(11)]
        assert locked_gps_coverage(objs, 0.0, 10.0) == 1.0
        assert locked_gps_coverage(tuples, 0.0, 10.0) == 1.0

    def test_degenerate_inputs_are_zero_not_one(self):
        one = _dicts([0.0])
        assert locked_gps_coverage([], 0.0, 10.0) == 0.0
        assert locked_gps_coverage(None, 0.0, 10.0) == 0.0
        assert locked_gps_coverage(one, 5.0, 5.0) == 0.0  # zero-length window
        assert locked_gps_coverage(one, 5.0, 4.0) == 0.0  # inverted window
        # A point with a position but no time cannot cover anything.
        assert locked_gps_coverage([SimpleNamespace(lat=BASE_LAT, lon=BASE_LON)], 0.0, 10.0) == 0.0

    def test_non_positive_hz_is_a_programming_error(self):
        with pytest.raises(ValueError):
            locked_gps_coverage(_dicts(range(11)), 0.0, 10.0, expected_hz=0.0)


class TestDurationCoverage:
    def test_half_the_duration_covered(self):
        assert locked_gps_duration_coverage(_dicts(range(6)), 10.0) == pytest.approx(0.6)

    def test_the_clock_origin_is_irrelevant(self):
        # The same six fixes, timestamped in a completely different clock, give
        # the same answer — that is the whole point of measuring by duration.
        near_zero = locked_gps_duration_coverage(_dicts(range(6)), 10.0)
        far_future = locked_gps_duration_coverage(_dicts(range(1_000_000, 1_000_006)), 10.0)
        assert near_zero == far_future

    def test_non_contiguous_material_is_not_penalised(self):
        # Ten seconds assembled from two five-second pieces that were nowhere
        # near each other in the original recording. A window-based measure
        # would call the gap between them dead GPS; this one does not.
        pieces = _dicts(range(5)) + _dicts(range(900, 905))
        assert locked_gps_duration_coverage(pieces, 10.0) == 1.0

    def test_oversampling_saturates(self):
        assert locked_gps_duration_coverage(_dicts(t * 0.2 for t in range(51)), 10.0) == 1.0

    def test_degenerate_inputs(self):
        assert locked_gps_duration_coverage(_dicts(range(6)), 0.0) == 0.0
        assert locked_gps_duration_coverage(_dicts(range(6)), -5.0) == 0.0
        assert locked_gps_duration_coverage(None, 10.0) == 0.0
        with pytest.raises(ValueError):
            locked_gps_duration_coverage(_dicts(range(6)), 10.0, expected_hz=-1.0)


class TestTraceTimeWindow:
    def test_min_and_max(self):
        assert trace_time_window(_dicts([5.0, 1.0, 9.0, 3.0])) == (1.0, 9.0)

    def test_under_two_fixes_is_none(self):
        assert trace_time_window([]) is None
        assert trace_time_window(None) is None
        assert trace_time_window(_dicts([4.0])) is None

    def test_points_without_time_do_not_count_towards_the_two(self):
        pts = _dicts([4.0]) + [SimpleNamespace(lat=BASE_LAT, lon=BASE_LON)]
        assert trace_time_window(pts) is None


class TestWindowMedianSpeed:
    def test_steady_motion(self):
        # 0.0001 degrees of latitude per second is 11.12 m/s.
        pts = [(float(t), BASE_LAT + t * 0.0001, BASE_LON) for t in range(11)]
        assert window_median_speed_mps(pts, 0.0, 10.0) == pytest.approx(11.12, abs=0.05)

    def test_parked_is_zero(self):
        pts = [(float(t), BASE_LAT, BASE_LON) for t in range(11)]
        assert window_median_speed_mps(pts, 0.0, 10.0) == 0.0

    def test_one_wild_fix_does_not_move_the_median(self):
        pts = [(float(t), BASE_LAT + t * 0.0001, BASE_LON) for t in range(11)]
        pts.insert(5, (4.5, BASE_LAT + 5.0, BASE_LON))  # 555 km off course
        assert window_median_speed_mps(pts, 0.0, 10.0) == pytest.approx(11.12, abs=1.0)

    def test_out_of_order_input_is_sorted_first(self):
        pts = [(float(t), BASE_LAT + t * 0.0001, BASE_LON) for t in range(11)]
        assert window_median_speed_mps(list(reversed(pts)), 0.0, 10.0) == pytest.approx(
            window_median_speed_mps(pts, 0.0, 10.0)
        )

    def test_unmeasurable_is_none(self):
        assert window_median_speed_mps([], 0.0, 10.0) is None
        assert window_median_speed_mps(None, 0.0, 10.0) is None
        assert window_median_speed_mps(_dicts([0.0]), 0.0, 10.0) is None
        # Fixes exist, but none inside the window.
        assert window_median_speed_mps(_dicts(range(11)), 500.0, 510.0) is None


class TestWindowStationaryFraction:
    def _half_and_half(self):
        # Six fixes parked (five intervals at 0 m/s), then five moving.
        still = [(float(t), BASE_LAT, BASE_LON) for t in range(6)]
        moving = [(6.0 + i, BASE_LAT + (i + 1) * 0.001, BASE_LON) for i in range(5)]
        return still + moving

    def test_fraction_and_interval_count(self):
        result = window_stationary_fraction(self._half_and_half(), 0.0, 10.0, stop_speed_mps=0.5)
        assert result is not None
        fraction, intervals = result
        assert intervals == 10
        assert fraction == pytest.approx(0.5)

    def test_threshold_is_the_caller_s_choice(self):
        # The moving intervals run at ~111 m/s here; a high enough cut-off
        # calls the whole window stationary.
        _, intervals = window_stationary_fraction(
            self._half_and_half(), 0.0, 10.0, stop_speed_mps=1000.0
        )
        assert intervals == 10
        fraction, _ = window_stationary_fraction(
            self._half_and_half(), 0.0, 10.0, stop_speed_mps=1000.0
        )
        assert fraction == 1.0

    def test_unmeasurable_is_none_and_must_not_read_as_moving(self):
        assert window_stationary_fraction([], 0.0, 10.0, stop_speed_mps=0.5) is None
        assert window_stationary_fraction(None, 0.0, 10.0, stop_speed_mps=0.5) is None
        assert window_stationary_fraction(_dicts([0.0]), 0.0, 10.0, stop_speed_mps=0.5) is None


class TestNearestTraceDistance:
    def test_exact_hit_is_zero(self):
        assert nearest_trace_distance_km(BASE_LAT, BASE_LON, _dicts(range(5)), 0.0, 10.0) == 0.0

    def test_a_known_offset(self):
        # 0.01 degrees of latitude is 1.112 km.
        pts = [(float(t), BASE_LAT, BASE_LON) for t in range(5)]
        d = nearest_trace_distance_km(BASE_LAT + 0.01, BASE_LON, pts, 0.0, 10.0)
        assert d == pytest.approx(1.112, abs=0.01)

    def test_only_in_window_fixes_are_considered(self):
        near = [(100.0, BASE_LAT, BASE_LON)]  # outside the window
        far = [(1.0, BASE_LAT + 1.0, BASE_LON)]  # inside it, 111 km away
        d = nearest_trace_distance_km(BASE_LAT, BASE_LON, near + far, 0.0, 10.0)
        assert d == pytest.approx(111.19, abs=0.1)

    def test_no_usable_fixes_is_none(self):
        assert nearest_trace_distance_km(BASE_LAT, BASE_LON, [], 0.0, 10.0) is None
        assert nearest_trace_distance_km(BASE_LAT, BASE_LON, None, 0.0, 10.0) is None
        assert nearest_trace_distance_km(BASE_LAT, BASE_LON, _dicts(range(5)), 500.0, 510.0) is None


class TestWindowBoundsAreInclusive:
    def test_a_fix_exactly_on_each_bound_counts(self):
        pts = [(0.0, BASE_LAT, BASE_LON), (10.0, BASE_LAT + 0.001, BASE_LON)]
        assert window_median_speed_mps(pts, 0.0, 10.0) is not None
        assert nearest_trace_distance_km(BASE_LAT, BASE_LON, pts, 0.0, 10.0) == 0.0
