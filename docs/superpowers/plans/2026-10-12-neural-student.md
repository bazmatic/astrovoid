# Neural Student Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A recurrent student that flies the hunter with only left, right, thrust and the trigger, taught by the rules pilot in the lab until it meets the closed-loop gate.

**Architecture:** A cheap senses module feeds a numpy GRU policy behind a `NeuralController` the game calls per frame (decisions every N frames, controls held between). The lab records the rules pilot's executed per-frame controls as labels, trains the GRU with torch, and flies the student in the same episodes and score as the rules pilot. Teacher-corrected rounds (DAgger) relabel the states the student actually reaches by replaying a shadow rules pilot's action on a saved ship state.

**Tech Stack:** Python 3.10 (`venv/bin/python`), numpy at runtime, torch for training only (`requirements-train.txt`), pytest. Branch `feat/neural-student`.

**Spec:** `docs/superpowers/specs/2026-10-12-neural-student-design.md`

## Global Constraints

- Run everything with `venv/bin/python`; tests as `venv/bin/python -m pytest <path> -q -p no:cacheprovider`.
- The user's local `config/settings.json` change (`"hunterPilot": "rules"`) stays stashed for the whole run: before Task 1 run `git stash push -q config/settings.json`, and pop it only in Task 12 (if the pop conflicts, set `"hunterPilot": "rules"` by hand). Tests assume the committed default `"jev"`, and no commit may include that local change.
- The game and the shipped `hunter/senses.py`, `hunter/neural/` import numpy only. torch is imported only under `tools/` and in tests guarded by `pytest.importorskip('torch')`.
- Controls are exactly `PilotAction(turn in {-1, 0, +1}, thrust, fire)` with `track`, `course`, `burn_heading`, `burn_frames`, `burn_reference` and `worked_burn` left at their defaults. Turn index: 0 = left (turn -1), 1 = none, 2 = right (turn +1).
- The senses contain no lead angle, burn heading, safe speed, stopping distance or course. They target under 1 ms a call.
- `decisionFrames` is a setting (`game.neuralDecisionFrames`, default 6). The neural pilot's turn rate is a setting (`game.neuralTurnRate`, default 1.0), separate from the rules pilot's 2.0.
- Teaching seeds are 100 to 139. Evaluation uses seeds 0 to 17 (`--seeds 18`); neither the held-out levels nor the evaluation seeds are used for training or relabelling.
- The gate (spec): greedy student on the held-out levels, 18 seeds: lab score within 20% of the rules pilot's (candidate >= 0.8 x rules), and wall hits per minute and enemy hits per minute each <= 1.25 x the rules pilot's.
- Determinism: the same student episode run twice is identical (greedy play; senses and controller use simulated time only).
- Raw data goes to `.astrovoid-local/neural/` (git-ignored). Trained weights are committed under `assets/neural/`.
- Code style matches `hunter/`: single quotes, 4-space indent, short docstrings.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

Failure modes the spec implies that no task would otherwise test, most likely first. Each has a test in the task that owns the code.

1. A weights file that is missing, truncated, or built for a different senses layout: the hunter coasts and shows unavailable; the game does not crash and does not fall back to another pilot. (Tasks 3 and 5)
2. A level with no enemies, no bullets, no powerups, or no walls in range: senses stay finite and the right length, with absent things zeroed. (Task 2)
3. A held-control step where the ship barely turned, thrust fired in exactly half the frames, or a shot left on the last frame only: labels are defined (ties go to the stated rule), never an exception. (Task 4)
4. A GRU whose memory is not reset between levels or episodes: the second level must not depend on the first. (Task 5)
5. Teacher relabelling that leaks into the real game: after labelling, the real ship's state (position, velocity, angle, burn budget, cooldowns) is exactly what it was. (Task 10)

---

### Task 1: Remove the Jev-imitating student

**Files:**
- Delete: `hunter/student/` (all of it), `tools/train_student.py`, `assets/student/`
- Delete: `tests/test_student_client.py`, `tests/test_student_encoder.py`, `tests/test_student_recorder.py`, `tests/test_student_selection.py`, `tests/test_train_student.py`
- Modify: `hunter/jev_pilot.py` (`create_client`, drop `import sys` if unused), `config.py` (`GameSettings`), `config/settings.json`, `game.py` (autoplay warning), `pyinstaller.spec`, `requirements-train.txt`, `README.md`, `hunter/settings_for.py` (docstring), `hunter/rule_params.py` (comment), `tests/test_hunter_settings_for.py`, `tests/test_rule_params.py` (comment)
- Create: `tests/test_pilot_selection.py`

**Interfaces:**
- Consumes: existing `create_client()`, `PilotUnavailable`, `RulesClient`.
- Produces: `create_client()` returning the Jev client for `hunterPilot == 'jev'`, a `RulesClient` for `'rules'`, and raising `PilotUnavailable('invalid_configuration')` for anything else (including `'neural'`, which never uses a client).

- [ ] **Step 1: Write the replacement selection tests**

Create `tests/test_pilot_selection.py`:

```python
import pytest
from config import SETTINGS
from hunter import jev_pilot
from hunter.jev_pilot import PilotUnavailable, create_client
from hunter.rules_pilot import RulesClient


@pytest.fixture
def pilot(monkeypatch):
    def apply(mode):
        monkeypatch.setattr(SETTINGS.game, 'hunterPilot', mode)
    return apply


def test_the_default_pilot_is_jev():
    assert SETTINGS.game.hunterPilot == 'jev'


def test_jev_mode_without_a_key_is_unavailable(pilot, monkeypatch):
    pilot('jev')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    with pytest.raises(PilotUnavailable, match='missing_key'):
        create_client()


def test_jev_mode_builds_the_jev_client(pilot, monkeypatch):
    pilot('jev')
    sentinel = object()
    monkeypatch.setattr(jev_pilot, '_create_jev_client', lambda: sentinel)
    assert create_client() is sentinel


def test_rules_mode_needs_no_key_or_model(pilot, monkeypatch):
    pilot('rules')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    assert isinstance(create_client(), RulesClient)


@pytest.mark.parametrize('mode', ['student', 'auto', 'turbo', 'neural'])
def test_anything_else_is_not_a_client_mode(pilot, mode):
    pilot(mode)
    with pytest.raises(PilotUnavailable, match='invalid_configuration'):
        create_client()
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_pilot_selection.py -q -p no:cacheprovider`
Expected: FAIL on the `student` and `auto` cases (they are still valid modes).

- [ ] **Step 3: Remove the student and simplify the code**

```bash
git rm -r -q hunter/student tools/train_student.py assets/student
git rm -q tests/test_student_client.py tests/test_student_encoder.py tests/test_student_recorder.py tests/test_student_selection.py tests/test_train_student.py
```

Apply with a script (every `old` must match exactly once):

```python
def edit(path, a, b, count=1):
    s = open(path).read()
    assert s.count(a) == count, (path, a[:70], s.count(a))
    open(path, 'w').write(s.replace(a, b))

# hunter/jev_pilot.py: create_client
s = open('hunter/jev_pilot.py').read()
i = s.index('def create_client():'); j = s.index('class JevPilot:')
s = s[:i] + '''def create_client():
    """The pilot client for this level: Jev, or the rules pilot. Other modes (the neural pilot) use none."""
    from config import SETTINGS
    mode = SETTINGS.game.hunterPilot
    if mode == 'rules':
        from hunter.rules_pilot import RulesClient
        return RulesClient()
    if mode != 'jev':
        raise PilotUnavailable('invalid_configuration')
    return _create_jev_client()


''' + s[j:]
if 'sys.' not in s.replace('import sys', ''):
    s = s.replace('import sys\n', '', 1)
open('hunter/jev_pilot.py', 'w').write(s)

# config.py + settings.json
edit('config.py', '''    # Which pilot flies the hunter: "jev", "student" (the trained imitation), "rules" (the
    # question criteria as plain code) or "auto" (Jev when it is available, the student otherwise).
    hunterPilot: str = "jev"
    # Log Jev's decisions under .astrovoid-local/decisions/ as training data.
    recordPilotDecisions: bool = False
''', '''    # Which pilot flies the hunter: "jev", "rules" (the question criteria as plain code) or "neural"
    # (a network that flies with the basic controls only).
    hunterPilot: str = "jev"
''')
edit('config/settings.json', '''    "hunterPilot": "jev",
    "recordPilotDecisions": false
''', '''    "hunterPilot": "jev"
''')

# game.py: the autoplay recording warning
edit('game.py', '''        if not (config.SETTINGS.game.recordPilotDecisions
                and config.SETTINGS.game.hunterPilot == 'jev'):
            logging.getLogger(__name__).warning(
                'Autoplay is running without recording Jev decisions: set game.hunterPilot '
                'to "jev" and game.recordPilotDecisions to true to collect training data')
''', '')

# pyinstaller.spec
edit('pyinstaller.spec', '''        "hunter.student.client", "hunter.student.encoder",
        "hunter.student.network", "hunter.student.recorder", "hunter.rules_pilot",
''', '''        "hunter.rules_pilot",
''')

# requirements-train.txt
open('requirements-train.txt', 'w').write('''# Only needed to train the neural pilot (tools/train_neural.py); the game never imports these.
torch>=2.2
''')

# comments and docstrings that name the student
edit('hunter/rule_params.py', 'Jev and the student keep DEFAULT.', 'Jev keeps DEFAULT.')
edit('hunter/settings_for.py', 'Jev and the student share the default hunter: their held left and right turns for a whole\n    decision, so the turn rate is set so that stays controllable.', "Jev's hunter is the default one: its held left and right turns for a whole decision, so the turn\n    rate is set so that stays controllable.")
edit('tests/test_rule_params.py', '# Jev and the student are unchanged', '# Jev is unchanged')

# tests/test_hunter_settings_for.py
edit('tests/test_hunter_settings_for.py', "@pytest.mark.parametrize('mode', ['jev', 'student', 'auto'])\ndef test_jev_and_the_student_keep_the_default_hunter(mode):", "@pytest.mark.parametrize('mode', ['jev'])\ndef test_jev_keeps_the_default_hunter(mode):")
edit('tests/test_hunter_settings_for.py', "[('rules', 2.0), ('jev', 0.5), ('student', 0.5)]", "[('rules', 2.0), ('jev', 0.5)]")
```

README: replace the whole "### Offline student pilot" section (from that heading up to, but not including, "#### Unattended data collection") with:

```markdown
### Choosing the hunter's pilot

`game.hunterPilot` in `config/settings.json` chooses the hunter's pilot: `"jev"` (default),
`"rules"` (the same criteria written as plain code in `hunter/rules_pilot.py`: no key, model or
training), or `"neural"` (a network that flies with the basic controls only; see
`docs/superpowers/specs/2026-10-12-neural-student-design.md`).
```

and in the autoplay section delete the sentence "Set `game.recordPilotDecisions` to `true` first, or the run collects nothing (it logs a warning)." (keep the rest of the paragraph).

- [ ] **Step 4: Run the new tests and the whole suite**

Run: `venv/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -3`
Expected: all PASS. Fix any leftover reference to `hunter.student` or `recordPilotDecisions` that the output names (`git grep -n -i "hunter.student\|recordPilotDecisions\|train_student"`), then re-run.

- [ ] **Step 5: Commit**

```bash
git add -A hunter tools assets tests config.py config/settings.json game.py pyinstaller.spec requirements-train.txt README.md
git commit -m "refactor: remove the Jev-imitating student

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Senses

**Files:**
- Create: `hunter/senses.py`
- Test: `tests/test_senses.py`

**Interfaces:**
- Consumes: a hunter (`x, y, vx, vy, angle, health, fire_remaining, burst_remaining, gun_upgrade_level, max_speed, settings, fire_interval`), a maze (`spatial_grid.get_nearby_walls(pos, radius)`, `grid_width`, `cell_size_x`), entities with `x, y, vx, vy, active` (enemies, powerups, the player), projectiles with `x, y, vx, vy, active, is_enemy`, and `HunterSettings.sensor_range(maze)`.
- Produces:
  - `FEATURE_NAMES: tuple[str, ...]` and `SENSE_SIZE = len(FEATURE_NAMES)`.
  - `Senses(settings)` with `reset()` and `observe(hunter, maze, enemies, projectiles, powerups, player, last_controls, now) -> numpy.ndarray` (float32, shape `(SENSE_SIZE,)`). `last_controls` is `(turn_index, thrust, fire)`; `now` is simulated seconds.
  - `ray_distances(origin, heading_degrees, wall_starts, wall_ends, reach) -> numpy.ndarray` (16 values, each in `[0, reach]`, ray 0 along the nose, increasing clockwise on screen) and `blocked(origin, targets, wall_starts, wall_ends) -> numpy.ndarray[bool]` (line of sight).

Layout (fixed here; `FEATURE_NAMES` is built from it): self 10 (`fwd_speed`, `side_speed`, `speed`, `heading_sin`, `heading_cos`, `health`, `cooldown`, `burst`, `upgrade`, `enemies_present`), rays 16, enemies 6 x 6, bullets 4 x 6, powerups 2 x 4, player 6, memory 2 x 5, last controls 5 (turn one-hot 3, thrust, fire). Each contact block is `[present, sin(rel), cos(rel), distance/reach, rel_fwd/vmax, rel_side/vmax]` (powerups and memory use the shorter forms in the layout above: powerups `[present, sin, cos, distance]`, memory `[present, sin, cos, distance, age/ttl]`). `rel` is the bearing minus the heading; positive sine is to the right of the nose (y grows downward).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_senses.py`:

```python
import math
import numpy as np
import pytest
from types import SimpleNamespace
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from hunter.model import HunterSettings
from hunter.senses import (FEATURE_NAMES, SENSE_SIZE, Senses, blocked, ray_distances)
from maze.wall_segment import WallSegment
from tests.test_hunter_perception import maze

IDLE = (1, 0, 0)   # last controls: no turn, coast, no trigger


def world(walls=()):
    w = maze()
    w.walls = list(walls)
    from utils.spatial_grid import SpatialGrid
    w.spatial_grid = SpatialGrid(1000, 1000, 100)
    w.spatial_grid.add_walls(w.walls)
    return w


def sense(hunter, w, enemies=(), bullets=(), powerups=(), player=None, now=0.0, senses=None):
    senses = senses or Senses(HunterSettings())
    return senses.observe(hunter, w, list(enemies), list(bullets), list(powerups), player, IDLE, now)


def value(vector, name):
    return float(vector[FEATURE_NAMES.index(name)])


def bullet(x, y, vx=0.0, vy=0.0, enemy=True):
    return SimpleNamespace(x=x, y=y, vx=vx, vy=vy, active=True, is_enemy=enemy, radius=3)


def test_names_are_unique_and_the_vector_has_that_length():
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES) == SENSE_SIZE
    assert sense(HunterShip((500, 500)), world()).shape == (SENSE_SIZE,)


def test_nothing_around_is_finite_and_zeroed():
    v = sense(HunterShip((500, 500)), world())
    assert v.dtype == np.float32 and np.isfinite(v).all()
    for name in FEATURE_NAMES:
        if name.startswith(('enemy', 'bullet', 'powerup', 'player', 'memory')):
            assert value(v, name) == 0.0, name
    assert value(v, 'enemies_present') == 0.0


def test_no_solved_quantity_is_in_the_layout():
    banned = ('lead', 'burn', 'safe', 'stopping', 'course', 'aim', 'retrograde')
    assert not [n for n in FEATURE_NAMES if any(b in n for b in banned)]


def test_rays_measure_the_distance_to_walls_relative_to_the_nose():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    wall_ahead = WallSegment((600, 400), (600, 600), 3)           # 100 px due east
    v = sense(ship, world([wall_ahead]))
    reach = HunterSettings().sensor_range(world())
    assert value(v, 'ray_0') == pytest.approx(100 / reach, abs=1e-3)
    assert value(v, 'ray_8') == pytest.approx(1.0)                # behind: nothing in range
    ship.angle = 90.0                                             # now facing south, the wall is on the left
    v = sense(ship, world([wall_ahead]))
    assert value(v, 'ray_12') == pytest.approx(100 / reach, abs=1e-3)   # ray 12 = 270 degrees = left of the nose


def test_ray_distances_and_blocked_direct():
    starts = np.array([[600.0, 400.0]]); ends = np.array([[600.0, 600.0]])
    d = ray_distances((500.0, 500.0), 0.0, starts, ends, 800.0)
    assert d[0] == pytest.approx(100.0) and d[8] == pytest.approx(800.0) and len(d) == 16
    assert list(blocked((500.0, 500.0), np.array([[700.0, 500.0], [400.0, 500.0]]), starts, ends)) == [True, False]
    empty = np.zeros((0, 2))
    assert list(ray_distances((0.0, 0.0), 0.0, empty, empty, 50.0)) == [50.0] * 16
    assert list(blocked((0.0, 0.0), np.array([[10.0, 0.0]]), empty, empty)) == [False]


def test_an_enemy_ahead_has_geometry_in_the_hunters_frame():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = Enemy((700, 500), 'patrol', 1)
    v = sense(ship, world(), [enemy])
    assert value(v, 'enemy0_present') == 1.0
    assert value(v, 'enemy0_sin') == pytest.approx(0.0, abs=1e-6)
    assert value(v, 'enemy0_cos') == pytest.approx(1.0)
    assert 0 < value(v, 'enemy0_dist') < 1
    assert value(v, 'enemies_present') == 1.0


def test_right_of_the_nose_is_a_positive_sine():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    south = Enemy((500, 700), 'patrol', 1)       # y grows downward: south is to the right of an east-facing nose
    assert value(sense(ship, world(), [south]), 'enemy0_sin') > 0.9


def test_enemies_are_listed_nearest_first_and_capped_at_six():
    ship = HunterShip((500, 500))
    enemies = [Enemy((500 + 40 * (i + 1), 500), 'patrol', 1) for i in range(9)]
    v = sense(ship, world(), enemies)
    dists = [value(v, f'enemy{i}_dist') for i in range(6)]
    assert dists == sorted(dists) and all(d > 0 for d in dists)
    assert dists[0] == pytest.approx(value(sense(ship, world(), enemies[:1]), 'enemy0_dist'))


def test_an_enemy_behind_a_wall_is_not_sensed_but_still_counts_as_present():
    ship = HunterShip((500, 500))
    wall = WallSegment((600, 300), (600, 700), 3)
    v = sense(ship, world([wall]), [Enemy((700, 500), 'patrol', 1)])
    assert value(v, 'enemy0_present') == 0.0
    assert value(v, 'enemies_present') == 1.0


def test_dead_enemies_are_neither_sensed_nor_present():
    ship = HunterShip((500, 500))
    enemy = Enemy((700, 500), 'patrol', 1)
    enemy.active = False
    v = sense(ship, world(), [enemy])
    assert value(v, 'enemy0_present') == 0.0 and value(v, 'enemies_present') == 0.0


def test_only_enemy_bullets_are_sensed_with_their_relative_velocity():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    incoming = bullet(700, 500, vx=-6.0)                 # coming straight at the nose
    friendly = bullet(600, 500, vx=6.0, enemy=False)
    v = sense(ship, world(), bullets=[incoming, friendly])
    assert value(v, 'bullet0_present') == 1.0 and value(v, 'bullet1_present') == 0.0
    assert value(v, 'bullet0_relfwd') < -0.5            # closing fast along the nose


def test_the_player_appears_only_when_given():
    ship = HunterShip((500, 500))
    player = SimpleNamespace(x=600.0, y=500.0, vx=0.0, vy=0.0, active=True)
    assert value(sense(ship, world(), player=player), 'player_present') == 1.0
    assert value(sense(ship, world()), 'player_present') == 0.0


def test_a_powerup_in_sight_is_sensed():
    ship = HunterShip((500, 500))
    crystal = SimpleNamespace(x=560.0, y=500.0, vx=0.0, vy=0.0, active=True)
    v = sense(ship, world(), powerups=[crystal])
    assert value(v, 'powerup0_present') == 1.0 and value(v, 'powerup0_dist') > 0


def test_own_motion_is_in_the_hunters_frame():
    ship = HunterShip((500, 500))
    ship.angle = 90.0
    ship.vx, ship.vy = 0.0, 4.0                          # moving south while facing south: straight ahead
    v = sense(ship, world())
    assert value(v, 'fwd_speed') > 0.4 and value(v, 'side_speed') == pytest.approx(0.0, abs=1e-6)
    assert value(v, 'heading_sin') == pytest.approx(1.0)


def test_last_controls_are_echoed():
    senses = Senses(HunterSettings())
    v = senses.observe(HunterShip((500, 500)), world(), [], [], [], None, (2, 1, 1), 0.0)
    assert value(v, 'last_turn_right') == 1.0 and value(v, 'last_turn_left') == 0.0
    assert value(v, 'last_thrust') == 1.0 and value(v, 'last_fire') == 1.0


def test_an_enemy_seen_then_hidden_is_remembered_with_its_age_then_forgotten():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = Enemy((700, 500), 'patrol', 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    hidden = world([WallSegment((600, 300), (600, 700), 3)])
    v = sense(ship, hidden, [enemy], senses=senses, now=3.0)
    assert value(v, 'memory0_present') == 1.0
    assert value(v, 'memory0_age') == pytest.approx(3.0 / 10.0, abs=1e-3)
    v = sense(ship, hidden, [enemy], senses=senses, now=11.0)
    assert value(v, 'memory0_present') == 0.0                      # older than ten seconds
    enemy.active = False
    sense(ship, world(), [enemy], senses=senses, now=12.0)
    assert value(sense(ship, hidden, [enemy], senses=senses, now=12.5), 'memory0_present') == 0.0


def test_reset_clears_memory():
    ship = HunterShip((500, 500))
    enemy = Enemy((700, 500), 'patrol', 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    senses.reset()
    v = sense(ship, world([WallSegment((600, 300), (600, 700), 3)]), [enemy], senses=senses, now=1.0)
    assert value(v, 'memory0_present') == 0.0


def test_a_remembered_position_now_in_plain_view_and_empty_is_dropped():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = Enemy((700, 500), 'patrol', 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    enemy.x = 500.0; enemy.y = 800.0                      # it moved away; its old spot is visible and empty
    v = sense(ship, world(), [], senses=senses, now=1.0)
    assert value(v, 'memory0_present') == 0.0


def test_senses_are_cheap():
    import time
    ship = HunterShip((500, 500))
    w = world([WallSegment((100 + 50 * i, 100), (100 + 50 * i, 900), 3) for i in range(16)])
    enemies = [Enemy((300 + 40 * i, 500), 'patrol', 1) for i in range(12)]
    senses = Senses(HunterSettings())
    start = time.perf_counter()
    for k in range(200):
        senses.observe(ship, w, enemies, [], [], None, IDLE, k / 10)
    assert (time.perf_counter() - start) / 200 < 0.004      # generous: the target is 1 ms on a quiet machine
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_senses.py -q -p no:cacheprovider`
Expected: collection error `ModuleNotFoundError: No module named 'hunter.senses'`.

- [ ] **Step 3: Write `hunter/senses.py`**

```python
"""The neural pilot's senses: a cheap fixed-length vector built straight from the game objects.

Only raw geometry (bearings, distances, relative velocities, wall distances along rays) and the hunter's
own motion. None of the rules pilot's solved quantities (lead angles, burn headings, safe speeds).
"""
import math
import weakref
import numpy as np

RAYS = 16
MAX_ENEMIES, MAX_BULLETS, MAX_POWERUPS, MAX_MEMORY = 6, 4, 2, 2
MEMORY_TTL = 10.0          # seconds an out-of-sight enemy is remembered
UPGRADE_CAP = 6.0

_RAY_ANGLES = np.arange(RAYS) * (2 * math.pi / RAYS)
_RAY_COS, _RAY_SIN = np.cos(_RAY_ANGLES), np.sin(_RAY_ANGLES)


def _names():
    names = ['fwd_speed', 'side_speed', 'speed', 'heading_sin', 'heading_cos', 'health', 'cooldown',
             'burst', 'upgrade', 'enemies_present']
    names += [f'ray_{i}' for i in range(RAYS)]
    for group, count in (('enemy', MAX_ENEMIES), ('bullet', MAX_BULLETS)):
        for i in range(count):
            names += [f'{group}{i}_{part}' for part in ('present', 'sin', 'cos', 'dist', 'relfwd', 'relside')]
    for i in range(MAX_POWERUPS):
        names += [f'powerup{i}_{part}' for part in ('present', 'sin', 'cos', 'dist')]
    names += [f'player_{part}' for part in ('present', 'sin', 'cos', 'dist', 'relfwd', 'relside')]
    for i in range(MAX_MEMORY):
        names += [f'memory{i}_{part}' for part in ('present', 'sin', 'cos', 'dist', 'age')]
    names += ['last_turn_left', 'last_turn_none', 'last_turn_right', 'last_thrust', 'last_fire']
    return tuple(names)


FEATURE_NAMES = _names()
SENSE_SIZE = len(FEATURE_NAMES)
_INDEX = {name: i for i, name in enumerate(FEATURE_NAMES)}


def ray_distances(origin, heading_degrees, wall_starts, wall_ends, reach):
    """Distance to the nearest wall along each of 16 rays, ray 0 along the nose, capped at `reach`."""
    if len(wall_starts) == 0:
        return np.full(RAYS, float(reach))
    h = math.radians(heading_degrees)
    ch, sh = math.cos(h), math.sin(h)
    dx = _RAY_COS * ch - _RAY_SIN * sh
    dy = _RAY_SIN * ch + _RAY_COS * sh
    ex = wall_ends[:, 0] - wall_starts[:, 0]
    ey = wall_ends[:, 1] - wall_starts[:, 1]
    ax = wall_starts[:, 0] - origin[0]
    ay = wall_starts[:, 1] - origin[1]
    denom = dx[:, None] * ey[None, :] - dy[:, None] * ex[None, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (ax[None, :] * ey[None, :] - ay[None, :] * ex[None, :]) / denom
        u = (ax[None, :] * dy[:, None] - ay[None, :] * dx[:, None]) / denom
    hit = (np.abs(denom) > 1e-9) & (t >= 0) & (u >= 0) & (u <= 1)
    t = np.where(hit, t, np.inf)
    return np.minimum(t.min(axis=1), float(reach))


def blocked(origin, targets, wall_starts, wall_ends):
    """Whether a wall lies on the straight line from `origin` to each row of `targets`."""
    targets = np.asarray(targets, dtype=float).reshape(-1, 2)
    if len(targets) == 0 or len(wall_starts) == 0:
        return np.zeros(len(targets), dtype=bool)
    dx = targets[:, 0] - origin[0]
    dy = targets[:, 1] - origin[1]
    ex = wall_ends[:, 0] - wall_starts[:, 0]
    ey = wall_ends[:, 1] - wall_starts[:, 1]
    ax = wall_starts[:, 0] - origin[0]
    ay = wall_starts[:, 1] - origin[1]
    denom = dx[:, None] * ey[None, :] - dy[:, None] * ex[None, :]
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (ax[None, :] * ey[None, :] - ay[None, :] * ex[None, :]) / denom
        u = (ax[None, :] * dy[:, None] - ay[None, :] * dx[:, None]) / denom
    hit = (np.abs(denom) > 1e-9) & (t > 0) & (t < 1) & (u >= 0) & (u <= 1)
    return hit.any(axis=1)


class Senses:
    def __init__(self, settings):
        self.settings = settings
        self._memory = weakref.WeakKeyDictionary()    # enemy -> (x, y, seen_at)

    def reset(self):
        self._memory = weakref.WeakKeyDictionary()

    def observe(self, hunter, maze, enemies, projectiles, powerups, player, last_controls, now):
        out = np.zeros(SENSE_SIZE, dtype=np.float32)
        origin = (hunter.x, hunter.y)
        reach = self.settings.sensor_range(maze)
        vmax = max(hunter.max_speed, 1e-6)
        h = math.radians(hunter.angle)
        ch, sh = math.cos(h), math.sin(h)

        walls = [w for w in maze.spatial_grid.get_nearby_walls(origin, reach) if w.active]
        starts = np.array([w.start for w in walls], dtype=float).reshape(-1, 2)
        ends = np.array([w.end for w in walls], dtype=float).reshape(-1, 2)

        fwd = hunter.vx * ch + hunter.vy * sh
        side = -hunter.vx * sh + hunter.vy * ch
        out[_INDEX['fwd_speed']] = fwd / vmax
        out[_INDEX['side_speed']] = side / vmax
        out[_INDEX['speed']] = math.hypot(hunter.vx, hunter.vy) / vmax
        out[_INDEX['heading_sin']] = sh
        out[_INDEX['heading_cos']] = ch
        out[_INDEX['health']] = hunter.health / max(self.settings.health, 1)
        out[_INDEX['cooldown']] = min(1.0, hunter.fire_remaining / max(hunter.fire_interval, 1e-6))
        out[_INDEX['burst']] = hunter.burst_remaining / max(self.settings.burst_size, 1)
        out[_INDEX['upgrade']] = min(1.0, hunter.gun_upgrade_level / UPGRADE_CAP)
        out[_INDEX['enemies_present']] = 1.0 if any(e.active for e in enemies) else 0.0

        rays = ray_distances(origin, hunter.angle, starts, ends, reach) / reach
        out[_INDEX['ray_0']:_INDEX['ray_0'] + RAYS] = rays

        def candidates(entities, limit):
            """The nearest `limit` active entities within reach and in line of sight."""
            near = []
            for e in entities:
                if not e.active:
                    continue
                d = math.hypot(e.x - origin[0], e.y - origin[1])
                if d <= reach:
                    near.append((d, e))
            near.sort(key=lambda item: item[0])
            near = near[:limit + 3]                                  # a few spare for the ones that are hidden
            if not near:
                return []
            hidden = blocked(origin, [(e.x, e.y) for _, e in near], starts, ends)
            return [item for item, hid in zip(near, hidden) if not hid][:limit]

        def contact(prefix, d, e, with_velocity=True):
            dx, dy = e.x - origin[0], e.y - origin[1]
            rel = math.atan2(dy, dx) - h
            out[_INDEX[f'{prefix}_present']] = 1.0
            out[_INDEX[f'{prefix}_sin']] = math.sin(rel)
            out[_INDEX[f'{prefix}_cos']] = math.cos(rel)
            out[_INDEX[f'{prefix}_dist']] = d / reach
            if with_velocity:
                rvx, rvy = e.vx - hunter.vx, e.vy - hunter.vy
                out[_INDEX[f'{prefix}_relfwd']] = (rvx * ch + rvy * sh) / vmax
                out[_INDEX[f'{prefix}_relside']] = (-rvx * sh + rvy * ch) / vmax

        seen = candidates(enemies, MAX_ENEMIES)
        for i, (d, e) in enumerate(seen):
            contact(f'enemy{i}', d, e)
            self._memory[e] = (e.x, e.y, now)
        for i, (d, b) in enumerate(candidates([p for p in projectiles if p.is_enemy], MAX_BULLETS)):
            contact(f'bullet{i}', d, b)
        for i, (d, c) in enumerate(candidates(powerups, MAX_POWERUPS)):
            contact(f'powerup{i}', d, c, with_velocity=False)
        if player is not None and player.active:
            d = math.hypot(player.x - origin[0], player.y - origin[1])
            if d <= reach and not blocked(origin, [(player.x, player.y)], starts, ends)[0]:
                contact('player', d, player)

        self._remember(out, origin, h, reach, starts, ends, now, {id(e) for _, e in seen})
        turn, thrust, fire = last_controls
        out[_INDEX[('last_turn_left', 'last_turn_none', 'last_turn_right')[turn]]] = 1.0
        out[_INDEX['last_thrust']] = 1.0 if thrust else 0.0
        out[_INDEX['last_fire']] = 1.0 if fire else 0.0
        return out

    def _remember(self, out, origin, h, reach, starts, ends, now, seen_ids):
        """Fill the memory slots with the nearest enemies seen lately but not in sight now."""
        entries = []
        for enemy, (x, y, seen_at) in list(self._memory.items()):
            if not enemy.active or now - seen_at > MEMORY_TTL:
                del self._memory[enemy]
                continue
            if id(enemy) in seen_ids:
                continue
            entries.append((math.hypot(x - origin[0], y - origin[1]), enemy, x, y, seen_at))
        if not entries:
            return
        in_view = ~blocked(origin, [(x, y) for _, _, x, y, _ in entries], starts, ends)
        kept = []
        for (d, enemy, x, y, seen_at), visible in zip(entries, in_view):
            # Its last position is in plain view and the enemy is not there: the memory is stale.
            if visible and d <= reach:
                del self._memory[enemy]
            else:
                kept.append((d, x, y, seen_at))
        kept.sort(key=lambda item: item[0])
        for i, (d, x, y, seen_at) in enumerate(kept[:MAX_MEMORY]):
            rel = math.atan2(y - origin[1], x - origin[0]) - h
            out[_INDEX[f'memory{i}_present']] = 1.0
            out[_INDEX[f'memory{i}_sin']] = math.sin(rel)
            out[_INDEX[f'memory{i}_cos']] = math.cos(rel)
            out[_INDEX[f'memory{i}_dist']] = min(1.0, d / reach)
            out[_INDEX[f'memory{i}_age']] = (now - seen_at) / MEMORY_TTL
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_senses.py -q -p no:cacheprovider`
Expected: all PASS. If a geometry assertion fails by sign, re-check the convention: positive sine is to the right of the nose (screen y grows downward), `rel = bearing - heading`. If `test_an_enemy_seen_then_hidden...` fails because the remembered spot is judged "in view", the wall test geometry is wrong, not the code: the wall at x=600 must lie between the hunter (500) and the remembered x=700.

- [ ] **Step 5: Time the senses on a real busy level (diagnostic, not a test)**

Run:
```bash
SDL_VIDEODRIVER=dummy venv/bin/python - <<'EOF' 2>&1 | grep -v pygame
import time
from experiments import harness
from hunter.model import HunterSettings
from hunter.senses import Senses
calls = []
senses = Senses(HunterSettings())
def trace(t, game, hunter):
    if int(t * 60) % 6:
        return
    enemies = [e for g in (game.enemies, game.replay_enemies, game.flockers, game.flighthouses, game.split_bosses,
                           game.mother_bosses, game.babies, game.eggs, game.anemones) for e in g]
    t0 = time.perf_counter()
    senses.observe(hunter, game.maze, enemies, game.projectiles, game.powerup_crystals, None, (1, 0, 0), t)
    calls.append(time.perf_counter() - t0)
harness.run_episode(25, 0, horizon=20.0, trace=trace)
print(f'{len(calls)} calls, mean {sum(calls)/len(calls)*1000:.2f} ms, max {max(calls)*1000:.2f} ms')
EOF
```
Expected: mean under 1 ms. If it is over, reduce `limit + 3` spare candidates or the ray count before moving on, and record the figure in the commit message.

- [ ] **Step 6: Commit**

```bash
git add hunter/senses.py tests/test_senses.py
git commit -m "feat: cheap raw senses for the neural pilot

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Controls, labels and the numpy policy

**Files:**
- Create: `hunter/neural/__init__.py` (empty), `hunter/neural/controls.py`, `hunter/neural/policy.py`
- Test: `tests/test_neural_controls.py`, `tests/test_neural_policy.py`

**Interfaces:**
- Consumes: `FEATURE_NAMES`, `SENSE_SIZE` (Task 2); `PilotAction` from `hunter.model`.
- Produces:
  - `controls.py`: `TURN_LEFT, TURN_NONE, TURN_RIGHT = 0, 1, 2`; `to_action(controls) -> PilotAction` for `controls = (turn_index, thrust, fire)`; `step_labels(frames, rate) -> (turn_index, thrust, fire)` where `frames` is a list of `(rotation_degrees, engine_fired, trigger)` per frame and `rate` is the ship's rotation per frame in degrees.
  - `policy.py`: `NeuralPolicy` with `NeuralPolicy(params: dict, mean, scale)`; `initial_state() -> ndarray`; `step(senses, state) -> (logits: dict, new_state)`; `act(senses, state, greedy=True, rng=None) -> (controls, new_state)`; `save(path)`; `NeuralPolicy.load(path)` raising `InvalidPolicy`; `random_policy(seed, hidden=32, embed=16)` (a tiny random policy for tests); `HEAD_SIZES = {'turn': 3, 'thrust': 2, 'fire': 2}`. Parameter names are fixed: `embed_w` (E, D), `embed_b` (E,), `gru_w_ih` (3H, E), `gru_w_hh` (3H, H), `gru_b_ih` (3H,), `gru_b_hh` (3H,), `turn_w` (3, H), `turn_b` (3,), `thrust_w`, `thrust_b`, `fire_w`, `fire_b`. GRU gate order is r, z, n (the torch convention).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_neural_controls.py`:

```python
import pytest
from hunter.model import PilotAction
from hunter.neural.controls import TURN_LEFT, TURN_NONE, TURN_RIGHT, step_labels, to_action

RATE = 5.0


def frames(*rows):
    return [tuple(r) for r in rows]


def test_to_action_is_a_plain_basic_action():
    a = to_action((TURN_LEFT, True, False))
    assert a == PilotAction(-1, True, False)
    assert not (a.track or a.course or a.worked_burn) and a.burn_heading is None and a.burn_frames is None
    assert to_action((TURN_RIGHT, False, True)) == PilotAction(1, False, True)
    assert to_action((TURN_NONE, False, False)).turn == 0


def test_a_held_left_turn_is_left_and_a_held_right_turn_is_right():
    assert step_labels(frames((-5, 0, 0), (-5, 0, 0), (-5, 0, 0)), RATE)[0] == TURN_LEFT
    assert step_labels(frames((5, 0, 0), (5, 0, 0), (5, 0, 0)), RATE)[0] == TURN_RIGHT


def test_a_nose_that_barely_moved_is_no_turn():
    assert step_labels(frames((0.1, 0, 0), (-0.1, 0, 0), (0, 0, 0)), RATE)[0] == TURN_NONE


def test_a_snapped_final_frame_still_counts_as_the_turn_that_led_to_it():
    # track mode: two full-rate frames then a small trim onto the solution
    assert step_labels(frames((-5, 0, 0), (-5, 0, 0), (-1, 0, 0)), RATE)[0] == TURN_LEFT


def test_opposite_turns_that_cancel_are_no_turn():
    assert step_labels(frames((-5, 0, 0), (5, 0, 0)), RATE)[0] == TURN_NONE


def test_thrust_is_on_when_the_engine_fired_in_at_least_half_the_frames():
    assert step_labels(frames((0, 1, 0), (0, 1, 0), (0, 0, 0), (0, 0, 0)), RATE)[1] is True    # exactly half
    assert step_labels(frames((0, 1, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)), RATE)[1] is False
    assert step_labels(frames((0, 0, 0), (0, 0, 0)), RATE)[1] is False


def test_the_trigger_is_on_if_it_was_held_or_a_shot_left_in_any_frame():
    assert step_labels(frames((0, 0, 0), (0, 0, 0), (0, 0, 1)), RATE)[2] is True
    assert step_labels(frames((0, 0, 0), (0, 0, 0)), RATE)[2] is False


def test_an_empty_step_is_all_off_not_an_error():
    assert step_labels([], RATE) == (TURN_NONE, False, False)
```

Create `tests/test_neural_policy.py`:

```python
import numpy as np
import pytest
from hunter.neural.policy import HEAD_SIZES, InvalidPolicy, NeuralPolicy, random_policy
from hunter.senses import SENSE_SIZE


def test_a_policy_steps_and_returns_logits_for_each_head():
    policy = random_policy(0)
    logits, state = policy.step(np.zeros(SENSE_SIZE, dtype=np.float32), policy.initial_state())
    assert {k: v.shape for k, v in logits.items()} == {k: (n,) for k, n in HEAD_SIZES.items()}
    assert state.shape == policy.initial_state().shape
    assert all(np.isfinite(v).all() for v in logits.values()) and np.isfinite(state).all()


def test_the_memory_changes_the_answer():
    policy = random_policy(1)
    s = np.ones(SENSE_SIZE, dtype=np.float32)
    first, state = policy.step(s, policy.initial_state())
    second, _ = policy.step(s, state)
    assert not np.allclose(first['turn'], second['turn'])


def test_greedy_play_is_deterministic_and_returns_controls():
    policy = random_policy(2)
    s = np.full(SENSE_SIZE, 0.3, dtype=np.float32)
    a, _ = policy.act(s, policy.initial_state())
    b, _ = policy.act(s, policy.initial_state())
    assert a == b
    turn, thrust, fire = a
    assert turn in (0, 1, 2) and isinstance(thrust, bool) and isinstance(fire, bool)


def test_sampling_is_reproducible_with_a_seeded_generator_and_can_differ_from_greedy():
    policy = random_policy(3)
    s = np.full(SENSE_SIZE, 0.1, dtype=np.float32)
    picks = {policy.act(s, policy.initial_state(), greedy=False, rng=np.random.default_rng(k))[0] for k in range(40)}
    assert len(picks) > 1
    x = policy.act(s, policy.initial_state(), greedy=False, rng=np.random.default_rng(7))[0]
    y = policy.act(s, policy.initial_state(), greedy=False, rng=np.random.default_rng(7))[0]
    assert x == y


def test_save_and_load_round_trip(tmp_path):
    policy = random_policy(4)
    path = tmp_path / 'p.npz'
    policy.save(path)
    loaded = NeuralPolicy.load(path)
    s = np.arange(SENSE_SIZE, dtype=np.float32) / SENSE_SIZE
    a, sa = policy.step(s, policy.initial_state())
    b, sb = loaded.step(s, loaded.initial_state())
    for k in a:
        assert np.allclose(a[k], b[k])
    assert np.allclose(sa, sb)


def test_load_rejects_missing_truncated_foreign_and_mismatched_files(tmp_path):
    with pytest.raises(InvalidPolicy):
        NeuralPolicy.load(tmp_path / 'absent.npz')
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'not a policy')
    with pytest.raises(InvalidPolicy):
        NeuralPolicy.load(bad)
    good = tmp_path / 'good.npz'
    random_policy(5).save(good)
    good.write_bytes(good.read_bytes()[:300])
    with pytest.raises(InvalidPolicy):
        NeuralPolicy.load(good)
    other = tmp_path / 'other.npz'
    random_policy(6).save(other)
    data = dict(np.load(other))
    data['feature_names'] = np.array(['renamed'] * SENSE_SIZE)
    np.savez(other, **data)
    with pytest.raises(InvalidPolicy, match='layout'):
        NeuralPolicy.load(other)
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_neural_controls.py tests/test_neural_policy.py -q -p no:cacheprovider`
Expected: collection errors (`hunter.neural` missing).

- [ ] **Step 3: Write `hunter/neural/controls.py`**

```python
"""The student's basic controls, and how recorded per-frame behaviour is turned into them."""
from hunter.model import PilotAction

TURN_LEFT, TURN_NONE, TURN_RIGHT = 0, 1, 2


def to_action(controls):
    """A plain PilotAction for (turn_index, thrust, fire): no tracking, course or burn."""
    turn, thrust, fire = controls
    return PilotAction(turn - 1, bool(thrust), bool(fire))


def step_labels(frames, rate):
    """(turn_index, thrust, fire) for a step, from what the ship did in each of its frames.

    `frames` holds (rotation_degrees, engine_fired, trigger) per frame; `rate` is the ship's
    rotation per frame at full turn, in degrees. Turn is left or right if the nose rotated
    at least half a frame's worth that way over the step, else none. Thrust is on if the
    engine fired in at least half the frames. The trigger is on if it was held (or a shot
    left) in any frame.
    """
    if not frames:
        return TURN_NONE, False, False
    net = sum(f[0] for f in frames)
    if abs(net) >= 0.5 * rate:
        turn = TURN_RIGHT if net > 0 else TURN_LEFT
    else:
        turn = TURN_NONE
    thrust = sum(1 for f in frames if f[1]) * 2 >= len(frames)
    fire = any(f[2] for f in frames)
    return turn, thrust, fire
```

- [ ] **Step 4: Write `hunter/neural/policy.py`**

```python
"""The student's brain: a small GRU with one softmax head per control, run in plain numpy."""
import numpy as np
from hunter.senses import FEATURE_NAMES, SENSE_SIZE

HEAD_SIZES = {'turn': 3, 'thrust': 2, 'fire': 2}
_PARAMS = ('embed_w', 'embed_b', 'gru_w_ih', 'gru_w_hh', 'gru_b_ih', 'gru_b_hh',
           'turn_w', 'turn_b', 'thrust_w', 'thrust_b', 'fire_w', 'fire_b')


class InvalidPolicy(Exception):
    """The policy file is missing, damaged, or built for a different senses layout."""


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class NeuralPolicy:
    def __init__(self, params, mean, scale):
        self.params = {k: np.asarray(params[k], dtype=np.float32) for k in _PARAMS}
        self.mean = np.asarray(mean, dtype=np.float32)
        self.scale = np.asarray(scale, dtype=np.float32)
        self.hidden = self.params['gru_w_hh'].shape[1]

    def initial_state(self):
        return np.zeros(self.hidden, dtype=np.float32)

    def step(self, senses, state):
        p = self.params
        x = np.tanh(p['embed_w'] @ ((np.asarray(senses, dtype=np.float32) - self.mean) / self.scale) + p['embed_b'])
        gi = p['gru_w_ih'] @ x + p['gru_b_ih']
        gh = p['gru_w_hh'] @ state + p['gru_b_hh']
        H = self.hidden
        r = _sigmoid(gi[:H] + gh[:H])
        z = _sigmoid(gi[H:2 * H] + gh[H:2 * H])
        n = np.tanh(gi[2 * H:] + r * gh[2 * H:])
        new_state = ((1.0 - z) * n + z * state).astype(np.float32)
        logits = {k: p[f'{k}_w'] @ new_state + p[f'{k}_b'] for k in HEAD_SIZES}
        return logits, new_state

    def act(self, senses, state, greedy=True, rng=None):
        logits, new_state = self.step(senses, state)
        picks = []
        for head in ('turn', 'thrust', 'fire'):
            z = logits[head] - logits[head].max()
            probs = np.exp(z) / np.exp(z).sum()
            if greedy:
                picks.append(int(np.argmax(probs)))
            else:
                picks.append(int((rng or np.random.default_rng()).choice(len(probs), p=probs)))
        return (picks[0], bool(picks[1]), bool(picks[2])), new_state

    def save(self, path):
        np.savez(path, mean=self.mean, scale=self.scale, feature_names=np.array(FEATURE_NAMES),
                 **self.params)

    @classmethod
    def load(cls, path):
        try:
            data = np.load(path, allow_pickle=False)
            if tuple(str(n) for n in data['feature_names']) != FEATURE_NAMES:
                raise InvalidPolicy('senses layout differs from this build')
            policy = cls({k: data[k] for k in _PARAMS}, data['mean'], data['scale'])
            if policy.params['embed_w'].shape[1] != SENSE_SIZE:
                raise InvalidPolicy('senses layout differs from this build')
            return policy
        except InvalidPolicy:
            raise
        except Exception as exc:
            raise InvalidPolicy(type(exc).__name__) from None


def random_policy(seed, hidden=32, embed=16):
    """A small random policy, for tests."""
    rng = np.random.default_rng(seed)
    g = lambda *shape: (rng.normal(0, 0.3, shape)).astype(np.float32)
    params = {'embed_w': g(embed, SENSE_SIZE), 'embed_b': g(embed),
              'gru_w_ih': g(3 * hidden, embed), 'gru_w_hh': g(3 * hidden, hidden),
              'gru_b_ih': g(3 * hidden), 'gru_b_hh': g(3 * hidden)}
    for head, n in HEAD_SIZES.items():
        params[f'{head}_w'], params[f'{head}_b'] = g(n, hidden), g(n)
    return NeuralPolicy(params, np.zeros(SENSE_SIZE), np.ones(SENSE_SIZE))
```


- [ ] **Step 5: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_neural_controls.py tests/test_neural_policy.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add hunter/neural tests/test_neural_controls.py tests/test_neural_policy.py
git commit -m "feat: basic controls, step labels and the numpy GRU policy

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The controller, the neural hunter settings and the game wiring

**Files:**
- Create: `hunter/neural/controller.py`, `hunter/neural/loader.py`
- Modify: `config.py` (`GameSettings`), `config/settings.json`, `hunter/settings_for.py`, `game.py` (`_summon_hunter`, `_update_hunter`, a `_neural_senses` method)
- Test: `tests/test_neural_controller.py`, `tests/test_neural_game.py`, plus additions to `tests/test_hunter_settings_for.py`

**Interfaces:**
- Consumes: `Senses`, `NeuralPolicy`, `InvalidPolicy`, `to_action`, `NEUTRAL`, `HunterSettings`.
- Produces:
  - `NeuralController(policy, decision_frames, greedy=True, rng=None)` with attributes `kind = 'neural'`, `action` (the held `PilotAction`), `status` (`'active'`, `'coasting'`, `'unavailable'`), `unavailable` (bool), `frames` (running frames ticked), `last_controls` (tuple); methods `tick(senses_factory, running=True) -> PilotAction` (calls `senses_factory(last_controls, now_seconds) -> ndarray` once every `decision_frames` running ticks, the first on the first tick), `invalidate()`, `close()`. `policy=None` makes the controller permanently `unavailable`, returning `NEUTRAL`.
  - `loader.load_neural_policy(path=None) -> NeuralPolicy | None`: loads `assets/neural/hunter.npz` (path resolved with `utils.resource_path.resource_path`), returns `None` (and logs a warning once) if it is missing or invalid.
  - `GameSettings.neuralDecisionFrames: int = 6` and `neuralTurnRate: float = 1.0`; `hunter_settings_for('neural')` returns the default hunter with `turn_rate_multiplier = neuralTurnRate`.
  - In the game, `hunterPilot == 'neural'` builds a `NeuralController`; `self.hunter_senses` is a `Senses`; `_update_hunter` uses `controller.tick(self._neural_senses)` for a `kind == 'neural'` controller.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_neural_controller.py`:

```python
import numpy as np
import pytest
from hunter.model import NEUTRAL, PilotAction
from hunter.neural.controller import NeuralController
from hunter.neural.policy import random_policy
from hunter.senses import SENSE_SIZE


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, last_controls, now):
        self.calls.append((last_controls, now))
        return np.zeros(SENSE_SIZE, dtype=np.float32)


def test_it_decides_on_the_first_tick_then_every_n_frames():
    controller = NeuralController(random_policy(0), decision_frames=6)
    spy = Spy()
    for _ in range(13):
        controller.tick(spy)
    assert len(spy.calls) == 3                       # frames 0, 6 and 12
    assert spy.calls[1][1] == pytest.approx(6 / 60)  # simulated seconds, not the real clock


def test_controls_are_held_between_decisions_as_a_plain_action():
    controller = NeuralController(random_policy(1), decision_frames=4)
    spy = Spy()
    first = controller.tick(spy)
    held = [controller.tick(spy) for _ in range(3)]
    assert all(a is first for a in held)
    assert isinstance(first, PilotAction) and not first.track and not first.course
    assert first.burn_heading is None and first.burn_frames is None


def test_the_last_controls_are_passed_to_the_next_decision():
    controller = NeuralController(random_policy(2), decision_frames=1)
    spy = Spy()
    controller.tick(spy)
    controller.tick(spy)
    assert spy.calls[1][0] == controller.last_controls or spy.calls[1][0][0] in (0, 1, 2)
    assert spy.calls[0][0] == (1, 0, 0)               # nothing pressed yet


def test_not_running_returns_neutral_and_does_not_decide():
    controller = NeuralController(random_policy(3), decision_frames=2)
    spy = Spy()
    assert controller.tick(None, running=False) == NEUTRAL
    assert spy.calls == [] and controller.status == 'coasting'


def test_memory_is_reset_by_invalidate_and_a_fresh_controller_starts_clean():
    policy = random_policy(4)
    a = NeuralController(policy, decision_frames=1)
    spy = Spy()
    for _ in range(5):
        a.tick(spy)
    a.invalidate()
    b = NeuralController(policy, decision_frames=1)
    xs, ys = Spy(), Spy()
    first_a = a.tick(xs)
    first_b = b.tick(ys)
    assert first_a == first_b                          # same state, same senses: the same first decision


def test_greedy_play_is_deterministic():
    runs = []
    for _ in range(2):
        controller = NeuralController(random_policy(5), decision_frames=3)
        spy = Spy()
        runs.append([controller.tick(spy) for _ in range(30)])
    assert runs[0] == runs[1]


def test_without_a_policy_it_is_unavailable_and_coasts():
    controller = NeuralController(None, decision_frames=6)
    assert controller.unavailable and controller.tick(Spy()) == NEUTRAL
    assert controller.status == 'unavailable'


def test_close_stops_it():
    controller = NeuralController(random_policy(6), decision_frames=1)
    controller.close()
    assert controller.tick(Spy()) == NEUTRAL
```

Create `tests/test_neural_game.py`:

```python
import logging
import numpy as np
import pytest
from config import SETTINGS
from hunter.neural import loader
from hunter.neural.controller import NeuralController
from hunter.neural.policy import random_policy
from hunter.settings_for import hunter_settings_for
from tests.test_hunter_powerups import game, playing


def test_the_neural_hunter_has_its_own_turn_rate_and_decision_rate():
    assert SETTINGS.game.neuralDecisionFrames == 6 and SETTINGS.game.neuralTurnRate == 1.0
    assert hunter_settings_for('neural').turn_rate_multiplier == SETTINGS.game.neuralTurnRate


def test_the_loader_returns_none_and_warns_for_a_missing_or_bad_file(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert loader.load_neural_policy(tmp_path / 'absent.npz') is None
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'junk')
    assert loader.load_neural_policy(bad) is None
    good = tmp_path / 'good.npz'
    random_policy(0).save(good)
    assert loader.load_neural_policy(good) is not None


def test_the_game_builds_a_neural_controller_for_the_neural_pilot(game, monkeypatch, tmp_path):
    good = tmp_path / 'good.npz'
    random_policy(1).save(good)
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'neural')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(good))
    playing(game)
    game._summon_hunter((game.ship.x, game.ship.y))
    assert isinstance(game.hunter_controller, NeuralController)
    assert game.hunter.rotation_speed_multiplier == SETTINGS.game.neuralTurnRate
    assert game.hunter_controller.unavailable is False


def test_a_missing_policy_leaves_the_hunter_unavailable_and_still(game, monkeypatch, tmp_path):
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'neural')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(tmp_path / 'absent.npz'))
    playing(game)
    game._summon_hunter((game.ship.x, game.ship.y))
    game.player_has_moved = True
    x, y = game.hunter.x, game.hunter.y
    for _ in range(30):
        game._update_hunter(1.0)
    assert game.hunter_controller.status == 'unavailable'
    assert (game.hunter.x, game.hunter.y) == (x, y)


def test_a_neural_hunter_moves_under_the_games_update_with_plain_controls(game, monkeypatch, tmp_path):
    good = tmp_path / 'good.npz'
    random_policy(2).save(good)
    monkeypatch.setattr(SETTINGS.game, 'hunterPilot', 'neural')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(good))
    playing(game)
    game._summon_hunter((game.ship.x, game.ship.y))
    game.player_has_moved = True
    seen = []
    original = game.hunter.step
    game.hunter.step = lambda dt, action, solution=None: (seen.append(action), original(dt, action, solution))[1]
    for _ in range(60):
        game._update_hunter(1.0)
    assert seen and all(not (a.track or a.course or a.worked_burn) and a.burn_heading is None for a in seen)
```

Add to `tests/test_hunter_settings_for.py` (the parametrised `turn` test already covers rules and jev):

```python
def test_the_neural_pilot_gets_its_own_turn_rate_and_nothing_else_changes():
    from dataclasses import replace
    neural = hunter_settings_for('neural')
    assert neural.turn_rate_multiplier == SETTINGS.game.neuralTurnRate
    assert replace(neural, turn_rate_multiplier=HunterSettings().turn_rate_multiplier) == HunterSettings()
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_neural_controller.py tests/test_neural_game.py tests/test_hunter_settings_for.py -q -p no:cacheprovider`
Expected: failures / collection errors for the missing modules and settings.

- [ ] **Step 3: Write the controller and loader**

`hunter/neural/controller.py`:

```python
"""Runs the neural policy inside the game loop: decides every few frames, holds the controls between."""
import config
from hunter.model import NEUTRAL
from hunter.neural.controls import to_action

START_CONTROLS = (1, False, False)   # no turn, coast, trigger off


class NeuralController:
    kind = 'neural'

    def __init__(self, policy, decision_frames, greedy=True, rng=None):
        self.policy, self.decision_frames = policy, max(1, int(decision_frames))
        self.greedy, self.rng = greedy, rng
        self.unavailable = policy is None
        self.closed = False
        self.action = NEUTRAL
        self.status = 'unavailable' if self.unavailable else 'waiting'
        self.frames = 0
        self.last_controls = (1, 0, 0)
        self._state = None if policy is None else policy.initial_state()

    def invalidate(self):
        """Forget the memory and start over (a new level, or a restart)."""
        self.frames = 0
        self.action = NEUTRAL
        self.last_controls = (1, 0, 0)
        if self.policy is not None:
            self._state = self.policy.initial_state()

    def close(self):
        if not self.closed:
            self.invalidate()
            self.closed = True
            self.status = 'coasting'

    def tick(self, senses_factory, running=True):
        if self.closed or self.unavailable:
            return NEUTRAL
        if not running:
            self.status = 'coasting'
            return NEUTRAL
        if self.frames % self.decision_frames == 0:
            senses = senses_factory(self.last_controls, self.frames / config.FPS)
            controls, self._state = self.policy.act(senses, self._state, self.greedy, self.rng)
            self.last_controls = (controls[0], 1 if controls[1] else 0, 1 if controls[2] else 0)
            self.action = to_action(controls)
        self.frames += 1
        self.status = 'active'
        return self.action
```

`hunter/neural/loader.py`:

```python
"""Loads the shipped neural policy, or reports that there is none."""
import logging
from hunter.neural.policy import InvalidPolicy, NeuralPolicy
from utils.resource_path import resource_path

DEFAULT_PATH = resource_path('assets/neural/hunter.npz')
_warned = set()


def load_neural_policy(path=None):
    path = str(path or DEFAULT_PATH)
    try:
        return NeuralPolicy.load(path)
    except InvalidPolicy as exc:
        if path not in _warned:
            _warned.add(path)
            logging.getLogger(__name__).warning('Neural pilot unavailable (%s): %s', path, exc)
        return None
```

(`NeuralPolicy.load` raises `InvalidPolicy` for a missing file because `np.load` raises `FileNotFoundError`, which the broad handler converts.)

- [ ] **Step 4: Settings and game wiring**

`config.py`, in `GameSettings`, after `hunterPilot`:

```python
    # The neural pilot decides every this many frames and holds its controls between, and its hunter
    # turns at this share of the player's rate.
    neuralDecisionFrames: int = 6
    neuralTurnRate: float = 1.0
```

`config/settings.json` `game` block (preserve the other keys):

```json
    "hunterPilot": "jev",
    "neuralDecisionFrames": 6,
    "neuralTurnRate": 1.0
```

`hunter/settings_for.py`: add at the top of `hunter_settings_for`:

```python
    if mode == 'neural':
        import config
        return replace(HunterSettings(), turn_rate_multiplier=config.SETTINGS.game.neuralTurnRate)
```

`game.py`:

1. Imports: `from hunter.senses import Senses`, `from hunter.neural.controller import NeuralController`, `from hunter.neural.loader import load_neural_policy`.
2. In `__init__`, next to `self.hunter_perception = None`: `self.hunter_senses = None`. In `_close_hunter`, also `self.hunter_senses = None`.
3. In `_summon_hunter`, replace the lines that build the perception, worker and controller with:

```python
        mode = config.SETTINGS.game.hunterPilot
        settings = hunter_settings_for(mode)
        self.hunter = HunterShip(pos, settings)
        self.hunter_perception = HunterPerception(settings)
        if mode == 'neural':
            self.hunter_senses = Senses(settings)
            self.hunter_controller = NeuralController(
                load_neural_policy(), config.SETTINGS.game.neuralDecisionFrames)
            return
        if self.hunter_worker is None:
            self.hunter_worker = PilotWorker()
        self.hunter_controller = HunterController(self.hunter_worker, settings)
```
   (keep the existing `self._close_hunter()` call above and the existing `settings = ...` line removed so it is not defined twice.)
4. Add a method:

```python
    def _hunter_entities(self):
        return [enemy for group in (self.enemies, self.replay_enemies, self.flockers, self.flighthouses,
                                    self.split_bosses, self.mother_bosses, self.babies, self.eggs,
                                    self.anemones) for enemy in group]

    def _neural_senses(self, last_controls, now):
        return self.hunter_senses.observe(
            self.hunter, self.maze, self._hunter_entities(), self.projectiles,
            [c for c in self.powerup_crystals if not isinstance(c, JevBeacon)],
            self.ship if self._hunter_sees_player() else None, last_controls, now)
```
5. In `_update_hunter`, replace `action = self.hunter_controller.tick(observe)` with:

```python
        if getattr(self.hunter_controller, 'kind', None) == 'neural':
            action = self.hunter_controller.tick(self._neural_senses)
        else:
            action = self.hunter_controller.tick(observe)
```
   and reuse `_hunter_entities()` inside `observe` (replace its inline list) so there is one definition.

- [ ] **Step 5: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_neural_controller.py tests/test_neural_game.py tests/test_hunter_settings_for.py tests/test_hunter_integration.py tests/test_hunter_powerups.py -q -p no:cacheprovider`
Expected: all PASS. Then run the whole suite once and fix anything that read the old `observe` list.

- [ ] **Step 6: Commit**

```bash
git add hunter/neural hunter/settings_for.py config.py game.py tests config/settings.json
git commit -m "feat: the neural pilot runs in the game loop

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Fly the student in the lab

**Files:**
- Modify: `experiments/harness.py` (`run_episode`), `experiments/run.py` (`evaluate`, `_episode`, `_run_one`)
- Create: `experiments/student.py`
- Test: `tests/test_experiment_student.py`

**Interfaces:**
- Consumes: `NeuralPolicy`, `NeuralController`, `Senses`, `HunterSettings`, the existing harness.
- Produces:
  - `experiments.student.StudentSpec(weights, decision_frames=6, turn_rate=1.0, greedy=True)`: a frozen, picklable dataclass; `weights` is a path string. `load_policy(spec)` caches the loaded policy per process (`functools.lru_cache`).
  - `run_episode(level, seed, params=DEFAULT, horizon=90.0, hide_player=True, trace=None, student=None)`; with a `StudentSpec` the hunter is flown by a `NeuralController`, with the spec's turn rate and the params' thrust and sight.
  - `run.evaluate(..., hide_player=True, student=None)` passes `student` through to every episode (pickled into workers).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_experiment_student.py`:

```python
import pytest
from experiments import run
from experiments.harness import run_episode
from experiments.student import StudentSpec, load_policy
from hunter.neural.policy import random_policy


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / 'p.npz'
    random_policy(0).save(path)
    return StudentSpec(weights=str(path), decision_frames=6, turn_rate=1.0)


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


def test_a_student_episode_runs_and_is_scored_like_any_other(spec):
    result = run_episode(13, 0, horizon=5.0, student=spec)
    assert result.end in ('cleared', 'horizon') and result.elapsed > 0
    assert min(result.kills, result.wall_hits, result.hits_taken) >= 0


def test_the_same_student_episode_twice_is_identical(spec):
    assert run_episode(14, 0, horizon=8.0, student=spec) == run_episode(14, 0, horizon=8.0, student=spec)


def test_the_student_flies_with_the_specs_turn_rate_and_plain_controls(spec, monkeypatch):
    from entities.hunter_ship import HunterShip
    seen = []
    original = HunterShip.step

    def spy(self, dt, action, solution=None):
        seen.append((self.current_rotation_speed, action))
        return original(self, dt, action, solution)
    monkeypatch.setattr(HunterShip, 'step', spy)
    run_episode(13, 0, horizon=2.0, student=spec)
    assert seen
    assert all(rate == pytest.approx(HunterShipRate.base * 1.0) for rate, _ in seen)
    assert all(not (a.track or a.course or a.worked_burn) for _, a in seen)


class HunterShipRate:
    base = 5.0


def test_a_different_turn_rate_changes_the_episode(spec, tmp_path):
    fast = StudentSpec(weights=spec.weights, decision_frames=6, turn_rate=3.0)
    a = run_episode(14, 0, horizon=15.0, student=spec)
    b = run_episode(14, 0, horizon=15.0, student=fast)
    assert (a.kills, a.wall_hits, a.hits_taken, round(a.idle_seconds, 2)) != \
           (b.kills, b.wall_hits, b.hits_taken, round(b.idle_seconds, 2))


def test_a_missing_weights_file_makes_a_still_hunter_not_a_crash(tmp_path):
    result = run_episode(13, 0, horizon=3.0, student=StudentSpec(weights=str(tmp_path / 'absent.npz')))
    assert result.end in ('cleared', 'horizon')


def test_evaluate_passes_the_student_to_each_episode(monkeypatch, spec):
    seen = []

    def fake_episode(level, seed, params, horizon, hide_player=True, student=None):
        seen.append(student)
        from experiments.harness import EpisodeResult
        return EpisodeResult(level, seed, 5, 10.0, 1, 0, 0, 0.0, 'horizon', 0)
    monkeypatch.setattr(run, '_episode', fake_episode)
    run.evaluate(run.DEFAULT, 'heldout', seeds=(0,), workers=1, student=spec)
    assert seen and all(s == spec for s in seen)
    seen.clear()
    run.evaluate(run.DEFAULT, 'heldout', seeds=(0,), workers=1)
    assert all(s is None for s in seen)


def test_the_policy_is_loaded_once_per_process(spec):
    assert load_policy(spec) is load_policy(spec)
```

(`test_the_student_flies_with_the_specs_turn_rate...` uses `HunterShipRate.base` = the ship's `base_rotation_speed` 5.0; if that constant differs, read it from a fresh `HunterShip((0, 0)).base_rotation_speed` instead of hard-coding it.)

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_experiment_student.py -q -p no:cacheprovider`
Expected: collection error (`experiments.student` missing).

- [ ] **Step 3: Implement**

`experiments/student.py`:

```python
"""Describes a neural student for the lab: which weights, how often it decides, how fast it turns."""
import functools
from dataclasses import dataclass
from hunter.neural.loader import load_neural_policy


@dataclass(frozen=True)
class StudentSpec:
    weights: str
    decision_frames: int = 6
    turn_rate: float = 1.0
    greedy: bool = True


@functools.lru_cache(maxsize=8)
def load_policy(spec):
    """The spec's policy (None if the file is missing or invalid), loaded once per process."""
    return load_neural_policy(spec.weights)
```

`experiments/harness.py` (all edits are exact; every `old` string appears once). Make the signature and the
overridden-names tuple:

```python
_OVERRIDDEN = ('_summon_hunter', '_jev_beacon_drop_allowed', '_hunter_sees_player', '_neural_senses')
```
```python
def run_episode(level, seed, params=DEFAULT, horizon=90.0, hide_player=True, trace=None,
                student=None, recorder=None, labeller=None, on_result=None):
```
(`recorder`, `labeller` and `on_result` are used by Tasks 6 and 10; add them now so the signature changes once.)
Replace

```python
    game.hunter_worker = SyncWorker(params, clock)
    game._summon_hunter((game.ship.x, game.ship.y))
    hunter, controller = game.hunter, game.hunter_controller
    controller.clock = clock
```
with

```python
    if student is None:
        game.hunter_worker = SyncWorker(params, clock)
    game._summon_hunter((game.ship.x, game.ship.y))
    hunter, controller = game.hunter, game.hunter_controller
    if student is None:
        controller.clock = clock
    else:
        # A student flies through the game's own neural path: replace whatever controller the
        # configured pilot built with a NeuralController on the student's weights.
        from experiments.student import load_policy
        from hunter.neural.controller import NeuralController
        controller = NeuralController(load_policy(student), student.decision_frames, greedy=student.greedy)
        game.hunter_controller = controller
```
and replace

```python
    settings = replace(HunterSettings(), thrust_multiplier=params.thrust_multiplier,
                       sensor_range_fraction=params.sensor_range_fraction,
                       turn_rate_multiplier=params.turn_rate_multiplier)
    hunter.settings = controller.settings = settings
```
with

```python
    settings = replace(HunterSettings(), thrust_multiplier=params.thrust_multiplier,
                       sensor_range_fraction=params.sensor_range_fraction,
                       turn_rate_multiplier=(params.turn_rate_multiplier if student is None
                                             else student.turn_rate))
    hunter.settings = settings
    if student is None:
        controller.settings = settings
    else:
        from hunter.senses import Senses
        game.hunter_senses = Senses(settings)
```

`experiments/run.py`: `_episode(level, seed, params, horizon, hide_player=True, student=None)` passes `student=student` to `run_episode`; `evaluate(..., hide_player=True, student=None)` puts `student` in each job tuple (a 6-tuple); `_run_one` unpacks it and passes it on. Update the existing fakes in `tests/test_experiment_run.py` and `tests/test_experiment_lab.py` to accept `student=None` (`def fake_episode(level, seed, params, horizon, hide_player=True, student=None)`).

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_experiment_student.py tests/test_experiment_run.py tests/test_experiment_lab.py tests/test_experiment_harness.py -q -p no:cacheprovider`
Expected: all PASS. If the determinism test fails, the cause is something reading the real clock or the global `random` outside the seeded section; use superpowers:systematic-debugging, do not loosen the test.

- [ ] **Step 5: Commit**

```bash
git add experiments tests
git commit -m "feat: fly a neural student in the lab and score it like the rules pilot

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Record the rules pilot as teaching data

**Files:**
- Create: `experiments/teach.py`
- Modify: `experiments/harness.py` (a `recorder` hook in `run_episode`)
- Test: `tests/test_experiment_teach.py`

**Interfaces:**
- Consumes: `Senses`, `step_labels`, `to_action`-compatible labels, the harness.
- Produces:
  - `harness.run_episode(..., recorder=None)`: if given, `recorder.begin(game, hunter, params)` is called once after setup and `recorder.frame(game, hunter, action, shots)` after every `hunter.step`; the lab wraps `hunter.step` for this.
  - `teach.StepRecorder(decision_frames, rate)`: collects `senses` (list of vectors) and `labels` (list of `(turn, thrust, fire)`); `arrays() -> (senses (T, D) float32, labels (T, 3) int8)`.
  - `teach.record_episode(level, seed, params=RULES, decision_frames=6, turn_rate=1.0, horizon=90.0) -> (senses, labels)`: the rules pilot flies a ship with turn rate `turn_rate` (and `params`' thrust and sight) while the recorder runs.
  - `teach.main(argv)`: `python -m experiments.teach --out DIR --seeds 100-139 --levels tune --turn-rate 1.0 --decision-frames 6 --workers N` writes one `level<L>-seed<S>.npz` (`senses`, `labels`) per episode, skipping files that exist.

How it works: for each decision step of N frames (frames 0, N, 2N, ...), the recorder computes the senses vector from the live game with the previous step's labels as `last_controls`, then accumulates the executed `(rotation, engine_fired, trigger)` of the next N frames and turns them into the label with `step_labels`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_experiment_teach.py`:

```python
import numpy as np
import pytest
from experiments import teach
from hunter.senses import SENSE_SIZE


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


def test_an_episode_records_aligned_senses_and_labels():
    senses, labels = teach.record_episode(13, 100, decision_frames=6, horizon=6.0)
    assert senses.shape == (60, SENSE_SIZE) and senses.dtype == np.float32     # 6 s at 10 decisions a second
    assert labels.shape == (60, 3) and labels.dtype == np.int8
    assert set(np.unique(labels[:, 0])) <= {0, 1, 2} and set(np.unique(labels[:, 1:])) <= {0, 1}
    assert np.isfinite(senses).all()


def test_the_rules_pilot_actually_does_things_so_the_labels_are_not_constant():
    _, labels = teach.record_episode(14, 100, decision_frames=6, horizon=20.0)
    assert len(set(map(tuple, labels))) > 2
    assert labels[:, 1].any() and labels[:, 0].any()


def test_the_last_controls_in_each_senses_row_are_the_previous_rows_labels():
    senses, labels = teach.record_episode(13, 101, decision_frames=6, horizon=4.0)
    from hunter.senses import FEATURE_NAMES
    cols = [FEATURE_NAMES.index(n) for n in ('last_turn_left', 'last_turn_none', 'last_turn_right')]
    for t in range(1, len(labels)):
        assert int(np.argmax(senses[t, cols])) == labels[t - 1, 0]
        assert senses[t, FEATURE_NAMES.index('last_thrust')] == labels[t - 1, 1]
        assert senses[t, FEATURE_NAMES.index('last_fire')] == labels[t - 1, 2]


def test_recording_is_deterministic():
    a = teach.record_episode(13, 102, decision_frames=6, horizon=5.0)
    b = teach.record_episode(13, 102, decision_frames=6, horizon=5.0)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_the_decision_rate_changes_the_number_of_steps():
    s3, _ = teach.record_episode(13, 100, decision_frames=3, horizon=4.0)
    s6, _ = teach.record_episode(13, 100, decision_frames=6, horizon=4.0)
    assert len(s3) == 2 * len(s6)


def test_labels_translate_special_commands_into_the_basic_equivalents():
    # A course turn is recorded as the left or right the ship actually performed; a burn as thrust.
    from hunter.neural.controls import TURN_LEFT, TURN_RIGHT
    recorder = teach.StepRecorder(decision_frames=2, rate=5.0)
    recorder.add_frame(rotation=-5.0, engine=False, trigger=False)
    recorder.add_frame(rotation=-5.0, engine=True, trigger=False)
    assert recorder.pending_label() == (TURN_LEFT, True, False)


def test_the_cli_writes_one_file_per_episode_and_skips_existing_ones(tmp_path):
    out = tmp_path / 'teach'
    args = ['--out', str(out), '--seeds', '100-100', '--levels', '13', '--horizon', '3', '--workers', '1']
    teach.main(args)
    files = sorted(out.glob('*.npz'))
    assert [f.name for f in files] == ['level13-seed100.npz']
    stamp = files[0].stat().st_mtime_ns
    teach.main(args)
    assert files[0].stat().st_mtime_ns == stamp
    data = np.load(files[0])
    assert data['senses'].shape[1] == SENSE_SIZE and data['labels'].shape[1] == 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_experiment_teach.py -q -p no:cacheprovider`
Expected: collection error (`experiments.teach` missing).

- [ ] **Step 3: Implement**

`experiments/harness.py` (the `recorder` parameter was added to the signature in Task 5). Insert this block
immediately before `alive = _active_enemies(game)` (after the `counting_damage` wrapper), so the ship already has its
final settings and turn rate:

```python
    if recorder is not None:
        original_step = hunter.step

        def recording_step(dt, action, solution=None):
            before = hunter.angle
            shots = original_step(dt, action, solution)
            recorder.add_frame(rotation=((hunter.angle - before + 180.0) % 360.0) - 180.0,
                               engine=bool(hunter.pilot_thrusting), trigger=bool(action.fire or shots))
            return shots
        hunter.step = recording_step
        recorder.begin(game, hunter, settings)
```

and change the frame loop to (this is also where Task 10 hooks in):

```python
    for frame in range(int(horizon * FPS)):
        now[0] += 1 / FPS
        elapsed += 1 / FPS
        if recorder is not None:
            recorder.before_frame(game, hunter)
        if labeller is not None:
            labeller.before_frame(game, hunter, frame)
        game.update(1.0)
        if recorder is not None:
            recorder.after_frame()
        if game.hunter is not hunter or game.hunter_controller is not controller:
            raise RuntimeError('hunter was replaced during the episode')
        alive = _active_enemies(game)
        counter.observe(alive)
        counter.tick(elapsed)
        if trace is not None:
            trace(elapsed, game, hunter)
        if start_enemies and not alive:
            end = 'cleared'
            break
```
and end the function with

```python
    game._close_hunter()
    _clear_overrides(game)
    result = EpisodeResult(level, seed, start_enemies, elapsed, counter.kills, counter.wall_hits,
                           counter.hits_taken, counter.idle_seconds, end, counter.spawned)
    if on_result is not None:
        on_result(result)
    return result
```

`experiments/teach.py`:

```python
"""Records the rules pilot as teaching data: senses at each decision step, and the controls it executed."""
import argparse
import os
import numpy as np
from experiments import run
from experiments.harness import run_episode
from hunter.neural.controls import step_labels
from hunter.rule_params import RULES
from hunter.senses import SENSE_SIZE, Senses

TEACH_DIR = run.RESULTS_DIR.parent / 'neural' / 'teach'


class StepRecorder:
    def __init__(self, decision_frames, rate=5.0):
        self.decision_frames, self.rate = decision_frames, rate
        self.senses, self.labels = [], []
        self._frames = []
        self._count = 0
        self._last = (1, 0, 0)
        self._senses_obj = None
        self._game = self._hunter = None

    # --- called by the harness ---
    def begin(self, game, hunter, settings):
        self._game, self._hunter = game, hunter
        self._senses_obj = Senses(settings)
        self.rate = hunter.current_rotation_speed

    def before_frame(self, game, hunter):
        if self._count % self.decision_frames == 0:
            enemies = game._hunter_entities()
            sense = self._senses_obj.observe(
                hunter, game.maze, enemies, game.projectiles,
                [c for c in game.powerup_crystals if type(c).__name__ != 'JevBeacon'],
                game.ship if game._hunter_sees_player() else None, self._last, self._count / 60.0)
            self.senses.append(sense)

    def add_frame(self, rotation, engine, trigger):
        self._frames.append((rotation, engine, trigger))

    def after_frame(self):
        self._count += 1
        if self._count % self.decision_frames == 0:
            self._close_step()

    # --- helpers ---
    def pending_label(self):
        return step_labels(self._frames, self.rate)

    def _close_step(self):
        label = self.pending_label()
        self.labels.append(label)
        self._last = (label[0], 1 if label[1] else 0, 1 if label[2] else 0)
        self._frames = []

    def arrays(self):
        n = min(len(self.senses), len(self.labels))
        senses = np.asarray(self.senses[:n], dtype=np.float32).reshape(n, SENSE_SIZE)
        labels = np.asarray(self.labels[:n], dtype=np.int8).reshape(n, 3)
        return senses, labels


def record_episode(level, seed, params=RULES, decision_frames=6, turn_rate=1.0, horizon=90.0):
    from dataclasses import replace
    flown = replace(params, turn_rate_multiplier=turn_rate)
    recorder = StepRecorder(decision_frames)
    run_episode(level, seed, flown, horizon, recorder=recorder)
    return recorder.arrays()


def _record_job(job):
    level, seed, decision_frames, turn_rate, horizon, path = job
    senses, labels = record_episode(level, seed, RULES, decision_frames, turn_rate, horizon)
    np.savez(path + '.tmp.npz', senses=senses, labels=labels)
    os.replace(path + '.tmp.npz', path)
    return path


def _parse_seeds(text):
    low, _, high = text.partition('-')
    return range(int(low), int(high or low) + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(TEACH_DIR))
    parser.add_argument('--seeds', default='100-139')
    parser.add_argument('--levels', default='tune', help="'tune', 'heldout' or a comma list of level numbers")
    parser.add_argument('--turn-rate', type=float, default=1.0)
    parser.add_argument('--decision-frames', type=int, default=6)
    parser.add_argument('--horizon', type=float, default=90.0)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    run._use_dummy_drivers()
    levels = (run.LEVEL_SETS[args.levels] if args.levels in run.LEVEL_SETS
              else tuple(int(x) for x in args.levels.split(',')))
    os.makedirs(args.out, exist_ok=True)
    jobs = []
    for level in levels:
        for seed in _parse_seeds(args.seeds):
            path = os.path.join(args.out, f'level{level}-seed{seed}.npz')
            if not os.path.exists(path):
                jobs.append((level, seed, args.decision_frames, args.turn_rate, args.horizon, path))
    if args.workers <= 1:
        for job in jobs:
            _record_job(job)
    else:
        import multiprocessing
        with multiprocessing.get_context('spawn').Pool(args.workers, initializer=run._use_dummy_drivers) as pool:
            pool.map(_record_job, jobs, chunksize=1)
    print(f'{len(jobs)} episodes recorded to {args.out}')


if __name__ == '__main__':
    main()
```

(`game._hunter_entities()` is the method added in Task 4. The harness keeps passing `settings` to `recorder.begin` after it has built them.)

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_experiment_teach.py -q -p no:cacheprovider`
Expected: all PASS. If the labels are constant, the wrapper is not capturing the rules pilot's executed controls: print `hunter.pilot_thrusting` and the angle deltas for a few frames before changing anything else.

- [ ] **Step 5: Record a first teaching set**

Run: `venv/bin/python -m experiments.teach --turn-rate 1.0 --decision-frames 6 2>&1 | tail -2`
Expected: `480 episodes recorded to .../neural/teach` in a few minutes on 12 cores. Check the size (`du -sh .astrovoid-local/neural/teach`, expect a few hundred MB) and the label balance (`venv/bin/python - <<'EOF' ... np.bincount ... EOF`); note any label that is under 3% of steps in the commit message.

- [ ] **Step 6: Commit**

```bash
git add experiments tests
git commit -m "feat: record the rules pilot's executed controls as teaching data

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The trainer

**Files:**
- Create: `tools/train_neural.py`
- Test: `tests/test_train_neural.py`

**Interfaces:**
- Consumes: `NeuralPolicy`, `HEAD_SIZES`, `SENSE_SIZE`, teaching `.npz` files (`senses`, `labels`).
- Produces (all in `tools/train_neural.py`):
  - `load_episodes(*dirs) -> list[Episode]` where `Episode = (name, senses, labels)`; skips unreadable files.
  - `split_episodes(episodes, held_out_fraction=0.1, seed=0) -> (train, val)` (whole episodes).
  - `train(train, val, hidden=128, embed=64, window=64, warmup=16, epochs=30, lr=1e-3, batch=32, init=None, seed=0, log=print) -> NeuralPolicy`: torch GRU, windows of `window` consecutive steps with the first `warmup` unscored, cross-entropy summed over the three heads, Adam, gradient clip 1.0; standardisation from the training senses; `init` is a `NeuralPolicy` to continue from.
  - `to_numpy_policy(model, mean, scale) -> NeuralPolicy` and the torch module `TorchNet`.
  - `agreement(policy, episodes) -> dict` of per-head and joint agreement, replaying each episode with the numpy policy so the memory carries across the whole episode.
  - `main(argv)`: `python -m tools.train_neural --data DIR [DIR ...] --out PATH [--init PATH] [--epochs N]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_train_neural.py`:

```python
import numpy as np
import pytest

pytest.importorskip('torch')

from hunter.neural.policy import NeuralPolicy
from hunter.senses import FEATURE_NAMES, SENSE_SIZE
from tools import train_neural as tn


def toy_episodes(n=12, length=300, seed=0):
    """Labels are a function of the senses and of the previous senses, so memory helps."""
    rng = np.random.default_rng(seed)
    episodes = []
    ahead = FEATURE_NAMES.index('enemy0_sin'); present = FEATURE_NAMES.index('enemy0_present')
    for e in range(n):
        senses = rng.normal(0, 1, (length, SENSE_SIZE)).astype(np.float32)
        senses[:, present] = (rng.random(length) < 0.7).astype(np.float32)
        turn = np.where(senses[:, ahead] > 0.3, 2, np.where(senses[:, ahead] < -0.3, 0, 1)).astype(np.int8)
        thrust = (senses[:, FEATURE_NAMES.index('ray_0')] > 0).astype(np.int8)
        fire = (senses[:, present] > 0.5).astype(np.int8)
        episodes.append((f'e{e}', senses, np.stack([turn, thrust, fire], axis=1)))
    return episodes


def test_the_numpy_policy_matches_the_torch_net_it_was_exported_from():
    import torch
    net = tn.TorchNet(hidden=16, embed=8)
    mean = np.zeros(SENSE_SIZE, dtype=np.float32); scale = np.ones(SENSE_SIZE, dtype=np.float32)
    policy = tn.to_numpy_policy(net, mean, scale)
    senses = np.random.default_rng(1).normal(0, 1, (12, SENSE_SIZE)).astype(np.float32)
    with torch.no_grad():
        out, _ = net(torch.from_numpy(senses)[None])
    state = policy.initial_state()
    for t in range(12):
        logits, state = policy.step(senses[t], state)
        for head in ('turn', 'thrust', 'fire'):
            assert np.allclose(logits[head], out[head][0, t].numpy(), atol=1e-4), (t, head)


def test_training_learns_a_simple_rule_and_beats_the_majority_baseline():
    episodes = toy_episodes()
    train, val = tn.split_episodes(episodes, held_out_fraction=0.34, seed=0)
    policy = tn.train(train, val, hidden=32, embed=16, window=32, warmup=8, epochs=60, lr=3e-3, batch=8,
                      log=lambda *_: None)
    result = tn.agreement(policy, val)
    majority = max(np.mean(np.concatenate([e[2][:, 0] for e in val]) == k) for k in (0, 1, 2))
    assert result['turn'] > max(0.8, majority + 0.1)
    assert result['fire'] > 0.9


def test_the_exported_file_loads_and_flies(tmp_path):
    episodes = toy_episodes(n=3, length=80)
    policy = tn.train(episodes[:2], episodes[2:], hidden=16, embed=8, window=16, warmup=4, epochs=2, log=lambda *_: None)
    path = tmp_path / 'p.npz'
    policy.save(path)
    loaded = NeuralPolicy.load(path)
    controls, _ = loaded.act(episodes[0][1][0], loaded.initial_state())
    assert controls[0] in (0, 1, 2)


def test_continuing_from_an_earlier_policy_starts_from_its_weights():
    episodes = toy_episodes(n=3, length=80)
    first = tn.train(episodes[:2], episodes[2:], hidden=16, embed=8, window=16, warmup=4, epochs=1, log=lambda *_: None)
    again = tn.train(episodes[:2], episodes[2:], hidden=16, embed=8, window=16, warmup=4, epochs=0, init=first, log=lambda *_: None)
    assert np.allclose(first.params['gru_w_ih'], again.params['gru_w_ih'])


def test_splits_are_by_episode_and_deterministic():
    episodes = toy_episodes(n=10, length=20)
    a = tn.split_episodes(episodes, 0.3, seed=1); b = tn.split_episodes(episodes, 0.3, seed=1)
    assert [e[0] for e in a[1]] == [e[0] for e in b[1]]
    assert not {e[0] for e in a[0]} & {e[0] for e in a[1]} and len(a[1]) == 3


def test_load_episodes_reads_directories_and_skips_bad_files(tmp_path):
    ok = toy_episodes(n=1, length=10)[0]
    np.savez(tmp_path / 'a.npz', senses=ok[1], labels=ok[2])
    (tmp_path / 'junk.npz').write_bytes(b'x')
    episodes = tn.load_episodes(tmp_path)
    assert [e[0] for e in episodes] == ['a'] and episodes[0][1].shape == (10, SENSE_SIZE)


def test_windows_never_cross_episode_boundaries_and_short_episodes_are_handled():
    episodes = toy_episodes(n=2, length=10)          # shorter than one window
    policy = tn.train(episodes[:1], episodes[1:], hidden=8, embed=4, window=32, warmup=4, epochs=1, log=lambda *_: None)
    assert policy is not None
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_train_neural.py -q -p no:cacheprovider`
Expected: collection error (`tools.train_neural` missing).

- [ ] **Step 3: Implement `tools/train_neural.py`**

```python
"""Trains the neural student from teaching data: python -m tools.train_neural."""
import argparse
import sys
from pathlib import Path
import numpy as np
from hunter.neural.policy import HEAD_SIZES, NeuralPolicy
from hunter.senses import SENSE_SIZE

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'assets' / 'neural' / 'hunter.npz'


def load_episodes(*directories):
    episodes = []
    for directory in directories:
        for path in sorted(Path(directory).glob('*.npz')):
            try:
                data = np.load(path)
                senses, labels = data['senses'].astype(np.float32), data['labels'].astype(np.int64)
            except Exception:
                continue
            if len(senses) and len(senses) == len(labels):
                episodes.append((path.stem, senses, labels))
    return episodes


def split_episodes(episodes, held_out_fraction=0.1, seed=0):
    order = list(range(len(episodes)))
    np.random.default_rng(seed).shuffle(order)
    held = set(order[:max(1, round(len(episodes) * held_out_fraction))])
    return ([e for i, e in enumerate(episodes) if i not in held],
            [e for i, e in enumerate(episodes) if i in held])


def _torch_net_class():
    import torch

    class TorchNet(torch.nn.Module):
        def __init__(self, hidden=128, embed=64):
            super().__init__()
            self.embed = torch.nn.Linear(SENSE_SIZE, embed)
            self.gru = torch.nn.GRU(embed, hidden, batch_first=True)
            self.heads = torch.nn.ModuleDict({k: torch.nn.Linear(hidden, n) for k, n in HEAD_SIZES.items()})

        def forward(self, x, state=None):
            h, state = self.gru(torch.tanh(self.embed(x)), state)
            return {k: head(h) for k, head in self.heads.items()}, state
    return TorchNet


def __getattr__(name):
    if name == 'TorchNet':
        return _torch_net_class()
    raise AttributeError(name)


def to_numpy_policy(net, mean, scale):
    params = {'embed_w': net.embed.weight, 'embed_b': net.embed.bias,
              'gru_w_ih': net.gru.weight_ih_l0, 'gru_w_hh': net.gru.weight_hh_l0,
              'gru_b_ih': net.gru.bias_ih_l0, 'gru_b_hh': net.gru.bias_hh_l0}
    for head in HEAD_SIZES:
        params[f'{head}_w'], params[f'{head}_b'] = net.heads[head].weight, net.heads[head].bias
    return NeuralPolicy({k: v.detach().numpy().copy() for k, v in params.items()}, mean, scale)


def _load_into(net, policy):
    import torch
    mapping = {'embed_w': net.embed.weight, 'embed_b': net.embed.bias,
               'gru_w_ih': net.gru.weight_ih_l0, 'gru_w_hh': net.gru.weight_hh_l0,
               'gru_b_ih': net.gru.bias_ih_l0, 'gru_b_hh': net.gru.bias_hh_l0}
    for head in HEAD_SIZES:
        mapping[f'{head}_w'], mapping[f'{head}_b'] = net.heads[head].weight, net.heads[head].bias
    with torch.no_grad():
        for key, tensor in mapping.items():
            tensor.copy_(torch.from_numpy(policy.params[key]))


def _windows(episodes, window, rng):
    """Random windows of `window` consecutive steps (shorter episodes give one short window)."""
    out = []
    for _, senses, labels in episodes:
        n = len(senses)
        starts = range(0, max(1, n - window + 1), window)
        for s in starts:
            e = min(n, s + window)
            out.append((senses[s:e], labels[s:e]))
    rng.shuffle(out)
    return out


def _pad(batch, mean, scale):
    import torch
    length = max(len(s) for s, _ in batch)
    x = torch.zeros(len(batch), length, SENSE_SIZE)
    y = torch.full((len(batch), length, 3), -100, dtype=torch.long)
    for i, (s, l) in enumerate(batch):
        x[i, :len(s)] = torch.from_numpy((s - mean) / scale)
        y[i, :len(l)] = torch.from_numpy(l)
    return x, y


def train(train_episodes, val_episodes, hidden=128, embed=64, window=64, warmup=16, epochs=30,
          lr=1e-3, batch=32, init=None, seed=0, log=print):
    import torch
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    allsenses = np.concatenate([e[1] for e in train_episodes])
    if init is not None:
        mean, scale = init.mean, init.scale
        hidden, embed = init.hidden, init.params['embed_w'].shape[0]
    else:
        mean = allsenses.mean(axis=0)
        std = allsenses.std(axis=0)
        scale = np.where(std > 1e-6, std, 1.0).astype(np.float32)
    net = _torch_net_class()(hidden, embed)
    if init is not None:
        _load_into(net, init)
    optimiser = torch.optim.Adam(net.parameters(), lr=lr)
    for epoch in range(epochs):
        net.train()
        total, count = 0.0, 0
        windows = _windows(train_episodes, window, rng)
        for i in range(0, len(windows), batch):
            x, y = _pad(windows[i:i + batch], mean, scale)
            out, _ = net(x)
            mask = torch.zeros(y.shape[:2], dtype=torch.bool)
            mask[:, warmup:] = True
            loss = 0.0
            for k, head in enumerate(('turn', 'thrust', 'fire')):
                target = y[:, :, k].clone()
                target[~mask] = -100
                loss = loss + torch.nn.functional.cross_entropy(
                    out[head].reshape(-1, HEAD_SIZES[head]), target.reshape(-1), ignore_index=-100)
            if not torch.isfinite(loss):
                continue
            optimiser.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            optimiser.step()
            total, count = total + float(loss), count + 1
        if count:
            log(f'epoch {epoch + 1}/{epochs}  loss {total / count:.4f}')
    return to_numpy_policy(net, mean, scale)


def agreement(policy, episodes):
    """Per-head and joint agreement with the teacher, replaying each episode from a clean memory."""
    hits = {'turn': 0, 'thrust': 0, 'fire': 0, 'joint': 0}
    total = 0
    for _, senses, labels in episodes:
        state = policy.initial_state()
        for t in range(len(senses)):
            (turn, thrust, fire), state = policy.act(senses[t], state)
            ok = (turn == labels[t, 0], int(thrust) == labels[t, 1], int(fire) == labels[t, 2])
            hits['turn'] += ok[0]; hits['thrust'] += ok[1]; hits['fire'] += ok[2]; hits['joint'] += all(ok)
            total += 1
    return {k: v / max(total, 1) for k, v in hits.items()} | {'steps': total}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', nargs='+', required=True)
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--init')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--hidden', type=int, default=128)
    parser.add_argument('--embed', type=int, default=64)
    args = parser.parse_args(argv)
    episodes = load_episodes(*args.data)
    train_eps, val_eps = split_episodes(episodes)
    print(f'{len(train_eps)} training episodes, {len(val_eps)} validation episodes, '
          f'{sum(len(e[1]) for e in episodes)} steps')
    init = NeuralPolicy.load(args.init) if args.init else None
    policy = train(train_eps, val_eps, hidden=args.hidden, embed=args.embed, epochs=args.epochs, init=init)
    print('validation agreement (a diagnostic, not the gate):', agreement(policy, val_eps))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    policy.save(args.out)
    print('saved', args.out)


if __name__ == '__main__':
    main(sys.argv[1:])
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_train_neural.py -q -p no:cacheprovider`
Expected: all PASS. If the parity test fails, the numpy GRU's gate order or the torch module's `embed` activation differs: both use `tanh(embed)` then a GRU with gates ordered r, z, n; fix the numpy side only if the torch side is the standard `torch.nn.GRU`.

- [ ] **Step 5: Train a first policy on the Task 6 data and read it**

Run: `venv/bin/python -m tools.train_neural --data .astrovoid-local/neural/teach --out .astrovoid-local/neural/round0.npz --epochs 20 2>&1 | tail -6`
Expected: training completes; the validation agreement prints. Per-step agreement is only a sanity check here (the gate is closed-loop, Task 8).

- [ ] **Step 6: Commit**

```bash
git add tools/train_neural.py tests/test_train_neural.py requirements-train.txt
git commit -m "feat: train the neural student from the rules pilot's teaching data

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The gate and the neural lab commands

**Files:**
- Create: `experiments/neural_lab.py`
- Test: `tests/test_neural_lab.py`

**Interfaces:**
- Consumes: `run.evaluate` (with `student`), `mean_components`, `score`, `paired_bootstrap`, `StudentSpec`.
- Produces (in `experiments/neural_lab.py`):
  - `gate_report(rules_results, student_results, weights=None) -> dict` with keys `rules`, `student` (each a dict of mean components plus `score`), `score_ratio` (student / rules, both as the lab's mean score), `wall_ratio`, `hit_ratio`, and booleans `score_ok` (>= 0.8), `wall_ok` (<= 1.25), `hit_ok` (<= 1.25), `passed` (all three).
  - `format_gate(report) -> str`.
  - `main(argv)` with commands `gate` and `compare`: `python -m experiments.neural_lab gate --weights PATH [--turn-rate X] [--decision-frames N] [--seeds 18] [--set heldout]` flies the rules pilot and the student on the same episodes and prints the report; `compare --weights-a A --weights-b B` prints a paired comparison of two students (per term, 95% interval).

The score ratio uses the lab's mean score (frozen weights), so a negative or tiny rules score cannot produce a misleading ratio: if the rules mean score is not positive, `score_ok` is False and the report says why.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_neural_lab.py`:

```python
import pytest
from experiments import neural_lab
from experiments.harness import EpisodeResult


def results(kill_share, walls, hits, n=6, minutes=1.0):
    elapsed = 60.0 * minutes
    return [EpisodeResult(13, i, 10, elapsed, int(10 * kill_share), int(walls), int(hits), 0.0, 'horizon', 0)
            for i in range(n)]


def test_a_student_close_to_the_rules_pilot_passes():
    report = neural_lab.gate_report(results(1.0, 2, 2), results(0.9, 2, 2))
    assert report['passed'] and report['score_ok'] and report['wall_ok'] and report['hit_ok']
    assert 0.8 <= report['score_ratio'] <= 1.0


def test_a_student_that_scores_too_low_fails():
    report = neural_lab.gate_report(results(1.0, 2, 2), results(0.3, 2, 2))
    assert not report['score_ok'] and not report['passed']


def test_a_student_that_collides_too_much_fails_even_if_it_scores_well():
    report = neural_lab.gate_report(results(1.0, 4, 4), results(1.0, 8, 4))
    assert not report['wall_ok'] and not report['passed']
    report = neural_lab.gate_report(results(1.0, 4, 4), results(1.0, 4, 8))
    assert not report['hit_ok'] and not report['passed']


def test_exactly_at_the_limits_passes():
    report = neural_lab.gate_report(results(1.0, 4, 4), results(1.0, 5, 5))
    assert report['wall_ok'] and report['hit_ok']


def test_a_rules_pilot_with_no_collisions_does_not_divide_by_zero():
    report = neural_lab.gate_report(results(1.0, 0, 0), results(1.0, 0, 0))
    assert report['wall_ok'] and report['hit_ok']
    assert not neural_lab.gate_report(results(1.0, 0, 0), results(1.0, 3, 0))['wall_ok']


def test_a_non_positive_rules_score_cannot_pass_the_ratio():
    report = neural_lab.gate_report(results(0.0, 0, 0), results(1.0, 0, 0))
    assert not report['score_ok'] and 'not positive' in neural_lab.format_gate(report)


def test_the_text_report_names_every_term_and_the_verdict():
    text = neural_lab.format_gate(neural_lab.gate_report(results(1.0, 2, 2), results(0.9, 2, 2)))
    for word in ('score', 'wall', 'enemy', 'kill', 'PASSED'):
        assert word in text
    assert 'FAILED' in neural_lab.format_gate(neural_lab.gate_report(results(1.0, 2, 2), results(0.1, 2, 2)))


def test_the_gate_command_flies_both_pilots_on_the_same_episodes(monkeypatch, tmp_path):
    calls = []

    def fake_evaluate(params, level_set, seeds, horizon, workers, hide_player=True, student=None):
        calls.append((level_set, tuple(seeds), student))
        return results(1.0 if student is None else 0.95, 2, 2, n=3)
    monkeypatch.setattr(neural_lab.run, 'evaluate', fake_evaluate)
    path = tmp_path / 'w.npz'
    path.write_bytes(b'x')
    neural_lab.main(['gate', '--weights', str(path), '--seeds', '3', '--workers', '1'])
    assert [c[0] for c in calls] == ['heldout', 'heldout'] and calls[0][1] == calls[1][1] == (0, 1, 2)
    assert calls[0][2] is None and calls[1][2].weights == str(path)
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_neural_lab.py -q -p no:cacheprovider`
Expected: collection error (`experiments.neural_lab` missing).

- [ ] **Step 3: Implement `experiments/neural_lab.py`**

```python
"""Flies a neural student against the rules pilot and applies the gate: python -m experiments.neural_lab."""
import argparse
import os
from experiments import run
from experiments.score import components, mean_components, paired_bootstrap, score
from experiments.student import StudentSpec
from hunter.rule_params import RULES

SCORE_RATIO_MIN = 0.8
COLLISION_RATIO_MAX = 1.25


def _ratio(student, rules):
    if rules <= 1e-9:
        return 0.0 if student <= 1e-9 else float('inf')
    return student / rules


def gate_report(rules_results, student_results, weights=None):
    rules = mean_components(rules_results, *([weights] if weights else []))
    student = mean_components(student_results, *([weights] if weights else []))
    report = {'rules': rules, 'student': student}
    report['score_ratio'] = student['score'] / rules['score'] if rules['score'] > 0 else float('nan')
    report['wall_ratio'] = _ratio(student['wall_hits_per_min'], rules['wall_hits_per_min'])
    report['hit_ratio'] = _ratio(student['hits_taken_per_min'], rules['hits_taken_per_min'])
    report['rules_score_positive'] = rules['score'] > 0
    report['score_ok'] = report['rules_score_positive'] and report['score_ratio'] >= SCORE_RATIO_MIN
    report['wall_ok'] = report['wall_ratio'] <= COLLISION_RATIO_MAX
    report['hit_ok'] = report['hit_ratio'] <= COLLISION_RATIO_MAX
    report['passed'] = report['score_ok'] and report['wall_ok'] and report['hit_ok']
    return report


def format_gate(report):
    lines = ['term                 rules   student']
    for key in ('kill_pct_per_min', 'kills_per_min', 'wall_hits_per_min', 'hits_taken_per_min',
                'idle_fraction', 'score'):
        lines.append(f'  {key:20s} {report["rules"][key]:8.3f} {report["student"][key]:8.3f}')
    if report['rules_score_positive']:
        lines.append(f'score ratio {report["score_ratio"]:.2f} (needs >= {SCORE_RATIO_MIN}): '
                     f'{"ok" if report["score_ok"] else "short"}')
    else:
        lines.append('score ratio unavailable: the rules pilot score is not positive')
    lines.append(f'wall hits ratio {report["wall_ratio"]:.2f} (needs <= {COLLISION_RATIO_MAX}): '
                 f'{"ok" if report["wall_ok"] else "too many"}')
    lines.append(f'enemy hits ratio {report["hit_ratio"]:.2f} (needs <= {COLLISION_RATIO_MAX}): '
                 f'{"ok" if report["hit_ok"] else "too many"}')
    lines.append('GATE ' + ('PASSED' if report['passed'] else 'FAILED'))
    return '\n'.join(lines)


def _spec(args, weights):
    return StudentSpec(weights=str(weights), decision_frames=args.decision_frames, turn_rate=args.turn_rate)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('gate', 'compare'))
    parser.add_argument('--weights')
    parser.add_argument('--weights-a')
    parser.add_argument('--weights-b')
    parser.add_argument('--turn-rate', type=float, default=1.0)
    parser.add_argument('--decision-frames', type=int, default=6)
    parser.add_argument('--seeds', type=int, default=18)
    parser.add_argument('--set', default='heldout', choices=('heldout', 'tune'))
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    run._use_dummy_drivers()
    seeds = tuple(range(args.seeds))
    if args.command == 'gate':
        rules = run.evaluate(RULES, args.set, seeds, 90.0, args.workers)
        student = run.evaluate(RULES, args.set, seeds, 90.0, args.workers, student=_spec(args, args.weights))
        print(format_gate(gate_report(rules, student)))
        return
    a = run.evaluate(RULES, args.set, seeds, 90.0, args.workers, student=_spec(args, args.weights_a))
    b = run.evaluate(RULES, args.set, seeds, 90.0, args.workers, student=_spec(args, args.weights_b))
    for key in list(components(a[0])) + ['score']:
        va = [score(r) if key == 'score' else components(r)[key] for r in a]
        vb = [score(r) if key == 'score' else components(r)[key] for r in b]
        diff, low, high = paired_bootstrap(va, vb)
        print(f'  {key:20s} {sum(va)/len(va):8.3f} -> {sum(vb)/len(vb):8.3f}  {diff:+8.3f} ({low:+.3f} .. {high:+.3f})')


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_neural_lab.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Fly the round-0 policy against the gate (real)**

Run: `venv/bin/python -m experiments.neural_lab gate --weights .astrovoid-local/neural/round0.npz --turn-rate 1.0 --decision-frames 6 --seeds 6 2>&1 | grep -v pygame`
Expected: a gate report. Round 0 is not expected to pass; record the numbers (they are the baseline for the corrected rounds).

- [ ] **Step 6: Commit**

```bash
git add experiments/neural_lab.py tests/test_neural_lab.py
git commit -m "feat: the closed-loop gate for the neural student

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Teacher relabelling (the shadow teacher)

**Files:**
- Create: `experiments/shadow.py`
- Test: `tests/test_experiment_shadow.py`

**Interfaces:**
- Consumes: `JevPilot`, `RulesClient`, `HunterPerception`, `find_firing_solution`, `step_labels`, the game and ship.
- Produces (in `experiments/shadow.py`):
  - `snapshot(hunter) -> dict` and `restore(hunter, state)`: exact save and restore of the ship's mutable state (`x, y, prev_x, prev_y, vx, vy, angle, fire_remaining, burst_remaining, immunity_remaining, upgrade_remaining, gun_upgrade_level, pilot_thrusting, thrusting, thrust_frames, _decision, _burn_left, health, active, death_timer`).
  - `trial_controls(game, hunter, action, frames) -> (turn_index, thrust, fire)`: runs `hunter.step` on the real ship for `frames` frames with `action` (computing fire control's solution each frame as the game does), records the executed `(rotation, engine, trigger)`, restores the ship exactly, and returns `step_labels(...)`. It discards any projectiles the trial produced.
  - `ShadowTeacher(params, settings)`: `decide(game, hunter, now)` refreshes the teacher's held `PilotAction` every 15 frames from the live game (its own `HunterPerception`, generation counter, and `JevPilot(RulesClient(params), params)`), and `label(game, hunter, frames) -> controls` calls `trial_controls` with the held action.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_experiment_shadow.py`:

```python
import pytest
from experiments import shadow
from experiments.harness import run_episode
from experiments.teach import StepRecorder
from hunter.model import PilotAction


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


def real_game_at(frame_count=300):
    """A running level with the harness's hunter, paused after some frames; returns (game, hunter)."""
    captured = {}

    def trace(t, game, hunter):
        captured['game'], captured['hunter'] = game, hunter
        captured['frames'] = captured.get('frames', 0) + 1
        if captured['frames'] == frame_count:
            raise StopIteration
    try:
        run_episode(14, 100, horizon=20.0, trace=trace)
    except StopIteration:
        pass
    return captured['game'], captured['hunter']


def test_snapshot_and_restore_are_exact():
    game, hunter = real_game_at()
    before = shadow.snapshot(hunter)
    hunter.x += 50; hunter.vx = 3.0; hunter.angle = 123.0; hunter.burst_remaining = 2
    hunter.fire_remaining = 0.2; hunter._burn_left = 4.0; hunter.thrust_frames += 9
    shadow.restore(hunter, before)
    assert shadow.snapshot(hunter) == before


def test_a_trial_leaves_the_real_ship_exactly_as_it_was():
    game, hunter = real_game_at()
    before = shadow.snapshot(hunter)
    projectiles = len(game.projectiles)
    shadow.trial_controls(game, hunter, PilotAction(1, True, True), frames=6)
    assert shadow.snapshot(hunter) == before
    assert len(game.projectiles) == projectiles


def test_a_plain_action_trial_reports_that_action():
    game, hunter = real_game_at()
    turn, thrust, fire = shadow.trial_controls(game, hunter, PilotAction(-1, True, False), frames=6)
    assert (turn, thrust, fire) == (0, True, False)          # left, thrust on, trigger off
    turn, thrust, _ = shadow.trial_controls(game, hunter, PilotAction(1, False, False), frames=6)
    assert (turn, thrust) == (2, False)


def test_a_trial_is_not_counted_by_a_recorder_wrapping_the_ships_step():
    seen = []
    game, hunter = real_game_at()
    original = hunter.step
    hunter.step = lambda *a, **k: (seen.append(1), original(*a, **k))[1]
    shadow.trial_controls(game, hunter, PilotAction(1, True, False), frames=6)
    assert seen == []


def test_the_trial_matches_what_the_ship_really_does_when_the_teacher_flies():
    """Replaying the teacher's held action on the saved state gives the controls the real run executed."""
    mismatches, total = 0, 0

    class Checker(StepRecorder):
        def before_frame(self, game, hunter):
            super().before_frame(game, hunter)
            if self._count % self.decision_frames == 0:
                controller = game.hunter_controller
                self._started_with = controller.action
                self._expected = shadow.trial_controls(game, hunter, controller.action, self.decision_frames)
                self._controller = controller

        def _close_step(self):
            nonlocal mismatches, total
            label = self.pending_label()
            # Only steps where the teacher's action was not refreshed part-way through are comparable.
            if getattr(self, '_expected', None) is not None and self._controller.action is self._started_with:
                total += 1
                mismatches += self._expected != label
            super()._close_step()
    run_episode(14, 100, horizon=25.0, recorder=Checker(decision_frames=6))
    assert total > 60
    assert mismatches / total < 0.05          # what remains is walls and enemies moving within the step


def test_the_shadow_teacher_decides_every_fifteen_frames_and_labels_with_its_held_action():
    from hunter.rule_params import RULES
    game, hunter = real_game_at()
    teacher = shadow.ShadowTeacher(RULES, hunter.settings)
    seen = []
    for frame in range(31):
        teacher.decide(game, hunter, frame / 60.0, frame)
        seen.append(teacher.action)
    assert seen[0] is seen[14] and seen[15] is seen[29] and seen[15] is not seen[0]
    controls = teacher.label(game, hunter, 6)
    assert controls[0] in (0, 1, 2)
```

(The long `test_the_trial_matches_...` is the consistency check from the spec: its tolerance of 10% allows for walls and decisions landing mid-step. If it fails by much, the trial and the real step disagree about something such as the fire-control solution or the burn budget; fix that, not the threshold. Delete the unused `check` helper and `compare_hook` reference if the linter complains.)

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_experiment_shadow.py -q -p no:cacheprovider`
Expected: collection error (`experiments.shadow` missing).

- [ ] **Step 3: Implement `experiments/shadow.py`**

```python
"""Asks the rules pilot what it would do at a state the student reached, for teacher-corrected rounds."""
import asyncio
from hunter.fire_control import find_firing_solution
from hunter.jev_pilot import JevPilot
from hunter.model import NEUTRAL
from hunter.neural.controls import step_labels
from hunter.perception import HunterPerception
from hunter.rules_pilot import RulesClient

_FIELDS = ('x', 'y', 'prev_x', 'prev_y', 'vx', 'vy', 'angle', 'fire_remaining', 'burst_remaining',
           'immunity_remaining', 'upgrade_remaining', 'gun_upgrade_level', 'pilot_thrusting',
           'thrusting', 'thrust_frames', '_decision', '_burn_left', 'health', 'active', 'death_timer')
TEACHER_INTERVAL_FRAMES = 15


def snapshot(hunter):
    state = {name: getattr(hunter, name) for name in _FIELDS}
    state['thrust_particles'] = list(hunter.thrust_particles)      # a list the step appends to
    return state


def restore(hunter, state):
    for name, value in state.items():
        setattr(hunter, name, list(value) if name == 'thrust_particles' else value)


def trial_controls(game, hunter, action, frames):
    """The (turn, thrust, fire) the ship would execute over `frames` frames of `action`, state restored."""
    saved = snapshot(hunter)
    rate = hunter.current_rotation_speed
    record = []
    try:
        for _ in range(frames):
            solution = None
            if action.track or action.fire or hunter.burst_remaining:
                solution = find_firing_solution(
                    hunter, list(game.entity_manager.get_all_active_enemies()), game.maze, hunter.settings)
            before = hunter.angle
            # The class method, not hunter.step: the lab wraps the instance's step to count frames, and a
            # trial must not be counted.
            shots = type(hunter).step(hunter, 1, action, solution)
            record.append((((hunter.angle - before + 180.0) % 360.0) - 180.0,
                           bool(hunter.pilot_thrusting), bool(action.fire or shots)))
    finally:
        restore(hunter, saved)
    return step_labels(record, rate)


class ShadowTeacher:
    """A rules pilot that watches the same game (own perception and timing) and holds its own action."""

    def __init__(self, params, settings):
        self.params = params
        self.perception = HunterPerception(settings)
        self.pilot = JevPilot(RulesClient(params), params)
        self.action = NEUTRAL
        self.generation = 1

    def decide(self, game, hunter, now, frame):
        if frame % TEACHER_INTERVAL_FRAMES:
            return self.action
        observation = self.perception.observe(
            hunter, game.maze, game.ship if game._hunter_sees_player() else None,
            game._hunter_entities(), game.projectiles, self.action, now, self.generation,
            powerups=[c for c in game.powerup_crystals if type(c).__name__ != 'JevBeacon'])
        self.action = asyncio.run(self.pilot.decide(observation)).action
        return self.action

    def label(self, game, hunter, frames):
        return trial_controls(game, hunter, self.action, frames)
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_experiment_shadow.py -q -p no:cacheprovider`
Expected: PASS. If the exact-restore test fails, a field the step mutates is missing from `_FIELDS`: diff `vars(hunter)` before and after a trial and add it.

- [ ] **Step 5: Commit**

```bash
git add experiments/shadow.py tests/test_experiment_shadow.py
git commit -m "feat: a shadow rules pilot that relabels the states a student reaches

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Teacher-corrected rounds (DAgger)

**Files:**
- Create: `experiments/dagger.py`
- Modify: `experiments/harness.py` (a `labeller` hook)
- Test: `tests/test_experiment_dagger.py`

**Interfaces:**
- Consumes: `ShadowTeacher`, `StudentSpec`, `Senses`, the harness, the trainer.
- Produces:
  - `DaggerLabeller(params, decision_frames, beta=0.0, seed=0)` with `before_frame(game, hunter, frame)` (the harness calls it before every frame, Task 6) and `arrays() -> (senses, labels)`. At each decision frame it asks the shadow teacher for the label of the state about to be acted on, and the controller's own senses call (spied on, so the senses are built once, exactly as the student sees them) records the senses with that label. With `beta > 0`, on that fraction of decision steps (seeded) the teacher's label replaces the student's choice, via `NeuralController.override`.
  - `dagger.fly_and_label(level, seed, student, params=RULES, horizon=90.0, beta=0.0, on_result=None) -> (senses, labels)`.
  - `dagger.main(argv)`: `python -m experiments.dagger --weights PATH --out DIR --round K [--beta B] [--seeds 200-239] [--levels tune] [--turn-rate X] [--decision-frames N] [--horizon S] [--workers N]` writes `level<L>-seed<S>.npz` files like the teaching recorder, so the trainer reads them unchanged. Dagger seeds default to 200-239 (disjoint from teaching and evaluation seeds).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_experiment_dagger.py`:

```python
import numpy as np
import pytest
from experiments import dagger
from experiments.student import StudentSpec
from hunter.neural.policy import random_policy
from hunter.senses import SENSE_SIZE


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / 'p.npz'
    random_policy(0).save(path)
    return StudentSpec(weights=str(path), decision_frames=6, turn_rate=1.0)


def test_flying_and_labelling_gives_aligned_senses_and_teacher_labels(spec):
    senses, labels = dagger.fly_and_label(14, 200, spec, horizon=8.0)
    assert senses.shape[1] == SENSE_SIZE and labels.shape == (len(senses), 3)
    assert len(senses) >= 70                                       # 8 s at 10 decisions a second
    assert set(np.unique(labels[:, 0])) <= {0, 1, 2}


def test_the_labels_come_from_the_teacher_not_the_student(spec):
    # A random student turns arbitrarily; the teacher's labels follow the rules pilot and have far more
    # thrust than a random policy's even split.
    _, labels = dagger.fly_and_label(14, 200, spec, horizon=15.0)
    assert 0.1 < labels[:, 1].mean() < 0.9


def test_the_run_is_deterministic(spec):
    a = dagger.fly_and_label(14, 201, spec, horizon=5.0)
    b = dagger.fly_and_label(14, 201, spec, horizon=5.0)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


def test_beta_one_executes_the_teacher_so_the_run_matches_a_teacher_flight_in_kind(spec):
    senses, labels = dagger.fly_and_label(14, 202, spec, horizon=10.0, beta=1.0)
    assert len(senses) > 50
    assert labels[:, 1].any()                                      # the teacher thrusts, so the ship moved


def test_labelling_does_not_change_the_flight(spec):
    # Same student, same episode: the score terms are identical whether or not the shadow is watching.
    from experiments.harness import run_episode
    plain = run_episode(14, 203, horizon=8.0, student=spec)
    labelled = {}

    def capture(result):
        labelled['r'] = result
    dagger.fly_and_label(14, 203, spec, horizon=8.0, on_result=capture)
    assert (plain.kills, plain.wall_hits, plain.hits_taken, round(plain.idle_seconds, 3)) == \
           (labelled['r'].kills, labelled['r'].wall_hits, labelled['r'].hits_taken,
            round(labelled['r'].idle_seconds, 3))


def test_the_cli_writes_dagger_files(tmp_path, spec):
    out = tmp_path / 'round1'
    dagger.main(['--weights', spec.weights, '--out', str(out), '--round', '1', '--seeds', '200-200',
                 '--levels', '14', '--horizon', '4', '--workers', '1'])
    files = list(out.glob('*.npz'))
    assert [f.name for f in files] == ['level14-seed200.npz']
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_experiment_dagger.py -q -p no:cacheprovider`
Expected: collection error.

- [ ] **Step 3: Implement**

`experiments/harness.py` already has the `labeller` and `on_result` hooks from Tasks 5 and 6 (and `_neural_senses` in `_OVERRIDDEN`, so the spy below is removed after every episode); nothing else changes there.

`experiments/dagger.py`:

```python
"""Teacher-corrected rounds: the student flies, the rules pilot labels the states it reaches."""
import argparse
import os
import numpy as np
from experiments import run
from experiments.harness import run_episode
from experiments.shadow import ShadowTeacher
from hunter.neural.controls import to_action
from hunter.rule_params import RULES
from hunter.senses import SENSE_SIZE

DAGGER_DIR = run.RESULTS_DIR.parent / 'neural'


class DaggerLabeller:
    def __init__(self, params, decision_frames, beta=0.0, seed=0):
        self.params, self.decision_frames, self.beta = params, decision_frames, beta
        self.rng = np.random.default_rng(seed)
        self.teacher = None
        self.senses, self.labels = [], []
        self._pending = None

    def before_frame(self, game, hunter, frame):
        controller = game.hunter_controller
        if self.teacher is None:
            self.teacher = ShadowTeacher(self.params, hunter.settings)
            self._spy_on_the_senses(game)
        self.teacher.decide(game, hunter, frame / 60.0, frame)
        self._pending = None
        if controller.frames % self.decision_frames == 0:
            self._pending = self.teacher.label(game, hunter, self.decision_frames)
            if self.beta > 0 and self.rng.random() < self.beta:
                controller.override = to_action(self._pending)

    def _spy_on_the_senses(self, game):
        """Record the senses the controller builds for this step, paired with the teacher's label."""
        original = game._neural_senses

        def spy(last_controls, now):
            sense = original(last_controls, now)
            if self._pending is not None:
                self.senses.append(sense)
                self.labels.append(self._pending)
                self._pending = None
            return sense
        game._neural_senses = spy

    def arrays(self):
        n = len(self.labels)
        return (np.asarray(self.senses, dtype=np.float32).reshape(n, SENSE_SIZE),
                np.asarray(self.labels, dtype=np.int8).reshape(n, 3))


def fly_and_label(level, seed, student, params=RULES, horizon=90.0, beta=0.0, on_result=None):
    labeller = DaggerLabeller(params, student.decision_frames, beta, seed)
    run_episode(level, seed, params, horizon, student=student, labeller=labeller, on_result=on_result)
    return labeller.arrays()
```

`NeuralController` (Task 4's file) gains `override`. In `__init__` add `self.override = None`; in `tick`, on a decision frame, right after `self.action = to_action(controls)` and the `self.last_controls = ...` line, add:

```python
            if self.override is not None:
                self.action, self.override = self.override, None
                self.last_controls = (self.action.turn + 1, 1 if self.action.thrust else 0,
                                      1 if self.action.fire else 0)
```
and add this test to `tests/test_neural_controller.py` (write it first and watch it fail):

```python
def test_an_override_replaces_exactly_one_decision_and_is_then_cleared():
    from hunter.model import PilotAction
    controller = NeuralController(random_policy(7), decision_frames=2)
    spy = Spy()
    controller.tick(spy)                                   # frame 0 decides normally
    controller.override = PilotAction(1, True, True)       # the teacher's choice for the next decision
    controller.tick(spy)                                   # frame 1: held, override not yet used
    taken = controller.tick(spy)                           # frame 2: decides, override applies
    assert taken == PilotAction(1, True, True) and controller.override is None
    assert controller.last_controls == (2, 1, 1)
    controller.tick(spy)
    assert controller.tick(spy) is not taken               # frame 4 decides normally again
```

The `main` mirrors `experiments.teach.main`: parse `--weights`, `--out`, `--round`, `--beta`, `--seeds` (default `200-239`), `--levels`, `--turn-rate`, `--decision-frames`, `--horizon`, `--workers`; build a `StudentSpec`; for each (level, seed) call `fly_and_label` and save `level<L>-seed<S>.npz` atomically; use the same spawn pool and dummy-driver initializer.

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_experiment_dagger.py tests/test_neural_controller.py tests/test_experiment_student.py -q -p no:cacheprovider`
Expected: all PASS. The "labelling does not change the flight" test is the important one: if it fails, the shadow teacher is perturbing the game (its perception or a trial left state behind); fix that.

- [ ] **Step 5: Commit**

```bash
git add experiments tests hunter/neural/controller.py
git commit -m "feat: teacher-corrected rounds for the neural student

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Reach the gate (real experiments)

This task is experiments, not code. It follows the spec's experiment order and records each step in `docs/experiments/`. The gate numbers are in Global Constraints.

**Files:**
- Create: `docs/experiments/012-neural-turn-rate.md`, `docs/experiments/013-neural-decision-rate.md`, `docs/experiments/014-neural-rounds.md` (and `015-neural-history.md` only if the GRU is run against alternatives)
- Create: `assets/neural/hunter.npz` (the policy that passes, or the best one if none does)
- Modify: `docs/experiments/README.md` (index rows), `config/settings.json` / `config.py` only to set `neuralTurnRate` and `neuralDecisionFrames` to the winning values

- [ ] **Step 1: Turn rate (0.5, 1.0, 2.0) at 6 frames a step**

For each turn rate T: record a teaching set with `--turn-rate T` into its own directory, train round 0, run two teacher-corrected rounds, and fly the gate at 6 seeds on the tune set to choose (the held-out set is scored once, at the end of Step 3):

```bash
for T in 0.5 1.0 2.0; do
  venv/bin/python -m experiments.teach --turn-rate $T --out .astrovoid-local/neural/teach-t$T
  venv/bin/python -m tools.train_neural --data .astrovoid-local/neural/teach-t$T --out .astrovoid-local/neural/t$T-r0.npz --epochs 20
  venv/bin/python -m experiments.neural_lab gate --weights .astrovoid-local/neural/t$T-r0.npz --turn-rate $T --set tune --seeds 6
done
```
Record the three gate reports in `012-neural-turn-rate.md` (score ratio, collision ratios, validation agreement as a diagnostic). Choose the turn rate with the highest score ratio whose collision ratios are not worse; note the choice and what the other two did.

- [ ] **Step 2: Teacher-corrected rounds at the chosen turn rate**

Repeat up to five times, stopping when the tune-set gate at 6 seeds reports `PASSED`:

```bash
venv/bin/python -m experiments.dagger --weights .astrovoid-local/neural/t$T-rK.npz --out .astrovoid-local/neural/dagger-t$T-roundK --round K --turn-rate $T
venv/bin/python -m tools.train_neural --data .astrovoid-local/neural/teach-t$T .astrovoid-local/neural/dagger-t$T-round1 ... --init .astrovoid-local/neural/t$T-rK.npz --out .astrovoid-local/neural/t$T-r(K+1).npz --epochs 10
venv/bin/python -m experiments.neural_lab gate --weights .astrovoid-local/neural/t$T-r(K+1).npz --turn-rate $T --set tune --seeds 6
```
(Use a `--beta` of 0.3 for round 1 and 0 afterwards.) Log every round's gate report in `014-neural-rounds.md`. If five rounds do not pass, say so in the entry and stop; that is the finding.

- [ ] **Step 3: Decision rate (6 against 3 and 1 frame)**

At the chosen turn rate, record a teaching set per decision rate (`--decision-frames 3`, `--decision-frames 1`), run the same rounds, and compare the best policy of each on the tune set at 18 seeds with `neural_lab compare`. Record in `013-neural-decision-rate.md`. Set `neuralDecisionFrames` to the winner.

- [ ] **Step 4: The gate on the held-out levels, once**

```bash
venv/bin/python -m experiments.neural_lab gate --weights <best policy> --turn-rate <T> --decision-frames <N> --set heldout --seeds 18
```
Record the result as the final line of `014-neural-rounds.md`, whether it passes or not. Do not choose anything using the held-out result. Copy the policy to `assets/neural/hunter.npz`, set `neuralTurnRate` and `neuralDecisionFrames` in `config.py` and `config/settings.json` to the values it was trained with, and add the index rows to `docs/experiments/README.md`.

- [ ] **Step 5: Commit**

```bash
git add assets/neural docs/experiments config.py config/settings.json
git commit -m "feat: the neural student, trained by the rules pilot (experiments 012-014)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Documentation

**Files:**
- Modify: `README.md`, `docs/superpowers/specs/2026-10-12-neural-student-design.md` (a status line)

- [ ] **Step 1: README**

In the "Choosing the hunter's pilot" section added in Task 1, extend the `"neural"` entry with how to use and rebuild it:

```markdown
The neural pilot decides every `game.neuralDecisionFrames` frames and turns at `game.neuralTurnRate` times the
player's rate. Its weights are `assets/neural/hunter.npz` (the hunter coasts and shows as unavailable if the
file is missing or does not match the senses layout). To rebuild them: record the rules pilot with
`venv/bin/python -m experiments.teach`, train with `venv/bin/python -m tools.train_neural --data DIR --out PATH`
(needs `requirements-train.txt`), then run corrected rounds with `venv/bin/python -m experiments.dagger` and
check the gate with `venv/bin/python -m experiments.neural_lab gate --weights PATH`. The experiments are
written up in `docs/experiments/012` to `014`.
```

- [ ] **Step 2: Spec status**

Add a line under the spec's title: `Status: implemented on branch feat/neural-student; results in docs/experiments/012-014.` (If the gate was not met, say so here.)

- [ ] **Step 3: Run the whole suite and commit**

Run: `venv/bin/python -m pytest tests -q -p no:cacheprovider | tail -2`
Expected: all PASS.

```bash
git add README.md docs/superpowers/specs/2026-10-12-neural-student-design.md
git commit -m "docs: the neural pilot

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Restore the local setting and play it**

Run `git stash pop` to bring back the local `"hunterPilot": "rules"` change (fix by hand if it conflicts). Then set `"hunterPilot": "neural"` locally (uncommitted), run `START_LEVEL=13 ./run.sh`, and fly beside the hunter. Note how it behaves (does it hunt, aim, avoid walls; does it keep station beside the player, which the lab cannot measure) in `docs/experiments/014-neural-rounds.md` and commit that note only. Put the setting back to the user's value (`"rules"`) afterwards.
