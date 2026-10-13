# FUN Menu and Pilot Duel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FUN item on the main menu that lists experimental levels, starting with "Pilot fight: Rules vs Vibes", an empty-maze duel between the rules pilot's hunter and the neural pilot's hunter with the player as a hidden spectator.

**Architecture:** The duel is a self-contained module (`hunter/duel.py`: the arena's rules, no drawing) and its own game states (`STATE_FUN`, `STATE_DUEL`). The existing single-hunter game loop, the Jev beacon and the normal levels are not touched. Each pilot is shown the other hunter as an ordinary enemy; the existing perception, senses and fire control do the rest.

**Tech Stack:** Python 3, pygame, the existing hunter package (`HunterShip`, `HunterController`, `NeuralController`, `HunterPerception`, `Senses`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-13-pilot-duel-design.md`

## Global Constraints

- Run tests with `venv/bin/python -m pytest ... -p no:cacheprovider`. Work on branch `feat/pilot-duel`. Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Hunters are destructible only inside the duel (`replace(settings, indestructible=False, health=N)` on that hunter's own settings). `HunterSettings` defaults, `hunter_settings_for` and every normal level stay as they are.
- The duel never touches the profile, the scoring system, `game.hunter`, `game.hunter_controller` or `game.hunter_worker`.
- Settings live in the `game` section: `duelHealth` (default 5) and `duelTimeoutSeconds` (default 120.0). (The spec says `duel.health`; the game section is where hunter settings already are.)
- The neural hunter uses `load_neural_policy()` (`assets/neural/hunter.npz`) and `game.neuralDecisionFrames`; the rules hunter uses `hunter_settings_for('rules')`, `PilotWorker(client_factory=RulesClient)` and `HunterController`.
- Do not stop or disturb the background training run (`tools.ppo_neural`); keep test runs short (`timeout 110`) because they slow it a little.
- The pygame `game` fixture and `key()` helper come from `tests/test_replay_loop.py`; mimic how `tests/test_hunter_hotkey.py` imports them.

## Review Focus

1. A destroyed hunter must really stop (no ghost shots, no further damage) and the duel must end exactly once. (Task 1)
2. A hunter's own shots must never damage itself, even at point-blank range. (Task 1)
3. Leaving a duel by cancel, or finishing one, must leave the normal game clean (no stray hunter, projectiles, controller or worker), so START GAME afterwards behaves as before. (Task 3)
4. Missing neural weights must not crash; the FUN list shows "Vibes unavailable". (Task 2)
5. The profile (stars, score, progress) must be unchanged after any duel. (Task 3)

---

### Task 1: The duel arena

**Files:**
- Create: `hunter/duel.py`
- Test: `tests/test_duel_arena.py`

**Interfaces:**
- Consumes: `HunterShip(pos, settings)` (`entities/hunter_ship.py`: `step`, `take_damage`, `check_wall_collision`, `check_circle_collision`, `health`, `active`, `COLOR`, `FILL`, `NOSE_COLOR`, `COCKPIT_COLOR`), `HunterController(worker, settings)`, `NeuralController(policy, decision_frames)`, `HunterPerception(settings).observe(hunter, maze, player, enemies, projectiles, previous_action, now, generation)`, `Senses(settings).observe(hunter, maze, enemies, projectiles, powerups, player, last_controls, now)`, `find_firing_solution(hunter, enemies, maze, settings)`, `nearest_hunter_spawn(near, maze, player)`, `hunter_settings_for(mode)`, `get_angle_to_point(from, to)` (`utils/math_utils.py`).
- Produces (all in `hunter/duel.py`):
  - `DuelResult(winner: Optional[str], reason: str)` dataclass; `winner` is a side's `name` or None; `reason` is `'destroyed'`, `'draw'` or `'timeout'`.
  - `Combatant(name, hunter, controller)` dataclass (the arena adds `.perception`).
  - `DuelArena(maze, combatants, timeout_seconds, clock=time.monotonic)` with `.sides` (list of two), `.shots` (dict name -> list of that side's projectiles), `.elapsed` (game seconds), `.result` (None until the end), `update(dt)` (dt in frame units, 1.0 = 1/60 s), `close()`.
  - `duel_spawns(maze, player) -> (pos_a, pos_b)`.
  - `build_duel(maze, player, rules_worker, policy, health, timeout_seconds, decision_frames) -> DuelArena`; side names are `'rules'` and `'vibes'`.
  - `VIBES_COLORS` dict of the Vibes hunter's colour attributes.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_duel_arena.py`:

```python
import json
import math
from dataclasses import replace

import pygame
import pytest

import config
from entities.hunter_ship import HunterShip
from entities.projectile import Projectile
from hunter.duel import Combatant, DuelArena, DuelResult, build_duel, duel_spawns
from hunter.model import NEUTRAL, HunterSettings
from hunter.neural.controller import NeuralController
from hunter.controller import HunterController
from hunter.neural.policy import random_policy
from hunter.senses import FEATURE_NAMES
from hunter.settings_for import hunter_settings_for
from maze.config import MazeComplexity
from maze.generator import Maze

SETTINGS = replace(HunterSettings(), indestructible=False, health=3)


class ScriptedRules:
    """Stands in for HunterController: asks for an observation each tick, then flies the given action."""

    def __init__(self, action=NEUTRAL):
        self.action, self.seen, self.closed = action, [], False

    def tick(self, observe, running=True):
        self.seen.append(json.loads(observe(0.0, 0).state_json))
        return self.action

    def close(self):
        self.closed = True


class ScriptedNeural:
    kind = 'neural'

    def __init__(self, action=NEUTRAL):
        self.action, self.seen, self.closed = action, [], False

    def tick(self, senses_factory, running=True):
        self.seen.append(senses_factory((1, 0, 0), 0.0))
        return self.action

    def close(self):
        self.closed = True


@pytest.fixture
def maze():
    pygame.init()
    pygame.display.set_mode((320, 240))
    return Maze(1, complexity=MazeComplexity.EMPTY, grid_size=8)


def cell(maze, col, row):
    return maze.position_calculator.grid_center_to_screen(col, row)


@pytest.fixture
def arena(maze):
    a = HunterShip(cell(maze, 2, 3), SETTINGS)
    b = HunterShip(cell(maze, 5, 3), SETTINGS)
    rules, vibes = ScriptedRules(), ScriptedNeural()
    duel = DuelArena(maze, [Combatant('rules', a, rules), Combatant('vibes', b, vibes)], timeout_seconds=60.0)
    duel.scripted = (rules, vibes)
    return duel


def shot_on(hunter, owner):
    shot = Projectile((hunter.x, hunter.y), 0.0, source='hunter')
    shot.is_enemy = True
    return shot


def test_each_pilot_is_shown_the_other_hunter_as_an_enemy_and_only_its_bullets(arena):
    rules, vibes = arena.scripted
    rules_hunter, vibes_hunter = arena.sides[0].hunter, arena.sides[1].hunter
    arena.shots['vibes'].append(shot_on(rules_hunter, 'vibes'))        # a Vibes bullet near the rules hunter
    arena.shots['rules'].append(shot_on(rules_hunter, 'rules'))        # the rules hunter's own bullet
    arena.update(0.0)
    contacts = rules.seen[0]['visible_contacts']
    assert len(contacts) == 1 and contacts[0]['allegiance'] == 'enemy'
    assert len(rules.seen[0]['visible_projectiles']) == 1               # its own bullet is not a threat to it
    assert vibes.seen[0][FEATURE_NAMES.index('enemies_present')] == 1.0


def test_a_hunters_shot_damages_the_opponent_and_never_the_shooter(arena):
    rules_hunter, vibes_hunter = arena.sides[0].hunter, arena.sides[1].hunter
    arena.shots['rules'].append(shot_on(vibes_hunter, 'rules'))         # rules fires at Vibes
    arena.shots['vibes'].append(shot_on(vibes_hunter, 'vibes'))         # Vibes' own shot at point-blank range
    arena.update(0.0)
    assert vibes_hunter.health == SETTINGS.health - 1
    assert rules_hunter.health == SETTINGS.health


def test_a_destroyed_hunter_ends_the_duel_once_and_everything_stops(arena):
    rules, vibes = arena.scripted
    rules_hunter, vibes_hunter = arena.sides[0].hunter, arena.sides[1].hunter
    vibes_hunter.health = 1
    arena.shots['rules'].append(shot_on(vibes_hunter, 'rules'))
    arena.update(0.0)
    assert arena.result == DuelResult('rules', 'destroyed') and not vibes_hunter.active
    result, elapsed, ticks = arena.result, arena.elapsed, len(rules.seen)
    for _ in range(3):
        arena.update(1.0)
    assert arena.result is result and arena.elapsed == elapsed and len(rules.seen) == ticks


def test_both_destroyed_in_the_same_frame_is_a_draw(arena):
    rules_hunter, vibes_hunter = arena.sides[0].hunter, arena.sides[1].hunter
    rules_hunter.health = vibes_hunter.health = 1
    arena.shots['rules'].append(shot_on(vibes_hunter, 'rules'))
    arena.shots['vibes'].append(shot_on(rules_hunter, 'vibes'))
    arena.update(0.0)
    assert arena.result == DuelResult(None, 'draw')


def test_the_duel_times_out_as_a_draw(maze):
    a, b = HunterShip(cell(maze, 2, 3), SETTINGS), HunterShip(cell(maze, 5, 3), SETTINGS)
    duel = DuelArena(maze, [Combatant('rules', a, ScriptedRules()), Combatant('vibes', b, ScriptedNeural())],
                     timeout_seconds=1.0)
    duel.update(30.0)
    assert duel.result is None
    duel.update(30.0)
    assert duel.result == DuelResult(None, 'timeout')


def test_bullets_stop_at_walls_and_do_not_survive_their_lifetime(arena):
    far = Projectile((arena.maze.walls[0].start[0], arena.maze.walls[0].start[1]), 0.0, source='hunter')
    arena.shots['rules'].append(far)
    far.lifetime = 1
    arena.update(1.0)
    assert not arena.shots['rules'] or not arena.shots['rules'][0].active
    assert far not in arena.shots['rules']


def test_close_closes_both_controllers(arena):
    arena.close()
    assert all(c.closed for c in arena.scripted)


def test_the_spawns_are_far_apart_and_clear_of_walls(maze):
    from entities.ship import Ship
    player = Ship(maze.start_pos)
    a, b = duel_spawns(maze, player)
    assert math.dist(a, b) > 0.5 * math.hypot(config.SCREEN_WIDTH, config.SCREEN_HEIGHT) * 0.6


def test_build_duel_makes_a_destructible_rules_hunter_and_a_distinct_neural_one(maze):
    from entities.ship import Ship
    player = Ship(maze.start_pos)
    duel = build_duel(maze, player, rules_worker=object(), policy=random_policy(0), health=5,
                      timeout_seconds=120.0, decision_frames=6)
    rules, vibes = duel.sides
    assert (rules.name, vibes.name) == ('rules', 'vibes')
    assert isinstance(rules.controller, HunterController) and isinstance(vibes.controller, NeuralController)
    assert rules.hunter.health == vibes.hunter.health == 5
    assert not rules.hunter.settings.indestructible and not vibes.hunter.settings.indestructible
    assert rules.hunter.settings.turn_rate_multiplier == hunter_settings_for('rules').turn_rate_multiplier
    assert vibes.hunter.settings.turn_rate_multiplier == config.SETTINGS.game.neuralTurnRate
    assert rules.hunter.COLOR != vibes.hunter.COLOR                      # you can tell them apart
    assert HunterShip.COLOR == (120, 255, 90)                            # the class, so normal hunters, is unchanged
    toward = math.degrees(math.atan2(vibes.hunter.y - rules.hunter.y, vibes.hunter.x - rules.hunter.x)) % 360
    assert abs((rules.hunter.angle - toward + 180) % 360 - 180) < 1.0    # they start facing each other
    assert HunterSettings().indestructible is True                       # the default hunter is still unkillable
```

- [ ] **Step 2: Run to verify it fails**

Run: `timeout 110 venv/bin/python -m pytest tests/test_duel_arena.py -q -p no:cacheprovider`
Expected: collection error (`hunter.duel` missing).

- [ ] **Step 3: Implement `hunter/duel.py`**

```python
"""A duel between two pilots' hunters in an empty maze. The rules only: no drawing, no menus."""
import time
from dataclasses import dataclass, replace
from typing import Optional

import config
from entities.hunter_ship import HunterShip
from hunter.controller import HunterController
from hunter.fire_control import find_firing_solution
from hunter.neural.controller import NeuralController
from hunter.perception import HunterPerception
from hunter.senses import Senses
from hunter.settings_for import hunter_settings_for
from hunter.spawn import nearest_hunter_spawn
from utils.math_utils import get_angle_to_point

# The Vibes hunter's look: the rules hunter keeps the standard green, so the two are told apart at a glance.
VIBES_COLORS = {'COLOR': (255, 90, 200), 'FILL': (90, 25, 80), 'NOSE_COLOR': (255, 215, 240),
                'COCKPIT_COLOR': (60, 10, 50), 'ENGINE_COLOR': (160, 60, 120), 'ENGINE_LIT_COLOR': (255, 170, 230)}


@dataclass(frozen=True)
class DuelResult:
    winner: Optional[str]       # a side's name, or None for a draw
    reason: str                 # 'destroyed', 'draw' or 'timeout'


@dataclass
class Combatant:
    name: str
    hunter: HunterShip
    controller: object
    perception: object = None


class DuelArena:
    """Two hunters, each shown the other as an enemy, until one is destroyed or the time runs out."""

    def __init__(self, maze, combatants, timeout_seconds, clock=time.monotonic):
        if len(combatants) != 2:
            raise ValueError('a duel needs exactly two combatants')
        self.maze, self.sides, self.clock = maze, list(combatants), clock
        self.timeout_seconds = timeout_seconds
        self.elapsed = 0.0
        self.result = None
        self.shots = {side.name: [] for side in self.sides}
        for side in self.sides:
            neural = getattr(side.controller, 'kind', None) == 'neural'
            side.perception = Senses(side.hunter.settings) if neural else HunterPerception(side.hunter.settings)

    def _other(self, side):
        return self.sides[1] if side is self.sides[0] else self.sides[0]

    def update(self, dt):
        """Advance one frame (dt in frame units, 1.0 = 1/60 s). Does nothing once the duel has ended."""
        if self.result is not None:
            return
        self.elapsed += dt / config.FPS
        now = self.clock()
        for side in self.sides:
            self._fly(side, dt, now)
        first, second = self.sides
        if first.hunter.active and second.hunter.active:
            first.hunter.check_circle_collision(second.hunter.get_pos(), second.hunter.radius, second.hunter)
        self._move_shots(dt)
        self._judge()

    def _fly(self, side, dt, now):
        hunter, other = side.hunter, self._other(side)
        if not hunter.active:
            side.controller.close()
            return
        threats = self.shots[other.name]            # only the opponent's bullets are a danger to this pilot
        if getattr(side.controller, 'kind', None) == 'neural':
            action = side.controller.tick(lambda last_controls, t: side.perception.observe(
                hunter, self.maze, [other.hunter], threats, [], None, last_controls, t))
        else:
            action = side.controller.tick(lambda t, generation: side.perception.observe(
                hunter, self.maze, None, [other.hunter], threats, side.controller.action, t, generation))
        solution = None
        if action.track or action.fire or hunter.burst_remaining:
            solution = find_firing_solution(hunter, [other.hunter], self.maze, hunter.settings)
        shots = hunter.step(dt, action, solution)
        if shots:
            for shot in shots:
                shot.is_enemy = True                 # the pilots read a bullet's allegiance from this flag
            self.shots[side.name].extend(shots)
        hunter.check_wall_collision(self.maze.walls, self.maze.spatial_grid)

    def _move_shots(self, dt):
        for side in self.sides:
            victim = self._other(side).hunter
            alive = []
            for shot in self.shots[side.name]:
                shot.update(dt)
                if shot.active:
                    shot.check_wall_collision(self.maze.walls, self.maze.spatial_grid)
                if shot.active and victim.active and shot.check_circle_collision(victim.get_pos(), victim.radius):
                    shot.active = False
                    victim.take_damage()
                if shot.active:
                    alive.append(shot)
            self.shots[side.name] = alive

    def _judge(self):
        down = [side for side in self.sides if not side.hunter.active]
        if len(down) == 2:
            self.result = DuelResult(None, 'draw')
        elif down:
            self.result = DuelResult(self._other(down[0]).name, 'destroyed')
        elif self.elapsed >= self.timeout_seconds:
            self.result = DuelResult(None, 'timeout')

    def close(self):
        for side in self.sides:
            side.controller.close()


def duel_spawns(maze, player):
    """Two safe cells as far apart as the maze allows: the safe cells nearest its opposite corners."""
    first = nearest_hunter_spawn((0, 0), maze, player)
    second = nearest_hunter_spawn((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), maze, player)
    if first == second:
        raise ValueError('the maze has no room for two hunters')
    return first, second


def build_duel(maze, player, rules_worker, policy, health, timeout_seconds, decision_frames):
    """The rules pilot's hunter against the neural pilot's, facing each other from opposite corners."""
    rules_at, vibes_at = duel_spawns(maze, player)
    rules_settings = replace(hunter_settings_for('rules'), indestructible=False, health=health)
    vibes_settings = replace(hunter_settings_for('neural'), indestructible=False, health=health)
    rules, vibes = HunterShip(rules_at, rules_settings), HunterShip(vibes_at, vibes_settings)
    for name, value in VIBES_COLORS.items():
        setattr(vibes, name, value)                  # on this ship only: the class, and normal hunters, keep their look
    rules.angle = get_angle_to_point(rules_at, vibes_at)
    vibes.angle = get_angle_to_point(vibes_at, rules_at)
    return DuelArena(maze, [
        Combatant('rules', rules, HunterController(rules_worker, rules_settings)),
        Combatant('vibes', vibes, NeuralController(policy, decision_frames)),
    ], timeout_seconds)
```

- [ ] **Step 4: Run to verify it passes**

Run: `timeout 110 venv/bin/python -m pytest tests/test_duel_arena.py -q -p no:cacheprovider`
Expected: all PASS. If `Maze(1, complexity=..., grid_size=8)` needs more setup than the fixture gives, fix the fixture (the `Game` fixtures in `tests/test_hunter_integration.py` show a working set-up) and ledger a ruling. If a bullet-at-wall test is flaky, assert only that a bullet whose `lifetime` is 1 is gone after one `update`.

- [ ] **Step 5: Commit**

```bash
git add hunter/duel.py tests/test_duel_arena.py
git commit -m "feat: the duel arena: two hunters, each the other's enemy

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The FUN menu and the duel in the game

**Files:**
- Create: `rendering/fun_menu.py`, `rendering/duel_view.py`
- Modify: `config.py`, `config/settings.json`, `rendering/main_menu.py`, `game_handlers/state_handlers.py`, `game.py`, `tests/test_menu_visuals.py` (the menu-options assertion)
- Test: `tests/test_fun_menu.py`

**Interfaces:**
- Consumes: Task 1 (`build_duel`, `DuelArena`, `DuelResult`), `load_neural_policy`, `PilotWorker(client_factory=...)`, `RulesClient` (`hunter/rules_pilot.py`), `Button`, `AnimatedBackground`, `build_menu_backdrop`, `menu_scale` (`rendering/menu_components.py`), `get_font`.
- Produces:
  - `config.STATE_FUN`, `config.STATE_DUEL`; `GameSettings.duelHealth` (5), `GameSettings.duelTimeoutSeconds` (120.0).
  - `FunEntry(title, key)`, `FUN_ENTRIES`, `FunMenu(screen, entries=FUN_ENTRIES)` with `entries`, `selected_index`, `selected_entry`, `notice`, `navigate(delta)`, `refresh()`, `update(dt)`, `draw()`.
  - `rendering.duel_view.banner_text(result) -> str` and `draw_duel(screen, arena)`.
  - `Game.fun_menu`, `Game.duel`, `Game.duel_worker`, `Game.start_fun_entry(key)`, `Game.start_duel()`, `Game._make_duel_worker()`, `Game._update_duel(dt)`, `Game.end_duel()`, module constant `game.DUEL_BANNER_SECONDS = 3.0`, `FunStateHandler`, `DuelStateHandler`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fun_menu.py`:

```python
import time
from unittest.mock import Mock

import pygame
import pytest

import config
import game as game_module
from config import SETTINGS
from entities.projectile import Projectile
from hunter.duel import DuelResult
from hunter.neural import loader
from hunter.neural.policy import random_policy
from rendering.duel_view import banner_text
from rendering.fun_menu import FUN_ENTRIES
from tests.test_replay_loop import game, key  # noqa: F401 - pytest fixture


def to_fun(game):
    game.state = config.STATE_MENU
    game.main_menu.menu_selected_index = game.main_menu.menu_options.index('FUN')
    key(game, pygame.K_RETURN)


@pytest.fixture
def policy_file(tmp_path, monkeypatch):
    path = tmp_path / 'vibes.npz'
    random_policy(2).save(path)
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(path))
    return path


def test_fun_sits_between_levels_and_select_profile(game):
    options = game.main_menu.menu_options
    assert options.index('FUN') == options.index('LEVELS') + 1 == options.index('SELECT PROFILE') - 1


def test_fun_opens_the_list_with_the_pilot_fight_and_cancel_goes_back(game):
    to_fun(game)
    assert game.state == config.STATE_FUN
    assert [e.title for e in game.fun_menu.entries] == ['Pilot fight: Rules vs Vibes']
    assert game.fun_menu.selected_entry.key == 'pilot_duel'
    key(game, pygame.K_DOWN)
    assert game.fun_menu.selected_index == 0                      # one entry: it stays put
    key(game, pygame.K_ESCAPE)
    assert game.state == config.STATE_MENU


def test_the_list_is_data_so_more_levels_are_one_line(game):
    assert FUN_ENTRIES[0].key == 'pilot_duel'
    from rendering.fun_menu import FunEntry, FunMenu
    menu = FunMenu(game.screen, [FunEntry('A', 'a'), FunEntry('B', 'b')])
    menu.navigate(1)
    menu.navigate(1)
    assert menu.selected_index == 1 and menu.selected_entry.key == 'b'
    menu.navigate(-5)
    assert menu.selected_index == 0


def test_missing_neural_weights_keep_you_in_the_list_with_a_notice(game, monkeypatch, tmp_path):
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(tmp_path / 'absent.npz'))
    to_fun(game)
    key(game, pygame.K_RETURN)
    assert game.state == config.STATE_FUN and game.duel is None
    assert 'unavailable' in game.fun_menu.notice.lower()
    game.update(1.0)
    game.draw()                                                   # the notice draws without error


def test_starting_the_pilot_fight_builds_a_duel_and_leaves_the_normal_hunter_alone(game, policy_file):
    to_fun(game)
    key(game, pygame.K_RETURN)
    assert game.state == config.STATE_DUEL and game.duel is not None
    assert [s.name for s in game.duel.sides] == ['rules', 'vibes']
    assert game.hunter is None and game.hunter_controller is None and game.hunter_worker is None
    for _ in range(3):
        game.update(1.0)
    game.draw()
    game.end_duel()


def test_escape_leaves_the_duel_for_the_list_and_cleans_up(game, policy_file):
    to_fun(game)
    key(game, pygame.K_RETURN)
    worker = game.duel_worker
    worker.close = Mock(wraps=worker.close)
    key(game, pygame.K_ESCAPE)
    assert game.state == config.STATE_FUN and game.duel is None and game.duel_worker is None
    worker.close.assert_called_once()
    assert game.projectiles == [] and game.hunter is None


def test_a_finished_duel_shows_the_banner_then_returns_to_the_list(game, policy_file, monkeypatch):
    from experiments.harness import SyncWorker
    from hunter.rule_params import RULES
    monkeypatch.setattr(SETTINGS.game, 'duelTimeoutSeconds', 2.0)
    monkeypatch.setattr(game_module, 'DUEL_BANNER_SECONDS', 0.0)
    monkeypatch.setattr(type(game), '_make_duel_worker', lambda self: SyncWorker(RULES, time.monotonic))
    to_fun(game)
    key(game, pygame.K_RETURN)
    for _ in range(400):
        game.update(1.0)
        if game.state != config.STATE_DUEL:
            break
    assert game.state == config.STATE_FUN and game.duel is None


def test_the_banner_names_the_winner_or_the_draw():
    assert banner_text(DuelResult('rules', 'destroyed')) == 'RULES WINS'
    assert banner_text(DuelResult('vibes', 'destroyed')) == 'VIBES WINS'
    assert banner_text(DuelResult(None, 'draw')) == 'DRAW'
    assert banner_text(DuelResult(None, 'timeout')) == 'DRAW: TIME UP'
```

Also update the existing assertion in `tests/test_menu_visuals.py` (line ~266) to
`assert game.main_menu.menu_options == ["START GAME", "LEVELS", "FUN", "SELECT PROFILE", "CONTROLS", "QUIT"]`.

- [ ] **Step 2: Run to verify it fails**

Run: `timeout 110 venv/bin/python -m pytest tests/test_fun_menu.py -q -p no:cacheprovider`
Expected: collection error (`rendering.fun_menu` missing).

- [ ] **Step 3: Implement**

`config.py`: in `GameSettings`, after `lowGraphics: bool = False`, add

```python
    # The pilot duel (FUN menu): hits each hunter survives, and the game seconds before it is called a draw.
    duelHealth: int = 5
    duelTimeoutSeconds: float = 120.0
```

and in `STATES_DEFAULTS` add `"fun": "fun",` and `"duel": "duel",`; after `STATE_LEVEL_SELECT = ...` add

```python
STATE_FUN = STATES_DEFAULTS["fun"]
STATE_DUEL = STATES_DEFAULTS["duel"]
```

`config/settings.json`: in the `game` section after `"lowGraphics": false` (add a comma) add `"duelHealth": 5, "duelTimeoutSeconds": 120.0`.

`rendering/main_menu.py`: change the options line to
`self.menu_options = ["START GAME", "LEVELS", "FUN", "SELECT PROFILE", "CONTROLS", "QUIT"]`.

`rendering/fun_menu.py`:

```python
"""The FUN screen: a list of experimental levels."""
from dataclasses import dataclass

import config
from rendering.fonts import get_font
from rendering.menu_components import AnimatedBackground, Button, build_menu_backdrop, menu_scale


@dataclass(frozen=True)
class FunEntry:
    title: str
    key: str                     # what Game.start_fun_entry starts


# Add an experimental level by adding a line here and a branch in Game.start_fun_entry.
FUN_ENTRIES = (FunEntry('Pilot fight: Rules vs Vibes', 'pilot_duel'),)


class FunMenu:
    def __init__(self, screen, entries=FUN_ENTRIES):
        self.screen = screen
        self.entries = list(entries)
        self.selected_index = 0
        self.notice = ''
        self.pulse_phase = 0.0
        self.scale = menu_scale()
        self.background = AnimatedBackground(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        self.backdrop = build_menu_backdrop(config.SCREEN_WIDTH, config.SCREEN_HEIGHT).convert()
        self.title_font = get_font(self._scaled(72))
        self.notice_font = get_font(self._scaled(30))
        font = get_font(self._scaled(40))
        top = int(config.SCREEN_HEIGHT * 0.34)
        self.buttons = [Button(entry.title, (config.SCREEN_WIDTH // 2, top + i * self._scaled(80)), font,
                               width=self._scaled(760), height=self._scaled(64))
                        for i, entry in enumerate(self.entries)]

    def _scaled(self, value):
        return max(1, int(round(value * self.scale)))

    @property
    def selected_entry(self):
        return self.entries[self.selected_index] if self.entries else None

    def navigate(self, delta):
        if self.entries:
            self.selected_index = max(0, min(len(self.entries) - 1, self.selected_index + delta))

    def refresh(self):
        self.notice = ''

    def update(self, dt):
        self.background.update(dt)
        self.pulse_phase = (self.pulse_phase + config.BUTTON_GLOW_PULSE_SPEED * dt / 60.0) % 6.2832

    def draw(self):
        self.screen.blit(self.backdrop, (0, 0))
        self.background.draw(self.screen)
        title = self.title_font.render('FUN', True, (215, 225, 255))
        self.screen.blit(title, title.get_rect(center=(config.SCREEN_WIDTH // 2, int(config.SCREEN_HEIGHT * 0.18))))
        for i, button in enumerate(self.buttons):
            button.selected = (i == self.selected_index)
            button.draw(self.screen, self.pulse_phase)
        if self.notice:
            text = self.notice_font.render(self.notice, True, (255, 170, 120))
            self.screen.blit(text, text.get_rect(center=(config.SCREEN_WIDTH // 2, int(config.SCREEN_HEIGHT * 0.78))))
```

`rendering/duel_view.py`:

```python
"""Draws the pilot duel: the maze, both hunters with name tags and health pips, bullets, and the end banner."""
import pygame

import config
from rendering.fonts import get_font

TAGS = {'rules': 'RULES', 'vibes': 'VIBES'}


def banner_text(result):
    if result.winner is not None:
        return f'{TAGS.get(result.winner, result.winner.upper())} WINS'
    return 'DRAW: TIME UP' if result.reason == 'timeout' else 'DRAW'


def draw_duel(screen, arena):
    arena.maze.draw(screen)
    tag_font = get_font(22)
    for side in arena.sides:
        for shot in arena.shots[side.name]:
            shot.draw(screen)
    for side in arena.sides:
        hunter = side.hunter
        if hunter.active:
            hunter.draw(screen)
        colour = hunter.COLOR
        tag = tag_font.render(TAGS.get(side.name, side.name.upper()), True, colour)
        screen.blit(tag, tag.get_rect(center=(int(hunter.x), int(hunter.y - hunter.radius * 3.2))))
        for pip in range(max(hunter.settings.health, 0)):
            x = int(hunter.x + (pip - (hunter.settings.health - 1) / 2) * 9)
            y = int(hunter.y - hunter.radius * 2.2)
            pygame.draw.circle(screen, colour, (x, y), 3, 0 if pip < max(hunter.health, 0) else 1)
    if arena.result is not None:
        font = get_font(96)
        text = font.render(banner_text(arena.result), True, (255, 255, 255))
        rect = text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2))
        pygame.draw.rect(screen, (10, 10, 30), rect.inflate(60, 40), border_radius=12)
        pygame.draw.rect(screen, (215, 225, 255), rect.inflate(60, 40), 2, border_radius=12)
        screen.blit(text, rect)
```

`game_handlers/state_handlers.py`: in `MenuStateHandler`, in both the keyboard and the controller confirm branches add, after the `LEVELS` branch,

```python
            elif selected_option == "FUN":
                game.fun_menu.refresh()
                game.state = config.STATE_FUN
```

(indented to match each branch), add these classes before `StateHandlerRegistry`:

```python
class FunStateHandler(StateHandler):
    """The FUN list: up and down choose, confirm starts, cancel goes back to the main menu."""

    def __init__(self):
        self.last_navigation_time = 0.0

    def _start(self, game):
        entry = game.fun_menu.selected_entry
        if entry is not None:
            game.start_fun_entry(entry.key)
        return True

    def handle_keyboard(self, event, game):
        if event.key == pygame.K_UP:
            game.fun_menu.navigate(-1)
            return True
        if event.key == pygame.K_DOWN:
            game.fun_menu.navigate(1)
            return True
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            return self._start(game)
        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            game.state = config.STATE_MENU
            return True
        return False

    def handle_controller(self, event, game):
        if event.type == pygame.JOYBUTTONDOWN:
            if game.input_handler.is_controller_menu_confirm_pressed(event.button):
                return self._start(game)
            if game.input_handler.is_controller_menu_cancel_pressed(event.button):
                game.state = config.STATE_MENU
                return True
        now = time.monotonic()
        if now - self.last_navigation_time < 0.15:
            return False
        step = 0
        if event.type == pygame.JOYHATMOTION:
            step = event.value[1] * -1
        elif event.type == pygame.JOYAXISMOTION and event.axis in (1, 3) and abs(event.value) > config.CONTROLLER_DEADZONE:
            step = 1 if event.value > 0 else -1
        if step:
            game.fun_menu.navigate(step)
            self.last_navigation_time = now
            return True
        return False


class DuelStateHandler(StateHandler):
    """During a duel the only input is cancel, which ends it."""

    def handle_keyboard(self, event, game):
        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            game.end_duel()
            return True
        return False

    def handle_controller(self, event, game):
        if event.type == pygame.JOYBUTTONDOWN and game.input_handler.is_controller_menu_cancel_pressed(event.button):
            game.end_duel()
            return True
        return False
```

and register them: add `config.STATE_FUN: FunStateHandler(),` and `config.STATE_DUEL: DuelStateHandler(),` to the registry's `self.handlers` dict.

`game.py`:
- Imports (with the others): `from rendering.fun_menu import FunMenu`, `from rendering.duel_view import draw_duel`, `from hunter.duel import build_duel`, `from hunter.rules_pilot import RulesClient`, `from maze.config import MazeComplexity`.
- Module level, after `_hunter_hotkey_enabled`: `DUEL_BANNER_SECONDS = 3.0` and `DUEL_GRID_SIZE = 14`.
- In `Game.__init__`, after `self.level_select_menu = LevelSelectMenu(screen, self.profile_manager)`: 

```python
        self.fun_menu = FunMenu(screen)
        self.duel = None                 # the pilot fight in progress (STATE_DUEL)
        self.duel_worker = None
        self.duel_banner_until = None
```

- New methods (next to `_hotkey_summon_hunter`):

```python
    def start_fun_entry(self, key: str) -> None:
        """Start the FUN-list entry with this key."""
        if key == 'pilot_duel':
            self.start_duel()

    def _make_duel_worker(self):
        """The rules pilot's worker for a duel: its own thread, apart from the game's hunter worker."""
        return PilotWorker(client_factory=RulesClient)

    def start_duel(self) -> None:
        """Pilot fight: the rules pilot's hunter against the neural pilot's, in an empty maze, player watching."""
        policy = load_neural_policy()
        if policy is None:
            self.fun_menu.notice = 'Vibes unavailable: no neural policy found'
            self.state = config.STATE_FUN
            return
        self._close_hunter()
        random.seed(0)
        self.maze = Maze(1, complexity=MazeComplexity.EMPTY, grid_size=DUEL_GRID_SIZE)
        self.ship = Ship(self.maze.start_pos)    # the hidden spectator: only here so spawns keep clear of it
        self.projectiles = []
        worker = self._make_duel_worker()
        game_settings = config.SETTINGS.game
        try:
            self.duel = build_duel(self.maze, self.ship, worker, policy, game_settings.duelHealth,
                                   game_settings.duelTimeoutSeconds, game_settings.neuralDecisionFrames)
        except ValueError as exc:
            worker.close()
            self.fun_menu.notice = f'Duel unavailable: {exc}'
            self.state = config.STATE_FUN
            return
        self.duel_worker = worker
        self.duel_banner_until = None
        self.state = config.STATE_DUEL

    def _update_duel(self, dt: float) -> None:
        if self.duel is None:
            return
        self.duel.update(dt)
        if self.duel.result is not None:
            if self.duel_banner_until is None:
                self.duel_banner_until = time.monotonic() + DUEL_BANNER_SECONDS
            elif time.monotonic() >= self.duel_banner_until:
                self.end_duel()

    def end_duel(self) -> None:
        """Leave the duel for the FUN list, closing its controllers and worker; the normal game is left clean."""
        if self.duel is not None:
            self.duel.close()
            self.duel = None
        if self.duel_worker is not None:
            self.duel_worker.close()
            self.duel_worker.join(2.0)
            self.duel_worker = None
        self.duel_banner_until = None
        self.projectiles = []
        self.fun_menu.refresh()
        self.state = config.STATE_FUN
```

- At the very top of `update` (before `hunter_running = ...`):

```python
        if self.state == config.STATE_DUEL:
            self._update_duel(dt)
            return
        if self.state == config.STATE_FUN:
            self.fun_menu.update(dt)
            return
```

- In `draw`, after the `STATE_CONTROLS` branch: 

```python
        elif self.state == config.STATE_FUN:
            self.fun_menu.draw()
        elif self.state == config.STATE_DUEL:
            if self.duel is not None:
                draw_duel(self.screen, self.duel)
```

- In `run`'s `finally`, first line: `if self.duel is not None:\n                self.end_duel()`.

- [ ] **Step 4: Run to verify it passes**

Run: `timeout 115 venv/bin/python -m pytest tests/test_fun_menu.py tests/test_duel_arena.py tests/test_menu_visuals.py -q -p no:cacheprovider`
Expected: all PASS. If a draw call needs a different `Maze.draw` signature or `Projectile.draw`, follow `Game.draw_game` (`self.maze.draw(self.screen)`, projectiles drawn there) and ledger a ruling.

- [ ] **Step 5: Commit**

```bash
git add config.py config/settings.json rendering/fun_menu.py rendering/duel_view.py rendering/main_menu.py game_handlers/state_handlers.py game.py tests/test_fun_menu.py tests/test_menu_visuals.py
git commit -m "feat: FUN menu with the Rules vs Vibes pilot fight

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Safety checks, a real look, and docs

**Files:**
- Modify: `README.md`, `docs/superpowers/specs/2026-10-13-pilot-duel-design.md` (status line)
- Test: `tests/test_duel_safety.py`

**Interfaces:**
- Consumes: Task 2 (`Game.start_duel`, `end_duel`, `fun_menu`, state constants).
- Produces: nothing new in code; tests and docs.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_duel_safety.py`:

```python
import pygame
import pytest

import config
from hunter.neural import loader
from hunter.neural.policy import random_policy
from tests.test_fun_menu import policy_file, to_fun  # noqa: F401 - pytest fixture
from tests.test_replay_loop import game, key  # noqa: F401 - pytest fixture


def test_a_duel_leaves_the_profile_untouched(game, policy_file, tmp_path):
    path = game.profile_manager.profiles_file if hasattr(game.profile_manager, 'profiles_file') else tmp_path / 'profiles.json'
    before = path.read_bytes() if path.exists() else b''
    level, score = game.profile_manager.get_active_level(), game.scoring.get_total_score()
    to_fun(game)
    key(game, pygame.K_RETURN)
    for _ in range(5):
        game.update(1.0)
    key(game, pygame.K_ESCAPE)
    assert game.profile_manager.get_active_level() == level and game.scoring.get_total_score() == score
    assert (path.read_bytes() if path.exists() else b'') == before


def test_start_game_after_a_duel_behaves_as_before(game, policy_file):
    to_fun(game)
    key(game, pygame.K_RETURN)
    game.update(1.0)
    key(game, pygame.K_ESCAPE)
    game.state = config.STATE_PLAYING
    game.level = 1
    game.start_level()
    assert game.hunter is None and game.projectiles == [] and game.duel is None
    game.update(1.0)
    game.draw()


def test_a_corrupt_weights_file_does_not_crash_the_list(game, monkeypatch, tmp_path):
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'junk')
    monkeypatch.setattr(loader, 'DEFAULT_PATH', str(bad))
    to_fun(game)
    key(game, pygame.K_RETURN)
    assert game.state == config.STATE_FUN and 'unavailable' in game.fun_menu.notice.lower()


def test_the_normal_hunters_stay_indestructible(game, policy_file):
    from hunter.model import HunterSettings
    from hunter.settings_for import hunter_settings_for
    to_fun(game)
    key(game, pygame.K_RETURN)
    key(game, pygame.K_ESCAPE)
    assert HunterSettings().indestructible and hunter_settings_for('rules').indestructible
    assert hunter_settings_for('neural').indestructible
```

- [ ] **Step 2: Run to verify**

Run: `timeout 110 venv/bin/python -m pytest tests/test_duel_safety.py -q -p no:cacheprovider`
Expected: these exercise Task 2's behaviour, so they should PASS at once. A pass-first-time test here is a finding about the test, not the code: for each one, break the behaviour it guards for a moment (for example, make `end_duel` skip `self.projectiles = []`, or make `start_duel` set `self.hunter`) and confirm it fails, then restore. Record the mutations tried in the ledger.

- [ ] **Step 3: Look at it for real**

Render the FUN menu and a running duel at the real fullscreen size with the real display driver (the dummy driver hides alpha bugs; the real fullscreen window is 1352x878) and save PNGs. Run (no `SDL_VIDEODRIVER` override):

```bash
venv/bin/python - <<'EOF'
import pygame, config
pygame.init()
screen = pygame.display.set_mode((1352, 878))
config.SCREEN_WIDTH, config.SCREEN_HEIGHT = 1352, 878
from game import Game
g = Game(screen)
g.state = config.STATE_FUN
for _ in range(30):
    g.update(1.0); g.draw()
pygame.image.save(screen, '.astrovoid-local/fun-menu.png')
g.start_duel()
for _ in range(240):
    g.update(1.0); g.draw()
pygame.image.save(screen, '.astrovoid-local/duel.png')
g.end_duel()
EOF
```

Read both PNGs. Expected: the FUN title and one button, readable; the duel with a green and a magenta hunter, name tags, health pips, bullets in their owners' colours. Fix what looks wrong (overlaps, unreadable tags) and re-run once. Also check the main menu with the sixth button: it must not overlap the profile badge at the bottom.

- [ ] **Step 4: Docs and status**

README: in the "Choosing the hunter's pilot" section, after the hotkey paragraph, add:

```markdown
The **FUN** item on the main menu holds experimental levels. The first is **Pilot fight: Rules vs Vibes**: the rules
pilot's hunter and the neural pilot's hunter (in magenta) fight in an empty maze while you watch. It uses whatever
policy is in `assets/neural/hunter.npz`; each hunter takes `game.duelHealth` hits (5), and a fight that is not settled in
`game.duelTimeoutSeconds` (120) is a draw. It does not touch your profile.
```

Spec: change the status line to `Status: implemented on branch feat/pilot-duel.`

- [ ] **Step 5: Run the whole suite and commit**

Run: `venv/bin/python -m pytest tests -q -p no:cacheprovider | tail -3`
Expected: all PASS (this takes a few minutes while training runs).

```bash
git add tests/test_duel_safety.py README.md docs/superpowers/specs/2026-10-13-pilot-duel-design.md
git commit -m "test: duel safety checks; docs for the FUN menu

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
