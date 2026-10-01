"""The effective threshold profile a filter run used, and how it is named.

Coordinates are synthetic throughout — see ``synthetic.py``.
"""

from __future__ import annotations

import dataclasses

import pytest
from synthetic import BASE_LAT, BASE_LON, straight_track

from gpxkit import (
    GROUND_VEHICLE_PROFILE,
    SPATIAL_OUTLIER_KM,
    TELEPORT_JUMP_FLOOR_KM,
    TELEPORT_SPEED_CEILING_KMH,
    TELEPORT_STEP_MULTIPLE,
    FilterProfile,
    filter_points_with_report,
)


class TestGroundVehicleProfile:
    def test_names_the_existing_defaults(self):
        assert GROUND_VEHICLE_PROFILE.name == "ground-vehicle"
        assert GROUND_VEHICLE_PROFILE.max_hdop == 3.0
        assert GROUND_VEHICLE_PROFILE.min_speed_mps == 1.0
        assert GROUND_VEHICLE_PROFILE.min_gap_sec == 1.0
        assert GROUND_VEHICLE_PROFILE.spatial_outlier_km == SPATIAL_OUTLIER_KM
        assert GROUND_VEHICLE_PROFILE.teleport_speed_ceiling_kmh == TELEPORT_SPEED_CEILING_KMH
        assert GROUND_VEHICLE_PROFILE.teleport_jump_floor_km == TELEPORT_JUMP_FLOOR_KM
        assert GROUND_VEHICLE_PROFILE.teleport_step_multiple == TELEPORT_STEP_MULTIPLE

    def test_is_immutable(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            GROUND_VEHICLE_PROFILE.max_hdop = 9.0  # type: ignore[misc]

    def test_profile_is_the_single_source_of_the_function_defaults(self):
        # If the signature defaults ever drift from the named profile, a
        # default run would report "ground-vehicle" for thresholds it did not use.
        import inspect

        from gpxkit import filter_high_quality_points

        sig = inspect.signature(filter_high_quality_points)
        for field in dataclasses.fields(GROUND_VEHICLE_PROFILE):
            if field.name == "name":
                continue
            assert sig.parameters[field.name].default == getattr(GROUND_VEHICLE_PROFILE, field.name)


class TestReportCarriesTheEffectiveProfile:
    def test_a_default_run_reports_the_ground_vehicle_profile(self):
        report = filter_points_with_report(straight_track(n=10, step_sec=2.0))
        assert report.profile == GROUND_VEHICLE_PROFILE

    def test_empty_input_still_reports_its_profile(self):
        assert filter_points_with_report([]).profile == GROUND_VEHICLE_PROFILE
        assert filter_points_with_report(None).profile == GROUND_VEHICLE_PROFILE

    def test_all_rejected_still_reports_its_profile(self):
        report = filter_points_with_report([(0.0, 0.0, 0.0)])
        assert report.outcome == "all_rejected"
        assert report.profile == GROUND_VEHICLE_PROFILE

    def test_overrides_are_reported_and_the_run_is_not_called_ground_vehicle(self):
        report = filter_points_with_report(
            straight_track(n=10, step_sec=2.0),
            max_hdop=10.0,
            spatial_outlier_km=5.0,
        )
        assert report.profile.name == "custom"
        assert report.profile.max_hdop == 10.0
        assert report.profile.spatial_outlier_km == 5.0
        # Untouched thresholds are still reported at their effective value.
        assert report.profile.min_speed_mps == GROUND_VEHICLE_PROFILE.min_speed_mps

    def test_overriding_a_threshold_to_its_default_value_is_still_the_named_profile(self):
        report = filter_points_with_report(
            [(0.0, BASE_LAT, BASE_LON), (2.0, BASE_LAT + 0.001, BASE_LON)], max_hdop=3.0
        )
        assert report.profile == GROUND_VEHICLE_PROFILE

    def test_the_reported_profile_is_the_one_the_run_used(self):
        # A loose HDOP ceiling keeps a point the default profile drops, and the
        # report says which profile produced that result.
        pts = [{"time": 0.0, "lat": BASE_LAT, "lon": BASE_LON, "hdop": 5.0}]
        assert filter_points_with_report(pts).points == []
        loose = filter_points_with_report(pts, max_hdop=6.0)
        assert len(loose.points) == 1
        assert loose.profile.max_hdop == 6.0

    def test_profile_type_is_exported(self):
        assert isinstance(GROUND_VEHICLE_PROFILE, FilterProfile)
