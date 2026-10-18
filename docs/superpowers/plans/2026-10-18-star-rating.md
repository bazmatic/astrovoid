# Star Rating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A level's five stars come from what the player did (finished, half the enemies, every enemy, every crystal, inside par), shown live during play and explained on the level-complete screen.

**Architecture:** A pure `scoring/stars.py` holds the rule (`StarTally` in, five flags and five lines out) and a pure `scoring/par.py` holds the par formula and the maze route. The game keeps the tally (kills and crystals by the player and the Jev hunter), fixes the base par at level start, freezes the tally when the exit is reached, and hands the flags to the HUD row, the chimes, the level-complete stars and the profile.

**Tech Stack:** Python 3.10, pygame, pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-star-rating-design.md`

## Global Constraints

- Tests: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider <paths>`.
- The full suite has 27 known failures, all in `test_anemone_game`, `test_experiment_dagger`, `test_hunter_integration`, `test_hunter_powerups`, `test_hunter_settings_for`, `test_jev_beacon`, `test_level_arc`, `test_neural_game` and `test_rules_hunter_training`. After each task the full suite must fail nothing outside those files, and no more than 27 tests.
- `config/settings.json` holds the user's uncommitted `autoplay.firstLevel` edit (13 → 10). Stage only your own hunk: write HEAD's file plus your change to a scratch copy, then `git update-index --cacheinfo 100644,$(git hash-object -w <copy>),config/settings.json`. Never `git add -A` / `git add .`; never stage `assets/neural/hunter.npz`.
- Star order everywhere (flags, HUD row, level-complete slots): finish, half the enemies, every enemy, every crystal, par.
- Par numbers, in the `game` settings section with these defaults: `parSpeedShare` 0.5, `parSecondsPerEnemy` 6, `parSecondsPerSpawningBoss` 30, `parSecondsPerCrystal` 3, `parTimerMargin` 10. Spawning bosses are `mother_boss` and `split_boss`.
- The par clock is `Game.play_seconds`. Kills and crystals by the Jev hunter count like the player's. The Jev beacon is never a crystal.
- The score itself is unchanged; it no longer decides stars. Stars saved in profiles are still a count 0–5.
- Rendering changes are checked on the real display at 1352×878 (the dummy driver hides alpha and layout faults).
- End every commit with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The exit explosion (1.5 s) and the level-complete screen must not change the result**: the tally is frozen when the ship enters the exit, so kills, drops or time after that don't count. Pinned in Task 3 (`test_the_tally_is_frozen_when_the_exit_is_reached`).
2. **A Jev hunter flight that ends mid-level** (the hunter dies or is replaced): its kills and crystals so far still count. Pinned in Task 3 (`test_hunter_kills_and_pickups_count`, which kills via a 'hunter' projectile without a live hunter).
3. **A maze with no route from start to exit** (a layout walled shut, or a level using destructible blocks): par must still be a number, never a crash. Pinned in Task 2 (`test_no_route_falls_back_to_the_straight_line`).
4. **A replay of the level from the level-complete screen, or a death and restart**: the tally and par start again from zero. Pinned in Task 3 (`test_restarting_resets_the_tally`).
5. **The level-complete lines with large numbers** (`120/120 KILLED`, `12:05 / PAR 9:40`) must fit their slots at 1352×878 and 1280×720. Pinned in Task 5 (`test_the_star_lines_fit_their_slots`).

---

## File Structure

| File | Responsibility |
|---|---|
| `scoring/stars.py` (new) | `StarTally`, the rule (`earned`), `star_count`, the level-complete lines (`describe`). |
| `scoring/par.py` (new) | `route_cells` (BFS over the maze grid) and `par_seconds`. |
| `config.py`, `config/settings.json` | The five par settings in `GameSettings`. |
| `game_handlers/collision_handler.py` | Level tallies: `level_kills`, `level_crystals_collected`. |
| `game.py` | Base par at level start, `star_tally()`, the frozen finish tally, completion, the HUD row, the live chimes. |
| `rendering/ui_elements.py` | `StarIndicator` follows flags; `AnimatedStarRating` takes flags. |
| `rendering/star_row.py` (new) | The five small stars drawn during play. |
| `rendering/level_complete_menu.py` | The line under each star. |
| `README.md` | How stars are earned. |

---

### Task 1: The star rule

**Files:**
- Create: `scoring/stars.py`
- Test: `tests/test_star_rule.py` (new)

**Interfaces:**
- Produces:
  - `STAR_NAMES = ('finish', 'half_enemies', 'every_enemy', 'every_crystal', 'par')`
  - `@dataclass(frozen=True) StarTally(kills: int, alive: int, crystals_collected: int, crystals_left: int, play_seconds: float, par_seconds: float)`
  - `earned(tally: StarTally) -> Tuple[bool, bool, bool, bool, bool]`
  - `star_count(flags: Sequence[bool]) -> int`
  - `describe(tally: StarTally) -> Tuple[str, str, str, str, str]`
  - `format_clock(seconds: float) -> str` (`m:ss`, seconds rounded down)

- [ ] **Step 1: Write the failing tests**

```python
from scoring.stars import StarTally, describe, earned, star_count

def tally(kills=0, alive=0, collected=0, left=0, seconds=10.0, par=60.0):
    return StarTally(kills, alive, collected, left, seconds, par)

def test_finishing_alone_is_one_star():
    assert earned(tally(kills=0, alive=4, collected=0, left=1, seconds=90)) == (True, False, False, False, False)

def test_half_the_enemies_is_a_star_and_all_of_them_another():
    assert earned(tally(kills=2, alive=2))[1:3] == (True, False)       # exactly half
    assert earned(tally(kills=1, alive=2))[1:3] == (False, False)
    assert earned(tally(kills=4, alive=0))[1:3] == (True, True)

def test_a_level_with_no_enemies_or_crystals_gives_those_stars():
    assert earned(tally()) == (True, True, True, True, True)

def test_every_crystal_means_none_left():
    assert earned(tally(collected=3, left=0))[3] and not earned(tally(collected=3, left=1))[3]

def test_par_is_met_on_the_second_and_missed_after_it():
    assert earned(tally(seconds=60.0, par=60.0))[4] and not earned(tally(seconds=60.01, par=60.0))[4]

def test_the_count_is_the_number_of_stars_lit():
    assert star_count((True, False, True, True, False)) == 3

def test_the_lines_under_the_stars():
    assert describe(tally(kills=9, alive=5, collected=2, left=1, seconds=102.4, par=103.0)) == \
        ('FINISHED', '9/14 KILLED', '5 LEFT', '2/3 CRYSTALS', '1:42 / PAR 1:43')
    assert describe(tally(kills=14, alive=0))[1:4] == ('14/14 KILLED', 'NONE LEFT', 'NO CRYSTALS')
```

- [ ] **Step 2: Run to see it fail**: `… pytest tests/test_star_rule.py -q` → `ModuleNotFoundError: No module named 'scoring.stars'`.

- [ ] **Step 3: Implement `scoring/stars.py`.** Half the enemies: `kills * 2 >= kills + alive`. Every crystal with nothing dropped: `NO CRYSTALS` line, star earned. Par line uses `format_clock` for both times.

- [ ] **Step 4: Run to see it pass**: same command → all pass.

- [ ] **Step 5: Commit** `scoring/stars.py tests/test_star_rule.py`: `feat: the star rule, from kills, crystals and par`.

---

### Task 2: Par

**Files:**
- Create: `scoring/par.py`
- Modify: `config.py` (`GameSettings`), `config/settings.json` (`game` section; see the staging rule)
- Test: `tests/test_par.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `route_cells(grid: Sequence[Sequence[int]], start: Tuple[int, int], end: Tuple[int, int]) -> Optional[int]`: steps on the shortest 4-neighbour path through cells where `grid[row][col] == 0` (cells are `(col, row)`); `None` when there's no path. The start and end cells count as open.
  - `par_seconds(route_px: float, enemy_counts: Mapping[str, int], crystals: int, timer_seconds: Optional[float] = None, settings=config.SETTINGS.game) -> float`: `route_px / (parSpeedShare * SHIP_MAX_SPEED * FPS)` + `parSecondsPerSpawningBoss` × (mother_boss + split_boss) + `parSecondsPerEnemy` × every other enemy + `parSecondsPerCrystal` × crystals; then at least `timer_seconds + parTimerMargin` when a timer is given.
  - `GameSettings.parSpeedShare: float = 0.5`, `parSecondsPerEnemy: float = 6.0`, `parSecondsPerSpawningBoss: float = 30.0`, `parSecondsPerCrystal: float = 3.0`, `parTimerMargin: float = 10.0`.

- [ ] **Step 1: Write the failing tests**
  - `test_the_route_goes_round_the_walls`: a 5×5 grid, border walls, a wall at `(2,1)` and `(2,2)`; `route_cells(grid, (1,1), (3,1)) == 6`.
  - `test_no_route_is_none`: the same grid with `(2,3)` walled too gives `None`.
  - `test_par_adds_route_enemies_bosses_and_crystals`: `par_seconds(2400, {'static': 10, 'replay': 2, 'mother_boss': 1, 'egg': 1}, 3) == 2400 / 240 + 13 * 6 + 30 + 9`.
  - `test_a_timer_exit_sets_a_floor`: `par_seconds(240, {}, 0, timer_seconds=60) == 70`; `par_seconds(4800, {}, 0, timer_seconds=5) == 20` (the formula's 20 s beats the floor's 15 s).
  - `test_the_settings_have_the_defaults`: each of the five settings equals its default.

- [ ] **Step 2: Run to see it fail**: `… pytest tests/test_par.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement** `scoring/par.py` (`collections.deque` BFS) and the five settings, in `GameSettings` and in `settings.json`'s `game` section.

- [ ] **Step 4: Run to see it pass**: `… pytest tests/test_par.py tests/test_neural_game.py -q` → `test_par.py` all pass; `test_neural_game.py` no new failures.

- [ ] **Step 5: Commit** `scoring/par.py config.py tests/test_par.py` and your `settings.json` hunk only: `feat: par time from the maze route, the enemies and the crystals`.

---

### Task 3: The game keeps the tally and awards the stars

**Files:**
- Modify: `game_handlers/collision_handler.py` (`_record_projectile_kill`, `handle_ship_crystal_collision`, `handle_hunter_crystal_collision`)
- Modify: `game.py` (`start_level`, the exit-reached block at about line 1042, `complete_level` at about 1102-1170)
- Modify: `rendering/ui_elements.py` (`AnimatedStarRating`)
- Test: `tests/test_star_game.py` (new); rewrite `tests/test_reward_stars.py`, `tests/test_star_thresholds.py` (the `AnimatedStarRating` parts), `tests/test_menu_visuals.py:145,154,206`

**Interfaces:**
- Consumes: Task 1 (`StarTally`, `earned`, `star_count`, `describe`), Task 2 (`route_cells`, `par_seconds`).
- Produces:
  - `CollisionHandler.level_kills: int` (kills by projectiles with source `'player'` or `'hunter'`), `CollisionHandler.level_crystals_collected: int` (crystals taken by the player or the hunter). Both are reset to 0 by `Game.start_level`.
  - `Game.base_par_seconds: float` (set in `start_level` from the route, the enemies present, and the exit policy's timer), `Game.star_tally() -> StarTally` (live; `par_seconds = base + parSecondsPerCrystal × crystals dropped so far`, where dropped = collected + active non-beacon crystals), `Game.finish_tally: Optional[StarTally]` (frozen when the ship enters the exit; `None` otherwise).
  - `Game.star_lines: Tuple[str, ...]` (set at completion from `describe(finish_tally)`).
  - `AnimatedStarRating(earned: Sequence[bool], x, y, star_size=…, star_spacing=None, previous_stars=None)`: `num_stars = star_count(earned)`; only earned slots get a star, landing in slot order with today's spring and chime; `glow_color(i)` is the record colour for every earned slot when `previous_stars is not None and num_stars > previous_stars`; `flash` when all five are earned.

- [ ] **Step 1: Write the failing tests** in `tests/test_star_game.py`, with the `game` fixture style of `tests/test_exit_policies_game.py` (`level_file`, `start`, `kill`):
  - `test_player_kills_are_counted`: `patrol=2`; two player `Projectile`s on the enemies; update; `game.star_tally().kills == 2` and `.alive == 0`.
  - `test_hunter_kills_and_pickups_count`: a `Projectile(..., source='hunter')` on an enemy → `kills == 1`; a `PowerupCrystal` collected through `collision_handler.handle_hunter_crystal_collision(hunter, crystal)` with a `HunterShip` on it → `level_crystals_collected == 1`.
  - `test_the_beacon_is_not_a_crystal`: a `JevBeacon` in `powerup_crystals` gives `crystals_left == 0`.
  - `test_enemies_that_appear_are_counted_but_do_not_extend_par`: `level_file(egg=1)`; note `base_par_seconds`; append two `Baby` objects to `game.babies`; `alive` rises by 2 and `base_par_seconds` is unchanged.
  - `test_a_dropped_crystal_adds_to_par`: append a `PowerupCrystal`; `star_tally().par_seconds == base_par_seconds + 3`.
  - `test_no_route_falls_back_to_the_straight_line`: a layout whose exit is walled in; `start_level` doesn't raise and `base_par_seconds > 0` (route = straight-line pixels from start to exit when `route_cells` is `None`).
  - `test_the_tally_is_frozen_when_the_exit_is_reached`: put the ship on the exit, update; `finish_tally` is set; append a `Baby`; update; `finish_tally.alive` unchanged.
  - `test_restarting_resets_the_tally`: kill one, then `start(game, 3)`: `star_tally().kills == 0`, `finish_tally is None`.
  - `test_completion_records_the_star_count`: `level_file()` (no enemies), reach the exit, run updates until `game.state == config.STATE_LEVEL_COMPLETE`; `game.star_animation.num_stars == 5`, the profile's best stars for the level is 5, `game.star_lines[0] == 'FINISHED'`.
  - Rewrite the `AnimatedStarRating` tests: `AnimatedStarRating((True,) * 5, 250, 200)` lands five; `(True, False, True, True, False)` gives `num_stars == 3`, `star_scale(1) == 0.0` once landed, and slot 2 lands second; `previous_stars=3` with five earned glows every slot; `previous_stars=3` with three earned glows none. Drop the score-threshold parts of `tests/test_star_thresholds.py` (Task 4 rewrites the rest).

- [ ] **Step 2: Run to see them fail**: `… pytest tests/test_star_game.py tests/test_reward_stars.py -q` → `AttributeError` on `star_tally` / `level_kills`, `TypeError` on `AnimatedStarRating`.

- [ ] **Step 3: Implement.**
  - Route: start cell = `screen_to_grid(*maze.start_pos)`, exit cell = `screen_to_grid(*maze.exit.get_pos())`; route px = `cells * maze.cell_size`; with no route, the straight-line distance in px.
  - Enemies present for par: `entity_manager.active_counts()` after spawning in `start_level`. Timer: `exit_policy.seconds` when it's an `OpenAfterTime`.
  - Freeze `finish_tally = self.star_tally()` in the exit-reached block where `exit_explosion_active` becomes True.
  - `complete_level(success=True)`: flags = `earned(finish_tally)`; record `star_count(flags)` with the profile; `AnimatedStarRating(flags, …)`; `star_lines = describe(finish_tally)`. Drop `level_score_percentage` if nothing else reads it.

- [ ] **Step 4: Run to see them pass**: `… pytest tests/test_star_game.py tests/test_reward_stars.py tests/test_star_thresholds.py tests/test_menu_visuals.py tests/test_exit_policies_game.py tests/test_profile_bests.py -q` → all pass; then the full suite against the Global Constraints.

- [ ] **Step 5: Commit** the files named in this task: `feat: stars from kills, crystals and par, counting the Jev hunter's`.

---

### Task 4: Stars during play

**Files:**
- Create: `rendering/star_row.py`
- Modify: `rendering/ui_elements.py` (`StarIndicator`), `game.py` (the live update at about line 1072, `draw_game`)
- Test: `tests/test_star_thresholds.py` (rewrite as `tests/test_live_stars.py` with `git mv`), `tests/test_star_row.py` (new)

**Interfaces:**
- Consumes: `Game.star_tally()`, `earned`.
- Produces:
  - `StarIndicator(on_star_lost=None, on_star_gained=None)`, `update(flags: Sequence[bool])` (one callback per star that went out or lit since the last update; none on the first update after construction or `reset()`), `reset()`, `flags` property. `calculate_star_count` and `SCORE_THRESHOLDS` are removed.
  - `rendering.star_row.draw_star_row(screen, flags: Sequence[bool], pulse: float, center: Tuple[int, int], size: int) -> pygame.Rect`; `pulse` 0..1 scales the par star's brightness; `STAR_ROW_Y` constant for its place in the side panel.
  - `Game.par_pulse() -> float`: 0 until 10 s before par, then a 0..1 sine pulse, and 0 once par has passed (the star is out then anyway).

- [ ] **Step 1: Write the failing tests**
  - Live: a star lighting calls `on_star_gained` once; two going out call `on_star_lost` twice; nothing on the first update; nothing after `reset()` and one update.
  - Game: `level_file(patrol=2)`; `game.star_indicator.flags` after an update is `(True, False, False, True, True)`; kill one and update → the half star lights and `play_star_gained` (Mock sound manager) was called.
  - Row: `draw_star_row` on a background surface draws lit stars brighter than unlit ones (compare the brightest pixel in each slot) and stays inside `config.UI_ZONE_WIDTH`.

- [ ] **Step 2: Run to see them fail**: `… pytest tests/test_live_stars.py tests/test_star_row.py -q` → `TypeError`/`ModuleNotFoundError`.

- [ ] **Step 3: Implement.** Feed `earned(self.star_tally())` to `star_indicator.update` each frame (until `finish_tally` is set) in place of the score percentage. Draw the row in `draw_game` beside the other HUD items.

- [ ] **Step 4: Run to see them pass**: same command → pass; then the full suite.

- [ ] **Step 5: Check on the real display** (1352×878): the row must not overlap the level number, the TIME gauge or the panel's lower blocks; screenshot a level with the par star pulsing. Move `STAR_ROW_Y` if needed.

- [ ] **Step 6: Commit**: `feat: the stars you'd get now, shown and chimed during play`.

---

### Task 5: The level-complete lines and the README

**Files:**
- Modify: `rendering/level_complete_menu.py` (`draw`, `layout`), `game.py` (the `level_complete_menu.draw` call), `README.md`
- Test: `tests/test_menu_visuals.py`

**Interfaces:**
- Consumes: `Game.star_lines`.
- Produces: `LevelCompleteMenu.draw(..., star_lines: Sequence[str] = ())`; `layout()`'s `'stars'` rect grows to hold one line under each slot, and the stats move down to match.

- [ ] **Step 1: Write the failing tests** in `tests/test_menu_visuals.py`:
  - `test_each_star_has_its_line`: draw a success with `star_lines=('FINISHED', '9/14 KILLED', '5 LEFT', '2/3 CRYSTALS', '1:42 / PAR 1:43')`; text pixels appear under each star slot.
  - `test_the_star_lines_fit_their_slots`: at 1352×878 and 1280×720, with `('FINISHED', '120/120 KILLED', 'NONE LEFT', '12/12 CRYSTALS', '12:05 / PAR 9:40')`, no two lines overlap and the stats block still clears the buttons (the existing no-overlap checks in this file show how).

- [ ] **Step 2: Run to see them fail**: `… pytest tests/test_menu_visuals.py -q` → `TypeError` on `star_lines`.

- [ ] **Step 3: Implement.** Lines in a small font (about `get_font(self._scaled(20))`), centred under each slot, shrunk to the slot width if wider; lit-star lines in the label colour, missed ones dimmer. Pass `self.star_lines` from `game.py`. Add a short "Stars" section to `README.md` with the table from the spec and the par formula with its settings.

- [ ] **Step 4: Run to see them pass**: `… pytest tests/test_menu_visuals.py -q`, then the full suite.

- [ ] **Step 5: Check on the real display**: finish a level with a missed star and screenshot the level-complete screen.

- [ ] **Step 6: Commit** `rendering/level_complete_menu.py game.py README.md tests/test_menu_visuals.py`: `feat: the level-complete screen says what each star was for`.
