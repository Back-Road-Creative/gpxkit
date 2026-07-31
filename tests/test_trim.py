"""Restricting a track to the ranges that survived an edit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from synthetic import BASE_LAT, BASE_LON

from gpxkit import trim_gps_to_clip_timeline


def _track(times):
    return [(float(t), BASE_LAT + i * 0.001, BASE_LON + i * 0.001) for i, t in enumerate(times)]


class TestRanges:
    def test_keeps_only_points_inside_a_range(self):
        kept = trim_gps_to_clip_timeline(_track([0, 5, 10, 15, 20, 25, 30]), [(4.0, 11.0)])
        assert [p[0] for p in kept] == [5.0, 10.0]

    def test_several_ranges(self):
        kept = trim_gps_to_clip_timeline(
            _track(range(0, 100, 10)), [(0.0, 25.0), (50.0, 65.0), (85.0, 100.0)]
        )
        assert [p[0] for p in kept] == [0.0, 10.0, 20.0, 50.0, 60.0, 90.0]

    def test_bounds_are_inclusive(self):
        kept = trim_gps_to_clip_timeline(_track([12, 13, 14, 15, 16]), [(12.0, 16.0)])
        assert len(kept) == 5

    def test_ranges_need_not_be_sorted(self):
        kept = trim_gps_to_clip_timeline(_track([0, 10, 20, 30]), [(25.0, 35.0), (0.0, 5.0)])
        assert [p[0] for p in kept] == [0.0, 30.0]

    def test_overlapping_ranges_do_not_duplicate_a_point(self):
        kept = trim_gps_to_clip_timeline(_track([0, 10, 20]), [(0.0, 15.0), (5.0, 25.0)])
        assert [p[0] for p in kept] == [0.0, 10.0, 20.0]

    def test_output_is_in_input_order(self):
        track = _track([30, 10, 20])
        kept = trim_gps_to_clip_timeline(track, [(0.0, 100.0)])
        assert [p[0] for p in kept] == [30.0, 10.0, 20.0]


class TestNoneVersusEmpty:
    def test_none_ranges_means_no_edit_happened(self):
        track = _track([1, 2, 3])
        assert trim_gps_to_clip_timeline(track, None) == track

    def test_empty_ranges_means_nothing_survived(self):
        assert trim_gps_to_clip_timeline(_track([0, 1, 2, 3]), []) == []

    def test_none_track_is_empty(self):
        assert trim_gps_to_clip_timeline(None, [(0.0, 10.0)]) == []
        assert trim_gps_to_clip_timeline(None, None) == []


class TestTimeAccessors:
    def test_objects_with_a_recognised_attribute(self):
        pts = [SimpleNamespace(t=float(s), lat=BASE_LAT, lon=BASE_LON) for s in (0, 30, 60, 90)]
        kept = trim_gps_to_clip_timeline(pts, [(25.0, 65.0)])
        assert [p.t for p in kept] == [30.0, 60.0]

    def test_datetime_points_need_a_time_key(self):
        base = datetime(2020, 4, 22, 10, 0, 0)

        @dataclass
        class Waypoint:
            timestamp: datetime

        wps = [Waypoint(timestamp=base + timedelta(seconds=s)) for s in (0, 30, 60, 90, 120)]
        kept = trim_gps_to_clip_timeline(
            wps,
            [(25.0, 65.0)],
            time_key=lambda w: (w.timestamp - base).total_seconds(),
        )
        assert [w.timestamp for w in kept] == [
            base + timedelta(seconds=30),
            base + timedelta(seconds=60),
        ]

    def test_an_unreadable_shape_says_what_to_do_about_it(self):
        with pytest.raises(TypeError, match="time_key"):
            trim_gps_to_clip_timeline([object()], [(0.0, 10.0)])

    def test_returns_the_original_objects(self):
        pt = SimpleNamespace(t=5.0)
        assert trim_gps_to_clip_timeline([pt], [(0.0, 10.0)])[0] is pt
