# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- `gpxkit.filters.filter_points_with_report` and `FilterReport` — the filter
  plus per-class rejected-point counts and an explicit `outcome`
  (`ok` / `empty_input` / `all_rejected`).

### Fixed

- `filter_high_quality_points` now drops fixes whose latitude or longitude is
  NaN, infinite, or out of range (`|lat| > 90`, `|lon| > 180`) at intake,
  before the null-island and statistical tests. Previously such a fix passed
  through and could skew the cluster median.

## 0.1.0

First release.

### Added

- `gpxkit.points` — duck-typed accessors (`point_lat`, `point_lon`,
  `point_time`, `point_seconds`, `get_field`) that read mappings, `(t, lat,
  lon)` and `(lat, lon)` sequences, and arbitrary attribute objects, so no
  adapter layer is needed for a caller's own point type.
- `gpxkit.geo.haversine_km` — great-circle distance on a mean-radius sphere.
- `gpxkit.filters.filter_high_quality_points` — single-pass noise rejection:
  null-island sentinels, an HDOP ceiling, a reported-speed floor, sub-second
  duplicates, spatial outliers beyond a radius from the cluster median, and
  leading or trailing teleport runs. Every threshold is a keyword argument.
- `gpxkit.filters.exceeds_physical_speed` — the implied-speed discriminator
  that separates a legitimate dropout from a stale lock.
- `gpxkit.filters.strip_teleport_runs` — run-level seam stripping, exposed
  separately for callers that want it without the rest of the pipeline.
- `gpxkit.windows` — `locked_gps_coverage`, `locked_gps_duration_coverage`,
  `trace_time_window`, `window_median_speed_mps`, `window_stationary_fraction`
  and `nearest_trace_distance_km`, each returning `None` rather than a default
  when the answer is unmeasurable.
- `gpxkit.trim.trim_gps_to_clip_timeline` — restrict a track to the ranges that
  survived an edit, with an optional `time_key` projection for `datetime`
  points.
- `gpxkit.segments.select_significant_roads` — reduce a segment timeline to the
  few worth naming, ranked by duration and returned in travel order.
