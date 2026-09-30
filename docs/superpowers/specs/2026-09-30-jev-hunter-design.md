# Jev independent hunter

## Approved behaviour

A level may opt into one allied hunter. It explores independently and destroys enemies rather than following the player. Jev controls turning, thrust, and firing. The hunter perceives local surroundings and retains observations, rather than receiving the complete world state. Enemies can target and destroy it. It does not respawn within a level. Friendly fire is disabled.

Requests run outside the game loop. While awaiting a decision, the hunter briefly retains its previous inputs, then stops turning, thrusting, and firing. Existing momentum and normal physics continue. There is no fallback autopilot.

## Level configuration and lifecycle

Add an optional top-level `hunter` object to level JSON:

```json
{"hunter": {"spawn_cell": [2, 3]}}
```

Coordinates are zero-based column and row in the generated maze; spawn at the cell centre. Absence or null means no hunter. Accept exactly one object, not a count or array. Validate bounds and clearance against the actual generated maze, including player and enemy spawn exclusion. Reserve its location before enemy placement. An invalid configuration disables the hunter with a clear diagnostic rather than moving it silently. Existing level files remain unchanged unless explicitly enabled later.

Create fresh memory and health on each level start/restart. Destroying the hunter ends its requests and removes it from targeting. Level changes, restart, and shutdown invalidate outstanding results and clean up the client worker. It is not counted as an enemy and never blocks the exit.

## Components and boundaries

- `HunterShip`: a `RotatingThrusterShip` subclass owning physical state, health, fire cooldown, and distinct cyan rendering. Accepts a validated input tuple; knows nothing about HTTP or prompts.
- `HunterPerception`: constructs immutable observations from local geometry and entities and updates bounded, level-local memory. It owns visibility rules and never exposes live game objects to the worker.
- `JevPilot`: converts an observation into a typed request and validates the resulting action. A replaceable client boundary supports scripted responses in tests.
- `HunterController`: schedules requests, tracks result age and level generation, and applies inputs on the main thread. No worker mutates Pygame or world state.
- Combat integration: explicit projectile source attribution, hunter damage handling, and target selection among living player/allied ships.

Reuse existing movement, wall collision, projectile behaviour, and enemy destruction effects. Preserve the working tree's existing physics, updater, fire-rate, and level edits. Avoid unrelated refactoring.

## Jev decisions

Use the official Python `typesafe-sdk`, credentials from `TYPESAFE_API_KEY`, and configurable model default `jev-latest`. Initialise it only for enabled hunter levels; levels without a hunter require neither credentials nor a connection. Never store credentials in level files or logs.

Ask one Choice question with 12 explicitly described action options: the Cartesian product of turn `{left, none, right}`, thrust `{on, off}`, and fire `{on, off}`. A combined action keeps simultaneous controls coherent; independent questions cannot see one another's answers. Every valid tuple is permitted, including firing while turning.

Instructions describe the objective, coordinate and heading conventions, momentum, current movement constants, weapon cooldown, action horizon, and uncertainty of remembered sightings. State includes hunter position, velocity, heading, health, cooldown, previous action, observation time, visible contacts and geometry, and bounded memory. Jev alone chooses inputs; code does not aim, navigate, choose targets, or perform automatic obstacle avoidance for the hunter. Normal collision response and weapon cooldown still apply.

Validate the returned choice against the closed action set. Record confidence for diagnostics without adding an uncalibrated confidence cutoff. Unknown or missing choices and malformed responses count as failed decisions.

## Timing and failure behaviour

Initial tunable defaults:

- Request interval: 250 ms, with at most one request in flight and no backlog.
- Action expiry: 750 ms after the source snapshot, not after response arrival.
- Request timeout: 1 second; SDK automatic retries disabled for action requests.
- Transient failure backoff: 1, 2, 4, then at most 8 seconds; reset after success.

Apply a result only if its level generation still matches, the hunter is alive, and its snapshot is younger than 750 ms. A response arriving after expiry is discarded. Keep the last accepted action only until its own expiry; failure does not extend it. Before the first accepted response, coast. Fire-on repeats shots only at the weapon's allowed rate.

Use monotonic wall time for network deadlines and freshness. On pause, neutralise inputs and invalidate pending actions; send a fresh snapshot on resume. No requests run while paused. Movement and cooldown use the game's existing simulation-time conventions, with explicit conversion where needed.

Missing credentials or authentication failure leaves the configured hunter coasting, shows a concise unavailable status, and disables further requests for that level. Transient errors recover via backoff. Slow service can cause frequent coasting; these defaults are starting values, not a claim that Jev can sustain effective flight at this cadence.

## Sensors and memory

Start with a sensor radius of four maze-cell widths. Walls occlude ships and projectiles. Send visible wall portions within that radius, not whole segments whose hidden extent would disclose distant layout. Include the player as a friendly contact when visible. Contact IDs are stable within a level and do not disclose unseen entities.

Cap each snapshot at the nearest 24 visible ships/enemies and 32 projectiles, breaking ties by ID. Include relative position, velocity, heading where applicable, allegiance, and observed type. Supply distances and bearings as numeric observations without computing preferred actions.

Store observed map geometry and explored cell locations for this level only. Unknown areas remain unknown. Memory is bounded by the finite level grid; retain partial observations without revealing unobserved cell edges. Send at most 64 nearby remembered cells per request with known edges, visit counts, last-visit ages, and observed unexplored exits.

Remember at most 32 enemy contacts for 10 seconds, evicting oldest first. Each record contains last-observed position/velocity and age; it is not silently updated from hidden world state. Remove a sighting after observed destruction, expiry, or direct observation of its now-empty last-known position. Do not retain projectile sightings after they leave visibility. Memory is observational data, not learned model weights or free-form generated text.

## Combat and scoring defaults

Hunter uses player-scale movement and a forward-facing, single-shot weapon with unlimited ammunition, no upgrades, and a 250 ms cooldown. Start with three hit points. Enemy bullets and hostile ship contact each deal one damage; grant 500 ms damage immunity after a hit to avoid repeated overlap damage. Walls bounce normally and do not damage it. Friendly ships may bounce physically without damage.

Enemy behaviours that currently aim or chase the player select the nearest living player or hunter, preserving their existing range and firing rules. Recompute selection on update; ties prefer the player. Replay movement remains replay-driven, but its aiming may target the hunter. Stationary/non-attacking enemies retain their existing behaviours.

Distinguish player, hunter, and enemy projectile ownership. Player and hunter bullets hit enemies only; enemy bullets can hit either ally and are consumed once. Hunter kills execute the same destruction, spawning, and portal-condition effects as player kills, but do not award personal player kill points. Hunter damage and expenditure do not affect player collision, ammunition, or energy statistics. Existing world drops remain available to the player; the hunter does not collect upgrades.

## Diagnostics and validation

Show hunter health and pilot status (`active`, `waiting`, `coasting`, `unavailable`) with a small label. Diagnostic logs include latency, accepted/discarded decisions, action age, confidence, and error category; omit secrets. A live smoke test measures median and tail latency and the fraction of time coasting before adjusting defaults.

Tests use a fake clock and injected client; ordinary tests make no paid API calls. Cover:

1. Absent configuration, valid spawn, invalid spawn, one-per-level lifecycle, and memory reset.
2. Sensor radius, occlusion, no hidden-state leakage, contact expiry, and memory bounds.
3. All 12 actions, weapon cadence, no automatic steering, and normal momentum after neutralisation.
4. Single in-flight request, snapshot-based expiry, malformed output, timeouts, backoff, pause, death, and late results from prior levels.
5. Enemy retargeting, hunter death, friendly-fire exclusion, projectile consumption, kill attribution, and normal enemy death side effects.
6. Headless integration through level load/update/reset using fake decisions, followed by existing relevant physics/collision/level tests.

Manual verification with credentials checks responsiveness, visible distinctness, exploration, enemy engagement, destruction, and recovery from connection loss. Effective autonomous combat is an empirical validation goal, not guaranteed by the API's structured output.

## Alternatives considered

The user selected full piloting over tactical decisions or target selection with local flight control. A fixed request cadence is simpler to measure than event-triggered calls; overlapping speculative requests would increase cost and complicate stale-result handling. The first version therefore uses one request at a time. No training, persistent cross-level memory, fleet coordination, or local autopilot is included.

## Sources

- [TypeSafe introduction](https://docs.typesafe.ai/introduction): structured decision primitives and independent evaluation of questions.
- [Python SDK](https://docs.typesafe.ai/sdk/python): Python clients, package, and environment-based credentials.
- [API reference](https://docs.typesafe.ai/api): state, Choice options, response structure, and model alias.

Documentation checked 2026-09-30. Verify installed SDK compatibility with the project's Python runtime during implementation.
