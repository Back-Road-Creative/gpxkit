"""Great-circle distance."""

from __future__ import annotations

import pytest

from gpxkit import haversine_km


def test_identical_points_are_zero():
    assert haversine_km(45.0, -99.0, 45.0, -99.0) == 0.0


def test_one_degree_of_latitude_is_about_111_km():
    # A degree of latitude is ~111.19 km everywhere on a sphere.
    assert haversine_km(45.0, -99.0, 46.0, -99.0) == pytest.approx(111.19, abs=0.05)


def test_longitude_degree_shrinks_with_latitude():
    at_equator = haversine_km(0.0, 0.0, 0.0, 1.0)
    at_sixty = haversine_km(60.0, 0.0, 60.0, 1.0)
    # cos(60 degrees) is exactly 0.5, so the higher-latitude degree is half —
    # to within the curvature the flat-earth version of that rule ignores.
    assert at_sixty == pytest.approx(at_equator / 2, rel=1e-4)


def test_symmetric():
    a = haversine_km(45.0, -99.0, 30.0, -88.0)
    b = haversine_km(30.0, -88.0, 45.0, -99.0)
    assert a == pytest.approx(b, rel=1e-12)


def test_antipodal_points_do_not_raise():
    # The float clamp inside haversine_km exists for this case: without it the
    # inner term can overshoot 1.0 and asin() raises.
    d = haversine_km(0.0, 0.0, 0.0, 180.0)
    assert d == pytest.approx(20015.0, abs=1.0)


def test_crossing_the_antimeridian_is_a_short_hop():
    assert haversine_km(45.0, 179.9, 45.0, -179.9) == pytest.approx(15.7, abs=0.5)
