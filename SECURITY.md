# Security Policy

## Supported versions

Only the latest released tag receives fixes. Pin a released `v*` tag; `main` is
unstable.

## What gpxkit's attack surface actually is

gpxkit is a pure-Python library with no dependencies. It opens no files, makes
no network calls, spawns no subprocesses, and executes nothing it is given. It
reads attributes and dictionary keys off the objects you hand it and returns
numbers and sub-lists.

That makes the realistic risks narrow, and worth stating plainly:

- **Denial of service via input size.** Every function is at worst linear or
  `n log n` in the number of points, but nothing here caps input length or
  guards recursion. If you pass an attacker-controlled track, bound its size
  before you do.
- **Attribute access on hostile objects.** The accessors call `getattr` and
  `.timestamp()` on whatever you pass. If a point object's property has side
  effects, gpxkit will trigger them. Do not pass objects you do not trust.
- **Wrong answers as a security property.** If you gate a decision on
  `locked_gps_coverage` or `window_stationary_fraction`, an incorrect result is
  a real bug worth reporting, not merely a correctness nit — particularly any
  case where an *unmeasurable* input returns a number instead of `None`.

## Privacy

gpxkit processes location data, which is personal data in most jurisdictions.
The library itself stores nothing and transmits nothing; everything is in
memory and returned to you. The obligations that come with location history are
yours.

Every coordinate in this repository is synthetic. If you believe a real track
has been committed here, report it privately as a vulnerability — do not open a
public issue naming it.

## Reporting a vulnerability

Do **not** open a public issue for a security report.

- Preferred: GitHub's **Security → Report a vulnerability** tab on this
  repository.
- Fallback: email **joepetjr@gmail.com** with `gpxkit security` in the subject.

Please include the affected version or commit, the impact, and reproduction
steps.

## What to expect

- Acknowledgement within 5 business days.
- Initial assessment and severity triage within 10 business days.
- Coordinated disclosure: a timeline agreed with you before any public
  write-up, and credit if you want it.
