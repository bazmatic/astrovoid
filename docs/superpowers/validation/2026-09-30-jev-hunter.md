# Jev hunter validation — 2026-09-30

Implemented on `feat/jev-hunter` against the approved design and implementation
plan. Existing edits to the base ship, enemy avoidance, fire-rate calculator and
level 1 were preserved byte-for-byte as additions/deletions and excluded from
feature commits. No existing level was opted into the hunter.

## Automated checks

Command:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tests -q
```

Final result: **160 passed, 3 failed**. All **69 hunter tests pass**.
The three failures existed before implementation (baseline: 91 passed, 3 failed):

- `tests/test_utils.py::TestReflectVelocity::test_reflect_velocity_perpendicular`
- `tests/test_utils.py::TestReflectVelocity::test_reflect_velocity_at_angle`
- `tests/test_utils.py::TestReflectVelocity::test_reflect_velocity_with_bounce_factor`

All three call `reflect_velocity(..., bounce_factor=...)`, but the current
function does not accept that keyword. This unrelated discrepancy was left
unchanged. No new test failures were introduced.

Coverage includes all twelve simultaneous controls, hit immunity and destruction,
projectile ownership, boss death effects, all six attacking enemy updater paths,
visibility and partial wall geometry, hidden enemy movement and wall destruction,
observed deaths, capped memory, snapshot detachment, real level creation/update,
pause/resume, death without respawn, fresh state on restart, stale decision rejection,
backoff, asynchronous timeout/cancellation and repeated cancellation during cleanup.
A regression test covers restart before the worker's first request.

The real TypeSafe SDK was verified using a local HTTP mock, including request
serialization and its actual response schema. Normal game import was also tested
with SDK imports deliberately blocked. Ordinary tests use no API credentials and
make no paid requests.

## Live Jev check

A 15-second headless arena used the real SDK and model, normal ship physics,
local perception, controller, enemy updater and combat handlers. Two enemies
started near the hunter. The API key was read through a non-echoing terminal
prompt into that process only; it was not saved to repository files or logs.

| Measurement | Result |
| --- | --- |
| SDK / Python | typesafe-sdk 0.7.2 / Python 3.10.13 |
| Model | jev-latest |
| Simulation duration | 15.2 seconds |
| Frames | 830 |
| Completed requests | 27 |
| Accepted decisions | 24 |
| Stale decisions discarded | 1 |
| Request failures | 2, followed by recovery |
| Median snapshot-to-result latency | 378 ms |
| p95 snapshot-to-result latency | 1,019.5 ms |
| Time in coasting status | 36.9% |
| Hunter shots | 36 |
| Enemies destroyed | 1 |
| Final hunter health | 3/3 |
| Displacement from spawn | 1,305 pixels |

Snapshot-to-result timing includes initial client loading; the first response
was discarded as stale. The one-second timeout applies to the asynchronous API
operation. Warm decisions usually arrived within the 750 ms freshness limit.
The hunter made observable turning/thrust/firing decisions and destroyed an enemy.
The captured final arena image was inspected for distinct cyan hunter rendering.
This small arena test is not evidence of reliable navigation through difficult
mazes: repeated control choices and network interruptions still warrant play tuning.
The approved timing values were not relaxed to hide latency.

## Sensor performance

An initial extreme-maze snapshot took approximately 72 ms. Coalescing duplicate
wall edges, reusing frontmost visible geometry and caching shared cell edges
reduced the median to **7.63 ms**, maximum **21.77 ms**, across 15 positions in
three seeded 15-cell extreme mazes. This bounds only the sampled scenarios;
dense scenes can still exceed a 60 FPS frame budget on a snapshot frame.

## Packaging

The PyInstaller one-file build completed with the hunter modules and SDK included.
An eight-second headless launch stayed running without startup errors and was then
terminated by the test harness. This checks startup, not a full packaged playthrough.

Packaging checks exposed two existing configuration omissions needed by this build:
`game.py` was not included for the dynamic loader, and one-file EXE construction
omitted the Python binaries/data. The spec now includes those and explicitly
lists the dynamically reached hunter modules. The optional SDK is still imported
lazily at runtime; non-hunter levels need no key.

Build command (outputs isolated from the repository):

```bash
PYINSTALLER_CONFIG_DIR=/tmp/astrovoid-hunter-build/cache \
ASTROVOID_PYINSTALLER_MODE=onefile \
venv/bin/python -m PyInstaller --noconfirm \
  --distpath /tmp/astrovoid-hunter-build/dist \
  --workpath /tmp/astrovoid-hunter-build/work pyinstaller.spec
```

## Execution notes

All eleven implementation tasks are complete. Small component commits were
consolidated into tested groups. Cancellation uses one lazily started, app-owned
worker; level changes close its client asynchronously and invalidate generations
before permitting a replacement request. This avoids overlapping requests across
levels. The thread is closed and joined at application shutdown.

Setup and level opt-in are documented in the main README and `levels/README.md`.
The feature is ready to try from source; full-suite success still depends on
resolving the three pre-existing utility-test failures. The branch remains local.
