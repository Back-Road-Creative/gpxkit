# Contributing to gpxkit

Thanks for your interest in improving gpxkit.

## Reporting

- **Bugs and features:** open an issue. For a filtering bug, the most useful
  thing you can include is a **synthetic** track that reproduces it — a few
  lines of Python that generate the points, not an export of a real journey.
  See below.
- **Security vulnerabilities:** do not open a public issue; follow
  [`SECURITY.md`](SECURITY.md).

## Setup

Python 3.11 or newer. There are no runtime dependencies and there will not be
any — that constraint is a feature of the library, not an accident.

```bash
git clone https://github.com/Back-Road-Creative/gpxkit.git
cd gpxkit
python -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
pytest
```

CI runs `pytest` on every supported Python version. Run it locally first.

## Never commit a real GPS track

Location history is personal data. A track shows where someone lives, works,
worships and sleeps, and re-identifies them from a handful of points. **Every
coordinate in this repository is invented**, generated arithmetically from a
round-numbered anchor in an empty stretch of country, and it must stay that
way.

- New fixtures go in `tests/synthetic.py`, built from constants or a generator.
- Never paste coordinates from your own device, a friend's, a customer's, or a
  public dataset of real traces.
- If you are debugging against a real track, reproduce the failure with a
  synthetic one before you open the PR. If the bug will not reproduce
  synthetically, describe the geometry in words and we will build a fixture.

## Design rules

Three constraints shape this library. A change that breaks one needs a very
good argument.

1. **No dependencies.** Standard library only.
2. **No point type of our own.** Everything reads coordinates through
   `gpxkit.points`. If a new shape needs supporting, it is supported *there*
   and every function gets it at once.
3. **Unmeasurable is `None`.** Never return `0.0` or `1.0` to mean "not enough
   data". Callers build gates out of these numbers, and a gate that silently
   opens when it knows nothing is worse than no gate.

## Tests

- **Behaviour changes come with a test that fails before the change.** Never
  weaken or delete a test to make the suite pass.
- Thresholds are keyword arguments; a test that pins behaviour to a *default*
  value should say so, and there should be a companion test proving the
  argument actually changes the outcome.
- Doctests in the source count — `pytest` runs them.

## Commits and pull requests

- Conventional commit subjects (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- One logical change per pull request, with the reasoning in the description.
- Update `CHANGELOG.md` under an `## Unreleased` heading in the same change.
- Update the README in the same change when behaviour or the public API moves.
- Pin GitHub Actions to a version tag, never a moving branch.

## Conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
