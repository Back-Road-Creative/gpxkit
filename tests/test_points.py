"""The duck-typed accessors — the reason gpxkit needs no adapter for your data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from synthetic import Trackpoint

from gpxkit import get_field, point_lat, point_lon, point_seconds, point_time


class TestMappings:
    def test_short_names(self):
        p = {"time": 12.0, "lat": 45.0, "lon": -99.0}
        assert (point_lat(p), point_lon(p), point_seconds(p)) == (45.0, -99.0, 12.0)

    def test_long_names(self):
        p = {"timestamp": 12.0, "latitude": 45.0, "longitude": -99.0}
        assert (point_lat(p), point_lon(p), point_seconds(p)) == (45.0, -99.0, 12.0)

    def test_lng_spelling(self):
        assert point_lon({"lat": 45.0, "lng": -99.0}) == -99.0

    def test_missing_fields_are_none(self):
        assert point_lat({}) is None
        assert point_lon({}) is None
        assert point_seconds({}) is None

    def test_explicit_none_falls_through_to_the_alias(self):
        # A parser that emits every key, some of them null, must not shadow the
        # alias that does have a value.
        assert point_lat({"lat": None, "latitude": 45.0}) == 45.0


class TestTuples:
    def test_three_tuple_is_time_first(self):
        p = (12.0, 45.0, -99.0)
        assert (point_lat(p), point_lon(p), point_seconds(p)) == (45.0, -99.0, 12.0)

    def test_two_tuple_is_lat_lon_and_has_no_time(self):
        p = (45.0, -99.0)
        assert (point_lat(p), point_lon(p)) == (45.0, -99.0)
        assert point_time(p) is None
        assert point_seconds(p) is None

    def test_lists_behave_like_tuples(self):
        assert point_lat([12.0, 45.0, -99.0]) == 45.0

    def test_one_element_sequence_is_unreadable(self):
        assert point_lat((12.0,)) is None
        assert point_lon((12.0,)) is None

    def test_extra_trailing_elements_are_ignored(self):
        # A (t, lat, lon, elevation) row still reads correctly.
        assert point_lat((12.0, 45.0, -99.0, 310.0)) == 45.0
        assert point_lon((12.0, 45.0, -99.0, 310.0)) == -99.0


class TestObjects:
    def test_attribute_object(self):
        p = SimpleNamespace(lat=45.0, lon=-99.0, time=12.0)
        assert (point_lat(p), point_lon(p), point_seconds(p)) == (45.0, -99.0, 12.0)

    def test_dataclass_trackpoint(self):
        p = Trackpoint(lat=45.0, lon=-99.0, elevation=310.0, timestamp=12.0)
        assert (point_lat(p), point_lon(p), point_seconds(p)) == (45.0, -99.0, 12.0)

    def test_object_without_the_fields_is_none_not_an_error(self):
        assert point_lat(object()) is None
        assert point_seconds(object()) is None


class TestTimeConversion:
    def test_datetime_becomes_epoch_seconds(self):
        base = datetime(2020, 1, 1, tzinfo=timezone.utc)
        later = base + timedelta(seconds=30)
        assert point_seconds({"time": later}) - point_seconds({"time": base}) == 30.0

    def test_numeric_string_is_coerced(self):
        assert point_seconds({"time": "12.5"}) == 12.5

    def test_unparseable_time_is_none(self):
        assert point_seconds({"time": "half past four"}) is None

    def test_broken_timestamp_method_is_none(self):
        class Exploding:
            def timestamp(self):
                raise RuntimeError("no clock here")

        assert point_seconds({"time": Exploding()}) is None


class TestGetField:
    def test_first_present_alias_wins(self):
        assert get_field({"speed": 3.0, "speed_mps": 7.0}, "speed_mps", "speed") == 7.0

    def test_default_when_absent(self):
        assert get_field({}, "hdop", default=1.0) == 1.0

    def test_default_when_present_but_none(self):
        assert get_field({"hdop": None}, "hdop", default=1.0) == 1.0

    def test_zero_is_a_real_value_not_a_miss(self):
        assert get_field({"speed": 0.0}, "speed", default=9.9) == 0.0
