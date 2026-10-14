# The Rules Hunter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Rules pilot's hunter ship as an enemy that hunts only its protagonist, make level 25 a boss level built on it, and make it a training opponent for the neural hunter.

**Architecture:** One enemy class, `RulesHunter(HunterShip)`, flown by the existing `HunterFlight` with the Rules pilot. A new `ProtagonistSurroundings` shows it only its protagonist and that protagonist's shots; `Game.protagonist()` names the protagonist (the player's ship in play, the hunter in training, where the harness replaces it). The entity manager, level config, collision handler and game loop each gain a small, parallel path for it, copied from the boss patterns already there.

**Tech Stack:** Python 3.10, pygame, numpy, pytest. Run everything with `venv/bin/python`.

**Spec:** `docs/superpowers/specs/2026-10-14-rules-hunter-boss-design.md`

## Global Constraints

- **Hostile only to its protagonist:** it never sees other enemies, pickups or a friend, and never fires at other enemies.
- **12 hits** destroy it (`RULES_HUNTER_HIT_POINTS = 12`); it leaves **no crystal**.
- **Level 25 file:** `complex` maze, grid size **26**, enemies `aggressive: 2`, `flocker: 2`, `rules_hunter: 1`, all else 0.
- **Levels 1 to 24, the arc, and the every-sixth-level boss rotation from level 30 are unchanged.**
- **Training flags:** `--rules-share` default **0.25**; `--rules-bounty` default **50** points.
- **Never commit** the user's local test files: the `hunterPilot: "neural"` line in `config/settings.json` and the trained checkpoint `assets/neural/hunter.npz`. Commit `config/settings.json` only with `"hunterPilot": "jev"` (see Task 0 for how).
- **No status text or health pips beside the allied hunter ship.** The Rules hunter is an enemy, so its health bar is allowed.
- Commit messages end with: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`

## Review Focus

Failure modes the spec implies but no happy-path test would exercise. Each has a test in the task that owns the code.

1. **Killing a Rules hunter must not crash the level-complete screen.** The collision handler deep-copies the killed enemy for the death portrait, and a Rules hunter holds a worker thread and a reference to the whole game. Pinned in Task 1 (`__deepcopy__`) and Task 3 (a player kill feeds `EnemyDeathPortrait`).
2. **No worker thread may outlive a level.** Restarting a level, finishing it, or closing the game must stop every Rules hunter's pilot worker. Task 3.
3. **A dead or missing protagonist must not crash the enemy.** When the player's ship is inactive the Rules hunter sees no target and simply coasts. Task 1 and Task 3.
4. **No valid spawn spot.** A maze too small or crowded to place the hunter must skip it with a log message and leave the level playable, not raise. Task 3.
5. **The level must still be winnable.** The exit stays locked until the Rules hunter is dead, and it must count as an enemy for "all enemies dead". Task 3.

---

### Task 0: Commit the pending mortality work

The working tree holds an uncommitted block from earlier work: mortality, the energy gauge, wall energy, the reversal penalty and the arrowhead restore. It overlaps the files this plan edits, so it must be committed first or task commits would sweep it in.

**Files:**
- Commit (do not edit): everything `git status --short` lists except `assets/neural/hunter.npz`, and `config/settings.json` with `hunterPilot` set to `"jev"` for the commit.

- [ ] **Step 1: Check the suite and the state**

Run: `venv/bin/python -m pytest tests -q 2>&1 | tail -8` and `git status --short`

Expected: the only failures are tests that assume the default pilot is Jev (because the local setting is `"neural"`) and, occasionally, `test_the_spawns_are_far_apart_but_within_sight_of_each_other` or `test_in_a_dense_maze_the_spawns_still_have_a_clear_line_of_sight` (random). Anything else: stop and investigate.

- [ ] **Step 2: Make settings.json committable**

```bash
cp config/settings.json /tmp/local-settings.json
python3 - <<'EOF'
p='config/settings.json'
s=open(p).read()
assert '"hunterPilot": "neural"' in s
open(p,'w').write(s.replace('"hunterPilot": "neural"','"hunterPilot": "jev"'))
EOF
venv/bin/python -m pytest tests -q 2>&1 | tail -4
```

Expected: only the random duel-spawn tests may fail.

- [ ] **Step 3: Commit everything except the checkpoint**

```bash
git add -A config.py config entities experiments game.py hunter rendering tools tests utils
git reset -q assets/neural/hunter.npz 2>/dev/null; git status --short
git commit -m "feat: the neural hunter is mortal; energy gauge, wall energy, reversal penalty

- the neural pilot's hunter has game.neuralHunterHealth energy (default 10) and loses energy to
  enemy hits and, in proportion to the speed they take, to walls (game.neuralWallEnergy)
- a small HUD gauge shows the hunter's energy while one flies
- training: --health, --death-penalty, --reversal-penalty, deaths logged
- the hunter is drawn as the arrowhead again

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: `git status --short` before the commit shows no `assets/neural/hunter.npz` staged; after it only that file (modified) and `.codegraph/` remain.

- [ ] **Step 4: Restore the local setting**

```bash
cp /tmp/local-settings.json config/settings.json
git status --short
```

Expected: `config/settings.json` and `assets/neural/hunter.npz` show as modified (local only).

---

### Task 1: The RulesHunter entity and its surroundings

**Files:**
- Create: `entities/rules_hunter.py`
- Modify: `hunter/surroundings.py` (add `ProtagonistSurroundings`), `entities/hunter_ship.py` (a `SHOT_SOURCE` class attribute used by `_shots`)
- Test: `tests/test_rules_hunter.py`

**Interfaces:**
- Produces:
  - `hunter.surroundings.ProtagonistSurroundings(game)` with `maze`, `enemies()`, `threats()`, `pickups()`, `friend()`. It calls `game.protagonist()`, `game.maze` and `game.projectiles`.
  - `entities.rules_hunter.RulesHunter(start_pos, worker, surroundings, clock=time.monotonic)`; attributes `hit_points`, `max_hit_points`, `flight`; methods `fly(dt) -> list[Projectile]`, `take_damage() -> bool` (True when destroyed), `die()`, `draw(screen)`, `draw_death(screen)`, `close()`.
  - `entities.rules_hunter.RULES_HUNTER_HIT_POINTS = 12`.
  - `HunterShip.SHOT_SOURCE = 'hunter'`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rules_hunter.py
"""The Rules hunter: the Rules pilot's hunter ship as an enemy that hunts only its protagonist."""
import copy
from types import SimpleNamespace

import pygame
import pytest

from entities.hunter_ship import HunterShip
from entities.rules_hunter import RULES_HUNTER_HIT_POINTS, RulesHunter
from hunter.surroundings import ProtagonistSurroundings
from tests.test_senses import world


class FakeGame:
    """Just what ProtagonistSurroundings reads from a game."""

    def __init__(self, protagonist, projectiles=()):
        self.maze = world()
        self._protagonist = protagonist
        self.projectiles = list(projectiles)

    def protagonist(self):
        return self._protagonist


def target(x=700.0, y=500.0, active=True):
    return SimpleNamespace(x=x, y=y, vx=0.0, vy=0.0, radius=8, active=active,
                           get_pos=lambda: (x, y))


def shot(is_enemy):
    return SimpleNamespace(is_enemy=is_enemy, active=True, x=0.0, y=0.0, vx=0.0, vy=0.0, radius=3)


class SilentWorker:
    """A pilot worker that never answers, and records that it was closed."""
    busy = False

    def __init__(self):
        self.closed = False

    def submit(self, observation):
        return True

    def poll(self):
        return None

    def close(self):
        self.closed = True


def make(game=None, worker=None):
    game = game or FakeGame(target())
    worker = worker or SilentWorker()
    return RulesHunter((500.0, 500.0), worker, ProtagonistSurroundings(game)), worker, game


def test_it_is_shown_only_its_protagonist_and_the_protagonists_shots():
    mine, theirs = shot(False), shot(True)
    game = FakeGame(target(), [mine, theirs])
    view = ProtagonistSurroundings(game)
    assert view.enemies() == [game.protagonist()]
    assert view.threats() == [mine]                      # enemy shots are not a threat to an enemy
    assert view.pickups() == [] and view.friend() is None
    assert view.maze is game.maze


def test_a_dead_or_missing_protagonist_leaves_it_nothing_to_hunt():
    assert ProtagonistSurroundings(FakeGame(target(active=False))).enemies() == []
    assert ProtagonistSurroundings(FakeGame(None)).enemies() == []


def test_it_flies_without_a_target_and_returns_a_list():
    hunter, _, _ = make(FakeGame(None))
    for _ in range(30):
        assert hunter.fly(1.0) == []


def test_twelve_hits_destroy_it_and_the_twelfth_reports_it():
    hunter, _, _ = make()
    assert hunter.hit_points == hunter.max_hit_points == RULES_HUNTER_HIT_POINTS == 12
    assert [hunter.take_damage() for _ in range(12)] == [False] * 11 + [True]


def test_its_shots_are_enemy_shots():
    hunter, _, _ = make()
    shots = hunter._shots()
    assert shots and all(s.is_enemy and s.source == 'enemy' for s in shots)


def test_the_normal_hunters_shots_are_still_the_hunters():
    shots = HunterShip((100.0, 100.0))._shots()
    assert all(s.source == 'hunter' and not s.is_enemy for s in shots)


def test_dying_stops_its_pilot_and_its_worker():
    hunter, worker, _ = make()
    hunter.die()
    assert not hunter.active and hunter.is_dying and worker.closed
    assert hunter.fly(1.0) == []


def test_a_copy_for_the_death_portrait_carries_no_pilot_worker_or_game():
    hunter, _, game = make()
    clone = copy.deepcopy(hunter)
    assert clone.flight is None and clone._worker is None and clone.surroundings is None
    assert (clone.x, clone.y, clone.radius) == (hunter.x, hunter.y, hunter.radius)
    assert hunter.flight is not None                     # the original is untouched


def test_the_copy_plays_a_death_portrait():
    from rendering.enemy_death_portrait import EnemyDeathPortrait
    pygame.init()
    hunter, _, _ = make()
    hunter.die()
    portrait = EnemyDeathPortrait(hunter, 20)
    portrait.update(10.0)
    portrait.draw(pygame.Surface((200, 200)), (100, 100))


def test_it_draws_red_with_a_health_bar_that_shrinks():
    pygame.init()
    hunter, _, _ = make()

    def red_pixels():
        screen = pygame.Surface((300, 300))
        hunter.x, hunter.y = 150.0, 150.0
        hunter.draw(screen)
        return sum(1 for x in range(300) for y in range(300)
                   if screen.get_at((x, y))[0] > screen.get_at((x, y))[1] + 40)

    full = red_pixels()
    assert full > 0
    for _ in range(6):
        hunter.take_damage()
    assert red_pixels() < full                          # the bar has lost half its fill


def test_its_colours_are_not_the_allied_hunters():
    assert RulesHunter.COLOR != HunterShip.COLOR
    assert RulesHunter.COLOR[0] > RulesHunter.COLOR[1]   # red


def test_it_fires_at_a_protagonist_in_the_open_in_a_few_seconds():
    """The real Rules pilot, answered at once, aims at what it is shown."""
    from experiments.harness import SyncWorker
    from hunter.rule_params import RULES
    clock_time = [1000.0]
    game = FakeGame(target(x=640.0, y=500.0))
    hunter = RulesHunter((500.0, 500.0), SyncWorker(RULES, lambda: clock_time[0]),
                         ProtagonistSurroundings(game), clock=lambda: clock_time[0])
    fired = []
    for _ in range(6 * 60):
        clock_time[0] += 1 / 60
        fired += hunter.fly(1.0)
    assert fired and all(s.is_enemy for s in fired)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_rules_hunter.py -q 2>&1 | tail -5`
Expected: collection error, `ModuleNotFoundError: No module named 'entities.rules_hunter'`.

- [ ] **Step 3: Add `SHOT_SOURCE` to the hunter ship**

In `entities/hunter_ship.py`, add `SHOT_SOURCE = 'hunter'` to the class attributes (after `ENGINE_LIT_COLOR`), and in `_shots` change `source='hunter'` to `source=self.SHOT_SOURCE`.

```python
    ENGINE_LIT_COLOR = (255, 200, 80)  # ... and engine on
    SHOT_SOURCE = 'hunter'  # whose shots these are; an enemy hunter fires 'enemy' shots
```

```python
            source=self.SHOT_SOURCE, dynamic_color=self.COLOR) for angle in angles]
```

- [ ] **Step 4: Add `ProtagonistSurroundings`**

Append to `hunter/surroundings.py`:

```python
class ProtagonistSurroundings:
    """What a Rules hunter perceives: its protagonist and that protagonist's shots, and nothing else.

    The protagonist is whoever the game names (`Game.protagonist()`): the player's ship in play, the hunter in the
    lab. No other enemy, no pickup and no friend is shown, so the enemy never hunts or fires at anything else.
    """

    def __init__(self, game):
        self._game = game

    @property
    def maze(self):
        return self._game.maze

    def enemies(self):
        target = self._game.protagonist()
        return [target] if target is not None and target.active else []

    def threats(self):
        return [p for p in self._game.projectiles if not p.is_enemy]

    def pickups(self):
        return []

    def friend(self):
        return None
```

- [ ] **Step 5: Write the entity**

```python
# entities/rules_hunter.py
"""The Rules hunter: the Rules pilot's hunter ship, flown as an enemy that hunts only its protagonist.

It is a HunterShip flown by a HunterFlight and the Rules pilot, and a game enemy: shots damage it, it takes
RULES_HUNTER_HIT_POINTS of them, and its shots are enemy shots. What it hunts comes from its surroundings
(see hunter.surroundings.ProtagonistSurroundings), so it never sees or fires at anything else.
"""
import copy
import time
from dataclasses import replace

import pygame

from entities.hunter_ship import HunterShip
from hunter.flight import HunterFlight, WorkerPilot
from hunter.settings_for import hunter_settings_for

RULES_HUNTER_HIT_POINTS = 12
_LIVE = ('flight', '_worker', 'surroundings')       # what a copy for a death portrait must not carry


class RulesHunter(HunterShip):
    # The enemy colour: red, where the allied hunter is green and the Vibes hunter pink.
    COLOR = (255, 90, 90)
    FILL = (110, 25, 25)
    NOSE_COLOR = (255, 215, 200)
    COCKPIT_COLOR = (60, 10, 10)
    ENGINE_COLOR = (170, 60, 20)
    ENGINE_LIT_COLOR = (255, 150, 80)
    SHOT_SOURCE = 'enemy'
    DEATH_DURATION = 0.8
    BAR_WIDTH = 40
    BAR_HEIGHT = 4

    def __init__(self, start_pos, worker, surroundings, clock=time.monotonic):
        # Hit points, not the hunter's health, are what a hit costs it: the ship itself is indestructible.
        super().__init__(start_pos, replace(hunter_settings_for('rules'), indestructible=True))
        self.hit_points = self.max_hit_points = RULES_HUNTER_HIT_POINTS
        self.surroundings = surroundings
        self._worker = worker
        self.flight = HunterFlight(self, WorkerPilot(worker, clock), surroundings)

    def fly(self, dt):
        """Fly one frame; returns the shots fired, for the game to place."""
        if not self.active or self.flight is None:
            return []
        return self.flight.fly(dt)

    def take_damage(self):
        """A shot hit it. Returns True when that destroyed it."""
        self.hit_points -= 1
        return self.hit_points <= 0

    def die(self):
        super().die()
        self.close()

    def close(self):
        """Stop its pilot and its worker."""
        if self.flight is not None:
            self.flight.close()
        close = getattr(self._worker, 'close', None)     # the lab's synchronous worker has nothing to close
        if close is not None:
            close()

    def draw(self, screen):
        if not self.active:
            return
        super().draw(screen)
        bar = pygame.Rect(0, 0, self.BAR_WIDTH, self.BAR_HEIGHT)
        bar.midbottom = (round(self.x), round(self.y - self.radius * 2.2))
        pygame.draw.rect(screen, (60, 20, 20), bar)
        fill = bar.copy()
        fill.width = round(bar.width * max(0, self.hit_points) / self.max_hit_points)
        if fill.width:
            pygame.draw.rect(screen, self.COLOR, fill)
        pygame.draw.rect(screen, (150, 70, 70), bar, 1)

    def draw_death(self, screen):
        """An expanding ring where it was destroyed."""
        progress = self.death_progress
        radius = round(self.radius * (1.5 + 4.0 * progress))
        pygame.draw.circle(screen, self.COLOR, (round(self.x), round(self.y)), radius,
                           max(1, round(3 * (1.0 - progress))))

    def __deepcopy__(self, memo):
        """A copy for a death portrait: the ship as it was, without its pilot, worker or view of the game."""
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(copy.deepcopy({k: v for k, v in self.__dict__.items() if k not in _LIVE}, memo))
        for name in _LIVE:
            clone.__dict__[name] = None
        return clone
```

- [ ] **Step 6: Run the tests and iterate**

Run: `venv/bin/python -m pytest tests/test_rules_hunter.py -q 2>&1 | tail -15`
Expected: all pass. If `test_it_fires_at_a_protagonist_in_the_open_in_a_few_seconds` fails because the real player-style target lacks an attribute the Rules pilot's perception reads, add the missing attribute to `target()` in the test (the real player `Ship` has it); do not weaken the assertion. If it still fails because the pilot does not fire within 6 simulated seconds, raise the range to 12 seconds and say so in the commit message.

- [ ] **Step 7: Run the hunter suites for regressions, then commit**

Run: `venv/bin/python -m pytest tests/test_hunter_ship.py tests/test_hunter_appearance.py tests/test_duel_arena.py tests/test_senses.py -q 2>&1 | tail -4`
Expected: pass (apart from the random duel-spawn tests).

```bash
git add entities/rules_hunter.py entities/hunter_ship.py hunter/surroundings.py tests/test_rules_hunter.py
git commit -m "feat: the Rules hunter, an enemy flown by the Rules pilot that hunts only its protagonist

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Entity manager, level config and the level 25 file

**Files:**
- Modify: `game_handlers/entity_manager.py`, `level_config.py`
- Create: `levels/25.json`
- Test: `tests/test_rules_hunter_level.py`

**Interfaces:**
- Consumes: nothing from Task 1 beyond the class name (the manager only holds the list).
- Produces:
  - `EntityManager.rules_hunters: list`, included in `clear_all`, `get_all_enemy_positions`, `get_all_active_enemies`, `get_all_enemies`.
  - `level_config.get_level_rules_hunter_count(level: int) -> int`.
  - `level_config.is_boss_level` counts Rules hunters.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rules_hunter_level.py
import json
from types import SimpleNamespace

import level_config
from game_handlers.entity_manager import EntityManager


def fake_hunter(active=True):
    return SimpleNamespace(active=active, get_pos=lambda: (5.0, 6.0), is_dying=False)


def test_the_entity_manager_tracks_rules_hunters_with_the_other_enemies():
    manager = EntityManager()
    alive, dead = fake_hunter(), fake_hunter(active=False)
    manager.rules_hunters.extend([alive, dead])
    assert list(manager.get_all_active_enemies()) == [alive]
    assert alive in manager.get_all_enemies() and dead in manager.get_all_enemies()
    assert (5.0, 6.0) in manager.get_all_enemy_positions()
    manager.clear_all()
    assert manager.rules_hunters == []


def test_level_25_has_one_rules_hunter_and_no_other_level_does():
    assert level_config.get_level_rules_hunter_count(25) == 1
    for level in (1, 12, 24, 26, 30, 36):
        assert level_config.get_level_rules_hunter_count(level) == 0


def test_level_25_is_a_boss_level_without_a_jev_beacon():
    assert level_config.is_boss_level(25)
    assert not level_config.level_allows_jev_beacon(25)
    assert not level_config.level_has_hunter(25)


def test_the_boss_rotation_after_level_25_is_unchanged():
    assert not level_config.is_boss_level(26)
    assert not level_config.is_boss_level(29)
    assert level_config.is_boss_level(30) and level_config.is_boss_level(36)


def test_a_level_file_can_place_a_rules_hunter_on_any_level(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {'enemies': {'rules_hunter': 2}} if level == 7 else None)
    assert level_config.get_level_rules_hunter_count(7) == 2
    assert level_config.is_boss_level(7)


def test_the_level_25_file_matches_the_design():
    data = json.load(open('levels/25.json'))
    assert data['maze'] == {'complexity': 'complex', 'grid_size': 26}
    enemies = {name: count for name, count in data['enemies'].items() if count}
    assert enemies == {'aggressive': 2, 'flocker': 2, 'rules_hunter': 1}
    assert 'hunter' not in data
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_rules_hunter_level.py -q 2>&1 | tail -6`
Expected: failures (`AttributeError`, missing file).

- [ ] **Step 3: Entity manager**

In `game_handlers/entity_manager.py`:

1. Add `from entities.rules_hunter import RulesHunter` under `TYPE_CHECKING`, and `self.rules_hunters: List['RulesHunter'] = []` after `self.anemones` in `__init__`.
2. In `clear_all`, add `self.rules_hunters.clear()`.
3. In `get_all_enemy_positions`, add `positions.extend([rh.get_pos() for rh in self.rules_hunters])` before `return positions`.
4. In `get_all_active_enemies`, after the anemone loop add:

```python
        for rules_hunter in self.rules_hunters:
            if rules_hunter.active:
                yield rules_hunter
```

5. In `get_all_enemies`, add `self.rules_hunters` to the tuple of groups.

- [ ] **Step 4: Level config**

In `level_config.py`, add after `get_level_mother_boss_count`:

```python
def get_level_rules_hunter_count(level: int) -> int:
    """Rules hunters on a level: the level file's `rules_hunter` count, else none."""
    config = load_level_config(level)
    if config and 'enemies' in config and 'rules_hunter' in config['enemies']:
        return int(config['enemies']['rules_hunter'])
    return 0
```

and change `is_boss_level` to:

```python
def is_boss_level(level: int) -> bool:
    """A boss level is any level with a split boss, a mother boss or a Rules hunter on it."""
    return (get_level_split_boss_count(level) + get_level_mother_boss_count(level)
            + get_level_rules_hunter_count(level)) > 0
```

- [ ] **Step 5: The level file**

```json
{
  "seed": 125,
  "maze": {
    "complexity": "complex",
    "grid_size": 26
  },
  "enemies": {
    "static": 0,
    "patrol": 0,
    "aggressive": 2,
    "replay": 0,
    "flocker": 2,
    "flighthouse": 0,
    "egg": 0,
    "anemone": 0,
    "split_boss": 0,
    "mother_boss": 0,
    "rules_hunter": 1
  }
}
```

Save it as `levels/25.json`.

- [ ] **Step 6: Run the new tests, then find what else assumed level 25 was ordinary**

Run: `venv/bin/python -m pytest tests/test_rules_hunter_level.py -q 2>&1 | tail -5` (expect pass), then
`venv/bin/python -m pytest tests -q -k "level or boss or arc or rules or difficulty" 2>&1 | tail -15`

Expected: new tests pass. Any other failure that asserts level 25's formula-derived enemy counts, grid or boss status is a test that assumed level 25 had no file: update its expectation to the file's values (or move its level to 26) and say so in the commit message. Do not change `tests/test_level_arc.py`: its arc is levels 1 to 24.

- [ ] **Step 7: Commit**

```bash
git add game_handlers/entity_manager.py level_config.py levels/25.json tests/test_rules_hunter_level.py
git add -u tests
git commit -m "feat: level 25 is a boss level with a Rules hunter

The level file gains a rules_hunter count; is_boss_level counts it, so the exit stays locked,
ammo is infinite and no beacon appears. The every-sixth-level rotation from 30 is unchanged.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

(`git add -u tests` picks up only tests edited in Step 6; check `git status --short` first so no local-only file is swept in.)

---

### Task 3: The game: spawn, fly, collide, draw, close

**Files:**
- Modify: `game.py`, `game_handlers/collision_handler.py`
- Test: `tests/test_rules_hunter_game.py`

**Interfaces:**
- Consumes: `RulesHunter(start_pos, worker, surroundings, clock)`, `ProtagonistSurroundings(game)`, `EntityManager.rules_hunters`, `level_config.get_level_rules_hunter_count(level)`.
- Produces:
  - `Game.rules_hunters` (property: the entity manager's list), `Game._rules_worker_factory` (class attribute `None`; the lab sets an instance attribute), `Game.protagonist() -> ship`, `Game._make_rules_worker()`, `Game._spawn_rules_hunters(spawn_positions)`, `Game._fly_rules_hunters(dt)`, `Game._close_rules_hunters()`.
  - `CollisionHandler.handle_projectile_enemy_collisions(..., rules_hunters=None)`.

- [ ] **Step 1: Read the three call sites you will edit**

Read `game.py` around `start_level` (the `spawn_all_enemies` call, about line 360), the enemy update block (`update_split_bosses` / `update_mother_bosses` and `self.entity_manager.update_dying(dt)`, about lines 850 to 865), the projectile loop (`handle_projectile_enemy_collisions(`, about line 900), the draw block (`# Draw SplitBoss enemies`, about line 1163) and the `finally:` in `run`. Confirm that the boss-level exit lock (about line 658) counts enemies through `self.entity_manager.get_all_active_enemies()`; if it does not, make it do so for Rules hunters too.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_rules_hunter_game.py
import math
from types import SimpleNamespace

import pygame
import pytest

import config
import level_config
from entities.projectile import Projectile
from entities.rules_hunter import RULES_HUNTER_HIT_POINTS, RulesHunter
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_rules_hunter import SilentWorker


@pytest.fixture
def arena(game, monkeypatch):
    """A started level with one Rules hunter whose pilot never answers."""
    workers = []

    def factory():
        workers.append(SilentWorker())
        return workers[-1]

    game._rules_worker_factory = factory
    monkeypatch.setattr(level_config, 'get_level_rules_hunter_count', lambda level: 1)
    monkeypatch.setattr(level_config, 'get_level_enemy_counts', lambda level: None)
    game.level = 3          # a small level: the fixture's maze is a tiny empty one
    game.start_level()
    game.workers = workers
    return game


def shot_at(hunter, source='player'):
    return Projectile((hunter.x, hunter.y), 0.0, source=source)


def test_the_protagonist_is_the_players_ship(arena):
    assert arena.protagonist() is arena.ship


def test_a_level_with_a_rules_hunter_spawns_one_clear_of_the_player(arena):
    assert len(arena.rules_hunters) == 1 and isinstance(arena.rules_hunters[0], RulesHunter)
    hunter = arena.rules_hunters[0]
    assert hunter in arena.entity_manager.get_all_active_enemies()
    assert math.hypot(hunter.x - arena.ship.x, hunter.y - arena.ship.y) >= config.ENEMY_START_CLEARANCE


def test_it_starts_far_from_the_player_and_clear_of_the_other_enemies(arena):
    hunter = arena.rules_hunters[0]
    others = [e.get_pos() for e in arena.entity_manager.get_all_enemies() if e is not hunter]
    assert all(math.hypot(hunter.x - x, hunter.y - y) > hunter.radius * 2 for x, y in others)


def test_a_level_without_one_spawns_none(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_rules_hunter_count', lambda level: 0)
    game.start_level()
    assert game.rules_hunters == []


def test_restarting_the_level_stops_the_old_hunters_worker(arena):
    first = arena.workers[0]
    arena.start_level()
    assert first.closed and len(arena.workers) == 2 and not arena.workers[1].closed


def test_closing_stops_every_rules_hunters_worker(arena):
    arena._close_rules_hunters()
    assert all(w.closed for w in arena.workers)


def test_the_players_shots_destroy_it_in_twelve_hits_with_no_crystal(arena):
    hunter = arena.rules_hunters[0]
    crystals_before = len(arena.powerup_crystals)
    destroyed = 0
    for hit in range(RULES_HUNTER_HIT_POINTS):
        projectile = shot_at(hunter)
        used = arena.collision_handler.handle_projectile_enemy_collisions(
            projectile, arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
            arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
            anemones=arena.anemones, jev_beacon_allowed=False, rules_hunters=arena.rules_hunters)
        assert used
        destroyed += not hunter.active
    assert destroyed == 1 and not hunter.active and hunter.hit_points == 0
    assert len(arena.powerup_crystals) == crystals_before


def test_the_hunters_shots_hurt_it_too(arena):
    hunter = arena.rules_hunters[0]
    arena.collision_handler.handle_projectile_enemy_collisions(
        shot_at(hunter, 'hunter'), arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
        arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
        anemones=arena.anemones, rules_hunters=arena.rules_hunters)
    assert hunter.hit_points == RULES_HUNTER_HIT_POINTS - 1


def test_its_own_shots_do_not_hurt_it(arena):
    hunter = arena.rules_hunters[0]
    assert not arena.collision_handler.handle_projectile_enemy_collisions(
        shot_at(hunter, 'enemy'), arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
        arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
        anemones=arena.anemones, rules_hunters=arena.rules_hunters)
    assert hunter.hit_points == RULES_HUNTER_HIT_POINTS


def test_killing_it_with_a_player_shot_feeds_the_level_complete_portrait(arena):
    from rendering.enemy_death_portrait import EnemyDeathPortrait
    hunter = arena.rules_hunters[0]
    hunter.hit_points = 1
    arena.collision_handler.handle_projectile_enemy_collisions(
        shot_at(hunter), arena.enemies, arena.replay_enemies, arena.flockers, arena.flighthouses,
        arena.split_bosses, arena.mother_bosses, arena.babies, arena.eggs, arena.powerup_crystals,
        anemones=arena.anemones, rules_hunters=arena.rules_hunters)
    assert arena.scoring.enemies_destroyed >= 1
    portrait = EnemyDeathPortrait(arena.collision_handler.last_player_kill, 20)
    portrait.update(5.0)


def test_the_level_cannot_be_finished_while_it_lives(arena):
    hunter = arena.rules_hunters[0]
    assert any(e is hunter for e in arena.entity_manager.get_all_active_enemies())
    for other in list(arena.entity_manager.get_all_active_enemies()):
        if other is not hunter:
            other.active = False
    assert list(arena.entity_manager.get_all_active_enemies()) == [hunter]
    hunter.die()
    assert list(arena.entity_manager.get_all_active_enemies()) == []


def test_touching_it_counts_as_an_enemy_collision_for_the_player(arena):
    hunter = arena.rules_hunters[0]
    arena.ship.x, arena.ship.y = hunter.x, hunter.y
    arena.ship.shield_active = False
    before = arena.scoring.enemy_collisions
    arena._fly_rules_hunters(1.0)
    assert arena.scoring.enemy_collisions > before


def test_flying_with_the_player_inactive_does_not_crash(arena):
    arena.ship.active = False
    for _ in range(20):
        arena._fly_rules_hunters(1.0)


def test_its_shots_join_the_games_projectiles(arena):
    hunter = arena.rules_hunters[0]
    hunter.flight.fly = lambda dt: [shot_at(hunter, 'enemy')]
    before = len(arena.projectiles)
    arena._fly_rules_hunters(1.0)
    assert len(arena.projectiles) == before + 1


def test_a_level_with_no_room_for_it_skips_it_and_stays_playable(arena):
    arena.entity_manager.rules_hunters.clear()
    arena._spawn_rules_hunters([])                      # no valid spot at all
    assert arena.rules_hunters == []
    arena._spawn_rules_hunters([(arena.ship.x, arena.ship.y)])    # a spot, but on top of the player's start
    assert len(arena.rules_hunters) <= 1                # placed or skipped, never an exception


def test_it_is_drawn_while_it_lives_and_its_death_is_animated(arena):
    pygame.init()
    screen = pygame.Surface((1352, 878))
    hunter = arena.rules_hunters[0]
    hunter.x, hunter.y = 600.0, 400.0
    arena.draw_rules_hunters(screen)
    assert any(screen.get_at((x, y))[:3] != (0, 0, 0)
               for x in range(560, 640) for y in range(360, 440))
    hunter.die()
    screen.fill((0, 0, 0))
    arena.entity_manager.draw_dying(screen)
    assert any(screen.get_at((x, y))[:3] != (0, 0, 0)
               for x in range(540, 660) for y in range(340, 460))
```

- [ ] **Step 3: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_rules_hunter_game.py -q 2>&1 | tail -6`
Expected: errors, `AttributeError: 'Game' object has no attribute 'rules_hunters'`.

- [ ] **Step 4: Collision handler**

In `game_handlers/collision_handler.py`, add `'RulesHunter'` to the typing imports block if one exists for the other classes, add a keyword parameter `rules_hunters: Optional[List['RulesHunter']] = None` to the end of `handle_projectile_enemy_collisions` (after `jev_beacon_allowed`), and insert this block immediately after the "projectile-Mother Boss collision" loop (before "projectile-baby"):

```python
        # Check projectile-Rules hunter collision: it takes hits like a boss and leaves no crystal
        for rules_hunter in rules_hunters or ():
            if rules_hunter.active and projectile.active:
                if projectile.check_circle_collision(rules_hunter.get_pos(), rules_hunter.radius):
                    if rules_hunter.take_damage():
                        rules_hunter.die()
                        self.sound_manager.play_enemy_destroy()
                        self._record_projectile_kill(projectile, rules_hunter)
                    return True  # Projectile destroyed
```

Also document the new parameter in the docstring (`rules_hunters: List of Rules hunters (optional).`).

- [ ] **Step 5: Game**

In `game.py`:

1. Imports (with the other entity and hunter imports): `from entities.rules_hunter import RulesHunter`, `from hunter.surroundings import ProtagonistSurroundings` (add to the existing `GameSurroundings` import if there is one), `from hunter.rules_pilot import RulesClient` (add to the existing rules-pilot import), and `PilotWorker` is already imported.
2. Class attribute and property. Add to the `Game` class body near `hunter`:

```python
    # How a Rules hunter's pilot worker is made. None: a threaded one answering on the real clock. The lab sets an
    # instance attribute to give a synchronous worker on its own clock.
    _rules_worker_factory = None

    @property
    def rules_hunters(self):
        """The level's Rules hunters (the entity manager's list)."""
        return self.entity_manager.rules_hunters

    def protagonist(self):
        """Whom the Rules hunters hunt: the player's ship. (The lab replaces this with the hunter.)"""
        return self.ship

    def _make_rules_worker(self):
        if self._rules_worker_factory is not None:
            return self._rules_worker_factory()
        return PilotWorker(client_factory=RulesClient)

    def _spawn_rules_hunters(self, spawn_positions):
        """Place the level's Rules hunters on open ground: as far from the player as the maze allows, clear of every
        other enemy. A level with no such room skips them (and says so) and stays playable."""
        count = level_config.get_level_rules_hunter_count(self.level)
        if not count or self.ship is None:
            return
        taken = list(self.entity_manager.get_all_enemy_positions())
        start = (self.ship.x, self.ship.y)
        clear = 2.0 * config.SHIP_SIZE * 2
        candidates = sorted(
            (p for p in spawn_positions
             if all(math.hypot(p[0] - x, p[1] - y) > clear for x, y in taken)),
            key=lambda p: -math.hypot(p[0] - start[0], p[1] - start[1]))
        for pos in candidates[:count]:
            self.rules_hunters.append(RulesHunter(pos, self._make_rules_worker(), ProtagonistSurroundings(self)))
        if len(self.rules_hunters) < count:
            logging.getLogger(__name__).warning(
                'Level %d: room for %d of %d Rules hunters', self.level, len(self.rules_hunters), count)

    def _fly_rules_hunters(self, dt):
        """Each Rules hunter looks, decides, fires and flies; touching one hurts the player as touching a boss does."""
        for rules_hunter in self.rules_hunters:
            if not rules_hunter.active:
                continue
            self.projectiles.extend(rules_hunter.fly(dt))
            if self.ship is not None and self.ship.active and not self.ship.is_shield_active():
                if self.ship.check_circle_collision(rules_hunter.get_pos(), rules_hunter.radius, rules_hunter):
                    self.scoring.record_enemy_collision()

    def _close_rules_hunters(self):
        """Stop every Rules hunter's pilot and worker (a level ends, restarts, or the game closes)."""
        for rules_hunter in self.rules_hunters:
            rules_hunter.close()

    def draw_rules_hunters(self, screen):
        for rules_hunter in self.rules_hunters:
            if rules_hunter.active:
                rules_hunter.draw(screen)
```

3. In `start_level`, at the very top (before the entity lists are cleared or rebuilt) call `self._close_rules_hunters()`. Add `+ level_config.get_level_rules_hunter_count(self.level)` to the `get_valid_spawn_positions(...)` count expression, and call `self._spawn_rules_hunters(spawn_positions)` immediately after the `self.spawn_manager.spawn_all_enemies(...)` call.
4. In the update block, add `self._fly_rules_hunters(dt)` immediately before `self.entity_manager.update_dying(dt)`.
5. In the projectile loop, add `rules_hunters=self.rules_hunters` to the `handle_projectile_enemy_collisions(` call.
6. In the draw block, after the "Draw Mother Boss enemies" loop, add `self.draw_rules_hunters(self.screen)`.
7. In `run`'s `finally:` block, add `self._close_rules_hunters()` next to `self._close_hunter()`.

If the `game` test fixture's `Game.__new__` object lacks something these methods read (it already has `entity_manager`, `ship` set by `start_level`, `scoring`, `collision_handler`, `projectiles`), the property and class attribute above mean no fixture change is needed.

- [ ] **Step 6: Run the tests**

Run: `venv/bin/python -m pytest tests/test_rules_hunter_game.py tests/test_rules_hunter.py tests/test_rules_hunter_level.py -q 2>&1 | tail -15`
Expected: pass. If `start_level` in the fixture game fails for a reason unrelated to this change (the fixture is minimal), copy the setup that `tests/test_outer_walls.py::_play` uses (`game.start_level(); game.state = config.STATE_PLAYING; ...`) into the `arena` fixture.

- [ ] **Step 7: Regression run, then commit**

Run: `venv/bin/python -m pytest tests -q 2>&1 | tail -8`
Expected: only the known random duel-spawn failures and tests that assume the Jev default pilot (local setting).

```bash
git add game.py game_handlers/collision_handler.py tests/test_rules_hunter_game.py
git commit -m "feat: Rules hunters in the game: spawn, fly, take hits, draw, close

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The training harness: protagonist, worker, bounty

**Files:**
- Modify: `experiments/harness.py`, `experiments/rollout.py`
- Test: `tests/test_rules_hunter_training.py`; update `tests/test_experiment_rollout.py` (`_Counter` gains `rules_beaten = False`, event rows gain a column)

**Interfaces:**
- Consumes: `Game._rules_worker_factory`, `Game.protagonist`, `Game._close_rules_hunters`, `Game.rules_hunters`.
- Produces:
  - `EpisodeResult.rules_hunters: int = 0` and `EpisodeResult.rules_beaten: bool = False`.
  - `EventCounter.rules_beaten: bool`.
  - `RolloutRecorder(..., rules_bounty=0.0)`; events gain a tenth column (the bounty step); `fly_rollout(..., rules_bounty=0.0)` returns `'rules_arena': bool` and `'rules_beaten': bool`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rules_hunter_training.py
import numpy as np
import pytest

import level_config
from experiments import rollout
from experiments.harness import run_episode
from hunter.senses import SENSE_SIZE


@pytest.fixture(autouse=True)
def one_rules_hunter(monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_rules_hunter_count', lambda level: 1 if level == 13 else 0)


def test_in_training_the_rules_hunter_hunts_the_hunter_not_the_parked_player():
    seen = []

    def trace(t, game, hunter):
        seen.append((game.protagonist() is hunter, [e for e in game.rules_hunters[0].surroundings.enemies()]))
    result = run_episode(13, 0, horizon=2.0, pursue_hunter=True, trace=trace)
    assert result.rules_hunters == 1
    assert seen and all(is_hunter for is_hunter, _ in seen)
    assert all(len(foes) == 1 for _, foes in seen)


def test_an_episode_on_another_level_has_no_rules_hunter():
    assert run_episode(14, 0, horizon=2.0, pursue_hunter=True).rules_hunters == 0


def test_destroying_it_marks_the_episode_rules_beaten():
    def kill_it(t, game, hunter):
        if t > 0.5:
            for rules_hunter in game.rules_hunters:
                rules_hunter.die()
    result = run_episode(13, 0, horizon=3.0, pursue_hunter=True, trace=kill_it)
    assert result.rules_beaten and result.rules_hunters == 1


def test_an_episode_it_survives_is_not_rules_beaten():
    result = run_episode(13, 0, horizon=2.0, pursue_hunter=True)
    assert result.rules_hunters == 1 and not result.rules_beaten


def test_the_lab_overrides_do_not_outlive_the_episode():
    run_episode(13, 0, horizon=1.0, pursue_hunter=True)
    from experiments import harness
    game = harness._game
    assert '_rules_worker_factory' not in game.__dict__ and 'protagonist' not in game.__dict__


class _Counter:
    kills = wall_impulse = hits_taken = spawned = powerups = 0
    idle_seconds = 0.0
    died = False
    rules_beaten = False


def _bounty_rewards(beaten_at, bounty, steps=4):
    recorder = rollout.RolloutRecorder(6, rules_bounty=bounty)
    recorder._start_enemies = 1
    for step in range(steps):
        recorder.senses.append(np.zeros(SENSE_SIZE, np.float32))
        recorder.controls.append((1, 0, 0))
        recorder._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0])
        counter = _Counter()
        counter.rules_beaten = beaten_at is not None and step >= beaten_at
        recorder.counted(counter, step / 10.0)
    return recorder.arrays()[2]


def test_destroying_it_pays_the_bounty_once_in_the_step_it_happens():
    assert _bounty_rewards(2, 50.0).tolist() == pytest.approx([0.0, 0.0, 50.0, 0.0])


def test_no_bounty_without_a_win_and_none_by_default():
    assert not _bounty_rewards(None, 50.0).any()
    assert not _bounty_rewards(2, 0.0).any()


def test_a_rollout_reports_the_arena_and_the_win(monkeypatch, tmp_path):
    from experiments.student import StudentSpec
    from hunter.neural.policy import random_policy
    path = tmp_path / 'w.npz'
    random_policy(0).save(path)
    spec = StudentSpec(weights=str(path), sample_seed=1)
    flown = rollout.fly_rollout(13, 300, spec, horizon=3.0, rules_bounty=50.0)
    assert flown['rules_arena'] is True and flown['rules_beaten'] is False
    other = rollout.fly_rollout(14, 300, spec, horizon=3.0)
    assert other['rules_arena'] is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_rules_hunter_training.py -q 2>&1 | tail -8`
Expected: failures (`AttributeError: ... 'rules_hunters'`).

- [ ] **Step 3: Harness**

In `experiments/harness.py`:

1. `EpisodeResult`: add after `wall_impulse`:

```python
    rules_hunters: int = 0  # Rules hunters on the level
    rules_beaten: bool = False  # every one of them was destroyed
```

2. `EventCounter.__init__`: add `self.rules_beaten = False  # every Rules hunter was destroyed`.
3. Find `_OVERRIDDEN` and add `'_rules_worker_factory'` and `'protagonist'` to it.
4. In `_run_episode`, immediately before `game.start_level()` add:

```python
    # A Rules hunter's pilot answers synchronously on the episode clock, like the hunter's own
    game._rules_worker_factory = lambda: SyncWorker(params, clock)
```

5. After the `flight = HunterFlight(...)` / `hunter = flight.ship` lines, add:

```python
    # In the lab a Rules hunter hunts the hunter, not the parked player
    game.protagonist = lambda: hunter
```

6. Before the `for frame in range(...)` loop add `rules_total = len(game.rules_hunters)`. Inside the loop, right after the `counter.died` handling, add:

```python
        if rules_total and not counter.rules_beaten and not any(r.active for r in game.rules_hunters):
            counter.rules_beaten = True
```

7. After the loop, before `game._close_hunter()`, add `game._close_rules_hunters()`. In the `EpisodeResult(...)` construction add `rules_hunters=rules_total, rules_beaten=counter.rules_beaten` as trailing keyword arguments.

- [ ] **Step 4: Recorder and rollout**

In `experiments/rollout.py`:

1. `RolloutRecorder.__init__`: add parameter `rules_bounty=0.0` (after `death_penalty`), store `self.rules_bounty = rules_bounty` and `self._rules_paid = False`.
2. Every `self._events.append([...])` row gets a tenth element `0`; the comment listing the columns gains `, rules bounty`. Change `reshape(n, 9)` to `reshape(n, 10)`.
3. In `counted`, after the death handling:

```python
        if getattr(counter, 'rules_beaten', False) and not self._rules_paid:
            self._events[-1][9] = 1        # the step in which the last Rules hunter was destroyed
            self._rules_paid = True
```

4. In `arrays`, add `+ self.rules_bounty * events[:, 9]` to the reward expression.
5. `fly_rollout`: add parameter `rules_bounty=0.0` and pass it to `RolloutRecorder(...)`; add to the returned dict `'rules_arena': result.rules_hunters > 0` and `'rules_beaten': result.rules_beaten`.

- [ ] **Step 5: Update the existing rollout tests for the new column**

In `tests/test_experiment_rollout.py`: add `rules_beaten = False` to `_Counter`; change every event row `[0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0]` or `[..., 2, 0.0, 0]` to carry a trailing extra `0` (ten elements).

- [ ] **Step 6: Run the tests**

Run: `venv/bin/python -m pytest tests/test_rules_hunter_training.py tests/test_experiment_rollout.py tests/test_experiment_harness.py tests/test_ppo_loop.py tests/test_ppo_neural.py -q 2>&1 | tail -10`
Expected: pass. Episodes on level 13 now include a Rules hunter only because the autouse fixture patches the count; no other test sees one.

- [ ] **Step 7: Commit**

```bash
git add experiments/harness.py experiments/rollout.py tests/test_rules_hunter_training.py tests/test_experiment_rollout.py
git commit -m "feat: training episodes with a Rules hunter: it hunts the hunter, and beating it pays a bounty

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Training flags, logging and the dashboard

**Files:**
- Modify: `tools/ppo_neural.py`, `.astrovoid-local/neural/rl/page.html` (git-ignored: edit it, do not commit it)
- Test: `tests/test_rules_share.py`

**Interfaces:**
- Consumes: `fly_rollout(..., rules_bounty=...)`, and the dicts' `'rules_arena'` / `'rules_beaten'` keys (read with `.get`, so older fake rollouts still work).
- Produces:
  - `make_jobs(iteration, count, weights, decision_frames, turn_rate, rules_share=0.0)`.
  - `train_rl(..., rules_share=0.0)`.
  - CLI flags `--rules-share` (default 0.25) and `--rules-bounty` (default 50.0).
  - Log fields `rules_beaten` and `rules_episodes`; a "Rules hunter destroyed" row in `config.json`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rules_share.py
from experiments.run import TUNE_LEVELS
from tools import ppo_neural as ppo

RULES_LEVEL = 25


def levels(jobs):
    return [job[0] for job in jobs]


def test_without_a_share_the_levels_cycle_as_before():
    jobs = ppo.make_jobs(0, len(TUNE_LEVELS) * 2, 'w.npz', 6, 1.0)
    assert levels(jobs) == list(TUNE_LEVELS) * 2


def test_a_share_of_the_episodes_fly_the_rules_level_and_the_rest_never_do():
    jobs = ppo.make_jobs(3, 100, 'w.npz', 6, 1.0, rules_share=0.25)
    flown = levels(jobs)
    assert flown.count(RULES_LEVEL) == 25
    others = [level for level in flown if level != RULES_LEVEL]
    assert RULES_LEVEL not in others and set(others) <= set(TUNE_LEVELS)


def test_the_share_is_spread_through_the_batch_not_bunched():
    flown = levels(ppo.make_jobs(0, 40, 'w.npz', 6, 1.0, rules_share=0.25))
    gaps = [i for i, level in enumerate(flown) if level == RULES_LEVEL]
    assert gaps and all(b - a in (3, 4, 5) for a, b in zip(gaps, gaps[1:]))


def test_a_full_share_is_all_rules_level_episodes():
    assert set(levels(ppo.make_jobs(0, 12, 'w.npz', 6, 1.0, rules_share=1.0))) == {RULES_LEVEL}


def test_the_reward_summary_lists_the_bounty_only_when_there_is_one():
    from argparse import Namespace
    base = dict(powerup_reward=0.0, upgrade_bonus=0.0, wall_scale=1.0, hit_scale=1.0, speed_penalty=0.0,
                still_penalty=0.0, still_speed=0.3, turn_change_penalty=0.0, reversal_penalty=0.0,
                death_penalty=0.0, health=0, rules_bounty=50.0)
    rows = {row['name']: row for row in ppo.reward_summary(Namespace(**base))}
    assert rows['Rules hunter destroyed']['sign'] == '+' and rows['Rules hunter destroyed']['value'] == 50.0
    base['rules_bounty'] = 0.0
    assert 'Rules hunter destroyed' not in {row['name'] for row in ppo.reward_summary(Namespace(**base))}
```

- [ ] **Step 2: Run to verify they fail**

Run: `venv/bin/python -m pytest tests/test_rules_share.py -q 2>&1 | tail -6`
Expected: failures (`unexpected keyword argument 'rules_share'`).

- [ ] **Step 3: `make_jobs` and `train_rl`**

Replace `make_jobs` in `tools/ppo_neural.py` with:

```python
RULES_LEVEL = 25          # the level with a Rules hunter on it (levels/25.json)


def make_jobs(iteration, count, weights, decision_frames, turn_rate, rules_share=0.0):
    """One job per episode: the training levels in turn, with `rules_share` of the episodes (spread evenly through
    the batch) flown on the Rules hunter's level and the other levels never including it."""
    from experiments.run import TUNE_LEVELS
    from experiments.student import StudentSpec
    others = tuple(level for level in TUNE_LEVELS if level != RULES_LEVEL)
    jobs = []
    for i in range(count):
        n = iteration * count + i
        spec = StudentSpec(weights=str(weights), decision_frames=decision_frames, turn_rate=turn_rate,
                           greedy=False, sample_seed=n)
        if rules_share > 0.0:
            rules_episode = int((n + 1) * rules_share + 1e-9) > int(n * rules_share + 1e-9)
            level = RULES_LEVEL if rules_episode else others[n % len(others)]
        else:
            level = TUNE_LEVELS[n % len(TUNE_LEVELS)]
        jobs.append((level, 300 + n % TRAIN_SEEDS, spec))
    return jobs
```

In `train_rl`, add the parameter `rules_share=0.0` (after `shaping=None`), pass it into `make_jobs(iteration, episodes, current, decision_frames, turn_rate, rules_share)`, and add to the per-iteration stats (next to `deaths_per_episode`):

```python
            arena = [e for e in flown if e.get('rules_arena')]
            stats.update(rules_episodes=len(arena),
                         rules_beaten=float(np.mean([1.0 if e.get('rules_beaten') else 0.0 for e in arena]))
                         if arena else 0.0)
```

(Place the `stats.update(...)` call after the existing `stats.update(iteration=..., ...)` so it is logged with the rest.)

- [ ] **Step 4: Flags, summary and config**

In `main`: add

```python
    parser.add_argument('--rules-share', type=float, default=0.25,
                        help='share of episodes flown on the Rules hunter level (25); 0 keeps the old level cycle')
    parser.add_argument('--rules-bounty', type=float, default=50.0,
                        help='points gained for destroying the Rules hunter in the training reward')
```

pass `rules_share=args.rules_share` to `train_rl(...)`, and add `'rules_bounty': args.rules_bounty` to the `shaping` dict.

In `reward_summary`, append to `rows` before the closing bracket:

```python
            ('Rules hunter destroyed', '+', args.rules_bounty, 'points, on top of its share of the kill reward'),
```

In `write_run_config`, add `'rules_share': args.rules_share` inside the `'episode'` dict.

- [ ] **Step 5: Dashboard (git-ignored)**

In `.astrovoid-local/neural/rl/page.html` add, before the "Kills per minute" chart line:

```javascript
   chart({title:'Rules hunter beaten',sub:'Higher is better. Share of Rules-hunter episodes in which it is destroyed.',key:'rules_beaten'}),
```

and, in the Episodes card text, after the health sentence:

```javascript
${e.rules_share?` ${Math.round(e.rules_share*100)}% of episodes are fought against a Rules hunter, which hunts only the hunter.`:''}
```

- [ ] **Step 6: Run the tests and commit**

Run: `venv/bin/python -m pytest tests/test_rules_share.py tests/test_ppo_loop.py tests/test_ppo_neural.py -q 2>&1 | tail -6`
Expected: pass.

```bash
git add tools/ppo_neural.py tests/test_rules_share.py
git commit -m "feat: training flags for the Rules hunter: --rules-share, --rules-bounty, rules_beaten logged

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Documentation and the final check

**Files:**
- Modify: `README.md`, `levels/README.md`

- [ ] **Step 1: README**

In the level table in `README.md` (the `### Level Progression` section), add after the `| 24 | ... |` row's following paragraph, in the "From level 25" section, a bullet:

```markdown
- **Level 25 is a boss level**: the **Rules hunter**, the Rules pilot's hunter ship flown as an enemy, in a dense 26-cell maze with two aggressive enemies and two flocker swarms. It hunts only you, takes 12 hits, and leaves no crystal. The exit stays locked until every enemy is dead, ammo is infinite and no Jev beacon appears. The every-sixth-level boss rotation from level 30 is unchanged.
```

In the Entities/enemies list (where **Split Boss** and **Mother Boss** are described) add:

```markdown
- **Rules hunter**: The Rules pilot's hunter ship, flown as an enemy (`entities/rules_hunter.py`). It sees only its target (you, or in training the neural hunter) and fires only at it. Requires 12 hits.
```

- [ ] **Step 2: Level file docs**

In `levels/README.md`, add `"rules_hunter": 0` to the example `enemies` block and a bullet under it:

```markdown
- **rules_hunter**: Rules hunters on the level (the Rules pilot's hunter ship as an enemy, hostile only to the player). A level with one is a boss level. Level 25 has one.
```

and change the "Boss levels" section's first sentence to `A level with at least one split_boss, mother_boss or rules_hunter is a boss level, whatever its number:`.

Also fix the sentence "Levels from 25 have no file" at the top to: `Levels 1 to 24 are a designed arc ... Levels from 25 have no file except level 25 (the Rules hunter boss) and come from the formulas in level_rules.py.`

- [ ] **Step 3: Full run**

Run: `venv/bin/python -m pytest tests -q 2>&1 | tail -10`
Expected: pass, apart from the random duel-spawn tests and tests that assume the Jev default pilot while the local `"neural"` setting is in place.

- [ ] **Step 4: Watch it work (manual, real display)**

Run `WINDOWED=1 START_LEVEL=25 ./run.sh` and confirm: a red hunter ship with a health bar appears far from you and hunts you; your shots reduce its bar; 12 hits destroy it with an expanding ring; the exit opens only after every enemy is dead; the level-complete screen shows. Report what you saw; if anything is off, do not claim success.

- [ ] **Step 5: Commit**

```bash
git add README.md levels/README.md
git commit -m "docs: the Rules hunter and level 25

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```
