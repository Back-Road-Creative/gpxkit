# gpxkit

**The GPS filter that knows a tunnel from a teleport.**

A consumer GPS receiver does not fail by going quiet. It fails by lying
confidently. It reports `(0, 0)` before it has a fix. It sits on a stale
almanac and puts you four hundred kilometres from where you are, for three
seconds, and then snaps back without comment. It jitters a metre back and forth
while you wait at a red light. Then you sum the distances between consecutive
fixes and a two-mile errand comes out at two hundred and fifty.

`gpxkit` removes that noise, and then answers questions about what is left.
Pure Python, standard library only, no dependencies, ever.

```python
from gpxkit import filter_high_quality_points

clean = filter_high_quality_points(raw_track)
```

## It works on your point type

There is no `gpxkit.Point` to convert to. Coordinates and times are read
through duck-typed accessors, so all of these are valid tracks — including all
of them in the same list:

```python
{"time": 12.0, "lat": 45.0, "lon": -99.0}     # a mapping, short keys
{"timestamp": t, "latitude": …, "longitude": …} # a mapping, GPX-schema keys
(12.0, 45.0, -99.0)                            # (t, lat, lon)
(45.0, -99.0)                                  # (lat, lon), no time
Trackpoint(lat=45.0, lon=-99.0, timestamp=12.0)  # anything with attributes
```

Whatever your GPX parser, telemetry SDK or database row hands back, `gpxkit`
reads it. Fields it cannot find are `None`, and a test that needs a field it
cannot see is skipped rather than failed — a missing HDOP channel is not
evidence of a bad fix. See `gpxkit.points`.

## The 400-kilometre spike

```python
from gpxkit import filter_high_quality_points, haversine_km

# Two minutes of real driving at 1 Hz and about 98 km/h, as (time, lat, lon).
drive = [(3.0 + i, 45.0 + i * 0.0002, -99.0 + i * 0.0002) for i in range(120)]

# The first three fixes came off a stale almanac: 400 km north, then a snap
# back to the real position one second later.
stale = [(t, 48.6, -99.0) for t in (0.0, 1.0, 2.0)]

raw = stale + drive
clean = filter_high_quality_points(raw)

def total_km(track):
    return sum(haversine_km(a[1], a[2], b[1], b[2]) for a, b in zip(track, track[1:]))
```

| | fixes | total distance |
|---|---|---|
| `raw` | 123 | 403.5 km |
| `clean` | 120 | 3.2 km |

Same two minutes of driving. One of those numbers is a trip summary; the other
is a bug report. `clean == drive` — the three stale fixes are gone and nothing
else moved.

## What it rejects, and why each test exists

| noise class | what it looks like | how it is caught |
|---|---|---|
| **Invalid coordinates** | NaN, infinite, or outside ±90° latitude / ±180° longitude | not a position at all; rejected, never clamped into plausible geography |
| **Null island** | exactly `(0.0, 0.0)` — a *valid* coordinate | it is the no-lock sentinel, not a spot in the Gulf of Guinea |
| **High HDOP** | a fix the receiver itself rates as poor | ceiling on the reported `hdop` field |
| **Stationary jitter** | a metre of drift at a red light | floor on the reported speed field |
| **Sub-second duplicates** | four fixes stamped the same second | minimum gap between consecutive fixes |
| **Spatial outliers** | one fix in another country | distance from the median of the surviving cluster |
| **Teleport runs** | a *run* of stale fixes joined to the track by an impossible seam | implied speed across the seam |

Need to know what was dropped? `filter_points_with_report` takes the same
arguments and returns a `FilterReport`: the surviving `points`, the `input_count`,
a `rejected` count for each row above, and an `outcome` (`"ok"`,
`"empty_input"`, or `"all_rejected"` — so a track that was entirely noise is not
mistaken for an empty input). It also carries `profile`: the thresholds that
run actually applied. That is `GROUND_VEHICLE_PROFILE` (`max_hdop=3.0`,
`min_speed_mps=1.0`, `min_gap_sec=1.0`, `spatial_outlier_km=500.0`, and the
three teleport thresholds) when you passed nothing, or a `"custom"`
`FilterProfile` holding your values. `gpxkit` has no walking, cycling, sailing
or flight profile; a `"custom"` profile means "your numbers", not "validated for
your activity".

```python
from gpxkit import filter_points_with_report

report = filter_points_with_report(raw_track)
report.rejected["invalid_coordinate"], report.rejected["null_island"]
report.profile.name   # "ground-vehicle", or "custom" if you changed a threshold
```

The last two are the interesting pair, because the obvious single test does
neither job properly.

### Distance alone cannot tell a dropout from a teleport

Fifty kilometres between consecutive fixes is either a catastrophe or a
Tuesday, and the distance does not tell you which:

```python
# Half an hour underground, and a 50 km jump on the far side of it.
# Nothing is wrong here.
before = [(float(i * 60), 45.0, -99.0) for i in range(10)]
after  = [(2400.0 + i * 60, 45.35 + i * 0.001, -98.6 + i * 0.001) for i in range(10)]

len(filter_high_quality_points(before + after))   # 20 — every fix survives
```

Fifty kilometres over half an hour is ninety-seven kilometres an hour. Fifty
kilometres in one second is a hundred and eighty thousand. `gpxkit` never
tests raw distance against a threshold; it tests **implied speed**, `km / hours`,
against a ceiling of 1000 km/h — far above any ground vehicle or ferry, far
below any instantaneous jump. Ferries, tunnels, underground car parks, a
receiver that simply stopped logging for a while: all preserved. Stale locks:
gone.

Two guards keep the speed test from firing on ordinary noise. A seam must
also clear an absolute floor (25 km) *and* twenty times the track's own median
step, so a dense 1 Hz trace can never trip it on jitter.

### Why single-point outlier rejection leaves a sawtooth

The intuitive filter is "drop any fix that is too far from its neighbours."
It does not work, because a stale lock is not one bad fix. It is a *run* of
consecutive bad fixes that all agree with each other.

```
 real track ──────●──●──●──●──●
                             ╲                 ← the only anomalous step
                              ●──●──●──●──●    ← the stale run: internally
                                                 consistent, looks perfect
```

In a run of five bad fixes, only the two at the seam are far from a neighbour.
The three in the middle sit a metre apart, exactly like good data. A per-point
rule drops the seam fixes and declares victory — but the run is still there,
now joined to the track by a *new* seam one fix along. Run the filter again and
it eats one more fix. Plot the result and you get a sawtooth: the polyline
shuttling between the real cluster and the stale one, adding hundreds of
kilometres every time it crosses.

A fixed radius around the median has the mirror-image problem. Make it tight
enough to catch a stale lock 50 km out and it will cut a legitimate long
journey in half. Make it loose enough to keep the journey and it waves the
stale lock through.

So `gpxkit` uses both, in order. The radius is the coarse net, deliberately
generous at 500 km, and it only has to catch the wild ones. Then
`strip_teleport_runs` looks at the *seams* — and when it finds an impossible
one near either end, it removes the whole run behind it, not just the fix at
the join.

Two limits on that, on purpose:

- **Interior anomalies are never removed.** A bad run in the middle of a track
  has several defensible fixes — interpolate across it, split the track in two,
  leave it and flag it — and which one is right depends on what you are doing.
  `gpxkit` will not guess on your behalf.
- **At most 5 % is stripped from either end,** and at least two fixes always
  survive. A filter that can quietly eat an arbitrary amount of your data is
  worse than the noise it removes.

## Asking questions about what survived

```python
from gpxkit import (
    trace_time_window,
    locked_gps_coverage,
    window_median_speed_mps,
    window_stationary_fraction,
    nearest_trace_distance_km,
)

w0, w1 = trace_time_window(clean)                      # (3.0, 122.0)

locked_gps_coverage(clean, w0, w1)                     # 1.0   — a fix every second
window_median_speed_mps(clean, w0, w1)                 # 27.24 — m/s, about 98 km/h
window_stationary_fraction(clean, w0, w1, stop_speed_mps=0.5)   # (0.0, 119)
nearest_trace_distance_km(45.05, -98.95, clean, w0, w1)         # 3.57 km
```

- **`locked_gps_coverage(track, start, end)`** — the share of a window that
  actually has fixes, bucketed so that an over-sampled trace saturates at 1.0
  instead of exceeding it and a dropout lowers it in proportion to how long it
  lasted. This is the number to demote on when you are about to make a claim
  about a stretch of a journey and want to know whether you have the evidence.
- **`locked_gps_duration_coverage(track, duration)`** — the same measure for
  material that is *not contiguous in any single clock*: a recording with
  sections cut out, a track stitched from several files, a set of fixes
  timestamped in one clock while the length you care about is measured in
  another. A start-to-end window would count every removed section as dead GPS.
  This does not.
- **`window_median_speed_mps` / `window_stationary_fraction`** — were we
  moving? Both derive speed from position and time rather than from a reported
  speed channel, because a parsed GPX file usually has no speed field and where
  one exists it is the receiver's own smoothed guess. The median answers "was
  the middle interval stopped"; the fraction answers "what share of the time
  were we stopped", against any cut-off you choose, and returns the interval
  count so you can refuse to act on a number derived from three samples.
- **`nearest_trace_distance_km(lat, lon, track, start, end)`** — how close did
  we pass to this place? Distance to the nearest *sampled fix*, not to the path
  between them, so a sparse track reports a larger number than a dense one over
  the same route.
- **`trace_time_window(track)`** — the window a track implies about itself,
  when you have not got one to supply.

Every one of these returns `None` when the answer is genuinely unmeasurable,
rather than `0.0` or `1.0`. A caller that reads "no data" as "passed" builds a
gate that opens widest exactly when it knows least.

## Trimming to an edit

If the recording a track accompanies has been cut — sections removed, a
highlight reel assembled, a trip split into legs — the raw track no longer
describes what is left, and statistics over it will include the roads you cut
out.

```python
from gpxkit import trim_gps_to_clip_timeline

survived = [(0.0, 25.0), (50.0, 65.0), (85.0, 100.0)]   # ranges that made the cut
trimmed = trim_gps_to_clip_timeline(track, survived)
```

`None` means no edit happened and returns everything; an empty list means
nothing survived and returns nothing. For `datetime` timestamps, which have no
single correct origin, pass a projection:

```python
trim_gps_to_clip_timeline(
    waypoints, survived,
    time_key=lambda wp: (wp.timestamp - journey_start).total_seconds(),
)
```

## Naming the roads

```python
from gpxkit import select_significant_roads

select_significant_roads(segments, min_duration_sec=30, min_length_m=1000, max_count=3)
```

A track matched against a road network becomes a long list of named segments,
most of which are noise — the slip road, the roundabout counted as its own way,
the forty metres of a side street you used to turn around in. This keeps the
few that lasted long enough *and* ran far enough to be worth mentioning, ranks
them by duration, and hands them back **in the order they were travelled** so
you can write a sentence with them.

## Install

```bash
pip install gpxkit
```

Python 3.11 or newer. No dependencies. From source:

```bash
git clone https://github.com/Back-Road-Creative/gpxkit.git
cd gpxkit
pip install -e '.[test]'
pytest
```

## Honest limits

- **It does not parse GPX.** It has no XML parser, no file I/O, and no opinion
  about where your points came from. Bring your own parser; `gpxkit` starts at
  the list of points. That is also why it has no dependencies.
- **The defaults are `GROUND_VEHICLE_PROFILE`, tuned for ground vehicles at roughly 1 Hz.** A 1000 km/h
  ceiling is nonsense for a hiker and useless for an aircraft; a 500 km radius
  is absurd for a park run. Every threshold is a keyword argument for exactly
  that reason — but you do have to set them.
- **Clocks are your responsibility.** The window functions cannot tell epoch
  seconds from seconds-into-a-recording. Mix them and you get `0.0` with no
  complaint. Points and window bounds must share a clock.
- **Distances are spherical, not ellipsoidal.** Haversine on a mean-radius
  sphere is up to ~0.5 % off from WGS-84. Every decision here is a threshold
  comparison three orders of magnitude coarser than that, so it does not
  matter — but do not use `haversine_km` for survey work.
- **The filter is order-dependent and single-pass.** Field tests run first,
  then the radius, then the seam test, each on the survivors of the last. It
  does not iterate to a fixed point.
- **`filter_high_quality_points` returns your objects, not copies,** and never
  mutates or interpolates. It only ever removes.

## License

MIT — see [LICENSE](LICENSE).
