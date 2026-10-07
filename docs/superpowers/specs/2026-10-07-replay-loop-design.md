# The "one more go" loop: per-level bests, instant retry, level select, and better stars

## Purpose

The game remembers only the furthest level and a running total, so there is nothing to beat on a level once it is cleared and no quick way to try again. This work gives every level a record worth beating, makes retrying instant, lets the player go back to any level, and makes the star reward feel like a reward.

Scoring itself does not change.

## 1. Per-level bests

### What is saved

Each profile gains `bests`: for every level the player has cleared, the best score, best time and best star count.

```json
{"name": "Player1", "level": 17, "total_score": 8141,
 "bests": {"4": {"score": 86, "time": 41.2, "stars": 5}}}
```

- Score and time are tracked independently: a run can set either, both or neither.
- `stars` is the highest star count earned on that level, using the existing `StarIndicator.calculate_star_count`.
- Scores are stored as whole numbers (`int`), times in seconds rounded to one decimal place, matching what the screens show.
- Profiles saved before this change load with empty bests. Malformed entries in `bests` are skipped, not fatal.
- Only cleared levels are recorded. A failed run records nothing.
- Recording happens every time a level is cleared, however it was started (normal play, level select, or `START_LEVEL`).

### On the level-complete screen

Under each of TIME and LEVEL SCORE, one small line:

- first clear of the level: `FIRST CLEAR` (under TIME only);
- a new record for that figure: `NEW BEST`, in gold;
- otherwise the record and the gap: `BEST 00:41.2  +0.4s` for time, `BEST 86  -12` for score.

TOTAL SCORE has no line.

## 2. Instant retry

- **R during play** restarts the current level immediately, with no confirmation. The total score goes back to what it was when the level started, exactly as RETRY LEVEL does today.
- **Controller:** the Y button (button 3, through a new `InputHandler.is_controller_restart_pressed(button)` beside the existing confirm/cancel/quit checks) does the same.
- R also works during the power-out sequence.
- **Power-out sequence:** fade 0.5 s, "GAME OVER" shown immediately as the fade completes, held 0.6 s, then the failed screen (about 1.1 s in all, down from 6 s). Any key or button during it skips straight to the failed screen. The power-down sound still plays.
- The failed screen is unchanged: RETRY LEVEL is selected by default, and R still retries from it.
- R is added to the keyboard panel of the Controls screen as `R — Restart level`, and Y to the controller panel.

## 3. Level select

### Getting there

A LEVELS button on the main menu between START GAME and SELECT PROFILE (five buttons). START GAME still continues from the profile's furthest level.

### The screen

- Heading `LEVELS`, in the shared gradient title style, on the shared menu backdrop.
- A grid of tiles, one per level from 1 to the profile's furthest level (`profile.level`), in rows. Each tile shows the level number and a row of five small stars, filled to that level's best star count. A level never cleared (the furthest one, normally) shows five empty stars.
- One further tile after the last unlocked level, greyed with a lock mark, not selectable. It is omitted when no such level exists to show.
- The selected tile uses the same highlight as a selected menu button. Under the grid, a line for the selected level: `BEST 00:41.2   SCORE 86`, or `NOT CLEARED YET`.
- A star total in the top right: `★ 43 / 85` (earned / 5 × unlocked levels).
- The grid scrolls by rows to keep the selection visible when there are more levels than fit.
- Key hints along the bottom: arrows move, Enter / A play, Esc / B back.
- Opening the screen puts the selection on the furthest level.

### Playing from it

- Choosing a tile starts that level as a **replay** unless it is the furthest level, which is ordinary play.
- A replay that is cleared records bests but does not change `profile.level` or `total_score`, and the running total shown is restored afterwards.
- On the level-complete screen after a replay, CONTINUE goes to the next level; if that is the furthest level it becomes ordinary play from there. RETRY and MAIN MENU are unchanged.
- A level started through `START_LEVEL` is a replay when it is below the profile's furthest level, and ordinary play otherwise.

## 4. Stars that feel like a reward

Applies to the star row on the level-complete screen. The level-select tiles and the play screen (section 5) use the same star shape, small and static.

- **The star itself:** larger (60 px, from 45), gold with a lighter top-left facet and a darker lower edge so it reads as cut metal, a thin bright outline, and a soft gold glow behind it. Unearned slots are dim outlines, as now.
- **Arrival:** each earned star drops in from 2.6× size, overshoots slightly below full size and settles (a short spring), over the existing `appearDuration`. The existing rising tinkle plays as it lands.
- **Impact:** on landing, a ring expands and fades from the star, and a burst of about a dozen gold sparks flies out and falls away.
- **Afterwards:** earned stars keep a gentle shimmer: a bright band sweeps across the row every few seconds, and the glow breathes slowly.
- **Five stars:** when the fifth lands, all five flash white together and a larger burst fires from the whole row.
- **NEW BEST for stars** (more stars than the level's previous best): the newly gained stars' glow is tinted cyan-to-magenta, matching the title art, for the rest of the screen.
- Everything is drawn procedurally; no new image or sound assets. Sparks are capped (about 80 alive) and the screen stays opaque.

## 5. Score on the play screen

The play screen shows the level score only as the POWER dial and never shows the total. A block is added in the HUD column under the AMMO dial, centred on the dials:

- **`SCORE`** label with the value beneath it, in the dial reading style with fixed-width digits. In ordinary play the value is the total before this level plus the level's current potential score, so it equals the TOTAL SCORE the level-complete screen would show if the level ended now. On a replay it is the level's current potential score alone.
- **Star row:** five small stars (the new star shape, static) filled to the count the current potential score would earn, with the rest as dim outlines.
- **`BEST n`** in small dim text, the level's best score, shown only when the level has one.
- The POWER dial and its label are unchanged.
- The `GUN UPGRADE xN` line moves below the new block. Everything stays inside `config.UI_ZONE_WIDTH` and above the bottom of the screen at 1352x878.

## Components

- **`profiles.py`**: `LevelBest` dataclass (`score`, `time`, `stars`); `Profile.bests: Dict[int, LevelBest]`; load/save; `ProfileManager.record_level_result(level, score, time_seconds, stars) -> LevelResult`, where `LevelResult` reports `first_clear`, `new_best_score`, `new_best_time`, `stars_gained`, and the previous best (or `None`). `update_active_profile_progress` is unchanged.
- **`rendering/stars.py`** (new): the faceted star drawing (`draw_star`), and `StarBurst` (ring and sparks). `AnimatedStarRating` in `rendering/ui_elements.py` is rebuilt on top of them and keeps its constructor, `update`, `draw`, `is_complete`, `set_sound_callback`, `x`, `y`, `star_spacing` so existing callers keep working; it gains an optional `previous_stars`.
- **`rendering/level_select_menu.py`** (new): `LevelSelectMenu` with `refresh()`, `navigate(dx, dy)`, `selected_level`, `can_play_selected`, `layout()`, `update(dt)`, `draw()`.
- **`rendering/level_complete_menu.py`**: draws the comparison lines from a `LevelResult` passed to `draw`.
- **`rendering/main_menu.py`**, **`rendering/controls_menu.py`**: the LEVELS button; the R / Y entries.
- **`config.py`**: `STATE_LEVEL_SELECT`; star size setting.
- **`game_handlers/state_handlers.py`**: `LevelSelectStateHandler`; R / Y in `PlayingStateHandler`; main-menu LEVELS option.
- **`entities/ship.py`**: `draw_ui` draws the score block from three new optional arguments (`score_value`, `star_count`, `best_score`).
- **`game.py`**: `replaying` flag; passing the score block's values to `draw_ui`; `restart_level()`; recording the result in `complete_level`; the shortened, skippable power-out sequence; update/draw for the new state.

## Testing

Written first.

- **Bests:** first clear; better score only; better time only; worse on both; stars never go down; failed run records nothing; round-trip through the file; old file without `bests` loads; malformed `bests` entry skipped; bests are per profile.
- **Retry:** R in play restarts the level and restores the pre-level total; R during the power-out sequence does too; a key during the sequence skips to the failed screen; the sequence ends by itself within 1.2 s.
- **Level select:** tiles for levels 1..furthest plus one locked; selection starts on the furthest; navigation clamps at the edges and scrolls; a locked tile cannot be played; star total; choosing a lower level is a replay that records bests without changing level or total; choosing the furthest is ordinary play; CONTINUE after a replay.
- **Level-complete lines:** FIRST CLEAR, NEW BEST, and the gap text with the right sign and format.
- **Stars:** earned stars arrive in order with one sound each; a star is larger than full size early in its arrival and full size at the end; a burst exists just after landing and is gone a second later; the five-star flash; `previous_stars` tints only the gained stars; spark count stays capped; drawing leaves the screen opaque.
- **HUD score:** the value equals pre-level total plus potential score in ordinary play and potential score alone on a replay; the star row matches `calculate_star_count`; BEST appears only when the level has one; the block and the gun-upgrade line stay inside the HUD column and on screen.
- **Menus:** LEVELS opens the screen and Esc returns; five main-menu buttons fit above the profile badge at 1352x878.

Final check: captures from the real game on the real display driver of the level select, the level-complete screen with a new best, and the star animation mid-burst.

## Out of scope

- Any change to how score, power or stars are calculated.
- Redefining total score.
- Online or shared leaderboards, daily levels, unlocks.
- New sounds or image assets.
- Mouse support for the grid.
