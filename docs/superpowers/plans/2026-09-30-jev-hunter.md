# Jev Independent Hunter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Default to inline execution unless the user selects delegation.

**Goal:** Add one optional, independently exploring allied ship per configured level, with Jev directly choosing its flight and weapon inputs from local observations and memory.

**Architecture:** Keep physical simulation and combat on the Pygame thread. A hunter controller produces detached observations, submits one asynchronous Jev decision at a time, and applies only fresh results; perception owns bounded memory, while the ship owns health and movement. Integrate allegiance and scoring into existing collision paths rather than copying enemy destruction logic.

**Tech Stack:** Python (current virtual environment: 3.10.13), Pygame, pytest, asyncio, standard-library threading, official TypeSafe Python SDK.

---

Approved source: `docs/superpowers/specs/2026-09-30-jev-hunter-design.md`, commit `92ee283`.

**Execution status:** Tasks 1–11 implemented and verified on `feat/jev-hunter`.
The original checklist below records the proposed sequence; completed work,
implementation adjustments, live measurements and baseline test exceptions are
recorded in [the validation report](../validation/2026-09-30-jev-hunter.md).

## Repository facts and execution rules

- `game.py` owns level creation, update, projectile collisions, drawing, and shutdown. `game/__init__.py` loads that file; there is no separate level manager.
- `Game.run()` converts milliseconds to frame-normalised `dt`. Hunter simulation seconds are `dt / config.FPS`; network freshness uses an injected monotonic clock.
- `Game.update()` holds enemies until `player_has_moved`; hold the hunter and its API requests as well.
- `Maze` exposes `grid_width`, `grid_height`, `cell_size_x/y`, offsets, `position_calculator`, and active destructible `WallSegment`s. Wall geometry, not the original occupancy grid, is authoritative after destruction.
- `SpawnManager.spawn_all_enemies()` clears `EntityManager`; keep `Game.hunter` separate from enemy lists.
- `Projectile.is_enemy` currently determines allegiance. Add source attribution without changing existing constructor call sites.
- Existing modifications must survive: `entities/rotating_thruster_ship.py`, `game_handlers/enemy_updater.py`, `game_handlers/fire_rate_calculator.py`, `levels/1.json`. Do not stage whole dirty files containing unrelated changes. Use selected hunks, inspect the staged diff, and commit only feature work. Do not stash, reset, or overwrite these edits.
- The numeric defaults below were approved as tunable starting values. Do not silently widen action freshness to make a slow API appear responsive.
- No existing level is automatically opted in. Enable a temporary fixture for integration tests; document the level JSON entry for the user.

## File map

| File | Responsibility |
| --- | --- |
| `hunter/__init__.py` | Lightweight package; no SDK/client initialisation |
| `hunter/model.py` | Frozen actions, observations/results, tunable settings |
| `hunter/spawn.py` | Parse optional configuration, validate cell and reserve clearance |
| `hunter/visibility.py` | Range clipping and occlusion geometry |
| `hunter/perception.py` | Local observations, IDs, remembered map and contacts |
| `hunter/jev_pilot.py` | Typed question, SDK adapter and response validation |
| `hunter/worker.py` | One asynchronous request, cancellation and client cleanup |
| `hunter/controller.py` | Freshness, cadence, failure backoff, lifecycle |
| `entities/hunter_ship.py` | Flight inputs, health, cooldown, rendering |
| `game_handlers/combat_targets.py` | Nearest living friendly target for enemies |
| `level_config.py` | Read the optional hunter entry using existing resource loading |
| `entities/projectile.py` | Player/hunter/enemy source attribution |
| `game_handlers/collision_handler.py` | Hunter damage and player-only kill credit |
| `game_handlers/enemy_updater.py` | Per-enemy target selection for chase/aim |
| `game.py` | Spawn, update, collision, draw and lifecycle wiring |
| `requirements-hunter.txt` | Optional TypeSafe dependency, selected after compatibility check |
| `README.md`, `levels/README.md`, `tests/README.md` | Setup, level opt-in and verification |
| `tests/test_hunter_*.py` | Focused behaviour tests, fake clocks/clients, integration |

## Task 1: Establish action and timing contracts

**Create:** `hunter/__init__.py`, `hunter/model.py`, `tests/test_hunter_model.py`.

- [ ] Write the action contract test:

```python
from hunter.model import ACTIONS, NEUTRAL, PilotAction, HunterSettings

def test_controls_are_complete_and_neutral_is_explicit():
    assert len(ACTIONS) == 12
    assert set(ACTIONS.values()) == {
        PilotAction(turn, thrust, fire)
        for turn in (-1, 0, 1)
        for thrust in (False, True)
        for fire in (False, True)
    }
    assert NEUTRAL == PilotAction(0, False, False)
    assert HunterSettings().action_ttl == 0.750
```

- [ ] Run `venv/bin/python -m pytest tests/test_hunter_model.py -q`; expect import failure before implementation.
- [ ] Implement the shared value types below; make `hunter/__init__.py` contain only a package docstring.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class PilotAction:
    turn: int
    thrust: bool
    fire: bool

NEUTRAL = PilotAction(0, False, False)
ACTIONS = {
    f'{name}_{"thrust" if thrust else "coast"}_{"fire" if fire else "hold"}':
        PilotAction(turn, thrust, fire)
    for name, turn in (("left", -1), ("none", 0), ("right", 1))
    for thrust in (False, True)
    for fire in (False, True)
}

@dataclass(frozen=True)
class HunterSettings:
    request_interval: float = 0.250
    action_ttl: float = 0.750
    request_timeout: float = 1.0
    sensor_cells: float = 4.0
    max_contacts: int = 24
    max_projectiles: int = 32
    max_memory_contacts: int = 32
    contact_ttl: float = 10.0
    max_sent_cells: int = 64
    health: int = 3
    fire_interval: float = 0.250
    damage_immunity: float = 0.500

@dataclass(frozen=True)
class PilotObservation:
    generation: int
    snapshot_at: float
    state_json: str

@dataclass(frozen=True)
class PilotDecision:
    action: PilotAction
    confidence: Optional[float]

@dataclass(frozen=True)
class PilotResult:
    generation: int
    snapshot_at: float
    finished_at: float
    decision: Optional[PilotDecision] = None
    error: Optional[str] = None
    permanent: bool = False
```

Serialising observations before handing them to a worker makes nested state immutable across threads. Use JSON-native numbers, lists and mappings; no entity references or credentials.

- [ ] Run the same test; expect pass. Commit the three new files as `feat: define hunter pilot actions and timing contracts`.

## Task 2: Add optional level parsing and spawn reservation

**Create:** `hunter/spawn.py`, `tests/test_hunter_spawn.py`. **Modify:** `level_config.py` at its loader helpers. Integration into `Game.start_level` occurs in Task 10.

- [ ] Add this parser test and parametrise malformed cases: `True`, `1`, `[]`, `{}`, string coordinates, booleans, non-integral coordinates, missing/extra keys.

```python
import pytest
from hunter.spawn import parse_hunter_cell

def test_optional_hunter_cell():
    assert parse_hunter_cell(None) is None
    assert parse_hunter_cell({"spawn_cell": [2, 3]}) == (2, 3)
    with pytest.raises(ValueError):
        parse_hunter_cell({"spawn_cell": [True, 3]})
```

- [ ] Run `venv/bin/python -m pytest tests/test_hunter_spawn.py -q`; expect failure.
- [ ] Implement the parser and level accessor:

```python
# hunter/spawn.py
def parse_hunter_cell(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"spawn_cell"}:
        raise ValueError("hunter must contain exactly spawn_cell")
    cell = value["spawn_cell"]
    if (not isinstance(cell, list) or len(cell) != 2
            or any(type(v) is not int for v in cell)):
        raise ValueError("hunter.spawn_cell must contain two integers")
    return tuple(cell)

# level_config.py
def get_level_hunter_config(level):
    data = load_level_config(level)
    return data.get("hunter") if data else None
```

- [ ] Add `resolve_hunter_spawn(value, maze, player) -> Optional[Tuple[float, float]]`. Parse; bounds-check; convert with `maze.position_calculator.grid_center_to_screen(col, row)`; reject an initial wall cell or circle/wall intersection using `circle_line_collision`; reject overlap with the player including both radii. Raise `ValueError` with the specific reason. None returns None. Test real generated maze coordinates plus small fake geometry fixtures.
- [ ] Add `reserve_hunter_clearance(positions, hunter_pos, radius)`. Filter positions whose distance is less than hunter radius plus the largest configured initial enemy radius; include mother/split boss multipliers, static/dynamic, replay, flocker, flighthouse and egg radii. Keep ordering. Reserving conservatively may reduce enemy count, consistent with existing spawn-position limits. Test a large boss cannot overlap the reserved hunter.
- [ ] Run `venv/bin/python -m pytest tests/test_hunter_spawn.py tests/test_spawn_manager.py -q`; expect pass. Commit as `feat: support optional hunter spawn cells`.

## Task 3: Give bullets explicit ownership

**Modify:** `entities/projectile.py`, `game_handlers/collision_handler.py`. **Create:** `tests/test_hunter_combat.py`.

- [ ] Add backward-compatibility tests:

```python
from entities.projectile import Projectile

def test_projectile_source_preserves_existing_calls():
    assert Projectile((100, 100), 0).source == "player"
    assert Projectile((100, 100), 0, is_enemy=True).source == "enemy"
    bullet = Projectile((100, 100), 0, source="hunter")
    assert bullet.source == "hunter"
    assert bullet.is_enemy is False
```

- [ ] Run `venv/bin/python -m pytest tests/test_hunter_combat.py -q`; expect failure.
- [ ] Append keyword-only `source: Optional[str] = None` after existing constructor parameters, preserving all existing positional calls. Replace the `is_enemy` assignment with:

```python
resolved_source = source if source is not None else (
    "enemy" if is_enemy else "player"
)
if resolved_source not in {"player", "hunter", "enemy"}:
    raise ValueError("unknown projectile source")
if is_enemy and resolved_source != "enemy":
    raise ValueError("enemy flag conflicts with projectile source")
self.source = resolved_source
self.is_enemy = resolved_source == "enemy"
```

- [ ] Add `CollisionHandler._record_projectile_kill(projectile)` and replace every `record_enemy_destroyed()` invocation in `handle_projectile_enemy_collisions` with the helper. Its complete body is:

```python
if projectile.source == "player":
    self.scoring.record_enemy_destroyed()
```

Leave destruction, momentum, sounds, drops, boss children and egg removal on the common path. Add paired player/hunter kill tests for regular enemies, all special types and bosses; spy on score and drops. Use final-hit health for multi-hit enemies. Assert hunter kills preserve death effects with zero player credit, rather than merely testing the helper.

- [ ] Run `venv/bin/python -m pytest tests/test_projectile.py tests/test_hunter_combat.py tests/test_scoring.py -q`; expect pass. Commit as `feat: attribute allied projectile kills correctly`.

## Task 4: Implement the physical hunter

**Create:** `entities/hunter_ship.py`, `tests/test_hunter_ship.py`.

- [ ] Write firing and damage tests using real `HunterShip` instances:

```python
from entities.hunter_ship import HunterShip
from hunter.model import PilotAction, NEUTRAL

def test_hunter_fire_cooldown_and_damage_immunity():
    ship = HunterShip((200, 200))
    fire = PilotAction(0, False, True)
    assert ship.step(1, fire).source == "hunter"
    assert ship.step(1, fire) is None
    assert ship.take_damage() is False
    assert ship.health == 2
    assert ship.take_damage() is False
    assert ship.health == 2
    for _ in range(31):
        ship.step(1, NEUTRAL)
    ship.take_damage()
    assert ship.health == 1
```

- [ ] Run `venv/bin/python -m pytest tests/test_hunter_ship.py -q`; expect failure.
- [ ] Implement `HunterShip(RotatingThrusterShip)` with constructor `(start_pos, settings=HunterSettings())`, `is_enemy_ship() -> False`, `step(dt, action) -> Optional[Projectile]`, `take_damage() -> bool`, and cyan `draw(screen)`.
- [ ] Use this control order in `step`: decrement cooldown/immunity by `dt / config.FPS`; apply left/right via inherited methods; call inherited thrust only when requested; fire a normal forward projectile at `radius + 5` muzzle offset if cooldown is zero; set cooldown to `settings.fire_interval`; call inherited `update(dt)` once. Return at most one projectile, never burst to catch up after a stall. Inactive ships return None and do not move/fire. Do not call enemy-avoidance helpers or auto-aim.
- [ ] Implement damage as:

```python
def take_damage(self):
    if not self.active or self.immunity_remaining > 0:
        return False
    self.health -= 1
    self.immunity_remaining = self.settings.damage_immunity
    self.active = self.health > 0
    return not self.active
```

- [ ] Draw `get_vertices()` as a cyan outlined polygon, include thrust feedback when active and blink during immunity; draw health/status separately in Task 10. Test all 12 actions, heading wrap, continued momentum when neutral, three separated damaging hits, and frame-normalised cooldown conversion. Wall collisions use inherited bounce and do not call `take_damage`.
- [ ] Run `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tests/test_hunter_ship.py tests/test_ship.py tests/test_ccd.py -q`; expect hunter tests and previously passing regressions to pass. Commit as `feat: add allied hunter ship physics and weapons`.

## Task 5: Implement local visibility without hidden geometry

**Create:** `hunter/visibility.py`, `tests/test_hunter_visibility.py`.

- [ ] Add the basic occlusion contract:

```python
from hunter.visibility import visible_point

def test_wall_hides_contact_and_range_limits_visibility():
    walls = [((5.0, -2.0), (5.0, 2.0))]
    assert visible_point((0, 0), (4, 0), walls, 10)
    assert not visible_point((0, 0), (8, 0), walls, 10)
    assert not visible_point((0, 0), (0, 11), walls, 10)
```

- [ ] Run `venv/bin/python -m pytest tests/test_hunter_visibility.py -q`; expect failure.
- [ ] Implement `visible_point(origin, point, segments, radius)` using squared range and segment intersection; intersections strictly before the target occlude it, including collinear overlap. Use a documented epsilon of `1e-7`. Test tangency, endpoint visibility and observer on a boundary.
- [ ] Implement `visible_wall_portions(origin, segments, radius)`. Clip each segment to the circle using its line parameter and quadratic roots. Deduplicate coincident clipped segments before occlusion tests. Split clipped segments at intersections with rays from origin through every clipped endpoint and at segment crossings; midpoint-test each resulting interval against all other walls. Return only frontmost visible intervals, deduplicated by endpoint coordinates. Ignore the candidate wall itself when checking occlusion. This retains partial walls without disclosing endpoints behind corners. Test a long wall crossing range, a partially occluded wall, overlapping duplicate walls, and total occlusion. Use only active walls intersecting sensor range for this geometry work; measure snapshot construction time on the existing extreme-maze fixture and keep it below one frame at configured FPS.
- [ ] Implement `visible_cell_edges(origin, cell_bounds, segments, radius)` with the same interval splitting, returning observed open/blocked edge portions. Do not label an entire edge open because its midpoint is visible. Mark an edge fully known only when its complete extent was observed. This powers remembered map exits without reading hidden `maze.grid` entries.
- [ ] Run `venv/bin/python -m pytest tests/test_hunter_visibility.py -q`; expect pass. Commit as `feat: constrain hunter vision to visible geometry`.

## Task 6: Build bounded observational memory

**Create:** `hunter/perception.py`, `tests/test_hunter_perception.py`.

- [ ] Define `HunterPerception(settings=HunterSettings())` with `observe(hunter, maze, player, enemies, projectiles, previous_action, now, generation) -> PilotObservation` and `reset()`. Use an instance-owned stable ID registry allocated only when a contact is first visible. Store entity objects only within main-thread perception, never in the serialised observation; avoid raw `id()` reuse by retaining live weak references and increasing numeric IDs.
- [ ] Write a hidden-motion regression with fake entities and a wall fixture: observe an enemy, hide it, move the real object, then decode the next observation and assert remembered coordinates remain the last observed coordinates. Also assert `age` increases and the contact expires at ten seconds. Run `venv/bin/python -m pytest tests/test_hunter_perception.py -q` before implementation and confirm failure.
- [ ] Implement snapshot keys exactly as follows:

```python
state = {
    "self": {"position": [hunter.x, hunter.y],
             "velocity": [hunter.vx, hunter.vy], "heading": hunter.angle,
             "health": hunter.health, "cooldown_seconds": hunter.fire_remaining},
    "previous_action": {"turn": previous_action.turn,
                        "thrust": previous_action.thrust,
                        "fire": previous_action.fire},
    "visible_contacts": [],
    "visible_projectiles": [],
    "visible_walls": [],
    "remembered_contacts": [],
    "remembered_cells": [],
    "physics": {"fps": config.FPS, "speed_limit": hunter.max_speed,
                "rotation_per_frame": hunter.current_rotation_speed,
                "thrust_per_frame": config.SHIP_THRUST_FORCE,
                "friction_per_frame": config.SHIP_FRICTION,
                "projectile_speed": config.PROJECTILE_SPEED},
    "action_horizon_seconds": self.settings.request_interval,
}
```

- [ ] Populate contacts only after visibility filtering. Include stable ID, type, allegiance, relative position, velocity, optional heading, distance and bearing. Use four `cell_size_x` widths for range. Sort by distance then stable ID; send at most 24 contacts and 32 projectiles. Visible friendly player consumes a contact slot. No projectile memory.
- [ ] Retain up to 32 enemy sightings, evicting oldest last-observed timestamp first. Include `age` in seconds. Refresh only actual visible contacts. Remove on observed death or visible empty last-known location; do not query an unseen object's `active` flag to erase memory. Absence from the capped payload is not proof of disappearance: visibility bookkeeping uses the uncapped visible set.
- [ ] Store explored cells keyed by `(column, row)` and observed edge portions, visit count, last-visit time. Increment count only on entering a different cell. Send nearest 64 remembered cells, including observed open edges leading into unknown cells. Leave everything outside observed portions unknown. When revisiting a destructible wall, replace only re-observed portions; hidden wall destruction must not change memory. Bounds come from maze dimensions, not hidden occupancy.
- [ ] Add tests for all caps, tie ordering, ID stability, visible-empty removal, hidden destruction, duplicate wall edges, partial cell knowledge, player allegiance, reset and JSON isolation after world mutation. Run `venv/bin/python -m pytest tests/test_hunter_visibility.py tests/test_hunter_perception.py -q`; expect pass. Commit as `feat: give hunter local sensors and bounded memory`.

## Task 7: Add the typed Jev adapter

**Create:** `hunter/jev_pilot.py`, `requirements-hunter.txt`, `tests/test_hunter_jev.py`.

- [ ] Verify SDK package metadata against Python 3.10 before selecting a dependency version. Keep it optional via `requirements-hunter.txt`; use a version pin for the release actually tested. Do not invent a version number or silently raise the base game's Python requirement. If no compatible release exists, report the concrete compatibility constraint before changing the runtime.
- [ ] Write an adapter test using an injected async client whose `system_one` returns `SimpleNamespace(choices={"pilot": SimpleNamespace(choice="left_thrust_fire", confidence=0.8)})`. Assert the adapter returns `PilotDecision(PilotAction(-1, True, True), 0.8)`, sends exactly 12 choices, and decodes `state_json` without adding hidden context. Run `venv/bin/python -m pytest tests/test_hunter_jev.py -q`; expect failure.
- [ ] Implement `JevPilot(client)` with `async decide(observation) -> PilotDecision`. Use a raw question dictionary so fake-client tests need no SDK import:

```python
import json
from hunter.model import ACTIONS, PilotDecision

PILOT_INSTRUCTIONS = (
    "Pilot an allied hunter that independently explores and destroys enemies. "
    "Choose the simultaneous flight and fire inputs for the next action horizon. "
    "Coordinates increase right and down; heading 0 points right, 90 down. "
    "Left decreases heading and right increases it. Thrust accelerates along "
    "the heading; coast preserves momentum subject to friction and collisions. "
    "Shots travel forward and fire-on repeats only when cooldown allows. "
    "Use supplied physics units: velocities are pixels per normalised frame. "
    "Avoid walls and hostile fire; seek enemies or explore observed exits. "
    "The player is friendly. Remembered positions can be stale; ages are seconds. "
    "Unknown geometry must not be assumed open."
)

class JevPilot:
    def __init__(self, client):
        self.client = client

    async def decide(self, observation):
        result = await self.client.system_one(
            state=json.loads(observation.state_json),
            questions={"pilot": {
                "type": "choice", "instructions": PILOT_INSTRUCTIONS,
                "criteria": {
                    name: {"turn": action.turn, "thrust": action.thrust,
                           "fire": action.fire}
                    for name, action in ACTIONS.items()
                },
            }},
        )
        answer = result.choices["pilot"]
        return PilotDecision(ACTIONS[answer.choice], answer.confidence)
```

- [ ] Validate confidence as absent or finite numeric data; unknown choice, missing answer and malformed response become invalid-response failures in the worker. Do not use confidence to override valid actions.
- [ ] Add the lazy client factory using `AsyncTypeSafeClient(model=os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest"), timeout=1.0, retry=RetryPolicy(max_retries=0))`. It reads credentials from the SDK's environment mechanism. SDK imports belong inside the factory; no factory call during game import or on non-hunter levels. Map missing key/dependency and HTTP 401/403 to permanent unavailable status; 429/5xx/network timeout to transient failure. Never log exception text containing request bodies or headers; log categories.
- [ ] Test every action name, malformed results and no import-time network/dependency requirement. Run the adapter tests; expect pass. Commit as `feat: connect hunter decisions to Jev`.

## Task 8: Schedule one request and enforce freshness

**Create:** `hunter/worker.py`, `hunter/controller.py`, `tests/test_hunter_controller.py`, `tests/test_hunter_worker.py`.

- [ ] Define `PilotWorker(client_factory, clock, settings=HunterSettings())` with nonblocking `submit(observation) -> bool`, `poll() -> Optional[PilotResult]`, `cancel()`, and `close()`. It lazily starts a dedicated asyncio event-loop thread, owns the client there, and permits one request task. A busy worker rejects submissions rather than queuing them. A cancellation remains busy until the coroutine's cleanup finishes. Expose read-only `busy` so the controller can avoid building snapshots until submission is possible. `close()` schedules cleanup without joining; a separate `join(timeout)` is called only during application shutdown, never during a frame update.
- [ ] Define `HunterController(worker, settings=HunterSettings(), clock=time.monotonic)` with `tick(observation_factory, running=True) -> PilotAction`, `invalidate()`, `close()`, and string `status`. `observation_factory(now, generation)` is called only when a submission can be made; test fakes can return a constant serialised snapshot.
- [ ] Write fake-clock/worker tests before implementation. The primary scenario is: snapshot at 10.0, response at 10.6 accepted, action neutral at 10.75, and an 11.0 response to that snapshot is rejected. Assert no request backlog after many ticks during one pending request. Run `venv/bin/python -m pytest tests/test_hunter_controller.py tests/test_hunter_worker.py -q`; expect failure.
- [ ] Use `asyncio.wait_for(pilot.decide(observation), timeout=settings.request_timeout)` to enforce total request deadline; SDK timeout alone is per HTTP operation. Return structured `PilotResult` for success or failure. Let cancellation propagate, perform `await client.aclose()` on the worker loop, and acknowledge cancellation before permitting another request. Never call `Future.result()` until it is done; never block `Game.update()` for network or thread joins.
- [ ] Controller acceptance gate:

```python
valid = (
    result.generation == self.generation
    and 0 <= now - result.snapshot_at < self.settings.action_ttl
    and result.decision is not None
    and result.error is None
)
if valid:
    self.action = result.decision.action
    self.action_expires_at = result.snapshot_at + self.settings.action_ttl
if now >= self.action_expires_at:
    self.action = NEUTRAL
```

- [ ] Schedule by last submission plus 250 ms, not last completion. Do not catch up missed intervals. Transient errors back off `min(8.0, 2.0 ** failure_index)` starting at index zero. Success resets backoff even if its action is already stale. Permanent failure disables requests until a new level; stale-result discard never renews action TTL.
- [ ] `invalidate()` increments generation, sets neutral inputs, clears accepted action expiry, and cancels pending work. `tick(..., running=False)` invalidates only on transition, submits nothing and returns neutral. Resume requests a new observation after cancellation completes. A level reset creates fresh perception/controller state, while an app-owned worker serialises cleanup before the next client's request. Shutdown closes and joins outside the frame update.
- [ ] Define status precedence: permanent error=`unavailable`; fresh accepted action=`active`; pending first decision=`waiting`; expired/no accepted action=`coasting` (including pending requests after expiry). Expose only timing/confidence/counters for diagnostics.
- [ ] Test timeout cancellation, HTTP failures, backoff cap/reset, death/reset/pause stale-result rejection, no request before first movement, no worker object mutation, and orderly `aclose`. Run both test files; expect pass. Commit as `feat: schedule fresh nonblocking hunter decisions`.

## Task 9: Let enemies target and damage the hunter

**Create:** `game_handlers/combat_targets.py`, `tests/test_hunter_targeting.py`. **Modify:** `game_handlers/enemy_updater.py`, `game_handlers/collision_handler.py`; extend `tests/test_hunter_combat.py`.

- [ ] Add target-selection tests with `SimpleNamespace(x, y, active, get_pos)` entities: nearest alive ally wins, player wins a tie, dead hunter is ignored, no candidates returns None. Run `venv/bin/python -m pytest tests/test_hunter_targeting.py -q`; expect failure.
- [ ] Implement:

```python
def nearest_friendly(enemy, player, hunter=None):
    candidates = [obj for obj in (player, hunter)
                  if obj is not None and obj.active]
    return min(candidates, key=lambda obj:
               (obj.x - enemy.x) ** 2 + (obj.y - enemy.y) ** 2,
               default=None)
```

- [ ] Append optional `hunter=None` to attacking enemy update methods. Inside each per-enemy iteration, choose a target, pass its position to existing movement and fire methods, and preserve player collision code. For flockers, reuse the selected position for both update and firing passes in the same frame. Replay movement stays recorder-driven. Flighthouses and eggs remain non-attacking. Do not change existing enemy-enemy avoidance behaviour.
- [ ] Add `handle_projectile_hunter_collision(projectile, hunter) -> bool`: ignore absent/dead hunter, inactive projectiles and non-enemy source; on contact consume the enemy bullet even during hunter immunity, apply existing projectile momentum physics, and call `take_damage`. Play hit/death feedback without player scoring calls. Return True on contact. Test both allies overlapping so the first collision consumes the bullet exactly once.
- [ ] Add `handle_hunter_contacts(hunter, player, enemies)`: call inherited circle collision once per active hostile, apply one damage through immunity on overlap, and bounce friendly player without damage. Use all active enemy types including eggs/flighthouses. Do not put damage in the base circle-collision hook, which cannot distinguish allegiance.
- [ ] Run `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tests/test_hunter_targeting.py tests/test_hunter_combat.py tests/test_enemy_strategies.py -q`; expect pass. Commit only selected updater hunks plus new feature files as `feat: make hunter a targetable allied combatant`.

## Task 10: Wire level lifecycle, simulation and display

**Modify:** `game.py`. **Create:** `tests/test_hunter_integration.py`.

- [ ] Create an integration fixture using `Game.__new__` with injected dummy screen, fake worker, stub sound/profile services and a small deterministic maze. Exercise real `start_level`/update entry points after supplying the fields they use; do not replace the controller or collision methods under test. Snapshot calls must be inspectable and no real credentials used.
- [ ] Test absent hunter config creates neither ship nor worker/client activity; valid config creates exactly one; invalid config logs the reason and keeps the rest of the level playable. Run `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tests/test_hunter_integration.py -q`; expect failure.
- [ ] Initialise `self.hunter`, `self.hunter_controller`, `self.hunter_perception` and lazy worker ownership to None in `Game.__init__`. Add `_close_hunter()` to invalidate/close the controller and clear ship/perception references; make it safe before first creation and on repeated calls.
- [ ] At `start_level`, close previous hunter state before creating the maze. Resolve optional spawn after player creation and before enemy placement. Filter spawn positions using reserved clearance, then construct `HunterShip`, fresh perception and controller separately from `EntityManager`. Log only validation reason if disabled. Preserve the user's edited `levels/1.json`.
- [ ] Add `_update_hunter(dt)` invoked once after the first-move gate and before enemy updates. Build observations with a copied active-enemy list, current projectile list, player and maze; let controller choose action; call `hunter.step`; append returned projectile; resolve wall collision through `maze.spatial_grid`. Pass live hunter into the updated enemy methods. Apply hunter-hostile contacts after enemy movement. Close controller immediately on death.
- [ ] At the top of `update`, suspend the controller whenever simulation is not playing, before early returns, and while waiting for first movement or exit/game-over animation. Neutralise inputs during these transitions. Normal playing resume requests a fresh observation. `complete_level`, restart and `run`'s `finally` close hunter resources; network cleanup must not stall an update.
- [ ] In the projectile loop, player-first then hunter collision gives deterministic single consumption if both overlap. Check hunter projectile collision after the existing player collision and before enemy collision. Keep enemy death handling shared. Hunter bullets damage walls like existing friendly bullets; update the misleading player-only comment. No hunter shot/ammo/fuel statistics are recorded.
- [ ] In `draw_game`, draw the active hunter and a small cyan `Hunter 3/3 · active`-style label using controller status. Use existing pygame font conventions; do not add a new UI system. On death render no active ship and leave no targetable object. The hunter never enters enemy-position lists, scoring totals or portal lock counts.
- [ ] Add integration assertions for no firing before first movement; no requests during quit confirmation; fresh request on resume; no respawn after death; restart memory reset; old-generation result ignored; enemy kill/egg removal still updates portal conditions; player-only upgrades; unchanged player score after hunter damage/fire/kill.
- [ ] Run all hunter tests plus `tests/test_spawn_manager.py`; expect pass. Commit as `feat: integrate optional Jev hunter into game levels`.

## Task 11: Document, validate and measure

**Modify:** `README.md`, `levels/README.md`, `tests/README.md`. **Create:** `docs/superpowers/validation/2026-09-30-jev-hunter.md` during execution to record actual results.

- [ ] Document optional setup with `venv/bin/python -m pip install -r requirements-hunter.txt`, shell environment variable `TYPESAFE_API_KEY`, optional `TYPESAFE_DEFAULT_MODEL`, and the level entry `"hunter": {"spawn_cell": [2, 3]}`. Explain the example cell must be a valid free cell in that level's seeded maze. Never add a real API key or enable a level as a side effect of documentation.
- [ ] Document behaviour: independent full pilot, local memory, damageable ally, no friendly fire or personal kill credit, unavailable/coasting status, timing defaults, no offline autopilot, and fresh state on level restart.
- [ ] Run `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tests -q` once after focused suites pass. Record any baseline failures separately; fix feature regressions without unrelated changes. Run `git diff --check` scoped to feature changes so existing whitespace is not mistaken for new failures.
- [ ] With available credentials, run a short live fixture and record request count, median/p95 latency, stale-response fraction and percentage of simulation spent coasting. Use a temporary level configuration restored in `finally`, or the integration fixture, without overwriting the user's level edits. Check turning/thrust/fire visually, enemy retargeting, hunter death, connection loss, and shutdown. Do not claim combat effectiveness from fake-client tests.
- [ ] If credentials are unavailable, complete offline implementation and explicitly record that live Jev latency/behaviour remains unverified. Do not fabricate results or require credentials for the normal game/test suite.
- [ ] Confirm normal startup with no hunter and no SDK installed remains supported. Because SDK imports are lazy, verify import discovery for the existing PyInstaller build; add a conditional `typesafe_sdk` hidden import only if the build check demonstrates it is needed. Keep optional dependency absence valid. Record whether packaging was actually tested.
- [ ] Inspect staged diff for unrelated files, credentials and level opt-ins; commit docs/verification as `docs: explain optional Jev hunter setup and validation`.

## Plan self-review

- Approved scope maps to Tasks 1–4 (configuration/actions/ship), 5–6 (sensors and memory), 7–8 (Jev and stale inputs), 9–10 (combat and lifecycle), 11 (setup and empirical checks).
- Public contracts are defined before their callers: `PilotAction`, `PilotObservation`, `PilotDecision`, `PilotResult`, `HunterShip.step`, `HunterPerception.observe`, `JevPilot.decide`, worker methods and controller methods.
- Worker cancellation is acknowledged before replacement requests; expiry is measured from snapshot time; failure cannot refresh an old action.
- No hidden world mutation updates remembered observations. Walls use visible portions and observed edge intervals, not complete maze data.
- Implementation is not complete until offline tests and integration pass. Live network behaviour and packaging are reported according to checks actually performed.

## Verified API references

- [Async client](https://docs.typesafe.ai/sdk/python/api/clients/async): client construction, `system_one`, operation timeouts and `aclose`.
- [Retry policy](https://docs.typesafe.ai/sdk/python/api/retries): `RetryPolicy(max_retries=0)` disables SDK retries.
- [Python SDK](https://docs.typesafe.ai/sdk/python): package and environment-based credentials.

Checked 2026-09-30. Dependency compatibility and release pin are verified during Task 7, before installation.
