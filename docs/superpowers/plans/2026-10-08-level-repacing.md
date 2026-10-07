# Level Re-pacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the front-loaded, ever-more-crowded level progression with a 24-level designed arc, boss levels with a locked exit, and a bounded endless game from level 25.

**Architecture:** Levels 1–24 are data: one `levels/N.json` each, read by the existing loader in `level_config.py`. Levels 25+ (and any arc level whose file is missing) come from rewritten formulas in `level_rules.py`. `level_config.py` stays the single place the game asks "what is on this level", and gains "is this a boss level" and the new hunter schedule. `game.py` changes in one place: the exit lock.

**Tech Stack:** Python 3.10, pygame 2.6, pytest. Settings live in `config/settings.json` and are exposed as constants by `config.py`.

**Spec:** `docs/superpowers/specs/2026-10-08-level-repacing-design.md`

## Global Constraints

- Run tests with: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest <args>`.
- Three tests fail before this work and are not ours to fix: `tests/test_utils.py::TestReflectVelocity::test_reflect_velocity_perpendicular`, `::test_reflect_velocity_at_angle`, `::test_reflect_velocity_with_bounce_factor`. Every "full suite" step expects exactly those three failures and no others.
- Game-level tests must set the display to 1352x878 (`config.SCREEN_WIDTH`, `config.SCREEN_HEIGHT`); `config/settings.json` says 3840x2160 and the game overwrites it at start-up.
- **Enemy count** means every enemy except bosses and the hunter; anemones are included. `EnemyCounts.total` keeps its existing, narrower meaning: static + patrol + aggressive.
- A **boss level** is a level whose resolved split boss count plus mother boss count is above zero.
- Enemy count cap in endless play: 36. Maze grid cap: 32. Boss level interval: 6. Hunter first level: 4. Speed and damage: +5% per level after level 4, at most 2.5x.
- Scoring, star thresholds, enemy behaviour and rendering do not change.
- Do not add status text near the Jev hunter.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A level file puts a boss on a level that is not a multiple of 6.** The exit locks and no hunter flies, exactly as on level 6. (Tests in Tasks 3 and 4.)
2. **A level file places a hunter on a boss level.** The file wins and the hunter flies. (Test in Task 3.)
3. **`levels_version` in the profiles file is the wrong type** (`"2"`, `null`, `true`, `2.0`). It is treated as old: bests cleared, no crash. (Test in Task 6.)
4. **A very high level (1000).** Enemy count stays at 36, bosses at 3, grid at 32, speed and damage at 2.5x. (Test in Task 2.)
5. **Restarting a boss level after killing the boss.** The exit is locked again on the new attempt. (Test in Task 4.)

## File Structure

| File | Responsibility after this work |
|---|---|
| `level_rules.py` | Formulas for any level without a file: counts, mix, bosses, maze, strength |
| `level_config.py` | Resolve what is on a level (file over formula); boss-level check; hunter schedule |
| `levels/1.json` … `levels/24.json` | The arc |
| `levels/README.md` | Level file format and the real rules |
| `game.py` | Exit lock also holds while a boss lives |
| `profiles.py` | `levels_version` and one-off clearing of bests |
| `config.py`, `config/settings.json` | New pacing settings; old count settings removed |
| `entities/enemy.py`, `main.py` | Dead `create_enemies` removed (it calls formulas that go away) |
| `tests/test_level_pacing.py` | Formula tests (new) |
| `tests/test_level_arc.py` | Arc file rules, hunter schedule on real files, spawn room (new) |
| `tests/test_boss_levels.py` | Exit lock and boss-level behaviour in the real game (new) |

---

### Task 1: Commit the start-clearance work already in the tree

The working tree holds finished, tested, uncommitted work from earlier the same day (300 px start clearance, 600 px fire-range cap). The spec assumes it. Commit it on its own so later commits are clean.

**Files:**
- Already modified: `config.py`, `config/settings.json`, `game.py`, `level_rules.py`, `maze/generator.py`
- Already created: `tests/test_start_clearance.py`

- [ ] **Step 1: Confirm the tree holds only that work**

Run: `git status --short`
Expected: exactly ` M config.py`, ` M config/settings.json`, ` M game.py`, ` M level_rules.py`, ` M maze/generator.py`, `?? tests/test_start_clearance.py`, plus this plan file if it is not yet committed.

- [ ] **Step 2: Run its tests**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_start_clearance.py -q`
Expected: `30 passed`

- [ ] **Step 3: Commit**

```bash
git add config.py config/settings.json game.py level_rules.py maze/generator.py tests/test_start_clearance.py
git commit -m "feat: clear space around the player at level start and cap enemy fire range

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: New level formulas and settings

**Files:**
- Create: `tests/test_level_pacing.py`
- Modify: `level_rules.py` (count functions, `get_enemy_speed`, `get_enemy_damage`, `get_enemy_counts`, `get_maze_complexity`, `get_maze_grid_size`)
- Modify: `config.py`, `config/settings.json`
- Modify: `level_config.py:12` (import line), `level_config.py` `get_level_egg_count`
- Modify: `entities/enemy.py` (delete `create_enemies`), `game.py:13`, `main.py:43` (its imports)
- Modify: `tests/test_anemone_levels.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces, all in `level_rules`:
  - `is_boss_level(level: int) -> bool` — by formula only (`level % 6 == 0`)
  - `get_boss_counts(level: int) -> Tuple[int, int]` — `(split, mother)`
  - `get_split_boss_count(level: int) -> int`, `get_mother_boss_count(level: int) -> int`
  - `get_enemy_count(level: int) -> int` — the spec's enemy count
  - `get_enemy_mix(level: int) -> Dict[str, int]` — keys `static, patrol, aggressive, replay, flocker, flighthouse, egg, anemone`
  - `get_enemy_counts(level: int) -> EnemyCounts` (unchanged signature)
  - `get_anemone_count(level: int) -> int` (unchanged signature)
  - `get_maze_complexity(level: int) -> MazeComplexity`, `get_maze_grid_size(level: int) -> int` (unchanged signatures)
- Produces, in `config`: `MAX_ENEMY_COUNT`, `BOSS_LEVEL_INTERVAL`, `ENEMY_SPEED_GROWTH`, `ENEMY_SPEED_CEILING`, `ENEMY_DAMAGE_GROWTH`, `ENEMY_DAMAGE_CEILING`.
- Removes: `level_rules.get_enemy_type_distribution`, `get_replay_enemy_count`, `get_flocker_count`, `get_flighthouse_count`, `get_egg_count`; `entities.enemy.create_enemies`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_level_pacing.py`:

```python
"""Formulas for levels that have no level file: the endless game and the safety net below it."""
import pytest

import config
import level_rules
from maze.config import MazeComplexity


def mix(level):
    return level_rules.get_enemy_mix(level)


@pytest.mark.parametrize('level, expected', [
    (25, 25), (26, 25), (27, 26), (29, 27), (31, 28), (35, 30), (47, 36), (49, 36), (1000, 36)])
def test_endless_enemy_count_rises_every_second_level_and_stops(level, expected):
    assert level_rules.get_enemy_count(level) == expected
    assert sum(mix(level).values()) == expected


def test_endless_mix_starts_from_the_end_of_the_arc():
    assert mix(25) == {'static': 4, 'patrol': 3, 'aggressive': 5, 'replay': 3, 'flocker': 3,
                       'flighthouse': 2, 'egg': 1, 'anemone': 4}


def test_endless_mix_grows_one_type_at_a_time():
    assert mix(35) == {'static': 5, 'patrol': 4, 'aggressive': 5, 'replay': 4, 'flocker': 4,
                       'flighthouse': 2, 'egg': 1, 'anemone': 5}


def test_endless_mix_at_the_cap_is_balanced():
    assert mix(47) == {'static': 6, 'patrol': 5, 'aggressive': 6, 'replay': 5, 'flocker': 5,
                       'flighthouse': 2, 'egg': 1, 'anemone': 6}
    assert mix(1000) == mix(47)


def test_enemy_counts_carry_the_mix():
    counts = level_rules.get_enemy_counts(47)
    assert (counts.static, counts.patrol, counts.aggressive) == (6, 5, 6)
    assert counts.total == 17  # static + patrol + aggressive, as the spawner expects
    assert (counts.replay, counts.flocker, counts.flighthouse, counts.egg, counts.anemone) == (5, 5, 2, 1, 6)


@pytest.mark.parametrize('level', [25, 29, 31, 47, 1001])
def test_ordinary_endless_levels_have_no_bosses(level):
    assert not level_rules.is_boss_level(level)
    assert level_rules.get_boss_counts(level) == (0, 0)


@pytest.mark.parametrize('level, split, mother', [
    (30, 2, 0), (36, 0, 1), (42, 1, 1),
    (48, 3, 0), (54, 0, 2), (60, 2, 1),
    (66, 3, 0), (72, 0, 3), (78, 2, 1), (996, 3, 0)])
def test_every_sixth_level_is_a_boss_level_and_the_bosses_build_up_to_three(level, split, mother):
    assert level_rules.is_boss_level(level)
    assert level_rules.get_boss_counts(level) == (split, mother)
    assert level_rules.get_split_boss_count(level) == split
    assert level_rules.get_mother_boss_count(level) == mother


@pytest.mark.parametrize('level, escort', [
    (30, {'flocker': 6}), (36, {'egg': 4}), (42, {'replay': 2, 'flocker': 2, 'egg': 2})])
def test_boss_levels_carry_only_their_escort(level, escort):
    assert {name: n for name, n in mix(level).items() if n} == escort
    assert level_rules.get_enemy_count(level) == sum(escort.values())


def test_boss_levels_are_small_open_arenas():
    assert level_rules.get_maze_grid_size(30) == 16
    assert level_rules.get_maze_complexity(30) == MazeComplexity.EMPTY


@pytest.mark.parametrize('level, grid, complexity', [
    (1, 10, MazeComplexity.EMPTY), (2, 12, MazeComplexity.SIMPLE), (5, 18, MazeComplexity.SIMPLE),
    (7, 22, MazeComplexity.NORMAL), (11, 30, MazeComplexity.NORMAL), (13, 32, MazeComplexity.COMPLEX),
    (17, 32, MazeComplexity.COMPLEX), (19, 32, MazeComplexity.EXTREME), (1000, 32, MazeComplexity.EXTREME)])
def test_ordinary_mazes_grow_steadily_and_stop_at_32(level, grid, complexity):
    assert level_rules.get_maze_grid_size(level) == grid
    assert level_rules.get_maze_complexity(level) == complexity


@pytest.mark.parametrize('level', [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 13, 17, 23])
def test_an_arc_level_without_a_file_uses_only_types_already_introduced(level):
    first = {'static': 1, 'patrol': 2, 'aggressive': 3, 'replay': 5, 'anemone': 7,
             'flocker': 8, 'flighthouse': 10, 'egg': 13}
    level_mix = mix(level)
    assert sum(level_mix.values()) == min(24, 3 + level)
    assert all(level >= first[name] for name, n in level_mix.items() if n)


def test_level_one_without_a_file_is_four_static_enemies():
    assert {name: n for name, n in mix(1).items() if n} == {'static': 4}


def test_speed_grows_five_percent_a_level_and_stops_at_two_and_a_half_times():
    base = config.ENEMY_AGGRESSIVE_SPEED
    assert level_rules.get_enemy_speed(4, 'aggressive') == base
    assert level_rules.get_enemy_speed(5, 'aggressive') == base
    assert level_rules.get_enemy_speed(15, 'aggressive') == pytest.approx(base * 1.5)
    assert level_rules.get_enemy_speed(35, 'aggressive') == pytest.approx(base * 2.5)
    assert level_rules.get_enemy_speed(1000, 'aggressive') == pytest.approx(base * 2.5)
    assert level_rules.get_enemy_speed(1000, 'patrol') == pytest.approx(config.ENEMY_PATROL_SPEED * 2.5)
    assert level_rules.get_enemy_speed(1000, 'static') == 0.0


def test_damage_grows_five_percent_a_level_and_stops_at_two_and_a_half_times():
    base = config.ENEMY_DAMAGE
    assert level_rules.get_enemy_damage(4) == base
    assert level_rules.get_enemy_damage(15) == int(base * 1.5)
    assert level_rules.get_enemy_damage(35) == int(base * 2.5)
    assert level_rules.get_enemy_damage(1000) == int(base * 2.5)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_level_pacing.py -q`
Expected: failures. Most with `AttributeError: module 'level_rules' has no attribute 'get_enemy_mix'` / `'is_boss_level'` / `'get_boss_counts'`; the speed, damage and maze tests with wrong values (for example `get_maze_grid_size(1000)` is 40).

- [ ] **Step 3: Change the settings**

In `config/settings.json`, replace the `"difficulty"` block with:

```json
  "difficulty": {
    "baseMazeSize": 10,
    "mazeSizeIncrement": 2,
    "maxMazeSize": 32,
    "maxEnemyCount": 36,
    "bossLevelInterval": 6,
    "enemySpeedGrowth": 0.05,
    "enemySpeedCeiling": 2.5,
    "enemyDamageGrowth": 0.05,
    "enemyDamageCeiling": 2.5,
    "tutorialLevels": 4
  },
```

In the same file:
- delete the `"baseCount"` and `"scaleFactor"` lines from `"replayEnemy"`, `"flockerEnemy"`, `"flighthouseEnemy"`, `"splitBoss"`, `"motherBoss"` and `"egg"`;
- in `"anemone"`, set `"firstLevel": 7` and delete `"baseCount"`, `"levelsPerExtra"` and `"maxCount"`.

After editing, check the file still parses: `python -c "import json; json.load(open('config/settings.json'))"` (a deleted last line of a block leaves a trailing comma on the line above; remove it).

In `config.py`:

Replace the `DifficultySettings` dataclass with:

```python
@dataclass
class DifficultySettings:
    baseMazeSize: int
    mazeSizeIncrement: int
    maxMazeSize: int
    maxEnemyCount: int
    bossLevelInterval: int
    enemySpeedGrowth: float
    enemySpeedCeiling: float
    enemyDamageGrowth: float
    enemyDamageCeiling: float
    tutorialLevels: int
```

Replace the two lines `BASE_ENEMY_COUNT = ...` and `ENEMY_COUNT_INCREMENT = ...` with:

```python
# Enemies on an endless level, not counting bosses or the hunter, never exceed this
MAX_ENEMY_COUNT = SETTINGS.difficulty.maxEnemyCount
# Every Nth level without a level file is a boss level
BOSS_LEVEL_INTERVAL = SETTINGS.difficulty.bossLevelInterval
# Speed and damage grow by this share per level after the tutorial levels, up to the ceiling
ENEMY_SPEED_GROWTH = SETTINGS.difficulty.enemySpeedGrowth
ENEMY_SPEED_CEILING = SETTINGS.difficulty.enemySpeedCeiling
ENEMY_DAMAGE_GROWTH = SETTINGS.difficulty.enemyDamageGrowth
ENEMY_DAMAGE_CEILING = SETTINGS.difficulty.enemyDamageCeiling
```

Then remove every trace of the deleted settings from `config.py`:
- the `baseCount: int` and `scaleFactor: float` fields from `ReplayEnemySettings`, `FlockerEnemySettings`, `FlighthouseEnemySettings`, `SplitBossSettings`, `MotherBossSettings` and `EggSettings`;
- from `AnemoneSettings`: `baseCount`, `levelsPerExtra`, `maxCount`;
- the `baseCount=raw[...]` and `scaleFactor=raw[...]` keyword arguments in the settings loader (for `replayEnemy`, `flockerEnemy`, `flighthouseEnemy`, `egg`);
- the constants `REPLAY_ENEMY_BASE_COUNT`, `REPLAY_ENEMY_SCALE_FACTOR`, `FLOCKER_ENEMY_BASE_COUNT`, `FLOCKER_ENEMY_SCALE_FACTOR`, `FLIGHTHOUSE_ENEMY_BASE_COUNT`, `FLIGHTHOUSE_ENEMY_SCALE_FACTOR`, `SPLIT_BOSS_BASE_COUNT`, `SPLIT_BOSS_SCALE_FACTOR`, `MOTHER_BOSS_BASE_COUNT`, `MOTHER_BOSS_SCALE_FACTOR`, `EGG_BASE_COUNT`, `EGG_SCALE_FACTOR`, `ANEMONE_BASE_COUNT`, `ANEMONE_LEVELS_PER_EXTRA`, `ANEMONE_MAX_COUNT`.

Check: `grep -nE "baseCount|scaleFactor|BASE_COUNT|SCALE_FACTOR|levelsPerExtra|LEVELS_PER_EXTRA|ANEMONE_MAX_COUNT|BASE_ENEMY_COUNT|ENEMY_COUNT_INCREMENT" config.py config/settings.json`
Expected: no output.

- [ ] **Step 4: Rewrite the count formulas in `level_rules.py`**

Change the typing import at the top to `from typing import Dict, Tuple` (it already is; keep it).

Delete these functions entirely: `get_enemy_count`, `get_enemy_type_distribution`, `get_replay_enemy_count`, `get_split_boss_count`, `get_flocker_count`, `get_flighthouse_count`, `get_anemone_count`, `get_egg_count`, `get_mother_boss_count`. Keep `anemones_that_fit` and `get_flighthouse_spawn_interval` as they are.

In their place (after the `EnemyStrength` dataclass), add:

```python
# The designed arc: levels 1 to ARC_LEVELS each have a level file. The formulas
# below are what the endless game uses, and a safety net for an arc level whose
# file is missing.
ARC_LEVELS = 24
BOSS_ARENA_SIZE = 16
MAX_BOSSES = 3

# Level each enemy type first appears on (anemones: config.ANEMONE_FIRST_LEVEL)
FIRST_LEVELS = {'static': 1, 'patrol': 2, 'aggressive': 3, 'replay': 5,
                'flocker': 8, 'flighthouse': 10, 'egg': 13}

# Each enemy added beyond the arc goes to the next type in this order, round and round
GROWTH_ORDER = ('aggressive', 'replay', 'flocker', 'static', 'patrol', 'anemone')

# What level 23, the last ordinary level of the arc, carries
ARC_END_MIX = {'static': 4, 'patrol': 3, 'aggressive': 4, 'replay': 3, 'flocker': 3,
               'flighthouse': 2, 'egg': 1, 'anemone': 4}


def first_level(enemy_type: str) -> int:
    """Level an enemy type first appears on."""
    if enemy_type == 'anemone':
        return config.ANEMONE_FIRST_LEVEL
    return FIRST_LEVELS[enemy_type]


def is_boss_level(level: int) -> bool:
    """Whether a level without a level file is a boss level."""
    return level % config.BOSS_LEVEL_INTERVAL == 0


def get_boss_counts(level: int) -> Tuple[int, int]:
    """Get the bosses on a level without a level file.

    Boss levels cycle through split bosses, a mother boss, then both. Each full
    turn of the cycle adds a boss, up to MAX_BOSSES on a level.

    Args:
        level: Current level number (1-based).

    Returns:
        (split boss count, mother boss count); (0, 0) on an ordinary level.
    """
    if not is_boss_level(level):
        return (0, 0)
    # Level 30 opens the first full cycle of the endless game
    cycle = level // config.BOSS_LEVEL_INTERVAL - 5
    kind, turn = cycle % 3, max(0, cycle // 3)
    if kind == 0:
        return (min(MAX_BOSSES, 2 + turn), 0)
    if kind == 1:
        return (0, min(MAX_BOSSES, 1 + turn))
    return (min(MAX_BOSSES - 1, 1 + turn), 1)


def get_split_boss_count(level: int) -> int:
    """Get number of SplitBoss enemies for a level without a level file."""
    return get_boss_counts(level)[0]


def get_mother_boss_count(level: int) -> int:
    """Get number of Mother Boss enemies for a level without a level file."""
    return get_boss_counts(level)[1]


def _boss_escort(level: int) -> Dict[str, int]:
    """Enemies that accompany the bosses on a boss level."""
    split, mother = get_boss_counts(level)
    if split and mother:
        return {'replay': 2, 'flocker': 2, 'egg': 2}
    if mother:
        return {'egg': 4}
    return {'flocker': 6}


def get_enemy_count(level: int) -> int:
    """Get the number of enemies on a level without a level file.

    Bosses and the hunter are not counted. Anemones are.

    Args:
        level: Current level number (1-based).

    Returns:
        The escort on a boss level. Otherwise a number that rises by one a
        level through the arc, then by one every two levels, up to
        config.MAX_ENEMY_COUNT.
    """
    if is_boss_level(level):
        return sum(_boss_escort(level).values())
    arc_end_count = sum(ARC_END_MIX.values())
    if level <= ARC_LEVELS:
        return min(arc_end_count, 3 + level)
    return min(config.MAX_ENEMY_COUNT, arc_end_count + (level - (ARC_LEVELS - 1)) // 2)


def get_enemy_mix(level: int) -> Dict[str, int]:
    """Get how many of each enemy type a level without a level file has.

    Args:
        level: Current level number (1-based).

    Returns:
        Count for each of static, patrol, aggressive, replay, flocker,
        flighthouse, egg and anemone. They add up to get_enemy_count(level).
    """
    mix = dict.fromkeys(ARC_END_MIX, 0)
    if is_boss_level(level):
        mix.update(_boss_escort(level))
        return mix

    count = get_enemy_count(level)
    if level > ARC_LEVELS:
        mix.update(ARC_END_MIX)
        order = GROWTH_ORDER
    else:
        # Only what the player has already met; one flighthouse and one egg once they have
        for enemy_type in ('flighthouse', 'egg'):
            if level >= first_level(enemy_type):
                mix[enemy_type] = 1
        order = [enemy_type for enemy_type in GROWTH_ORDER if level >= first_level(enemy_type)]

    for i in range(count - sum(mix.values())):
        mix[order[i % len(order)]] += 1
    return mix


def get_anemone_count(level: int) -> int:
    """Get number of anemones for a level without a level file."""
    return get_enemy_mix(level)['anemone']
```

Replace `get_enemy_counts` with:

```python
def get_enemy_counts(level: int) -> EnemyCounts:
    """Get complete enemy count configuration for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        EnemyCounts dataclass with all enemy counts.
    """
    mix = get_enemy_mix(level)
    return EnemyCounts(
        total=mix['static'] + mix['patrol'] + mix['aggressive'],
        static=mix['static'],
        patrol=mix['patrol'],
        aggressive=mix['aggressive'],
        replay=mix['replay'],
        flocker=mix['flocker'],
        flighthouse=mix['flighthouse'],
        egg=mix['egg'],
        anemone=mix['anemone']
    )
```

In `get_enemy_speed`, replace the last three lines with:

```python
    effective_level = level - config.TUTORIAL_LEVELS
    speed_multiplier = min(config.ENEMY_SPEED_CEILING, 1.0 + (effective_level - 1) * config.ENEMY_SPEED_GROWTH)
    return base_speed * speed_multiplier
```

In `get_enemy_damage`, replace everything after the tutorial-level `return` with:

```python
    # Base damage from config, scaled by effective level up to a ceiling
    effective_level = level - config.TUTORIAL_LEVELS
    damage_multiplier = min(config.ENEMY_DAMAGE_CEILING, 1.0 + (effective_level - 1) * config.ENEMY_DAMAGE_GROWTH)
    return int(config.ENEMY_DAMAGE * damage_multiplier)
```

Replace the bodies of `get_maze_complexity` and `get_maze_grid_size` (and fix their docstrings to match) with:

```python
def get_maze_complexity(level: int) -> MazeComplexity:
    """Get default maze complexity for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        EMPTY for level 1 and for boss levels (an open arena), then SIMPLE to
        level 5, NORMAL to 11, COMPLEX to 17 and EXTREME after.
    """
    if level == 1 or is_boss_level(level):
        return MazeComplexity.EMPTY
    if level <= 5:
        return MazeComplexity.SIMPLE
    if level <= 11:
        return MazeComplexity.NORMAL
    if level <= 17:
        return MazeComplexity.COMPLEX
    return MazeComplexity.EXTREME


def get_maze_grid_size(level: int) -> int:
    """Get default maze grid size for a level.
    
    Args:
        level: Current level number (1-based).
        
    Returns:
        Grid size (width/height in cells). Maze is always square. Boss levels
        get a small arena; other levels grow by MAZE_SIZE_INCREMENT a level
        up to MAX_MAZE_SIZE.
    """
    if is_boss_level(level):
        return BOSS_ARENA_SIZE
    return min(config.BASE_MAZE_SIZE + (level - 1) * config.MAZE_SIZE_INCREMENT, config.MAX_MAZE_SIZE)
```

(This also removes the three `print(f"Level {level} is ...")` calls.)

- [ ] **Step 5: Fix the callers of what was removed**

`level_config.py` line 12, replace the import with:

```python
from level_rules import EnemyCounts, anemones_that_fit, get_anemone_count, get_enemy_counts, get_split_boss_count
```

`level_config.py`, in `get_level_egg_count`, replace the last line `return get_egg_count(level)` with:

```python
    return get_enemy_counts(level).egg
```

`entities/enemy.py`: delete the whole `create_enemies` function (it starts at `def create_enemies(level: int, spawn_positions: ...)` near line 317 and runs to the end of that function). Nothing calls it. Then remove `create_enemies` from the imports that name it:
- `game.py:13`: `from entities.enemy import Enemy, create_enemies` becomes `from entities.enemy import Enemy`
- `main.py:43`: the same change.

Check: `grep -rnE "create_enemies|get_enemy_type_distribution|get_replay_enemy_count|get_flocker_count|get_flighthouse_count|get_egg_count" --include='*.py' . | grep -v "^./venv"`
Expected: no output. If `entities/enemy.py` is left with unused imports (`level_rules`, `random`) that only `create_enemies` used, remove them; check each with grep before removing.

- [ ] **Step 6: Run the new tests**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_level_pacing.py -q`
Expected: all pass.

- [ ] **Step 7: Bring `tests/test_anemone_levels.py` to the new schedule**

Change the module docstring to `"""Anemones arrive at level 7 and build up slowly; a level file can override the number."""`.

Replace `test_schedule` and its parametrize line with:

```python
@pytest.mark.parametrize('level, expected', [
    (1, 0), (6, 0), (7, 2), (9, 2), (12, 0), (17, 3), (23, 3), (25, 4), (35, 5), (47, 6), (100, 6)])
def test_schedule(level, expected):
    assert get_anemone_count(level) == expected
    assert get_enemy_counts(level).anemone == expected
```

In `test_level_file_without_the_key_uses_the_schedule`, change the last line to:

```python
    assert level_config.get_level_enemy_counts(9).anemone == 2
```

Replace `test_small_mazes_get_fewer_than_the_schedule_asks_for` with:

```python
def test_small_mazes_get_fewer_than_the_schedule_asks_for(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'maze': {'grid_size': 12}})
    assert get_anemone_count(47) == 6
    assert level_config.get_level_anemone_count(47) == 1
    assert level_config.get_level_anemone_count(2) == 0
```

Delete `test_level_four_is_a_gentle_introduction` (it pins the old `levels/4.json`; Task 5 tests the new files).

- [ ] **Step 8: Run the full suite**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q 2>&1 | tail -15`
Expected: only the three `TestReflectVelocity` failures. If another test fails because it pinned an old count, speed or maze size, update that expectation to the new rule and say which test in the commit message. Do not change production code to satisfy an old expectation.

- [ ] **Step 9: Commit**

```bash
git add -A config.py config/settings.json level_rules.py level_config.py entities/enemy.py game.py main.py tests/test_level_pacing.py tests/test_anemone_levels.py
git commit -m "feat: bounded level formulas with boss levels every sixth level

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Boss-level check and hunter schedule

**Files:**
- Modify: `level_config.py` (`level_has_hunter`, new `is_boss_level`)
- Modify: `config.py`, `config/settings.json` (`game.hunterFirstLevel`)
- Modify: `tests/test_hunter_integration.py`
- Test: `tests/test_boss_levels.py` (create)

**Interfaces:**
- Consumes: `level_rules.get_split_boss_count`, `get_mother_boss_count` (through the existing `level_config.get_level_split_boss_count` / `get_level_mother_boss_count`).
- Produces: `level_config.is_boss_level(level: int) -> bool` (file over formula); `level_config.level_has_hunter(level: int) -> bool` with the new rules; `config.HUNTER_FIRST_LEVEL`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_boss_levels.py`:

```python
"""Boss levels: which levels they are, who flies on them, and the locked exit."""
import pytest

import config
import level_config


def level_file(**enemies):
    """A loader that gives every level the same file."""
    return lambda level: {'seed': 1, 'maze': {'complexity': 'empty', 'grid_size': 12},
                          'enemies': {'static': 0, 'patrol': 0, 'aggressive': 0, 'replay': 0, 'flocker': 0,
                                      'flighthouse': 0, 'egg': 0, 'anemone': 0,
                                      'split_boss': 0, 'mother_boss': 0, **enemies}}


def no_level_files(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: None)


def test_without_a_file_every_sixth_level_is_a_boss_level(monkeypatch):
    no_level_files(monkeypatch)
    assert [level for level in range(25, 50) if level_config.is_boss_level(level)] == [30, 36, 42, 48]


@pytest.mark.parametrize('boss', ['split_boss', 'mother_boss'])
def test_a_level_file_with_a_boss_makes_any_level_a_boss_level(monkeypatch, boss):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(**{boss: 1}))
    assert level_config.is_boss_level(7)


def test_a_level_file_without_bosses_makes_a_sixth_level_ordinary(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(static=3))
    assert not level_config.is_boss_level(30)


def test_no_hunter_before_its_first_level(monkeypatch):
    no_level_files(monkeypatch)
    assert [level for level in range(1, 6) if level_config.level_has_hunter(level)] == [4, 5]


def test_no_hunter_on_boss_levels(monkeypatch):
    no_level_files(monkeypatch)
    assert [level for level in range(28, 38) if not level_config.level_has_hunter(level)] == [30, 36]


def test_no_hunter_on_a_boss_level_made_by_a_level_file(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1))
    assert not level_config.level_has_hunter(7)


def test_a_level_file_can_forbid_the_hunter(monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: {'hunter': False})
    assert not level_config.level_has_hunter(9)


def test_a_level_file_can_place_a_hunter_early_or_on_a_boss_level(monkeypatch):
    placed = {'hunter': {'spawn_cell': [4, 4]}}
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: placed)
    assert level_config.level_has_hunter(1)
    monkeypatch.setattr(level_config, 'load_level_config',
                        lambda level: {**level_file(split_boss=1)(level), **placed})
    assert level_config.level_has_hunter(6)


def test_the_hunter_interval_still_applies_from_the_first_level(monkeypatch):
    no_level_files(monkeypatch)
    monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 0)
    assert not level_config.level_has_hunter(9)
    monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 5)
    assert [level for level in range(1, 21) if level_config.level_has_hunter(level)] == [5, 10, 15, 20]
```

- [ ] **Step 2: Run them and watch them fail**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_boss_levels.py -q`
Expected: failures with `AttributeError: module 'level_config' has no attribute 'is_boss_level'`, and the hunter tests failing because a hunter flies on levels 1–3 and on boss levels (and `{'hunter': False}` counts as "place one").

- [ ] **Step 3: Add the setting**

`config/settings.json`, the `"game"` block becomes:

```json
  "game": {
    "criticalWarningThreshold": 20,
    "hunterLevelInterval": 1,
    "hunterFirstLevel": 4
  }
```

`config.py`, add the field to `GameSettings`:

```python
@dataclass
class GameSettings:
    criticalWarningThreshold: int
    hunterLevelInterval: int
    hunterFirstLevel: int
```

and next to `HUNTER_LEVEL_INTERVAL = SETTINGS.game.hunterLevelInterval`:

```python
# No hunter flies before this level
HUNTER_FIRST_LEVEL = SETTINGS.game.hunterFirstLevel
```

- [ ] **Step 4: Implement in `level_config.py`**

Replace `get_level_hunter_config`'s docstring and `level_has_hunter`, and add `is_boss_level` above them:

```python
def is_boss_level(level: int) -> bool:
    """A boss level is any level with a split boss or a mother boss on it."""
    return get_level_split_boss_count(level) + get_level_mother_boss_count(level) > 0


def get_level_hunter_config(level: int):
    """Return the level file's hunter entry: a spawn override, False for no hunter, or None if absent."""
    data = load_level_config(level)
    return data.get('hunter') if data else None


def level_has_hunter(level: int) -> bool:
    """Whether a hunter flies on a level.

    A level file decides if it says anything: False forbids one, a spawn
    override places one. Otherwise there is none before HUNTER_FIRST_LEVEL or
    on a boss level, and one every HUNTER_LEVEL_INTERVAL levels elsewhere.
    """
    hunter = get_level_hunter_config(level)
    if hunter is False:
        return False
    if hunter is not None:
        return True
    if level < config.HUNTER_FIRST_LEVEL or is_boss_level(level):
        return False
    interval = config.HUNTER_LEVEL_INTERVAL
    return interval > 0 and level % interval == 0
```

- [ ] **Step 5: Run the new tests**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_boss_levels.py -q`
Expected: all pass.

- [ ] **Step 6: Update the old interval test**

In `tests/test_hunter_integration.py`, `test_hunter_flies_every_third_level_and_wherever_a_level_places_one` walks levels 1–9 expecting a hunter on 3, 6 and 9. That test is about the interval, so take the two new rules out of its way. Add these two lines directly after its `monkeypatch.setattr(config,'HUNTER_LEVEL_INTERVAL',3)` line:

```python
    monkeypatch.setattr(config,'HUNTER_FIRST_LEVEL',1)
    monkeypatch.setattr(level_config,'is_boss_level',lambda _:False)
```

- [ ] **Step 7: Run the full suite**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q 2>&1 | tail -15`
Expected: only the three `TestReflectVelocity` failures. A test that starts a real level 1–3 or a boss level and expects `game.hunter` to exist must now either place one through `get_level_hunter_config` or move to an ordinary level from 4 up; fix the test, not the rule.

- [ ] **Step 8: Commit**

```bash
git add config.py config/settings.json level_config.py tests/test_boss_levels.py tests/test_hunter_integration.py
git commit -m "feat: hunter arrives at level 4 and stays off boss levels

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Boss levels lock the exit

**Files:**
- Modify: `game.py` (the exit-lock block in `update`, near line 473)
- Test: `tests/test_boss_levels.py` (extend)

**Interfaces:**
- Consumes: `game.split_bosses`, `game.mother_bosses`, `game.eggs` (lists of entities with `.active`); `game.maze.exit.is_activated`.
- Produces: no new names. Behaviour: `game.maze.exit.is_activated` is False while any egg, split boss or mother boss is active.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_boss_levels.py`:

```python
from unittest.mock import Mock

import pygame


@pytest.fixture
def game(tmp_path, monkeypatch):
    from game import Game
    from profiles import ProfileManager

    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    monkeypatch.setattr(config, 'SPLASH_ENABLED', False)
    monkeypatch.delenv('START_LEVEL', raising=False)
    manager = ProfileManager(tmp_path / 'profiles.json')
    monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
    monkeypatch.setitem(Game.__init__.__globals__, 'SoundManager', Mock)
    game = Game(screen)
    yield game
    game._close_hunter()


def start(game, level):
    game.level = level
    game.state = config.STATE_PLAYING
    game.start_level()
    game.update(1.0)


def kill(entities):
    for entity in entities:
        entity.active = False


def test_the_exit_is_locked_while_a_split_boss_lives(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, replay=2))
    start(game, 6)
    assert len(game.split_bosses) == 1
    assert not game.maze.exit.is_activated


def test_killing_the_boss_opens_the_exit_even_with_its_escort_alive(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, replay=2))
    start(game, 6)
    kill(game.split_bosses)
    game.update(1.0)
    assert any(ship.active for ship in game.replay_enemies)
    assert game.maze.exit.is_activated


def test_every_boss_must_die(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=2))
    start(game, 12)
    kill(game.split_bosses[:1])
    game.update(1.0)
    assert not game.maze.exit.is_activated


def test_a_mother_boss_level_needs_the_boss_and_the_eggs_dead(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(mother_boss=1, egg=2))
    start(game, 18)
    assert not game.maze.exit.is_activated
    kill(game.mother_bosses)
    game.update(1.0)
    assert not game.maze.exit.is_activated  # eggs remain
    kill(game.eggs)
    game.update(1.0)
    assert game.maze.exit.is_activated


def test_a_boss_on_any_level_locks_the_exit(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1, static=2))
    start(game, 7)
    assert not game.maze.exit.is_activated
    assert game.hunter is None


def test_restarting_a_boss_level_locks_the_exit_again(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(split_boss=1))
    start(game, 6)
    kill(game.split_bosses)
    game.update(1.0)
    assert game.maze.exit.is_activated
    start(game, 6)
    assert not game.maze.exit.is_activated


def test_an_ordinary_level_has_an_open_exit(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(static=3))
    start(game, 3)  # before the hunter's first level, so no pilot is started
    assert game.maze.exit.is_activated
```

- [ ] **Step 2: Run them and watch them fail**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_boss_levels.py -q`
Expected: `test_the_exit_is_locked_while_a_split_boss_lives`, `test_every_boss_must_die`, `test_a_boss_on_any_level_locks_the_exit` and `test_restarting_a_boss_level_locks_the_exit_again` fail on `assert not game.maze.exit.is_activated`. The mother boss test fails at its first assertion only if no egg has been laid yet; either way it must pass after Step 3. The others pass already.

- [ ] **Step 3: Implement**

In `game.py`, in `update`, replace:

```python
        # Check if any eggs are still alive - deactivate exit portal if eggs exist
        has_active_eggs = any(egg.active for egg in self.eggs)
        if self.maze.exit.active:
            self.maze.exit.set_activated(not has_active_eggs, self.sound_manager)
```

with:

```python
        # The exit stays shut while any egg or boss is alive
        exit_locked = (any(egg.active for egg in self.eggs)
                       or any(boss.active for boss in self.split_bosses)
                       or any(boss.active for boss in self.mother_bosses))
        if self.maze.exit.active:
            self.maze.exit.set_activated(not exit_locked, self.sound_manager)
```

In `entities/exit.py`, the class docstring says "While locked (eggs remain)"; change it to "While locked (eggs or a boss remain)". In `set_activated`'s docstring change "When deactivated (eggs present)" to "When deactivated (eggs or a boss present)" and "When activated (no eggs)" to "When activated (none left)".

- [ ] **Step 4: Run the tests**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_boss_levels.py -q`
Expected: all pass.

- [ ] **Step 5: Run the full suite**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q 2>&1 | tail -15`
Expected: only the three `TestReflectVelocity` failures.

- [ ] **Step 6: Commit**

```bash
git add game.py entities/exit.py tests/test_boss_levels.py
git commit -m "feat: the exit stays locked while a boss is alive

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The 24 arc level files

**Files:**
- Create or overwrite: `levels/1.json` … `levels/24.json`
- Modify: `levels/README.md`
- Test: `tests/test_level_arc.py` (create)

**Interfaces:**
- Consumes: `level_config.load_level_config`, `is_boss_level`, `level_has_hunter`, `get_maze_grid_size`; `level_rules.anemones_that_fit`.
- Produces: the level files. No code names.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_level_arc.py`:

```python
"""The designed arc, levels 1 to 24: every level has a file and the files keep the pacing rules."""
import pytest

import level_config
from level_rules import anemones_that_fit

ARC = range(1, 25)
BOSS_LEVELS = [6, 12, 18, 24]
ORDINARY = [level for level in ARC if level not in BOSS_LEVELS]
BOSSES = ('split_boss', 'mother_boss')
TYPES = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone') + BOSSES


def enemies(level):
    return level_config.load_level_config(level)['enemies']


def enemy_count(level):
    return sum(n for name, n in enemies(level).items() if name not in BOSSES)


@pytest.mark.parametrize('level', ARC)
def test_every_arc_level_has_a_complete_file(level):
    data = level_config.load_level_config(level)
    assert data is not None, f'levels/{level}.json is missing or does not parse'
    assert data['seed'] == 100 + level
    assert set(data['enemies']) == set(TYPES)
    assert all(type(n) is int and n >= 0 for n in data['enemies'].values())
    assert data['maze']['complexity'] in ('empty', 'simple', 'normal', 'complex', 'extreme')
    assert type(data['maze']['grid_size']) is int


def test_bosses_appear_only_on_the_boss_levels():
    assert [level for level in ARC if level_config.is_boss_level(level)] == BOSS_LEVELS


@pytest.mark.parametrize('level, split, mother', [(6, 1, 0), (12, 2, 0), (18, 0, 1), (24, 1, 1)])
def test_each_boss_level_has_its_bosses_in_an_open_arena(level, split, mother):
    assert (enemies(level)['split_boss'], enemies(level)['mother_boss']) == (split, mother)
    maze = level_config.load_level_config(level)['maze']
    assert maze['complexity'] == 'empty' and maze['grid_size'] <= 16


def test_at_most_one_enemy_type_is_new_on_any_level():
    seen = set()
    for level in ARC:
        new = {name for name, n in enemies(level).items() if n} - seen
        assert len(new) <= 1, f'level {level} introduces {sorted(new)}'
        seen |= new
    assert seen == set(TYPES)


def test_the_enemy_count_rises_gently_between_ordinary_levels():
    for earlier, later in zip(ORDINARY, ORDINARY[1:]):
        step = enemy_count(later) - enemy_count(earlier)
        assert -1 <= step <= 2, f'level {earlier} to {later} changes the count by {step}'


def test_the_arc_starts_small_and_ends_at_24():
    assert enemy_count(1) == 4
    assert enemy_count(23) == 24


def test_ordinary_mazes_never_shrink_and_stop_at_32():
    sizes = [level_config.get_maze_grid_size(level) for level in ORDINARY]
    assert sizes == sorted(sizes)
    assert sizes[0] == 10 and sizes[-1] == 32


@pytest.mark.parametrize('level', ARC)
def test_anemones_fit_the_maze(level):
    assert enemies(level)['anemone'] <= anemones_that_fit(level_config.get_maze_grid_size(level))


def test_the_hunter_flies_from_level_four_except_on_boss_levels():
    without = [level for level in ARC if not level_config.level_has_hunter(level)]
    assert without == [1, 2, 3] + BOSS_LEVELS
```

- [ ] **Step 2: Run them and watch them fail**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_level_arc.py -q`
Expected: many failures: files 10, 13–15 and 17–24 missing; seeds are 100 or 101; existing files lack keys; bosses on the wrong levels.

- [ ] **Step 3: Write the level files**

Run this once from the repository root. It is the spec's table; it is not kept in the repository.

```bash
python3 - <<'EOF'
import json

# level: (grid, complexity, static, patrol, aggressive, replay, flocker, flighthouse, egg, anemone, split_boss, mother_boss)
ARC = {
    1:  (10, 'empty',   4, 0, 0, 0, 0,  0, 0, 0, 0, 0),
    2:  (12, 'simple',  2, 2, 0, 0, 0,  0, 0, 0, 0, 0),
    3:  (14, 'simple',  2, 1, 2, 0, 0,  0, 0, 0, 0, 0),
    4:  (16, 'simple',  2, 1, 1, 0, 0,  0, 0, 0, 0, 0),
    5:  (18, 'simple',  2, 1, 1, 2, 0,  0, 0, 0, 0, 0),
    6:  (12, 'empty',   0, 0, 0, 2, 0,  0, 0, 0, 1, 0),
    7:  (20, 'normal',  2, 1, 2, 1, 0,  0, 0, 2, 0, 0),
    8:  (22, 'normal',  2, 0, 0, 0, 6,  0, 0, 2, 0, 0),
    9:  (22, 'normal',  2, 2, 2, 1, 2,  0, 0, 2, 0, 0),
    10: (24, 'normal',  2, 2, 2, 1, 2,  1, 0, 2, 0, 0),
    11: (24, 'normal',  3, 2, 2, 2, 2,  1, 0, 2, 0, 0),
    12: (14, 'empty',   0, 0, 0, 0, 6,  0, 0, 0, 2, 0),
    13: (26, 'complex', 2, 2, 2, 1, 2,  1, 1, 2, 0, 0),
    14: (26, 'complex', 3, 2, 2, 2, 2,  1, 1, 2, 0, 0),
    15: (28, 'complex', 0, 0, 0, 0, 10, 1, 1, 4, 0, 0),
    16: (28, 'complex', 3, 2, 3, 2, 3,  1, 1, 2, 0, 0),
    17: (30, 'complex', 3, 3, 3, 2, 3,  1, 1, 3, 0, 0),
    18: (14, 'empty',   0, 0, 0, 0, 0,  0, 4, 0, 0, 1),
    19: (30, 'extreme', 3, 3, 3, 2, 3,  1, 1, 4, 0, 0),
    20: (30, 'extreme', 3, 3, 3, 3, 3,  1, 1, 4, 0, 0),
    21: (32, 'extreme', 4, 3, 3, 3, 3,  1, 1, 4, 0, 0),
    22: (32, 'extreme', 4, 3, 3, 3, 3,  2, 1, 4, 0, 0),
    23: (32, 'extreme', 4, 3, 4, 3, 3,  2, 1, 4, 0, 0),
    24: (16, 'empty',   0, 0, 0, 2, 2,  0, 2, 0, 1, 1),
}
NAMES = ('static', 'patrol', 'aggressive', 'replay', 'flocker', 'flighthouse', 'egg', 'anemone',
         'split_boss', 'mother_boss')
for level, (grid, complexity, *counts) in ARC.items():
    data = {'seed': 100 + level,
            'maze': {'complexity': complexity, 'grid_size': grid},
            'enemies': dict(zip(NAMES, counts))}
    with open(f'levels/{level}.json', 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
EOF
```

Check: `ls levels/*.json | wc -l` prints `24`.

- [ ] **Step 4: Run the arc tests**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_level_arc.py -q`
Expected: all pass.

- [ ] **Step 5: Rewrite `levels/README.md`**

Replace the whole file with:

````markdown
# Level files

Levels 1 to 24 are a designed arc: each has a file here, `{level}.json`, that says exactly what is on it. Levels from 25 have no file and come from the formulas in `level_rules.py`.

A file can exist for any level, and can state as much or as little as it likes. Whatever it leaves out comes from the formulas.

## Format

```json
{
  "seed": 107,
  "maze": { "complexity": "normal", "grid_size": 20 },
  "enemies": {
    "static": 2, "patrol": 1, "aggressive": 2, "replay": 1,
    "flocker": 0, "flighthouse": 0, "egg": 0, "anemone": 2,
    "split_boss": 0, "mother_boss": 0
  },
  "hunter": false
}
```

- **seed**: random seed for the maze and enemy positions. Default: the level number. Arc levels use `100 + level`.
- **maze.complexity**: `empty` (perimeter walls only), `simple`, `normal`, `complex` or `extreme`.
- **maze.grid_size**: width and height in cells, 5 to 100. Bigger means more, smaller cells.
- **enemies**: a count for each type. Anemone counts in a file are taken as given; the formulas would hold them to what the maze has room for.
- **hunter**: leave it out for the normal rule. `false` means no hunter. `{"spawn_cell": [col, row]}` places one at that cell.

## Boss levels

A level with at least one `split_boss` or `mother_boss` is a boss level, whatever its number:

- the exit is locked until every boss is dead (and, as on any level, every egg);
- no hunter flies, unless the file places one.

In the arc these are levels 6, 12, 18 and 24.

## The hunter

Without a `hunter` entry: no hunter before level 4 (`game.hunterFirstLevel`), none on boss levels, and one on every other level (`game.hunterLevelInterval`).

## Pacing rules for the arc

`tests/test_level_arc.py` checks these, so a level can be retuned freely as long as they hold:

- at most one enemy type appears for the first time on any level;
- from one ordinary level to the next, the enemy count (everything except bosses) rises by at most 2 and falls by at most 1;
- bosses appear only on levels 6, 12, 18 and 24;
- ordinary mazes never shrink and stop at 32;
- anemones fit the maze.

## Levels without a file

- **Ordinary levels from 25**: grid 32, `extreme`. The enemy count is 25 at level 25 and rises by one every two levels to 36 (`difficulty.maxEnemyCount`). Each added enemy goes to the next of aggressive, replay, flocker, static, patrol, anemone.
- **Every sixth level** (`difficulty.bossLevelInterval`) is a boss level in a 16-cell open arena: split bosses, then a mother boss, then both, gaining a boss each time round up to three.
- **Enemy speed and damage** grow 5% a level after level 4 and stop at 2.5 times.
- **An arc level whose file is missing** gets `3 + level` enemies of the types introduced by then.
````

- [ ] **Step 6: Run the full suite**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q 2>&1 | tail -15`
Expected: only the three `TestReflectVelocity` failures. Tests that start a real level by number now get the new files; if one relied on old content (a hunter on level 1, anemones on level 4), give it its own `load_level_config` through monkeypatch, in the style of `level_file` in `tests/test_boss_levels.py`.

- [ ] **Step 7: Commit**

```bash
git add levels tests/test_level_arc.py
git commit -m "feat: a 24-level arc that introduces one thing at a time

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Clear bests saved against the old levels

**Files:**
- Modify: `profiles.py`
- Test: `tests/test_profile_bests.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `profiles.LEVELS_VERSION = 2`; the profiles file gains top-level `"levels_version"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_profile_bests.py` (it already imports `json` and `ProfileManager`; add `import pytest` at the top if it is not there):

```python
OLD_BEST = {'4': {'score': 83, 'time': 9.0, 'stars': 5}}


def write_profiles(path, **top_level):
    path.write_text(json.dumps({
        'profiles': [{'name': 'Old', 'level': 21, 'total_score': 9039, 'bests': OLD_BEST}],
        'active_profile': 'Old', **top_level}))


def test_bests_from_before_the_levels_changed_are_cleared_but_progress_is_kept(tmp_path):
    path = tmp_path / 'profiles.json'
    write_profiles(path)
    manager = ProfileManager(path)
    assert manager.get_active_profile().bests == {}
    assert manager.get_active_level() == 21 and manager.get_active_total_score() == 9039


def test_the_file_is_rewritten_at_once_so_bests_are_cleared_only_once(tmp_path):
    path = tmp_path / 'profiles.json'
    write_profiles(path)
    manager = ProfileManager(path)
    saved = json.loads(path.read_text())
    assert saved['levels_version'] == 2
    assert saved['profiles'][0]['bests'] == {}
    manager.record_level_result(4, 50, 12.0, 3)
    assert list(ProfileManager(path).get_active_profile().bests) == [4]


def test_a_current_file_keeps_its_bests(tmp_path):
    path = tmp_path / 'profiles.json'
    write_profiles(path, levels_version=2)
    assert list(ProfileManager(path).get_active_profile().bests) == [4]


@pytest.mark.parametrize('version', [None, '2', 1, 2.0, True, [], {}])
def test_a_missing_or_malformed_version_counts_as_old(tmp_path, version):
    path = tmp_path / 'profiles.json'
    write_profiles(path, levels_version=version)
    manager = ProfileManager(path)
    assert manager.get_active_profile().bests == {}
    assert manager.get_active_level() == 21


def test_a_new_profiles_file_is_written_with_the_version(tmp_path):
    path = tmp_path / 'profiles.json'
    ProfileManager(path)
    assert json.loads(path.read_text())['levels_version'] == 2
```

- [ ] **Step 2: Run them and watch them fail**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_profile_bests.py -q`
Expected: the five new tests fail (bests are kept, `KeyError: 'levels_version'`), except `test_a_current_file_keeps_its_bests`, which passes already.

- [ ] **Step 3: Implement in `profiles.py`**

Below `DEFAULT_PROFILES_PATH`, add:

```python
# Bests are stored by level number. Raise this when the levels change so that
# records set on the old levels are not shown against the new ones.
LEVELS_VERSION = 2
```

In `_load_profiles`, directly after the `if self.path.exists():` block, add:

```python
        version = data.get("levels_version")
        stale = type(version) is not int or version < LEVELS_VERSION
```

In the same method, change `if isinstance(raw_bests, dict):` to:

```python
            if not stale and isinstance(raw_bests, dict):
```

and at the end of the method, after `self._ensure_active_profile()`, add:

```python
        if stale:
            self._save_profiles()
```

In `_save_profiles`, add the version to the payload, after the `"active_profile"` entry:

```python
            "active_profile": self.active_profile_name,
            "levels_version": LEVELS_VERSION
```

- [ ] **Step 4: Update the existing test that loads old bests**

In `tests/test_profile_bests.py`, `test_old_profiles_and_malformed_bests_load` writes a file with no version and expects the `Mixed` profile to keep best `4`. It is testing malformed entries, so give it a current file. Change its `path.write_text(...)` line to:

```python
    path.write_text(json.dumps({'profiles': entries, 'active_profile': 'Old', 'levels_version': 2}))
```

- [ ] **Step 5: Run the tests**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_profile_bests.py -q`
Expected: all pass.

- [ ] **Step 6: Run the full suite**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q 2>&1 | tail -15`
Expected: only the three `TestReflectVelocity` failures.

- [ ] **Step 7: Commit**

```bash
git add profiles.py tests/test_profile_bests.py
git commit -m "feat: clear bests recorded against the old levels, once

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Note for whoever runs the game next: `profiles.json` in the repository root is the real, git-ignored save file. The first launch after this commit clears its bests and keeps the unlocked level. That is the intended effect; do not launch the game before the user has been told.

---

### Task 7: Every level has room for its enemies, and a played check

**Files:**
- Test: `tests/test_level_arc.py` (extend)

**Interfaces:**
- Consumes: everything above, through `Game.start_level`.
- Produces: nothing.

- [ ] **Step 1: Write the test**

Append to `tests/test_level_arc.py`:

```python
import math
from unittest.mock import Mock

import pygame

import config
import level_rules


@pytest.fixture
def game(tmp_path, monkeypatch):
    from game import Game
    from profiles import ProfileManager

    pygame.init()
    screen = pygame.display.set_mode((1352, 878))
    monkeypatch.setattr(config, 'SCREEN_WIDTH', 1352)
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', 878)
    monkeypatch.setattr(config, 'SPLASH_ENABLED', False)
    monkeypatch.delenv('START_LEVEL', raising=False)
    manager = ProfileManager(tmp_path / 'profiles.json')
    monkeypatch.setitem(Game.__init__.__globals__, 'ProfileManager', lambda: manager)
    monkeypatch.setitem(Game.__init__.__globals__, 'SoundManager', Mock)
    monkeypatch.setattr(level_config, 'level_has_hunter', lambda _: False)
    game = Game(screen)
    yield game
    game._close_hunter()


@pytest.mark.parametrize('level', list(ARC) + [25, 30, 36, 42, 47, 66])
def test_every_enemy_the_level_asks_for_is_placed_clear_of_the_start(game, level):
    counts = level_config.get_level_enemy_counts(level) or level_rules.get_enemy_counts(level)
    asked_for = {
        'enemies': counts.static + counts.patrol + counts.aggressive,
        'replay_enemies': counts.replay, 'flockers': counts.flocker, 'flighthouses': counts.flighthouse,
        'eggs': counts.egg, 'anemones': level_config.get_level_anemone_count(level),
        'split_bosses': level_config.get_level_split_boss_count(level),
        'mother_bosses': level_config.get_level_mother_boss_count(level)}
    game.level = level

    game.start_level()

    placed = {name: len(getattr(game.entity_manager, name)) for name in asked_for}
    assert placed == asked_for
    for enemy in game.entity_manager.get_all_enemies():
        assert math.dist(enemy.get_pos(), game.maze.start_pos) >= config.ENEMY_START_CLEARANCE
```

- [ ] **Step 2: Run it**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest tests/test_level_arc.py -q`
Expected: all pass. This test is a check on the level data, not a driver for new code, so it may pass first time.

If a level fails with fewer placed than asked for, the dictionary diff names the type and the shortfall. Anemones are the likely one: they are also kept `ANEMONE_REACH_CELLS` away from the start, and the small arenas and early mazes have few positions. The fix is in that level's file: lower that type's count by the shortfall, re-run `tests/test_level_arc.py` in full (the pacing rules must still hold), and name the level and the change in the commit message. Do not loosen the start clearance and do not change the spawner.

Flockers are placed in a cluster and may share a position when the cluster is full; that is existing behaviour and satisfies this test.

- [ ] **Step 3: Run the full suite**

Run: `source venv/bin/activate && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q 2>&1 | tail -15`
Expected: only the three `TestReflectVelocity` failures.

- [ ] **Step 4: Print the finished curve for the record**

Run:

```bash
source venv/bin/activate && python - <<'EOF'
import level_config as lc, level_rules as lr
for level in list(range(1, 31)) + [36, 42, 47, 48, 66]:
    c = lc.get_level_enemy_counts(level) or lr.get_enemy_counts(level)
    count = c.static + c.patrol + c.aggressive + c.replay + c.flocker + c.flighthouse + c.egg + lc.get_level_anemone_count(level)
    print(f"{level:3} grid {lc.get_maze_grid_size(level):2} count {count:2} "
          f"bosses {lc.get_level_split_boss_count(level)}+{lc.get_level_mother_boss_count(level)} "
          f"hunter {'yes' if lc.level_has_hunter(level) else 'no '} "
          f"speed x{lr.get_enemy_speed(level, 'aggressive'):.2f}")
EOF
```

Expected: counts 4, 4, 5, 4, 6, 2, 8, 10, 11, 12, 14, 6, 13, 15, 16, 17, 19, 4, 20, 21, 22, 23, 24, 6 for levels 1–24 (unless Step 2 lowered one), then 25, 25, 26, 26, 27 for 25–29; bosses only on multiples of 6; no hunter on 1–3 and on multiples of 6. Include this output in the final report.

- [ ] **Step 5: Commit**

```bash
git add tests/test_level_arc.py levels
git commit -m "test: every level places all its enemies clear of the start

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Hand over for the played check**

The spec calls for levels 4, 6, 12, 18, 24 and one endless level past 47 to be played on the real display. That is the user's to do: launching the game takes over their screen and clears the bests in their real `profiles.json`. Report that the automated checks pass, that this check is outstanding, and that a level can be started directly with `START_LEVEL=<n> ./run.sh`. Things to look at on each: on 4, the hunter arrives and the level is calm; on 6, 12, 18 and 24, the exit is visibly shut, opens with the ripple when the last boss (and egg) dies, and no hunter flies; past 47, the level is busy but not crowded.
