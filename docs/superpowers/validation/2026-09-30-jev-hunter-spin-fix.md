# Hunter spinning regression

The configured level reproduced 12 consecutive `left_thrust_fire` choices and
1,440 degrees of rotation over twelve representative 400 ms input intervals.
The adapter asked Jev to interpret raw coordinates and select three controls in
one question. It repeated choices even when the target changed sides. Holding
turn until the next response amplified each decision into roughly 120 degrees.

A fixed-target probe isolated the representation problem. For headings 45, 0,
and 315 degrees with a target due east, the original combined question returned
straight/thrust/fire three times. A separate steering question returned
right/straight/right; adding computed body-relative direction returned the
correct left/straight/right.

The adapter now asks separate steering, thrust, and firing questions in one
request. A compact sensor view supplies body-relative contacts, observed wall
clearance, visible exploration cells, and remembered contacts with ages. These
are geometric measurements; Jev still selects every control. Steering is a
100 ms pulse, bounded by the original snapshot expiry. Subsequent observations
wait for that pulse to finish, avoiding another decision based on the heading
before the previous turn.

Validation:

- Regression first failed: a delayed result turned the real ship 90 degrees
  during the test. It now turns at most 35 degrees and retains thrust/fire.
- Body-relative direction and occluded exploration regression tests pass.
- 75 hunter tests pass; full suite: 166 pass, three existing `bounce_factor`
  failures in `tests/test_utils.py` remain.
- Original twelve-decision feedback scenario no longer repeated one turn;
  it held heading and changed steering direction. A diagnostic five-second
  timeout was needed for its first request (1.956 s); subsequent requests
  took 251–368 ms. Production one-second attempts encountered timeouts.
- Actual asynchronous controller in the configured level, with production
  timeouts: 30 seconds, 13 accepted decisions, two stale results discarded,
  135 degrees net rotation, and 1,385 frames holding heading. It moved through
  the level instead of continuously spinning. This was a navigation check
  with enemies held stationary, not a claim of complete combat proficiency.
- Separate live combat check: 15 seconds, six accepted decisions, two shots,
  zero kills. Frequent timeouts caused 81.6% coasting, so combat quality under
  poor network latency remains limited. No timeout or stale-input limits were
  relaxed to hide that limitation.

Diagnostic scripts and traces are isolated under `/tmp/astrovoid-hunter-spin`;
no credentials or debug instrumentation were added to tracked files.

The representation follows TypeSafe's primary guidance:
https://docs.typesafe.ai/model-jaggedness/jev-1.13 and
https://docs.typesafe.ai/introduction.
