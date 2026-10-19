# Physics Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Free and motor-driven gates (a plank on a centre pin) that the ship and enemies push and are pushed by, placed in the level editor, simulated with pymunk.

**Architecture:** A new `physics/` package holds an `ObstacleWorld` around a `pymunk.Space`: the maze's active wall faces are static segments, each gate is a dynamic plank body pinned to the static body (plus a `SimpleMotor` for motor gates). The game's own movement is untouched; once per frame, after everything has moved, the ship and enemies near a gate are mirrored into the space as circle bodies, the space steps one frame, and only bodies that touched a gate get the difference written back (a position correction and a new velocity). Wall readers that *see* (hunter senses and line of sight, anemone and flighthouse sight) also read `maze.gate_segments`; wall *collision* code never does, so a gate is never a destructible wall and never costs power.

**Tech Stack:** Python 3.10, pygame, pymunk 7.3.1, pytest.

**Spec:** `docs/superpowers/specs/2026-10-19-physics-gates-design.md`

## Global Constraints

- Tests: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider <paths>`.
- The full suite has 27 known failures, all in `test_anemone_game`, `test_experiment_dagger`, `test_hunter_integration`, `test_hunter_powerups`, `test_hunter_settings_for`, `test_jev_beacon`, `test_level_arc`, `test_neural_game`, `test_rules_hunter_training`. After each task nothing else may fail, and no more than 27.
- `config/settings.json` holds the user's uncommitted `autoplay.firstLevel` edit (13 → 10). Stage only your own hunk: write HEAD's file plus your change to a scratch copy, then `git update-index --cacheinfo 100644,$(git hash-object -w <copy>),config/settings.json`. Never `git add -A`/`.`; never stage `assets/neural/hunter.npz` or `.codegraph/`.
- Units: game velocities are px per frame at `config.FPS` (60); `dt` counts frames. pymunk runs in px and seconds: velocity × FPS going in, ÷ FPS coming out; a frame is `dt / FPS` seconds.
- Pushing or being pushed by a gate is free: no `on_wall_collision`, no `record_wall_collision`, no enemy hit, no `maze.damage_wall`.
- Gates come from hand-made layouts only. A level with no gates builds no `ObstacleWorld` (`game.obstacles is None`) and pays nothing per frame.
- New settings live in a new `obstacles` section (`ObstacleSettings`, loaded with `raw.get("obstacles", {})` like `autoplay`).
- Rendering is checked on the real display at 1352×878.
- End every commit with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A ship at full speed (8 px/frame) driven straight at a plank** must not pass through it. Pinned in Task 2 (`test_a_fast_ship_does_not_pass_through_a_plank`).
2. **A mover squeezed between a motor gate and a wall, or a gate and an anemone**: the gate stalls, the mover never ends up inside a wall, and nothing becomes NaN. Pinned in Task 2 (`test_a_motor_gate_stalls_on_a_pinned_mover`) and Task 3 (`test_an_anemone_jams_a_motor_gate`).
3. **A crowd near a gate** (a dozen Jellies piling on): the step stays cheap. Pinned in Task 2 (`test_a_crowd_steps_quickly`).
4. **Restarting or replaying a level with gates**: the gates start again at their placed angles, with no leftover bodies or segments. Pinned in Task 3 (`test_restarting_puts_the_gates_back`).
5. **A gate whose plank would overlap a wall at its starting angle** (a typo in a level file, or a wall added next to it in the editor) is refused, not left to jitter. Pinned in Task 1 (`test_a_plank_across_a_wall_is_refused`) and Task 5 (`test_a_wall_cannot_go_across_a_plank`).

---

## File Structure

| File | Responsibility |
|---|---|
| `level_layout.py` | `GatePlacement`, `Layout.gates`, parsing, JSON, `plank_cells`. |
| `config.py`, `config/settings.json` | `ObstacleSettings` (`obstacles` section). |
| `physics/__init__.py`, `physics/obstacle_world.py` (new) | `Gate`, `ObstacleWorld`: the pymunk space, the step, mover write-back, bullets, plank segments. |
| `rendering/gates.py` (new) | `draw_gate`, shared by play and the editor. |
| `maze/generator.py` | `Maze.gate_segments` (empty by default). |
| `game.py` | Build the world at level start, step it, bullets, drawing. |
| `hunter/perception.py`, `hunter/senses.py`, `hunter/fire_control.py`, `entities/anemone.py`, `entities/flighthouse_enemy.py`, `game_handlers/enemy_updater.py` | See gates. |
| `editor/model.py`, `rendering/level_editor.py` | Place, turn and flip gates. |
| `requirements.txt`, `pyinstaller.spec`, `README.md`, `levels/README.md` | Dependency, build, docs. |

---

### Task 1: Gates in the layout, and the settings

**Files:**
- Modify: `level_layout.py`, `config.py`, `config/settings.json` (staging rule)
- Test: `tests/test_gate_layout.py` (new)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) GatePlacement(cell: Cell, angle: int = 0, motor: Optional[str] = None)`: `angle` in degrees, a multiple of 45 in `[0, 180)`; `motor` is `None` (free), `'cw'` or `'ccw'`.
  - `Layout.gates: Tuple[GatePlacement, ...] = ()` (sorted by row, col like enemies).
  - `plank_cells(placement: GatePlacement) -> FrozenSet[Cell]`: the cells the plank crosses at its angle: sample 9 evenly spaced points from tip to tip (tips one cell from the pin centre along the angle, in cell units), each point's cell.
  - JSON: `"gates": [{"cell": [c, r], "angle": 45, "motor": "cw"}]` (`motor` omitted when free; `angle` omitted when 0). `to_json` writes `gates` only when there are any.
  - `parse_layout` raises `LayoutError` for: a gate cell that is a wall, the start, the exit, the beacon or an enemy's cell, or another gate's; an angle not a multiple of 45 in `[0, 180)`; a motor other than `cw`/`ccw`; any of its `plank_cells` being a wall or outside the interior.
  - `ObstacleSettings` (defaults): `gateMass: float = 16.0` (the ship is r² = 64), `gateThicknessCells: float = 0.16`, `gateElasticity: float = 0.4`, `motorRate: float = 1.2` (rad/s), `motorMaxForce: float = 3_000_000.0`, `bulletImpulse: float = 300.0`, `substeps: int = 4`, `moverReachMargin: float = 24.0` (px). `Settings.obstacles` with `default_factory`.
- [ ] **Step 1: Failing tests** in `tests/test_gate_layout.py`:
  - `test_gates_round_trip_through_json`: a layout dict with one free gate at `[5, 5]` and a `'ccw'` motor gate at `[8, 5]`, angle 90; `parse_layout(parse_layout(d, 12).to_json(), 12) == parse_layout(d, 12)` and the parsed `gates` equal `(GatePlacement((5, 5)), GatePlacement((8, 5), 90, 'ccw'))`.
  - `test_a_layout_without_gates_writes_none`: `'gates' not in Layout(...).to_json()`.
  - `test_the_plank_crosses_its_neighbours`: `plank_cells(GatePlacement((5, 5))) == {(4, 5), (5, 5), (6, 5)}`; at 90 → `{(5, 4), (5, 5), (5, 6)}`.
  - `test_a_plank_across_a_wall_is_refused`: wall at `[6, 5]`, gate at `[5, 5]` angle 0 → `LayoutError`; the same at angle 90 parses.
  - `test_bad_gates_are_refused` (parametrized): gate on the start, on an enemy, two gates on one cell, angle 30, angle 180, motor `'fast'`.
  - `test_the_obstacle_settings_have_their_defaults`.
- [ ] **Step 2: Run** `… pytest tests/test_gate_layout.py -q` → fails on import of `GatePlacement`.
- [ ] **Step 3: Implement.** Settings in `config.py` and in a new `"obstacles"` section of `settings.json`.
- [ ] **Step 4: Run** the same plus `tests/test_level_layout.py tests/test_editor_files.py` → pass.
- [ ] **Step 5: Commit** `feat: gates in level layouts, and the obstacle settings`.

---

### Task 2: The obstacle world

**Files:**
- Create: `physics/__init__.py`, `physics/obstacle_world.py`
- Modify: `requirements.txt` (`pymunk==7.3.1`; install it into `venv`), `maze/generator.py` (`self.gate_segments: List[WallSegment] = []` in `Maze.__init__`)
- Test: `tests/test_obstacle_world.py` (new)

**Interfaces:**
- Consumes: Task 1 (`GatePlacement`, `ObstacleSettings`).
- Produces (`physics/obstacle_world.py`):
  - `ANCHORED_KINDS = ('anemone', 'flighthouse')`.
  - `class Gate`: `placement`, `pin: Tuple[float, float]` (cell centre), `half_length: float` (= `maze.cell_size`), `thickness: float` (= `max(6, gateThicknessCells × maze.cell_size)`), `angle: float` (radians, live), `angular_velocity: float` (rad/s, live), `ends() -> Tuple[Point, Point]`, `motor: Optional[str]`.
  - `class ObstacleWorld(maze, placements: Sequence[GatePlacement], settings=config.SETTINGS.obstacles)`: `gates: List[Gate]`.
    - `step(dt: float, movers: Sequence, anchored: Sequence = ()) -> None`.
    - `bullet_hit(projectile) -> bool`: True (and the projectile deactivated, the gate pushed) when the projectile's circle touches a plank.
    - `segments() -> List[WallSegment]`: one non-destructible `WallSegment(start, end, hit_points=1, destructible=False)` per plank, its centre line, rebuilt each step.
- [ ] **Step 1: Failing tests** in `tests/test_obstacle_world.py`. Build mazes from layouts (`Maze(1, complexity=MazeComplexity.EMPTY, grid_size=12, layout=…)`); a mover is a `SimpleNamespace(x, y, vx, vy, radius)` or a real `Ship`.
  - `test_pushing_a_free_gate_turns_it`: a mover moving into one end of a plank at 3 px/frame for 30 frames (moving it by its own `vx` each frame, then `step`); the gate's angle has changed and the mover kept more than half its speed.
  - `test_a_free_gate_runs_down_like_the_ship`: set `angular_velocity` to 2.0; after 60 one-frame steps it is `2.0 × SHIP_FRICTION ** 60` within 5%.
  - `test_a_resting_gate_stays_put`: 600 steps with no movers; angle unchanged to 1e-6.
  - `test_a_gate_stops_against_a_wall`: wall cell diagonal to the pin; spin the free gate; after 120 steps no plank end lies inside a wall cell (by `maze.position_calculator.screen_to_grid`).
  - `test_gates_stop_against_each_other`: two free gates whose sweeps overlap (pins two cells apart); spin one; after 120 steps the two planks' centre lines never crossed (segment intersection false every step).
  - `test_a_motor_gate_turns_at_its_rate`: `'cw'` motor gate in the open; after 60 steps the angle moved by `motorRate × 1 s` within 10%, increasing for `'cw'` in screen coordinates (y down), decreasing for `'ccw'`.
  - `test_a_motor_gate_pushes_a_mover_aside`: a resting mover in the sweep in open space is pushed out of the plank's way and the gate keeps turning.
  - `test_a_motor_gate_stalls_on_a_pinned_mover`: a mover between the plank and a wall; over 120 steps the gate's angle stops changing (below 0.01 rad per 30 steps once stalled), the mover never overlaps a wall face (distance to every active wall segment ≥ `radius - 1`), and all values are finite.
  - `test_a_jammed_motor_gate_frees_when_the_wall_goes`: wall in the sweep; the gate stalls; remove that block by `maze.damage_wall` until it breaks; within 60 steps the gate passes through where the wall was.
  - `test_a_fast_ship_does_not_pass_through_a_plank`: a mover at 8 px/frame straight at a gate's broad side, moving and stepping each frame for 40 frames; the mover ends on the side it started.
  - `test_a_bullet_nudges_a_gate`: a `Projectile` overlapping a plank end with speed; `bullet_hit` is True, the projectile is inactive, `angular_velocity` is no longer 0 but below 0.5 rad/s; a projectile far away returns False.
  - `test_only_movers_that_touch_a_gate_are_changed`: a mover far from the gate keeps exactly its x, y, vx, vy.
  - `test_a_crowd_steps_quickly`: 12 movers packed against a plank; 60 steps take under 0.25 s in total.
  - `test_segments_follow_the_plank`: after the gate turns 90°, `segments()[0]` endpoints are the plank's ends.
- [ ] **Step 2: Run** → `ModuleNotFoundError: physics`.
- [ ] **Step 3: Implement.**
  - Space: no gravity; static body holds one `pymunk.Segment` per active `maze.walls` face (radius 1, elasticity `config.SHIP_COLLISION_RESTITUTION` or the ship's restitution setting); rebuild those shapes when `maze.wall_generation` differs from the last build.
  - Gate: dynamic body, `mass = gateMass`, `moment = pymunk.moment_for_segment(mass, a, b, thickness / 2)`, a `Segment` shape of radius `thickness / 2`, a `PivotJoint(space.static_body, body, pin)`; motor gates add `SimpleMotor(space.static_body, body, rate)` with `max_force = motorMaxForce` (sign so `'cw'` increases the angle). Free gates' angular velocity is multiplied by `SHIP_FRICTION ** dt` each step.
  - Shape filters: walls, gates and movers are three categories; movers collide with walls and gates but not each other.
  - `step`: keep movers whose distance to some pin is under `half_length + radius + moverReachMargin`. For each: a body (`mass = radius²`, moment for a circle; anchored ones are `KINEMATIC` at rest) at the mover's position, velocity × FPS. Step `substeps` times by `dt / FPS / substeps`. A mover body with an arbiter against a gate shape (check with `body.each_arbiter`) writes back: `x, y += (moved − v_before × seconds)`, `vx, vy = body.velocity / FPS`. Remove mover bodies afterwards. Then refresh `segments()`.
  - Bullets: closest point on the plank's centre line to the projectile within `thickness / 2 + projectile.radius`; impulse `bulletImpulse` along the projectile's direction at that point (`body.apply_impulse_at_world_point`); `projectile.active = False`.
- [ ] **Step 4: Run** `… pytest tests/test_obstacle_world.py -q` → pass.
- [ ] **Step 5: Commit** `feat: an obstacle world on pymunk, with free and motor gates`.

---

### Task 3: Gates in play

**Files:**
- Create: `rendering/gates.py`
- Modify: `game.py` (`start_level`, `update`, the projectile loop, `draw_game`), `pyinstaller.spec` (add `"pymunk"` to `hiddenimports`)
- Test: `tests/test_gates_game.py` (new)

**Interfaces:**
- Consumes: Task 1 (`Layout.gates`), Task 2 (`ObstacleWorld`, `ANCHORED_KINDS`).
- Produces: `Game.obstacles: Optional[ObstacleWorld]`; `draw_gate(screen, gate) -> None` (plank as a filled capsule along `gate.ends()` with thickness, a pin dot; motor gates in a different colour with a small arrow showing direction).
- [ ] **Step 1: Failing tests** in `tests/test_gates_game.py`, with the `game` fixture and `start` from `tests/test_exit_policies_game.py`, and a layout level file holding a free gate (and, where named, a motor gate):
  - `test_a_level_without_gates_has_no_world`: `game.obstacles is None` and `game.maze.gate_segments == []`.
  - `test_thrusting_into_a_gate_turns_it_for_free`: put the ship next to a plank end moving into it; 60 updates; the gate turned; `scoring.wall_collisions == 0`, `scoring.hits_taken() == 0`.
  - `test_a_gate_shoves_an_enemy`: a patrol enemy in a motor gate's sweep is moved.
  - `test_an_anemone_jams_a_motor_gate`: an anemone in the sweep; after 180 updates the anemone has not moved and the gate has stalled.
  - `test_a_player_shot_stops_at_a_gate_and_damages_nothing`: a player projectile fired at a plank; it is gone, the gate nudged, every wall's hit points unchanged.
  - `test_restarting_puts_the_gates_back`: turn a gate, `start(game, level)` again: its angle is the placed angle and `len(game.obstacles.space.bodies)` equals the count after the first start.
- [ ] **Step 2: Run** → fail (`AttributeError: obstacles`).
- [ ] **Step 3: Implement.**
  - `start_level`: `self.obstacles = ObstacleWorld(self.maze, layout.gates) if layout is not None and layout.gates else None`; `self.maze.gate_segments = self.obstacles.segments() if self.obstacles else []`.
  - `update`: after the enemy and enemy-hunter updates and before the projectile loop, if `self.obstacles`: movers = the ship, the hunter, the enemy hunters and the active enemies not in `ANCHORED_KINDS`; anchored = active anemones and flighthouses; `self.obstacles.step(dt, movers, anchored)`; `self.maze.gate_segments = self.obstacles.segments()`.
  - Projectile loop: before the wall check, `if self.obstacles and self.obstacles.bullet_hit(projectile): continue`.
  - `draw_game`: draw each gate after the maze, before the entities.
- [ ] **Step 4: Run** the new file → pass; then the full suite.
- [ ] **Step 5: Real display**: a layout level with one free and one motor gate; screenshot at 1352×878 after pushing the free gate; both read clearly as planks on pins.
- [ ] **Step 6: Commit** `feat: gates in play: pushed, pushing, and stopping shots`.

---

### Task 4: Everything that sees walls sees gates

**Files:**
- Modify: `hunter/perception.py` (line of sight in `observe`, not `_route_to_player`), `hunter/senses.py` (rays), `hunter/fire_control.py`, `entities/anemone.py` (`_wall_between`), `entities/flighthouse_enemy.py` (its line-of-sight check gains `gates=()`), `game_handlers/enemy_updater.py` (pass `maze.gate_segments` to the flighthouse)
- Test: `tests/test_gates_seen.py` (new)

**Interfaces:**
- Consumes: `Maze.gate_segments` (Task 2/3).
- [ ] **Step 1: Failing tests**, each on a maze with one plank segment placed in `maze.gate_segments` between an observer and a target, and the same with the list empty:
  - `test_the_hunter_cannot_see_through_a_gate` (`HunterPerception.observe` gives no contact for the target behind the plank).
  - `test_the_neural_senses_feel_a_gate` (`ray_distances` through `senses` observe: the ray towards the plank is shorter than with no gate).
  - `test_fire_control_will_not_shoot_through_a_gate`.
  - `test_an_anemone_cannot_see_through_a_gate` (`_wall_between` True).
  - `test_a_flighthouse_cannot_see_through_a_gate`.
- [ ] **Step 2: Run** → the five tests fail.
- [ ] **Step 3: Implement**: each reader adds `maze.gate_segments` (active, as `(start, end)`) to the walls it looks through. Leave `_route_to_player` alone (the user: routes are not an issue).
- [ ] **Step 4: Run** the new file plus `tests/test_hunter_*.py tests/test_anemone*.py tests/test_flighthouse*.py` → no new failures.
- [ ] **Step 5: Commit** `feat: the hunter and sighted enemies see gates`.

---

### Task 5: Gates in the level editor, and the docs

**Files:**
- Modify: `editor/model.py`, `rendering/level_editor.py`, `README.md` (editor section, new "Gates" section), `levels/README.md` (the `gates` JSON)
- Test: `tests/test_level_editor.py` or a new `tests/test_editor_gates.py`

**Interfaces:**
- Consumes: Task 1 (`GatePlacement`, `plank_cells`), Task 3 (`draw_gate`, which needs a `Gate`-like object: build `Gate`s from the preview maze and placements without a world, or give `draw_gate` `(screen, pin, angle, half_length, thickness, motor)`).
- Produces: `PALETTE` gains `'gate'` and `'motor_gate'` after `'beacon'`; `EditorModel.gates: Dict[Cell, GatePlacement]`; `contents()` returns `'gate'` or `'motor_gate'`; `turn_gate() -> bool` (+45°, wrapping at 180); `flip_gate() -> bool` (`cw` ↔ `ccw`, motor gates only); `to_layout()` carries the gates.
- [ ] **Step 1: Failing tests**:
  - `test_placing_turning_and_flipping_a_gate`: place `'motor_gate'` on an open cell → `GatePlacement(cell, 0, 'cw')`; `turn_gate()` → 45; `flip_gate()` → `'ccw'`; `to_layout().gates` holds it; save and reload gives the same layout.
  - `test_a_gate_cannot_go_across_a_wall`: placing (or turning) a gate whose `plank_cells` hit a wall is refused.
  - `test_a_wall_cannot_go_across_a_plank`: placing a wall on one of a gate's `plank_cells` is refused.
  - `test_a_gate_cannot_share_a_cell` with the start, exit, beacon or an enemy; removing a gate works.
  - `test_the_preview_draws_gates` (pixels change where a gate is placed).
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement.** Keys: `R` turns the gate under the cursor, `F` flips a motor gate; add both to the hint rows; `LABELS` `'Gate'` and `'Motor gate'`; chip colours distinct from the enemies'. Docs: README "Gates" (free and motor gates, free to push, bullets nudge, walls jam them, settings in `obstacles`), the editor keys, and the `gates` JSON in `levels/README.md`.
- [ ] **Step 4: Run** the editor tests and the full suite.
- [ ] **Step 5: Real display**: the editor with a free gate at 45° and a motor gate at 90° on screen.
- [ ] **Step 6: Commit** `feat: place, turn and flip gates in the level editor`.
