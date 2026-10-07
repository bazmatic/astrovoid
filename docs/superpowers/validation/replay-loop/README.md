# Replay loop validation — 2026-10-07

Implemented on `feat/replay-loop`, on top of the existing uncommitted workspace.
The existing enemy, anemone, font, gauge, and menu work was preserved.

## Behavior covered

- Independent per-level score, time and star bests; first clears and subsequent
  improvements; durable per-profile storage; old and malformed bests data.
- R and controller Y restart during play and power-out, restore the pre-level
  total, reset the frozen state, and stop abandoned-run audio.
- Power-out displays GAME OVER immediately after the 0.5-second fade, finishes
  within 1.2 seconds, and accepts any key/button to skip. Failed runs save no bests.
- LEVELS opens and returns to the main menu, starts on the furthest level, shows
  five-star progress and a locked next tile, scrolls by rows, and supports arrows,
  d-pad and sticks. Locked tiles cannot start a level.
- Earlier-level and START_LEVEL replays save bests without changing saved progress
  or total; CONTINUE moves through replay levels and resumes ordinary play at the
  furthest level. Retrying an ordinary clear retains the original attempt's mode
  and pre-level total, preserving existing retry scoring behavior.
- Completion captions show FIRST CLEAR, NEW BEST, or signed gaps using the same
  precision as saved records. Total score has no comparison line.
- Reward stars land in order with one rising tinkle each, spring down from 2.6x,
  emit fading rings/sparks, flash together on a five-star clear, shimmer, and tint
  only newly gained record stars. Sparks are capped at 80 and screens stay opaque.
- Five main-menu buttons and the profile badge fit at 1352x878. Controls include R/Y.

## Automated checks

Targeted feature and affected integration/visual tests: **54 passed**.

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest \
  tests/test_profile_bests.py tests/test_replay_loop.py tests/test_level_select.py \
  tests/test_level_results.py tests/test_reward_stars.py tests/test_menu_visuals.py \
  tests/test_hunter_integration.py -q
```

Full suite: **982 passed, 3 failed** (25.63 seconds). Three pre-existing tests in
`tests/test_utils.py::TestReflectVelocity` pass the keyword `bounce_factor` to a
function whose parameter is `restitution`. Both that test file and the math
utility are unchanged from HEAD. Physics was left unchanged.

## Real-display captures

Captured from the real `Game.draw()` path on macOS's **cocoa** display driver at
**1352x878**, using an isolated temporary profile. The audio driver was dummy;
actual hardware-controller operation and listening to sound were not part of
this check. Input event handling and sound timing are covered by automated tests.

- [Level select](level-select.png)
- [Completion with new bests](new-best.png)
- [Stars mid-burst](stars-mid-burst.png)
- [Five-star flash](five-star-flash.png)
- [Five-button main menu](main-menu.png)
- [Restart controls](controls.png)

Inspected all six captures: text is legible, the grid and captions fit, the selected
tile is highlighted, stars show facets and landing effects, and no transparency
rectangles appear. The completed row uses the existing star-count calculation.

Reproduce from the project root (requires access to the desktop display):

```sh
PYTHONPATH=. SDL_AUDIODRIVER=dummy venv/bin/python \
  docs/superpowers/validation/replay-loop/capture.py
```

## Restart discoverability follow-up

Added a persistent **R — Restart** hint in the gameplay sidebar, including Y when
there is a connected controller. The hint stays visible below GAME OVER during
the power-out fade. Both completion screens now include **R — Retry level** in
the footer. Existing menu and replay-loop tests: **41 passed**.

Inspected fresh cocoa-driver captures:

- [Gameplay restart hint](playing-restart-hint.png)
- [Power-out restart hint](power-out-restart-hint.png)
- [Failed-screen retry hint](failed-retry-hint.png)

## Stricter star awards

New clears now require 20 / 40 / 60 / 80 / 95 points for one through five stars.
The old partial-star rounding is removed. Historical star records are retained.
Boundary, feedback, animation, menu, replay, persistence and scoring tests: **84 passed**.
Earlier captures show the pre-rebalance awards; the capture script now uses a
near-perfect run to demonstrate the five-star flash under the new thresholds.
