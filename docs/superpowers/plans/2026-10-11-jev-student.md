# Jev Student Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record Jev's pilot decisions, train a small numpy-runnable network on them, and let the hunter fly with that network (the "student") when Jev is unavailable or not wanted.

**Architecture:** Everything attaches at the client interface `JevPilot.decide` already calls, `client.system_one(state=..., questions=...)`. A `RecordingJevClient` wraps the real Jev client and logs decisions as JSONL. A `JevStudentClient` answers the same call from an MLP. `create_client()` chooses between them from two settings. `JevPilot`, `PilotWorker` and `HunterController` do not change.

**Tech Stack:** Python 3.10 (`venv/bin/python`), numpy at runtime, pytest. Training only: torch and scikit-learn in `requirements-train.txt`.

**Spec:** `docs/superpowers/specs/2026-10-11-jev-student-design.md`

## Global Constraints

- Run everything with `venv/bin/python` (Python 3.10). Run tests as `venv/bin/python -m pytest <path> -v`.
- The game runtime must import numpy only. torch and scikit-learn are imported solely under `tools/` and in tests guarded by `pytest.importorskip`.
- Do not modify `hunter/worker.py`, `hunter/controller.py`, or the `JevPilot` class. `hunter/jev_pilot.py` changes only in `create_client()` (and a private helper split out of it).
- Default behaviour is unchanged: `game.hunterPilot` defaults to `"jev"` and `game.recordPilotDecisions` to `false`.
- Student pilot values are exactly `"jev"`, `"student"`, `"auto"`. Anything else raises `PilotUnavailable('invalid_configuration')`.
- Recorded decisions go to `.astrovoid-local/decisions/<run_id>.jsonl` (already gitignored via `/.astrovoid-local/`). Never write credentials to a record. Recording only wraps a Jev client and is skipped in frozen builds (`sys.frozen`).
- The model file is `assets/student/jev_student.npz`, resolved with `utils.resource_path.resource_path`.
- No on-screen pilot label. The project owner removed status text near the hunter on purpose (saved feedback); do not add any.
- Code style matches the surrounding `hunter/` code: single-quoted strings, 4-space indent, short docstrings, no type-annotation churn.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

Failure modes the spec implies that no one task would otherwise test, most likely first. Each has a test in the task that owns the code.

1. A hunter with nothing in sight: every optional block `None`, every list empty. Expected: `encode` returns a finite vector of the right length. (Task 1)
2. More than three visible enemies or hostile projectiles. Expected: extras are ignored and the vector length never changes. (Task 1)
3. A stale, truncated or foreign model file (encoder edited since training, rubric edited, file corrupt or missing). Expected: `PilotUnavailable('invalid_model')` or `('missing_model')`, never a crash or silent nonsense. (Task 2)
4. Disk and serialisation trouble while recording: unwritable directory, a state that cannot be turned into JSON, a full queue. Expected: the Jev decision still returns unchanged and nothing raises. (Task 3)
5. A Jev answer with no `probabilities` (the existing fake clients and any older SDK). Expected: recorded as `null`, and the trainer falls back to a one-hot target. (Tasks 3 and 5)

---

### Task 1: Encoder

**Files:**
- Create: `hunter/student/__init__.py` (empty)
- Create: `hunter/student/encoder.py`
- Test: `tests/test_student_encoder.py`

**Interfaces:**
- Consumes: the dict returned by `hunter.pilot_sensors.pilot_state` (keys such as `motion.brake`, `engage`, `follow_player`, `visible_contacts[*].aim`).
- Produces: `FEATURE_NAMES: tuple[str, ...]` and `encode(state: dict) -> numpy.ndarray` (float32, shape `(len(FEATURE_NAMES),)`). `encode({})` must work and return all zeros.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_student_encoder.py`:

```python
import json
import math
import numpy as np
import pytest
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from hunter.model import NEUTRAL
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from hunter.student.encoder import FEATURE_NAMES, encode
from tests.test_hunter_perception import maze


def real_state(heading=10, enemies=()):
    ship = HunterShip((150, 150))
    ship.vx, ship.vy, ship.angle = 3, 1, heading
    obs = HunterPerception().observe(ship, maze(), None, list(enemies), [], NEUTRAL, 0, 1)
    return pilot_state(json.loads(obs.state_json))


def feature(vector, name):
    return float(vector[FEATURE_NAMES.index(name)])


def test_feature_names_are_unique_and_match_vector_length():
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)
    assert encode({}).shape == (len(FEATURE_NAMES),)


def test_empty_state_encodes_to_zeros():
    vector = encode({})
    assert vector.dtype == np.float32
    assert not vector.any()


def test_nothing_in_sight_is_finite_with_every_block_absent():
    state = {'engage': None, 'collect_powerup': None, 'follow_player': None,
             'wall_follow': None, 'visible_contacts': [], 'remembered_contacts': [],
             'hostile_projectiles': [], 'motion': {'brake': {}}, 'space': {}}
    vector = encode(state)
    assert np.isfinite(vector).all()
    assert feature(vector, 'engage.present') == 0
    assert feature(vector, 'enemies.visible') == 0
    assert feature(vector, 'enemy0.present') == 0


def test_real_pilot_state_encodes_finite_with_enemy_aim():
    state = real_state(enemies=[Enemy((250, 150), 'patrol', 1)])
    vector = encode(state)
    assert vector.shape == (len(FEATURE_NAMES),)
    assert np.isfinite(vector).all()
    assert feature(vector, 'enemies.any_aim') == 1
    assert feature(vector, 'enemy0.has_aim') == 1
    assert feature(vector, 'enemy0.distance') == pytest.approx(100)


def test_extra_enemies_and_projectiles_are_ignored():
    def enemy(i):
        return {'allegiance': 'enemy', 'distance_metres': 50 + i, 'aim': None,
                'degrees_off_nose_at_next_decision': 0.0}
    def shot(i):
        return {'allegiance': 'enemy', 'distance_metres': 10 * (10 - i), 'degrees_off_nose': 5.0}
    few = encode({'visible_contacts': [enemy(i) for i in range(3)],
                  'hostile_projectiles': [shot(i) for i in range(3)]})
    many = encode({'visible_contacts': [enemy(i) for i in range(9)],
                   'hostile_projectiles': [shot(i) for i in range(9)]})
    assert few.shape == many.shape
    # Nine shots sit at 100, 90, ... 20 metres: the nearest slot holds the 20, whatever the order.
    assert feature(many, 'projectile0.distance') == 20
    assert feature(many, 'projectile2.distance') == 40
    assert feature(many, 'projectiles.visible') == 9


def test_angle_features_are_linear_for_thresholds_and_continuous_across_180():
    plus = encode({'follow_player': {'degrees_off_nose_at_next_decision': 179.0}})
    minus = encode({'follow_player': {'degrees_off_nose_at_next_decision': -179.0}})
    assert feature(plus, 'follow.off_nose_next.linear') == pytest.approx(179 / 180)
    assert feature(minus, 'follow.off_nose_next.linear') == pytest.approx(-179 / 180)
    # Opposite on the linear feature, neighbours on cos/sin.
    assert feature(plus, 'follow.off_nose_next.cos') == pytest.approx(
        feature(minus, 'follow.off_nose_next.cos'))
    assert feature(plus, 'follow.off_nose_next.sin') == pytest.approx(
        -feature(minus, 'follow.off_nose_next.sin'))
    assert abs(feature(plus, 'follow.off_nose_next.sin')) == pytest.approx(
        math.sin(math.radians(1)), abs=1e-6)


def test_enums_are_one_hot_and_unknown_values_are_all_zero():
    state = {'motion': {'brake': {'speed_state': 'too_fast', 'thrust_effect': 'slows'}}}
    vector = encode(state)
    assert feature(vector, 'brake.speed_state.too_fast') == 1
    assert feature(vector, 'brake.speed_state.slow') == 0
    assert feature(vector, 'brake.thrust_effect.slows') == 1
    odd = encode({'motion': {'brake': {'speed_state': 'warp'}}})
    assert not any(feature(odd, f'brake.speed_state.{s}') for s in ('slow', 'cruising', 'too_fast'))
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_student_encoder.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'hunter.student'`.

- [ ] **Step 3: Write the implementation**

Create empty `hunter/student/__init__.py`, then `hunter/student/encoder.py`:

```python
"""Turns a pilot_state dict into the student's fixed-length feature vector."""
import math
import numpy as np

SPACE_NAMES = ('ahead', 'ahead_left', 'left', 'behind_left', 'behind', 'behind_right',
               'right', 'ahead_right')
TURN_DIRECTIONS = ('left', 'none', 'right', 'track', 'course')
SPEED_STATES = ('slow', 'cruising', 'too_fast')
THRUST_EFFECTS = ('slows', 'sideways', 'speeds_up')
RANGE_STATES = ('too_close', 'in_range', 'far')
ENEMY_SLOTS = 3
PROJECTILE_SLOTS = 3


class _Features:
    """Collects (name, value) pairs; names and values come from the same code path."""

    def __init__(self):
        self.items = []

    def number(self, name, value):
        self.items.append((name, 0.0 if value is None else float(value)))

    def flag(self, name, value):
        self.items.append((name, 1.0 if value else 0.0))

    def angle(self, name, degrees):
        # Linear for the +-20 degree thresholds, sin/cos so +-180 are neighbours.
        if degrees is None:
            linear = sin = cos = 0.0
        else:
            linear = max(-1.0, min(1.0, degrees / 180.0))
            sin, cos = math.sin(math.radians(degrees)), math.cos(math.radians(degrees))
        self.items.append((f'{name}.linear', linear))
        self.items.append((f'{name}.sin', sin))
        self.items.append((f'{name}.cos', cos))

    def onehot(self, name, value, options):
        for option in options:
            self.flag(f'{name}.{option}', value == option)


def _course(f, prefix, course):
    f.flag(f'{prefix}.present', course is not None)
    course = course or {}
    f.flag(f'{prefix}.burn_needed', course.get('burn_needed'))
    f.angle(f'{prefix}.burn_off_nose', course.get('burn_degrees_off_nose'))
    f.angle(f'{prefix}.burn_off_nose_next', course.get('burn_degrees_off_nose_at_next_decision'))
    f.number(f'{prefix}.burn_seconds', course.get('burn_seconds'))
    f.number(f'{prefix}.speed_after', course.get('speed_after_metres_per_second'))
    f.number(f'{prefix}.speed_limit', course.get('speed_limit_metres_per_second'))


def _features(state):
    f = _Features()
    motion = state.get('motion') or {}
    turning = state.get('turning') or {}
    f.number('speed', state.get('speed_metres_per_second'))
    f.number('speed_limit', state.get('speed_limit_metres_per_second'))
    f.number('rotation_speed', state.get('rotation_speed_degrees_per_second'))
    f.number('radius', state.get('radius_metres'))
    f.number('sensor_range', state.get('sensor_range_metres'))
    f.number('health', state.get('health'))
    f.number('turn_step', turning.get('degrees_per_decision'))
    f.onehot('turning', turning.get('direction'), TURN_DIRECTIONS)
    f.number('forward_speed', motion.get('forward_speed_metres_per_second'))
    f.number('rightward_speed', motion.get('rightward_speed_metres_per_second'))
    f.flag('wall_on_course', motion.get('wall_clearance_metres') is not None)
    f.number('wall_clearance', motion.get('wall_clearance_metres'))
    f.number('seconds_to_wall_impact', motion.get('seconds_to_wall_impact'))
    space = state.get('space') or {}
    for name in SPACE_NAMES:
        f.number(f'space.{name}', (space.get(name) or {}).get('clearance_metres'))

    brake = motion.get('brake') or {}
    f.onehot('brake.speed_state', brake.get('speed_state'), SPEED_STATES)
    f.onehot('brake.thrust_effect', brake.get('thrust_effect'), THRUST_EFFECTS)
    f.number('brake.safe_speed', brake.get('safe_speed_metres_per_second'))
    f.number('brake.stopping_distance', brake.get('stopping_distance_metres'))
    f.angle('brake.retrograde', brake.get('retrograde_degrees_off_nose'))
    f.angle('brake.retrograde_next', brake.get('retrograde_degrees_off_nose_at_next_decision'))
    f.number('brake.burn_seconds', brake.get('burn_seconds'))

    engage = state.get('engage')
    f.flag('engage.present', engage is not None)
    engage = engage or {}
    f.onehot('engage.range_state', engage.get('range_state'), RANGE_STATES)
    f.number('engage.distance', engage.get('distance_metres'))
    f.number('engage.standoff', engage.get('standoff_metres'))
    f.number('engage.closing_speed', engage.get('closing_speed_metres_per_second'))
    f.number('engage.target_closing_speed', engage.get('target_closing_speed_metres_per_second'))
    f.flag('engage.holding_still', engage.get('holding_still'))
    f.flag('engage.burn_needed', engage.get('burn_needed'))
    f.number('engage.burn_seconds', engage.get('burn_seconds'))

    powerup = state.get('collect_powerup')
    f.flag('powerup.present', powerup is not None)
    powerup = powerup or {}
    f.angle('powerup.off_nose_next', powerup.get('degrees_off_nose_at_next_decision'))
    f.number('powerup.distance', powerup.get('distance_metres'))
    _course(f, 'powerup.course', powerup.get('course'))

    follow = state.get('follow_player')
    f.flag('follow.present', follow is not None)
    follow = follow or {}
    f.angle('follow.off_nose_next', follow.get('degrees_off_nose_at_next_decision'))
    f.number('follow.waypoint_distance', follow.get('waypoint_distance_metres'))
    f.number('follow.route_distance', follow.get('route_distance_metres'))
    f.flag('follow.player_visible', follow.get('player_visible'))
    f.flag('follow.alongside', follow.get('alongside'))
    _course(f, 'follow.course', follow.get('course'))

    wall = state.get('wall_follow')
    f.flag('wall_follow.present', wall is not None)
    wall = wall or {}
    f.angle('wall_follow.off_nose_next', wall.get('degrees_off_nose_at_next_decision'))
    f.flag('wall_follow.wall_in_sight', wall.get('wall_distance_metres') is not None)
    f.number('wall_follow.wall_distance', wall.get('wall_distance_metres'))
    _course(f, 'wall_follow.course', wall.get('course'))

    # Enemies keep the order they arrive in: the engage reading takes the first one with an aim.
    enemies = [c for c in state.get('visible_contacts') or [] if c.get('allegiance') == 'enemy']
    f.number('enemies.visible', len(enemies))
    f.flag('enemies.any_aim', any(c.get('aim') for c in enemies))
    f.number('enemies.remembered', len(state.get('remembered_contacts') or []))
    for slot in range(ENEMY_SLOTS):
        enemy = enemies[slot] if slot < len(enemies) else None
        aim = (enemy or {}).get('aim')
        p = f'enemy{slot}'
        f.flag(f'{p}.present', enemy is not None)
        f.flag(f'{p}.has_aim', aim is not None)
        f.angle(f'{p}.off_nose_next', (enemy or {}).get('degrees_off_nose_at_next_decision'))
        f.number(f'{p}.distance', (enemy or {}).get('distance_metres'))
        aim = aim or {}
        f.angle(f'{p}.lead', aim.get('lead_degrees_off_nose'))
        f.angle(f'{p}.lead_next', aim.get('lead_degrees_off_nose_at_next_decision'))
        f.number(f'{p}.seconds_to_hit', aim.get('seconds_to_hit'))
        f.flag(f'{p}.on_target', aim.get('on_target'))
        f.number(f'{p}.miss_distance', aim.get('miss_distance_metres'))

    projectiles = sorted(state.get('hostile_projectiles') or [],
                         key=lambda c: c.get('distance_metres', 0))
    f.number('projectiles.visible', len(projectiles))
    for slot in range(PROJECTILE_SLOTS):
        shot = projectiles[slot] if slot < len(projectiles) else None
        p = f'projectile{slot}'
        f.flag(f'{p}.present', shot is not None)
        f.angle(f'{p}.off_nose', (shot or {}).get('degrees_off_nose'))
        f.number(f'{p}.distance', (shot or {}).get('distance_metres'))
    return f.items


FEATURE_NAMES = tuple(name for name, _ in _features({}))


def encode(state):
    """The feature vector for one pilot state, in FEATURE_NAMES order."""
    return np.array([value for _, value in _features(state)], dtype=np.float32)
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_student_encoder.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add hunter/student/__init__.py hunter/student/encoder.py tests/test_student_encoder.py
git commit -m "feat: encode a pilot state as a fixed-length feature vector

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Student model and client

**Files:**
- Create: `hunter/student/network.py`
- Create: `hunter/student/client.py`
- Test: `tests/test_student_client.py`

**Interfaces:**
- Consumes: `FEATURE_NAMES`, `encode` (Task 1); `PILOT_QUESTIONS`, `PilotUnavailable`, `JevPilot` from `hunter.jev_pilot`; `utils.resource_path.resource_path`.
- Produces:
  - `network.HEADS: dict[str, tuple[str, ...]]` — head name to choice labels, from `PILOT_QUESTIONS[name]['criteria']` key order.
  - `network.InvalidModel(Exception)`.
  - `network.StudentModel(mean, scale, layers, heads)` frozen dataclass: `predict(features) -> {head: {choice: probability}}`, `save(path, metrics=None)`, classmethod `load(path)` (raises `InvalidModel`).
  - `client.JevStudentClient(model)` with `async system_one(*, state, questions=None, **_)` and `async aclose()`.
  - `client.MODEL_PATH` (a `resource_path(...)` string) and `client.load_student_client(path=None) -> JevStudentClient` (raises `PilotUnavailable('missing_model'|'invalid_model')`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_student_client.py`:

```python
import asyncio
import json
import numpy as np
import pytest
from hunter.jev_pilot import JevPilot, PilotUnavailable, PILOT_QUESTIONS
from hunter.model import PilotObservation
from hunter.student.client import JevStudentClient, load_student_client
from hunter.student.encoder import FEATURE_NAMES
from hunter.student.network import HEADS, InvalidModel, StudentModel


def constant_model(favourites):
    """A model whose heads ignore the input and always favour one choice each."""
    n = len(FEATURE_NAMES)
    heads = {}
    for name, choices in HEADS.items():
        bias = np.zeros(len(choices), dtype=np.float32)
        bias[choices.index(favourites[name])] = 5.0
        heads[name] = (np.zeros((4, len(choices)), dtype=np.float32), bias)
    layers = ((np.zeros((n, 4), dtype=np.float32), np.zeros(4, dtype=np.float32)),)
    return StudentModel(np.zeros(n, dtype=np.float32), np.ones(n, dtype=np.float32), layers, heads)


FAVOURITES = {'turn': 'right', 'thrust': 'coast', 'fire': 'hold'}


def test_heads_follow_the_pilot_questions():
    assert set(HEADS) == {'turn', 'thrust', 'fire'}
    for name, choices in HEADS.items():
        assert choices == tuple(PILOT_QUESTIONS[name]['criteria'])


def test_predict_returns_normalised_probabilities_per_head():
    probs = constant_model(FAVOURITES).predict(np.zeros(len(FEATURE_NAMES)))
    for name, dist in probs.items():
        assert set(dist) == set(HEADS[name])
        assert sum(dist.values()) == pytest.approx(1.0)
        assert max(dist, key=dist.get) == FAVOURITES[name]


def test_student_client_answers_in_the_shape_jev_pilot_reads():
    client = JevStudentClient(constant_model(FAVOURITES))
    result = asyncio.run(client.system_one(state={}, questions=PILOT_QUESTIONS))
    assert result.choices['turn'].choice == 'right'
    assert 0.9 < result.choices['turn'].confidence <= 1.0
    assert result.choices['turn'].probabilities['right'] == result.choices['turn'].confidence


def test_jev_pilot_decides_with_the_student_client():
    client = JevStudentClient(constant_model(FAVOURITES))
    decision = asyncio.run(JevPilot(client).decide(PilotObservation(1, 0, json.dumps({}))))
    assert decision.action.turn == 1
    assert not decision.action.thrust and not decision.action.fire
    assert 0 < decision.confidence <= 1


def test_save_and_load_round_trip(tmp_path):
    model = constant_model(FAVOURITES)
    path = tmp_path / 'm.npz'
    model.save(path, metrics={'joint': 0.9})
    loaded = StudentModel.load(path)
    features = np.arange(len(FEATURE_NAMES), dtype=np.float32)
    assert loaded.predict(features) == model.predict(features)


def test_load_rejects_a_changed_feature_list(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    data = dict(np.load(path))
    data['feature_names'] = np.array(list(FEATURE_NAMES[:-1]) + ['renamed'])
    np.savez(path, **data)
    with pytest.raises(InvalidModel):
        StudentModel.load(path)


def test_load_rejects_changed_heads(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    data = dict(np.load(path))
    data['heads_json'] = np.array("{'turn': ['left']}")
    np.savez(path, **data)
    with pytest.raises(InvalidModel):
        StudentModel.load(path)


def test_load_rejects_a_truncated_file(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    path.write_bytes(path.read_bytes()[:200])
    with pytest.raises(InvalidModel):
        StudentModel.load(path)


def test_load_student_client_reports_missing_and_invalid_models(tmp_path):
    with pytest.raises(PilotUnavailable, match='missing_model'):
        load_student_client(tmp_path / 'absent.npz')
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'not a model')
    with pytest.raises(PilotUnavailable, match='invalid_model'):
        load_student_client(bad)


def test_load_student_client_loads_a_good_model(tmp_path):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    assert isinstance(load_student_client(path), JevStudentClient)
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_student_client.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'hunter.student.client'`.

- [ ] **Step 3: Write the implementation**

Create `hunter/student/network.py`:

```python
"""The trained student: a small MLP with one softmax head per Jev question."""
import ast
from dataclasses import dataclass
import numpy as np
from hunter.jev_pilot import PILOT_QUESTIONS
from hunter.student.encoder import FEATURE_NAMES

# Head and choice order come from the rubric, so a model file records exactly which
# questions and answers its outputs mean.
HEADS = {name: tuple(question['criteria']) for name, question in PILOT_QUESTIONS.items()}


def _heads_text():
    return repr({name: list(choices) for name, choices in HEADS.items()})


class InvalidModel(Exception):
    """The model file cannot drive the current encoder or questions."""


@dataclass(frozen=True)
class StudentModel:
    mean: np.ndarray
    scale: np.ndarray
    layers: tuple  # ((weights, bias), ...): the shared trunk, ReLU after each
    heads: dict  # head name -> (weights, bias)

    def predict(self, features):
        """Per-head probabilities as {head: {choice: probability}}."""
        x = (np.asarray(features, dtype=np.float32) - self.mean) / self.scale
        for weights, bias in self.layers:
            x = np.maximum(0.0, x @ weights + bias)
        out = {}
        for name, choices in HEADS.items():
            weights, bias = self.heads[name]
            logits = x @ weights + bias
            probs = np.exp(logits - logits.max())
            probs /= probs.sum()
            out[name] = dict(zip(choices, (float(p) for p in probs)))
        return out

    def save(self, path, metrics=None):
        arrays = {'mean': self.mean, 'scale': self.scale,
                  'feature_names': np.array(FEATURE_NAMES),
                  'heads_json': np.array(_heads_text()),
                  'trunk_count': np.array(len(self.layers)),
                  'metrics_json': np.array(repr(metrics or {}))}
        for i, (weights, bias) in enumerate(self.layers):
            arrays[f'trunk{i}_w'], arrays[f'trunk{i}_b'] = weights, bias
        for name, (weights, bias) in self.heads.items():
            arrays[f'head_{name}_w'], arrays[f'head_{name}_b'] = weights, bias
        np.savez(path, **arrays)

    @classmethod
    def load(cls, path):
        try:
            data = np.load(path, allow_pickle=False)
            if tuple(str(n) for n in data['feature_names']) != FEATURE_NAMES:
                raise InvalidModel('feature list differs from the encoder')
            if str(data['heads_json']) != _heads_text():
                raise InvalidModel('heads differ from the pilot questions')
            layers = tuple((data[f'trunk{i}_w'], data[f'trunk{i}_b'])
                           for i in range(int(data['trunk_count'])))
            heads = {name: (data[f'head_{name}_w'], data[f'head_{name}_b']) for name in HEADS}
            return cls(data['mean'], data['scale'], layers, heads)
        except InvalidModel:
            raise
        except Exception as exc:
            # Truncated or foreign files fail in many ways (zipfile, pickle, key, value).
            raise InvalidModel(type(exc).__name__) from None

    @staticmethod
    def metrics(path):
        """The metrics recorded at training time, for display."""
        return ast.literal_eval(str(np.load(path, allow_pickle=False)['metrics_json']))
```

Create `hunter/student/client.py`:

```python
"""A drop-in for the Jev client that answers from the trained student."""
from pathlib import Path
from types import SimpleNamespace
from hunter.jev_pilot import PilotUnavailable
from hunter.student.encoder import encode
from hunter.student.network import InvalidModel, StudentModel
from utils.resource_path import resource_path

MODEL_PATH = resource_path('assets/student/jev_student.npz')


class JevStudentClient:
    def __init__(self, model):
        self.model = model

    async def system_one(self, *, state, questions=None, **_):
        answers = {}
        for name, probabilities in self.model.predict(encode(state)).items():
            choice = max(probabilities, key=probabilities.get)
            answers[name] = SimpleNamespace(choice=choice, confidence=probabilities[choice],
                                            probabilities=probabilities)
        return SimpleNamespace(choices=answers)

    async def aclose(self):
        pass


def load_student_client(path=None):
    path = Path(path or MODEL_PATH)
    if not path.is_file():
        raise PilotUnavailable('missing_model')
    try:
        return JevStudentClient(StudentModel.load(path))
    except InvalidModel:
        raise PilotUnavailable('invalid_model') from None
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_student_client.py tests/test_student_encoder.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add hunter/student/network.py hunter/student/client.py tests/test_student_client.py
git commit -m "feat: add the student model and a Jev-compatible client for it

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Recording Jev's decisions

**Files:**
- Create: `hunter/student/recorder.py`
- Test: `tests/test_student_recorder.py`

**Interfaces:**
- Consumes: any client with `async system_one(**kwargs)` returning an object whose `.choices` maps `turn`/`thrust`/`fire` to objects with `.choice`, `.confidence`, and optionally `.probabilities`; optional `async aclose()`.
- Produces:
  - `DecisionSink(path, max_queue=256)`: `write(record: dict)` (never raises, never blocks), `flush()` (wait for queued records), `close()`.
  - `RecordingJevClient(inner, sink, run_id=None, model='jev-latest')`: `async system_one(**kwargs)` returns the inner result unchanged and queues one record on success; `async aclose()` closes the inner client then the sink; attribute `run_id`.
  - `DECISIONS_DIR` (Path, `<project root>/.astrovoid-local/decisions`) and `record_to_disk(inner, model='jev-latest') -> RecordingJevClient` writing `DECISIONS_DIR/<run_id>.jsonl`.
  - Record schema (one JSON object per line): `{'t': float epoch seconds, 'run_id': str, 'model': str, 'latency': float seconds, 'state': dict, 'answers': {'turn'|'thrust'|'fire': {'choice': str, 'confidence': float|None, 'probabilities': dict|None}}}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_student_recorder.py`:

```python
import asyncio
import json
import threading
from types import SimpleNamespace
import pytest
from hunter.student.recorder import DecisionSink, RecordingJevClient


def answer(choice, confidence=.9, probabilities=None):
    reply = SimpleNamespace(choice=choice, confidence=confidence)
    if probabilities is not None:
        reply.probabilities = probabilities
    return reply


class Inner:
    def __init__(self, probabilities=True, fail=False):
        self.probabilities, self.fail, self.closed = probabilities, fail, False

    async def system_one(self, **kwargs):
        if self.fail:
            raise RuntimeError('boom')
        p = (lambda c: {c: .9, 'other': .1}) if self.probabilities else (lambda c: None)
        return SimpleNamespace(choices={
            'turn': answer('left', probabilities=p('left')),
            'thrust': answer('burn', probabilities=p('burn')),
            'fire': answer('fire', probabilities=p('fire'))})

    async def aclose(self):
        self.closed = True


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def recorder(tmp_path, inner=None, **kwargs):
    sink = DecisionSink(tmp_path / 'run.jsonl', **kwargs)
    return RecordingJevClient(inner or Inner(), sink, run_id='r1', model='m'), sink


def test_success_returns_inner_result_and_writes_one_record(tmp_path):
    client, sink = recorder(tmp_path)
    result = asyncio.run(client.system_one(state={'speed': 3}, questions={}))
    sink.flush()
    assert result.choices['turn'].choice == 'left'
    [record] = lines(tmp_path / 'run.jsonl')
    assert record['run_id'] == 'r1' and record['model'] == 'm'
    assert record['state'] == {'speed': 3}
    assert record['latency'] >= 0 and record['t'] > 0
    assert record['answers']['turn'] == {
        'choice': 'left', 'confidence': .9, 'probabilities': {'left': .9, 'other': .1}}
    assert set(record['answers']) == {'turn', 'thrust', 'fire'}


def test_missing_probabilities_are_recorded_as_null(tmp_path):
    client, sink = recorder(tmp_path, Inner(probabilities=False))
    asyncio.run(client.system_one(state={}, questions={}))
    sink.flush()
    [record] = lines(tmp_path / 'run.jsonl')
    assert record['answers']['fire']['probabilities'] is None


def test_failed_calls_are_not_recorded_and_still_raise(tmp_path):
    client, sink = recorder(tmp_path, Inner(fail=True))
    with pytest.raises(RuntimeError):
        asyncio.run(client.system_one(state={}, questions={}))
    sink.flush()
    assert not (tmp_path / 'run.jsonl').exists() or lines(tmp_path / 'run.jsonl') == []


def test_unserialisable_state_does_not_break_the_decision(tmp_path):
    client, sink = recorder(tmp_path)
    result = asyncio.run(client.system_one(state={'bad': object()}, questions={}))
    sink.flush()
    assert result.choices['fire'].choice == 'fire'
    assert not (tmp_path / 'run.jsonl').exists() or lines(tmp_path / 'run.jsonl') == []


def test_unwritable_directory_does_not_break_the_decision(tmp_path):
    blocker = tmp_path / 'file'
    blocker.write_text('x')
    sink = DecisionSink(blocker / 'sub' / 'run.jsonl')
    client = RecordingJevClient(Inner(), sink, run_id='r1')
    result = asyncio.run(client.system_one(state={}, questions={}))
    sink.flush()
    assert result.choices['turn'].choice == 'left'


def test_full_queue_drops_records_without_blocking(tmp_path):
    gate = threading.Event()
    sink = DecisionSink(tmp_path / 'run.jsonl', max_queue=2)
    sink._open = lambda: gate.wait(2) and None  # hold the writer thread
    for _ in range(50):
        sink.write({'x': 1})  # must return immediately, never raise
    gate.set()


def test_aclose_closes_inner_and_sink(tmp_path):
    inner = Inner()
    client, sink = recorder(tmp_path, inner)
    asyncio.run(client.system_one(state={}, questions={}))
    asyncio.run(client.aclose())
    assert inner.closed
    assert len(lines(tmp_path / 'run.jsonl')) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_student_recorder.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'hunter.student.recorder'`.

- [ ] **Step 3: Write the implementation**

Create `hunter/student/recorder.py`:

```python
"""Logs Jev's pilot decisions as JSONL so a student can be trained on them."""
import json
import logging
import queue
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

DECISIONS_DIR = Path(__file__).resolve().parents[2] / '.astrovoid-local' / 'decisions'
_STOP = object()


class DecisionSink:
    """Appends JSON lines from a background thread; never blocks or raises into its caller."""

    def __init__(self, path, max_queue=256):
        self.path = Path(path)
        self._queue = queue.Queue(max_queue)
        self._file = None
        self._thread = threading.Thread(target=self._drain, name='decision-sink', daemon=True)
        self._thread.start()

    def write(self, record):
        try:
            line = json.dumps(record)
        except (TypeError, ValueError):
            log.warning('Decision record is not serialisable; dropped')
            return
        try:
            self._queue.put_nowait(line)
        except queue.Full:
            log.warning('Decision sink is full; dropped a record')

    def flush(self):
        self._queue.join()

    def close(self):
        self._queue.put(_STOP)
        self._thread.join(2)

    def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return open(self.path, 'a', encoding='utf-8')

    def _drain(self):
        while True:
            line = self._queue.get()
            try:
                if line is _STOP:
                    if self._file:
                        self._file.close()
                    return
                if self._file is None:
                    self._file = self._open()
                self._file.write(line + '\n')
                self._file.flush()
            except Exception:
                # Disk trouble must never reach the decision loop, nor kill this thread.
                log.warning('Decision sink cannot write %s; dropped a record', self.path)
                self._file = None
            finally:
                self._queue.task_done()


class RecordingJevClient:
    """Wraps the real Jev client and logs each successful decision."""

    def __init__(self, inner, sink, run_id=None, model='jev-latest'):
        self.inner, self.sink, self.model = inner, sink, model
        self.run_id = run_id or uuid.uuid4().hex

    async def system_one(self, **kwargs):
        started = time.monotonic()
        result = await self.inner.system_one(**kwargs)
        latency = time.monotonic() - started
        try:
            answers = {}
            for name, reply in result.choices.items():
                probabilities = getattr(reply, 'probabilities', None)
                answers[name] = {
                    'choice': reply.choice,
                    'confidence': getattr(reply, 'confidence', None),
                    'probabilities': None if probabilities is None else dict(probabilities)}
            self.sink.write({'t': time.time(), 'run_id': self.run_id, 'model': self.model,
                             'latency': latency, 'state': kwargs.get('state'),
                             'answers': answers})
        except Exception:
            # Recording is best effort: it must never cost the hunter a decision.
            log.warning('Could not record a decision', exc_info=True)
        return result

    async def aclose(self):
        try:
            close = getattr(self.inner, 'aclose', None)
            if close is not None:
                await close()
        finally:
            self.sink.close()


def record_to_disk(inner, model='jev-latest'):
    run_id = uuid.uuid4().hex
    return RecordingJevClient(inner, DecisionSink(DECISIONS_DIR / f'{run_id}.jsonl'),
                              run_id=run_id, model=model)
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_student_recorder.py -v`
Expected: all PASS. If `test_full_queue_drops_records_without_blocking` hangs, the sink's `_open` hook is not being reached: check that `_drain` calls `self._open()` and that the test patches the instance attribute before the first `write`.

- [ ] **Step 5: Commit**

```bash
git add hunter/student/recorder.py tests/test_student_recorder.py
git commit -m "feat: record Jev's pilot decisions as JSONL

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Settings and client selection

**Files:**
- Modify: `config.py:378-381` (`GameSettings`)
- Modify: `config/settings.json` (the `game` object, last block)
- Modify: `hunter/jev_pilot.py` (`create_client`, around line 237-252)
- Modify: `pyinstaller.spec` (`hiddenimports`)
- Modify: `README.md` (near the Jev hunter section, line ~398)
- Test: `tests/test_student_selection.py`

**Interfaces:**
- Consumes: `load_student_client` (Task 2), `record_to_disk` (Task 3), `config.SETTINGS.game`.
- Produces: `GameSettings.hunterPilot: str = 'jev'`, `GameSettings.recordPilotDecisions: bool = False`; `create_client()` (same signature) honouring them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_student_selection.py`:

```python
import sys
import numpy as np
import pytest
from config import SETTINGS
from hunter import jev_pilot
from hunter.jev_pilot import PilotUnavailable, create_client
from hunter.student import client as student_client
from hunter.student.client import JevStudentClient
from hunter.student.recorder import RecordingJevClient
from tests.test_student_client import FAVOURITES, constant_model


@pytest.fixture
def model_file(tmp_path, monkeypatch):
    path = tmp_path / 'm.npz'
    constant_model(FAVOURITES).save(path)
    monkeypatch.setattr(student_client, 'MODEL_PATH', str(path))
    return path


@pytest.fixture
def settings(monkeypatch):
    def apply(pilot='jev', record=False):
        monkeypatch.setattr(SETTINGS.game, 'hunterPilot', pilot)
        monkeypatch.setattr(SETTINGS.game, 'recordPilotDecisions', record)
    return apply


class FakeJev:
    pass


@pytest.fixture
def fake_jev(monkeypatch):
    monkeypatch.setattr(jev_pilot, '_create_jev_client', lambda: FakeJev())


def test_defaults_keep_todays_behaviour():
    assert SETTINGS.game.hunterPilot == 'jev'
    assert SETTINGS.game.recordPilotDecisions is False


def test_jev_mode_without_key_is_unavailable(settings, monkeypatch):
    settings('jev')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    with pytest.raises(PilotUnavailable, match='missing_key'):
        create_client()


def test_student_mode_loads_the_student_even_with_a_key(settings, model_file, monkeypatch):
    settings('student')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'k')
    assert isinstance(create_client(), JevStudentClient)


def test_auto_uses_jev_when_it_is_available(settings, fake_jev):
    settings('auto')
    assert isinstance(create_client(), FakeJev)


def test_auto_falls_back_to_the_student_when_jev_is_unavailable(settings, model_file, monkeypatch):
    settings('auto')
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    assert isinstance(create_client(), JevStudentClient)


def test_student_mode_without_a_model_is_unavailable(settings, tmp_path, monkeypatch):
    settings('student')
    monkeypatch.setattr(student_client, 'MODEL_PATH', str(tmp_path / 'absent.npz'))
    with pytest.raises(PilotUnavailable, match='missing_model'):
        create_client()


def test_unknown_mode_is_an_invalid_configuration(settings):
    settings('turbo')
    with pytest.raises(PilotUnavailable, match='invalid_configuration'):
        create_client()


def test_recording_wraps_jev_only(settings, fake_jev, model_file, monkeypatch, tmp_path):
    from hunter.student import recorder
    monkeypatch.setattr(recorder, 'DECISIONS_DIR', tmp_path)
    settings('jev', record=True)
    client = create_client()
    try:
        assert isinstance(client, RecordingJevClient)
        assert isinstance(client.inner, FakeJev)
    finally:
        client.sink.close()
    settings('student', record=True)
    assert isinstance(create_client(), JevStudentClient)


def test_recording_is_skipped_in_frozen_builds(settings, fake_jev, monkeypatch):
    settings('jev', record=True)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert isinstance(create_client(), FakeJev)
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_student_selection.py -v`
Expected: FAIL (`GameSettings` has no `hunterPilot`; `_create_jev_client` does not exist).

- [ ] **Step 3: Write the implementation**

In `config.py`, change `GameSettings` to:

```python
class GameSettings:
    criticalWarningThreshold: int
    hunterLevelInterval: int
    hunterFirstLevel: int
    # Which pilot flies the hunter: "jev", "student" (the trained imitation) or "auto"
    # (Jev when it is available, the student otherwise).
    hunterPilot: str = "jev"
    # Log Jev's decisions under .astrovoid-local/decisions/ as training data.
    recordPilotDecisions: bool = False
```

In `config/settings.json`, replace the `game` block with:

```json
  "game": {
    "criticalWarningThreshold": 20,
    "hunterLevelInterval": 1,
    "hunterFirstLevel": 4,
    "hunterPilot": "jev",
    "recordPilotDecisions": false
  }
```

In `hunter/jev_pilot.py`, add `import sys` beside the other imports and replace `create_client` with:

```python
def _create_jev_client():
    if not os.environ.get('TYPESAFE_API_KEY', '').strip():
        raise PilotUnavailable('missing_key')
    try:
        from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy
    except ImportError:
        raise PilotUnavailable('missing_sdk') from None
    try:
        return AsyncTypeSafeClient(
            model=os.environ.get('TYPESAFE_DEFAULT_MODEL', '').strip() or 'jev-latest',
            timeout=1.0, retry=RetryPolicy(max_retries=0))
    except Exception:
        # Client construction performs validation, not an inference request.
        raise PilotUnavailable('invalid_configuration') from None


def create_client():
    """The pilot client for this level: Jev, the trained student, or Jev with recording."""
    from config import SETTINGS
    from hunter.student.client import load_student_client
    mode = SETTINGS.game.hunterPilot
    if mode not in ('jev', 'student', 'auto'):
        raise PilotUnavailable('invalid_configuration')
    if mode == 'student':
        return load_student_client()
    try:
        client = _create_jev_client()
    except PilotUnavailable:
        if mode == 'auto':
            return load_student_client()
        raise
    # Frozen builds have no useful project directory to log into.
    if SETTINGS.game.recordPilotDecisions and not getattr(sys, 'frozen', False):
        from hunter.student.recorder import record_to_disk
        client = record_to_disk(
            client, model=os.environ.get('TYPESAFE_DEFAULT_MODEL', '').strip() or 'jev-latest')
    return client
```

In `pyinstaller.spec`, extend `hiddenimports` (the student modules are imported lazily, so the analysis would miss them):

```python
    hiddenimports=[
        "entities.hunter_ship", "hunter.controller", "hunter.perception",
        "hunter.spawn", "hunter.worker",
        "hunter.student.client", "hunter.student.encoder",
        "hunter.student.network", "hunter.student.recorder",
    ],
```

In `README.md`, directly after the paragraph at line ~398 that explains `TYPESAFE_API_KEY` and `TYPESAFE_DEFAULT_MODEL`, add:

```markdown
### Offline student pilot

`game.hunterPilot` in `config/settings.json` chooses the hunter's pilot: `"jev"` (default),
`"student"` (a small network trained to imitate Jev, no key or network needed), or `"auto"`
(Jev when it is available, the student otherwise). Set `game.recordPilotDecisions` to `true`
to log Jev's decisions to `.astrovoid-local/decisions/` while it flies. Train a student with
`venv/bin/python -m tools.train_student` (see `requirements-train.txt`); the model lives at
`assets/student/jev_student.npz`.
```

- [ ] **Step 4: Run the new tests and the existing hunter tests**

Run: `venv/bin/python -m pytest tests/test_student_selection.py tests/test_hunter_jev.py tests/test_hunter_worker.py tests/test_hunter_controller.py -v`
Expected: all PASS (`test_missing_key_is_unavailable` still passes because the default mode is `jev`).

- [ ] **Step 5: Commit**

```bash
git add config.py config/settings.json hunter/jev_pilot.py pyinstaller.spec README.md tests/test_student_selection.py
git commit -m "feat: choose the hunter's pilot from settings and optionally record Jev

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Trainer

**Files:**
- Create: `requirements-train.txt`
- Create: `tools/__init__.py` (empty)
- Create: `tools/train_student.py`
- Test: `tests/test_train_student.py`

**Interfaces:**
- Consumes: `encode`, `FEATURE_NAMES` (Task 1); `HEADS`, `StudentModel` (Task 2); the record schema (Task 3).
- Produces (all in `tools/train_student.py`):
  - `load_records(directory) -> list[dict]` — reads every `*.jsonl`, skipping blank or malformed lines.
  - `build_dataset(records) -> (X, targets, run_ids)` — `X` float32 `(N, F)`; `targets` is `{head: float32 (N, K)}` soft targets; `run_ids` a list of N strings. Records with an unknown choice are skipped.
  - `split_by_run(run_ids, held_out_fraction=0.2, seed=0) -> (train_idx, test_idx)` (numpy int arrays; raises `ValueError` with fewer than two runs).
  - `train(X, targets, train_idx, epochs=60, hidden=128, lr=1e-3, seed=0) -> StudentModel`.
  - `evaluate(model, X, targets, idx, majority) -> dict` and `majority_labels(targets, idx) -> {head: int}`.
  - `tree_baseline(X, targets, train_idx, test_idx) -> {head: float}`.
  - `main(argv=None)` with `--data DIR` (default `.astrovoid-local/decisions`) and `--out PATH` (default `assets/student/jev_student.npz`).

- [ ] **Step 1: Install the training dependencies**

Create `requirements-train.txt`:

```
# Only needed to train a student (tools/train_student.py); the game never imports these.
torch>=2.2
scikit-learn>=1.4
```

Run: `venv/bin/pip install -r requirements-train.txt`
Expected: installs without error. (This is large; if it fails on the platform, stop and report rather than skipping training.)

- [ ] **Step 2: Write the failing tests**

Create `tests/test_train_student.py`:

```python
import json
import numpy as np
import pytest

pytest.importorskip('torch')
pytest.importorskip('sklearn')

from hunter.student.client import JevStudentClient
from hunter.student.encoder import FEATURE_NAMES
from hunter.student.network import HEADS, StudentModel
from tools import train_student as ts


def jev_rule(rng):
    """A synthetic Jev: brake first, then fight, then follow the player."""
    if rng.random() < .3:
        state = {'motion': {'brake': {'speed_state': 'too_fast'}}}
        return state, ('course', 'burn', 'hold')
    if rng.random() < .5:
        state = {'visible_contacts': [{'allegiance': 'enemy', 'distance_metres': 80,
                                       'degrees_off_nose_at_next_decision': 10.0,
                                       'aim': {'lead_degrees_off_nose': 10.0, 'on_target': False}}]}
        return state, ('track', 'coast', 'fire')
    offset = float(rng.uniform(-90, 90))
    state = {'follow_player': {'degrees_off_nose_at_next_decision': offset}}
    turn = 'left' if offset < -20 else 'right' if offset > 20 else 'none'
    return state, (turn, 'coast', 'hold')


def write_logs(directory, runs=8, per_run=60, with_probabilities=True):
    rng = np.random.default_rng(0)
    for run in range(runs):
        with open(directory / f'run{run}.jsonl', 'w') as handle:
            for _ in range(per_run):
                state, picks = jev_rule(rng)
                answers = {}
                for head, pick in zip(('turn', 'thrust', 'fire'), picks):
                    probabilities = None
                    if with_probabilities:
                        probabilities = {c: (.9 if c == pick else .1 / (len(HEADS[head]) - 1))
                                         for c in HEADS[head]}
                    answers[head] = {'choice': pick, 'confidence': .9,
                                     'probabilities': probabilities}
                handle.write(json.dumps({'run_id': f'run{run}', 'state': state,
                                         'answers': answers}) + '\n')


def test_load_records_skips_blank_and_malformed_lines(tmp_path):
    (tmp_path / 'a.jsonl').write_text('{"run_id": "a"}\n\nnot json\n{"run_id": "b"}\n')
    assert [r['run_id'] for r in ts.load_records(tmp_path)] == ['a', 'b']


def test_build_dataset_uses_probabilities_and_falls_back_to_one_hot(tmp_path):
    write_logs(tmp_path, runs=1, per_run=5)
    X, targets, run_ids = ts.build_dataset(ts.load_records(tmp_path))
    assert X.shape == (5, len(FEATURE_NAMES))
    assert set(run_ids) == {'run0'}
    for head, choices in HEADS.items():
        assert targets[head].shape == (5, len(choices))
        assert targets[head].sum(axis=1) == pytest.approx(np.ones(5))
        assert targets[head].max(axis=1) == pytest.approx(np.full(5, .9))
    other = tmp_path / 'bare'
    other.mkdir()
    write_logs(other, runs=1, per_run=5, with_probabilities=False)
    _, hard, _ = ts.build_dataset(ts.load_records(other))
    assert hard['turn'].max(axis=1) == pytest.approx(np.ones(5))


def test_build_dataset_skips_records_with_unknown_choices():
    record = {'run_id': 'r', 'state': {}, 'answers': {
        'turn': {'choice': 'warp', 'probabilities': None},
        'thrust': {'choice': 'coast', 'probabilities': None},
        'fire': {'choice': 'hold', 'probabilities': None}}}
    X, targets, run_ids = ts.build_dataset([record])
    assert len(X) == 0 and run_ids == []


def test_split_by_run_never_splits_a_run():
    run_ids = [f'r{i // 10}' for i in range(100)]
    train_idx, test_idx = ts.split_by_run(run_ids, held_out_fraction=.2, seed=1)
    assert not set(train_idx) & set(test_idx)
    assert len(train_idx) + len(test_idx) == 100
    assert {run_ids[i] for i in train_idx}.isdisjoint({run_ids[i] for i in test_idx})
    assert len(test_idx) >= 10


def test_split_needs_two_runs():
    with pytest.raises(ValueError):
        ts.split_by_run(['a'] * 5)


def test_training_beats_the_majority_baseline_on_held_out_runs(tmp_path):
    write_logs(tmp_path)
    X, targets, run_ids = ts.build_dataset(ts.load_records(tmp_path))
    train_idx, test_idx = ts.split_by_run(run_ids)
    model = ts.train(X, targets, train_idx, epochs=80)
    metrics = ts.evaluate(model, X, targets, test_idx, ts.majority_labels(targets, train_idx))
    assert metrics['joint'] > .85
    assert metrics['joint'] > metrics['majority_joint']
    tree = ts.tree_baseline(X, targets, train_idx, test_idx)
    assert set(tree) == set(HEADS)


def test_main_writes_a_model_the_client_can_load(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    write_logs(data)
    out = tmp_path / 'student.npz'
    ts.main(['--data', str(data), '--out', str(out)])
    model = StudentModel.load(out)
    assert isinstance(JevStudentClient(model), JevStudentClient)
    assert 'joint' in StudentModel.metrics(out)
```

- [ ] **Step 3: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_train_student.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'tools'` (or `tools.train_student`).

- [ ] **Step 4: Write the implementation**

Create empty `tools/__init__.py`, then `tools/train_student.py`:

```python
"""Trains the Jev student from logged decisions: python -m tools.train_student."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
from hunter.student.encoder import FEATURE_NAMES, encode
from hunter.student.network import HEADS, StudentModel

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / '.astrovoid-local' / 'decisions'
DEFAULT_OUT = ROOT / 'assets' / 'student' / 'jev_student.npz'


def load_records(directory):
    records = []
    for path in sorted(Path(directory).glob('*.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _target(head, answer):
    """Jev's probabilities over the head's choices, or one-hot on the chosen option."""
    choices = HEADS[head]
    if answer['choice'] not in choices:
        raise KeyError(answer['choice'])
    probabilities = answer.get('probabilities')
    if probabilities and all(c in probabilities for c in choices):
        row = np.array([probabilities[c] for c in choices], dtype=np.float32)
        return row / row.sum()
    row = np.zeros(len(choices), dtype=np.float32)
    row[choices.index(answer['choice'])] = 1.0
    return row


def build_dataset(records):
    rows, run_ids = [], []
    columns = {head: [] for head in HEADS}
    for record in records:
        try:
            targets = {head: _target(head, record['answers'][head]) for head in HEADS}
            features = encode(record['state'])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append(features)
        run_ids.append(str(record.get('run_id', '')))
        for head in HEADS:
            columns[head].append(targets[head])
    X = np.stack(rows) if rows else np.zeros((0, len(FEATURE_NAMES)), dtype=np.float32)
    return X, {h: np.stack(v) if v else np.zeros((0, len(HEADS[h])), dtype=np.float32)
               for h, v in columns.items()}, run_ids


def split_by_run(run_ids, held_out_fraction=.2, seed=0):
    """Hold out whole runs: consecutive decisions are near-duplicates, so rows would leak."""
    runs = sorted(set(run_ids))
    if len(runs) < 2:
        raise ValueError('need at least two runs to hold one out')
    rng = np.random.default_rng(seed)
    rng.shuffle(runs)
    held = set(runs[:max(1, round(len(runs) * held_out_fraction))])
    ids = np.array(run_ids)
    test = np.flatnonzero(np.isin(ids, list(held)))
    train = np.flatnonzero(~np.isin(ids, list(held)))
    return train, test


def train(X, targets, train_idx, epochs=60, hidden=128, lr=1e-3, seed=0):
    import torch
    torch.manual_seed(seed)
    Xt = X[train_idx]
    mean = Xt.mean(axis=0)
    std = Xt.std(axis=0)
    scale = np.where(std > 1e-6, std, 1.0).astype(np.float32)
    inputs = torch.tensor((Xt - mean) / scale, dtype=torch.float32)
    soft = {h: torch.tensor(targets[h][train_idx]) for h in HEADS}
    trunk = torch.nn.Sequential(
        torch.nn.Linear(X.shape[1], hidden), torch.nn.ReLU(),
        torch.nn.Linear(hidden, hidden), torch.nn.ReLU())
    heads = torch.nn.ModuleDict({h: torch.nn.Linear(hidden, len(HEADS[h])) for h in HEADS})
    optimiser = torch.optim.Adam(list(trunk.parameters()) + list(heads.parameters()), lr=lr)
    count = len(inputs)
    for _ in range(epochs):
        order = torch.randperm(count)
        for start in range(0, count, 256):
            batch = order[start:start + 256]
            features = trunk(inputs[batch])
            loss = sum(-(soft[h][batch] * torch.log_softmax(heads[h](features), dim=1))
                       .sum(dim=1).mean() for h in HEADS)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()

    def arrays(layer):
        return (layer.weight.detach().numpy().T.copy(), layer.bias.detach().numpy().copy())

    return StudentModel(
        mean.astype(np.float32), scale,
        (arrays(trunk[0]), arrays(trunk[2])),
        {h: arrays(heads[h]) for h in HEADS})


def majority_labels(targets, idx):
    return {h: int(np.bincount(targets[h][idx].argmax(axis=1), minlength=len(HEADS[h])).argmax())
            for h in HEADS}


def evaluate(model, X, targets, idx, majority):
    """Agreement with Jev's most likely answer on the rows in idx."""
    predicted = {h: [] for h in HEADS}
    for row in X[idx]:
        probs = model.predict(row)
        for h, choices in HEADS.items():
            predicted[h].append(max(range(len(choices)), key=lambda i: probs[h][choices[i]]))
    metrics, joint, majority_joint = {}, np.ones(len(idx), bool), np.ones(len(idx), bool)
    for h in HEADS:
        truth = targets[h][idx].argmax(axis=1)
        match = np.array(predicted[h]) == truth
        metrics[h] = float(match.mean()) if len(idx) else 0.0
        metrics[f'majority_{h}'] = float((truth == majority[h]).mean()) if len(idx) else 0.0
        joint &= match
        majority_joint &= truth == majority[h]
    metrics['joint'] = float(joint.mean()) if len(idx) else 0.0
    metrics['majority_joint'] = float(majority_joint.mean()) if len(idx) else 0.0
    metrics['rows'] = int(len(idx))
    return metrics


def tree_baseline(X, targets, train_idx, test_idx):
    """A decision tree on the same features: does the network add anything?"""
    from sklearn.tree import DecisionTreeClassifier
    out = {}
    for h in HEADS:
        labels = targets[h].argmax(axis=1)
        tree = DecisionTreeClassifier(max_depth=12, random_state=0).fit(X[train_idx], labels[train_idx])
        out[h] = float((tree.predict(X[test_idx]) == labels[test_idx]).mean())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default=str(DEFAULT_DATA))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--epochs', type=int, default=60)
    args = parser.parse_args(argv)
    records = load_records(args.data)
    X, targets, run_ids = build_dataset(records)
    print(f'{len(X)} usable decisions from {len(set(run_ids))} runs '
          f'({len(records) - len(X)} records skipped)')
    train_idx, test_idx = split_by_run(run_ids)
    model = train(X, targets, train_idx, epochs=args.epochs)
    metrics = evaluate(model, X, targets, test_idx, majority_labels(targets, train_idx))
    metrics['tree'] = tree_baseline(X, targets, train_idx, test_idx)
    print(json.dumps(metrics, indent=2))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model.save(args.out, metrics)
    print(f'saved {args.out}')


if __name__ == '__main__':
    main(sys.argv[1:])
```

- [ ] **Step 5: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/test_train_student.py -v`
Expected: all PASS. If the joint-agreement assertion fails narrowly, raise `epochs` in the test before touching the model; do not lower the 0.85 bar without reporting it.

- [ ] **Step 6: Commit**

```bash
git add requirements-train.txt tools/__init__.py tools/train_student.py tests/test_train_student.py
git commit -m "feat: train the Jev student from logged decisions

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Collect real data and train the first model (manual, needs a Jev key)

This task needs gameplay and a live `TYPESAFE_API_KEY`, so a person does it. No code changes.

- [ ] **Step 1: Turn recording on and play**

Set `"recordPilotDecisions": true` in `config/settings.json` (leave `hunterPilot` at `"jev"`). Launch with `./run.sh` and play hunter levels. Each level attempt writes its own file in `.astrovoid-local/decisions/`. Aim for at least 20 attempts with varied situations (enemies, powerups, cut-off from the player, near walls) and at least 5,000 decisions in total. At about 4 decisions a second that is roughly 20 minutes of hunter flight.

- [ ] **Step 2: Train**

Run: `venv/bin/python -m tools.train_student`
Expected: it prints the run and decision counts, then metrics: per-head agreement, `joint`, the `majority_*` baselines and the `tree` baseline. The network should beat the majority baseline clearly and be at least level with the tree. Low `joint` agreement with plenty of data means the encoder is dropping something the rubric uses; look at which head is weakest before collecting more.

- [ ] **Step 3: Compare by eye**

Set `"hunterPilot": "student"` and `"recordPilotDecisions": false`, launch with `venv/bin/python main.py` (no key needed), and watch the hunter. Switch to `"jev"` and compare.

- [ ] **Step 4: Commit the model and reset the settings**

Restore `recordPilotDecisions` to `false` and `hunterPilot` to `"jev"` unless you want a different default, then:

```bash
git add assets/student/jev_student.npz config/settings.json
git commit -m "feat: add the first trained Jev student model

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage:** recorder with probabilities and per-run files (Task 3); student client (Task 2); settings, `auto` fallback, frozen-build skip, hiddenimports (Task 4); encoder (Task 1); trainer with run split, soft targets, majority and tree baselines (Task 5); model file with feature and head checks (Task 2); README note (Task 4); first real model (Task 6). Out-of-scope items (DAgger, harness, faster cadence, `previous_states`, on-screen label) have no tasks.
- **Type consistency:** `HEADS` ordering (from `criteria` keys) is used by `StudentModel.predict`, `_target` and the tests. `FAVOURITES`/`constant_model` are defined in `tests/test_student_client.py` and imported by `tests/test_student_selection.py`.
- **Known soft spot:** `test_full_queue_drops_records_without_blocking` patches `_open` on the instance to hold the writer thread; it asserts only that `write` never blocks or raises.
