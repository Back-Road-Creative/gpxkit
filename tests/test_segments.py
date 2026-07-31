"""Picking the segments worth naming."""

from __future__ import annotations

from types import SimpleNamespace

from gpxkit import select_significant_roads


def _seg(**kwargs):
    return SimpleNamespace(**kwargs)


class TestThresholds:
    def test_drops_the_trivial(self):
        segs = [
            _seg(name="Route 9", duration_sec=600.0, length_m=20_000.0),
            _seg(name="Mill Ln", duration_sec=5.0, length_m=100.0),
            _seg(name="Route 12", duration_sec=300.0, length_m=10_000.0),
        ]
        assert [s.name for s in select_significant_roads(segs)] == ["Route 9", "Route 12"]

    def test_both_thresholds_must_be_cleared(self):
        segs = [
            _seg(name="Long but brief", duration_sec=8.0, length_m=50_000.0),
            _seg(name="Slow but short", duration_sec=900.0, length_m=200.0),
            _seg(name="Route 9", duration_sec=600.0, length_m=20_000.0),
        ]
        assert [s.name for s in select_significant_roads(segs)] == ["Route 9"]

    def test_thresholds_are_configurable(self):
        segs = [_seg(name="Lane", duration_sec=10.0, length_m=200.0)]
        assert select_significant_roads(segs) == []
        assert len(select_significant_roads(segs, min_duration_sec=5.0, min_length_m=100.0)) == 1

    def test_drops_unnamed_segments(self):
        segs = [
            _seg(name=None, duration_sec=600.0, length_m=5000.0),
            _seg(name="", duration_sec=600.0, length_m=5000.0),
            _seg(name="Route 9", duration_sec=600.0, length_m=5000.0),
        ]
        assert [s.name for s in select_significant_roads(segs)] == ["Route 9"]

    def test_unparseable_measurements_are_dropped_not_crashed_on(self):
        segs = [
            _seg(name="Broken", duration_sec="a while", length_m=5000.0),
            _seg(name="Route 9", duration_sec=600.0, length_m=5000.0),
        ]
        assert [s.name for s in select_significant_roads(segs)] == ["Route 9"]


class TestCapAndOrder:
    def test_caps_the_count(self):
        segs = [
            _seg(name=n, duration_sec=d, length_m=5000.0)
            for n, d in [("A", 600.0), ("B", 500.0), ("C", 400.0), ("D", 300.0), ("E", 200.0)]
        ]
        assert len(select_significant_roads(segs, max_count=3)) == 3

    def test_ranks_by_duration_but_returns_in_travel_order(self):
        segs = [
            _seg(name=n, duration_sec=d, length_m=5000.0)
            for n, d in [("A", 200.0), ("B", 600.0), ("C", 400.0), ("D", 500.0)]
        ]
        # B, D, C are the three longest; they come back as B, C, D.
        assert [s.name for s in select_significant_roads(segs, max_count=3)] == ["B", "C", "D"]

    def test_under_the_cap_nothing_is_reordered(self):
        segs = [
            _seg(name="A", duration_sec=200.0, length_m=5000.0),
            _seg(name="B", duration_sec=600.0, length_m=5000.0),
        ]
        assert [s.name for s in select_significant_roads(segs)] == ["A", "B"]


class TestShapes:
    def test_mappings_work_too(self):
        segs = [
            {"name": "Route 9", "duration": 600.0, "length": 20_000.0},
            {"name": "Mill Ln", "duration": 5.0, "length": 100.0},
        ]
        assert [s["name"] for s in select_significant_roads(segs)] == ["Route 9"]

    def test_empty_input(self):
        assert select_significant_roads([]) == []
        assert select_significant_roads(None) == []

    def test_returns_the_original_records(self):
        seg = _seg(name="Route 9", duration_sec=600.0, length_m=20_000.0)
        assert select_significant_roads([seg])[0] is seg
