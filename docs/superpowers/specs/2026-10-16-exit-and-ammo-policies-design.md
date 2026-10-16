# Exit and ammo policies

Date: 2026-10-16. Status: design, awaiting review.

## Purpose

When a level's exit opens, and whether the player's ammo runs out, are hard-coded today, and both hang off an
inferred "boss level" idea. This replaces both with **policies** that each level names in its file. Adding a new
policy later should mean writing one small class and registering it, with no edits to the game loop, the loader or
the other policies. The code is to follow SOLID principles.

Success: every level plays as its file says; the player can always see what opens the exit; levels that have bosses
or eggs today play exactly as they do now; a new exit or
ammo policy can be added in one new class plus one registration line.

## What was decided

- **Exit policies (four to start):**
  - `always_open`: open from the start. **The default** when a level names no exit policy.
  - `timer`: opens once the level has run for a given number of seconds.
  - `type_cleared`: opens once every enemy of the named type(s) is dead.
  - `all_cleared`: opens once every enemy is dead.
- **Ammo policies (two to start):** `limited` (today's normal ammo: a stock of `initialAmmo`, topped up by powerups
  and kills) and `unlimited` (today's boss-level ammo). **The default is `limited`.**
- **No more boss levels.** `level_config.is_boss_level` and `Game.boss_level` go away. Nothing infers anything from
  the presence of a boss any more. A level that should make the player fight its boss says `all_cleared` (and
  `unlimited` ammo) in its file.
- **The Jev beacon** loses its "never on a boss level" rule. With no level-file override it appears from
  `hunterFirstLevel` on, every `hunterLevelInterval` levels, bosses or not. A level file's `hunter` key (or the
  layout's `beacon`) still forces it on or off. This change is accepted.
- **Existing levels keep playing as they do today.** Before today's changes the exit was shut on every level while
  any egg lived, and on boss levels while any enemy lived. So:
  - Every level file that is a boss level under today's rule gets `all_cleared` and `unlimited` written into it.
    That includes level 26, which is a boss level only because of its Neural hunter (confirmed).
  - Every other level file with eggs gets `type_cleared: ["egg"]` (confirmed). Babies are not included, matching
    today's rule, which checks eggs only.
  - Levels without a file get the same from the generation rules in `level_rules.py`: `all_cleared` and `unlimited`
    where `level_rules.is_boss_level` is true, `type_cleared: ["egg"]` where the level generates eggs, and the
    defaults otherwise.
- **Undo the "every enemy must die" change** made earlier today in `game.py`: that rule now lives only in the
  `all_cleared` policy.
- **Kept from today's earlier work** (already in the working tree, uncommitted): the per-kill power bonus (each enemy
  the player shoots down calls `Ship.activate_gun_upgrade()`), `CollisionHandler.player_kills`, and the scoring fix
  (`reset_scoring_to_profile_state` now points the collision handler at the new `ScoringSystem`), with their tests.

## Non-goals

- No new exit or ammo policies beyond the six above.
- No combining policies (no "timer OR all cleared"). A later combining policy should be possible without changing
  the interface, but is not built now.
- No change to how the exit portal looks or sounds when it opens or closes; `ExitPortal.set_activated` is reused.
- No level-start banner and no label at the portal; the side panel is the only place the condition is shown.

## Today's code this replaces

- `game.py`, in `update`: the `exit_locked` expression and `self.maze.exit.set_activated(not exit_locked, ...)`.
- `game.py`, in `start_level`: `self.boss_level = level_config.is_boss_level(self.level)` and
  `self.ship.infinite_ammo = self.boss_level`.
- `level_config.is_boss_level`, and its use in `level_allows_jev_beacon`.
- `level_rules.is_boss_level` stays: the generation rules still use it to decide which generated levels get bosses,
  and now also to give those levels their two policies. It describes generation only, not a property the game reads.

Under today's rule the level files 6, 12, 18, 24, 25 and 26 are boss levels (split boss, mother boss, Rules hunter or
Neural hunter, counted from the layout when a level has one). The reviewer found eggs on files 13, 14, 17, 19–23 and
26. Work the migration list out again from the code (`level_config` counts) rather than trusting these lists; several
level files have uncommitted edits in the working tree.

## The level file

Two optional top-level keys:

```json
"exit_policy": {"type": "all_cleared"},
"ammo_policy": {"type": "unlimited"}
```

with the other exit policies written as

```json
"exit_policy": {"type": "always_open"}
"exit_policy": {"type": "timer", "seconds": 60}
"exit_policy": {"type": "type_cleared", "enemy_types": ["egg", "mother_boss"]}
```

- `enemy_types` names come from `level_layout.ENEMY_TYPES`, plus `baby` for the babies that hatch from eggs.
- A missing key means the default (`always_open`, `limited`).
- An unknown `type` or bad settings (a missing or negative `seconds`, an empty or unknown `enemy_types`): log a
  warning and use the default, as a bad layout does today. A bad level file must never stop the game.
- The keys are top level rather than inside `layout`, so they apply to generated and laid-out levels alike and
  reverting a layout in the editor leaves them alone. (My call.)

## How it is built

**Exit policy.** One small interface, roughly:

```python
class ExitPolicy(Protocol):
    def is_open(self, state: ExitState) -> bool: ...
```

`ExitState` is a small read-only view the game builds each frame: the level's elapsed seconds and the active enemies
grouped by type. Policies read only that, never `Game`, so each one can be tested on its own with a hand-built
state. One class per policy. Once the exit has opened it stays open for the rest of the level, even if, say, a
replay ship spawns afterwards (my call: the game remembers the first "open" and stops asking).

**Ammo policy.** Same pattern: one interface the ship asks whether a shot costs ammo, with `LimitedAmmo` and
`UnlimitedAmmo`. It replaces `Ship.infinite_ammo`. The ammo gauge (`Ship.draw_ui`) shows infinity when the policy
says ammo is unlimited, as it does today.

**Registries.** Each family has a registry mapping a `type` name to a factory that builds the policy from the JSON
settings. Adding a policy = one class + one registration. The loader (`level_config`) parses the JSON through the
registry and falls back to the default. The game and the ship depend only on the interfaces.

**Generated levels.** For a level with no file, `level_config` asks the generation rules in `level_rules.py`
for its policies, as listed under "What was decided".

**Timer.** "Elapsed" is play time: it starts on the player's first move (`player_has_moved`) and adds up the
`dt` of each `Game.update` from then on, so time spent paused or before the first move doesn't count. It is not the
HUD clock (`ScoringSystem.get_current_time`), which counts wall time from when the level loads; that clock and the
score are left alone. (My call.)

## Showing the exit condition

The player has to be able to see what opens the exit. The side panel (`Ship.draw_ui`) gets an **EXIT** block below
the ammo gauge and the score readings (chosen from mockups). It stays visible all level: a small `EXIT` label, then
one or two short lines saying what's left. It counts down as progress is made and turns green with `OPEN` once the
exit opens.

Each policy supplies its own text, so a new policy brings its own wording and the HUD never needs a list of
policies: the interface gains something like `describe(state) -> list[str]`. The wording is my call:

| Policy | While shut | Once open |
|---|---|---|
| `always_open` | n/a | `OPEN` |
| `timer` | `OPENS IN` / `0:42` | `OPEN` |
| `type_cleared` | `KILL EGGS` / `3 LEFT` (several types: `KILL EGGS, SQUIDLETS`, with the total left) | `OPEN` |
| `all_cleared` | `KILL ALL` / `7 LEFT` | `OPEN` |

The text must fit the 200-pixel panel, shrinking the way the score readings already do. The colour while shut is
the builder's choice; green when open matches the portal (`colors.exit`). Check it on the real fullscreen display
(1352×878), not only under the dummy SDL driver.

## Enemy display names

Players will now read enemy names on the EXIT panel, so the enemies get new display names (chosen by the user).
Only what is shown changes; the internal names in level files, code and tests stay as they are.

| Internal | Name | Plural |
|---|---|---|
| `static` | Urchin | Urchins |
| `patrol` | Crab | Crabs |
| `aggressive` | Jelly | Jellies |
| `replay` | Squiddler | Squiddlers |
| `flocker` | Flocker | Flockers |
| `flighthouse` | Flighthouse | Flighthouses |
| `egg` | Egg | Eggs |
| `baby` | Squidlet | Squidlets |
| `anemone` | Anemone | Anemones |
| `split_boss` | Squiddler Boss | Squiddler Bosses |
| `mother_boss` | Mother | Mothers |
| `rules_hunter` | Terminator | Terminators |
| `neural_hunter` | Viber | Vibers |

- One shared table of names (singular and plural) that both the editor palette (today's `LABELS` in
  `rendering/level_editor.py`) and the exit policies' HUD text read. The non-enemy palette labels (Wall, Start,
  Exit, Jev beacon) stay where they are.
- The friendly hunter keeps its names ("Rules hunter", "Neural hunter", the pilot menu and so on). The new names
  are for enemies only.
- Add the new names to `GLOSSARY.md` so the code, the docs and the game use the same words.

## The level editor

The editor (`rendering/level_editor.py`, `editor/model.py`) shows the open level's exit and ammo policies and can
change them; saving writes `exit_policy` and `ammo_policy` beside the layout. Today `editor/files.py` keeps every key
it doesn't own, so existing policies survive a save. (Showing and setting policies in the editor is my guess at what
was wanted; it was not objected to.) The key bindings and the way policy settings (`seconds`, `enemy_types`) are
entered are left to the builder, in the style of the editor's existing key hints. Reverting a layout does not touch
the policy keys.

## Tests

- Each policy class against hand-built states, including bad settings falling back to the default.
- Loading: missing keys give the defaults; each `type` is parsed; a bad entry warns and falls back.
- Each policy's HUD text, shut and open, using the display names.
- Game wiring: a level file with each exit policy opens its exit when it should (reuse the `level_file` and `kill`
  helpers in `tests/test_boss_levels.py`); `unlimited` ammo never runs out.
- Migration: each migrated file, and each generated level that would be a boss level today, reports `all_cleared`
  and `unlimited`; each other file or generated level with eggs reports `type_cleared: ["egg"]`.
- The existing boss-level tests get rewritten for policies rather than deleted; tests that call `is_boss_level`
  (16 uses across `tests/`) move to the policies or to `level_rules.is_boss_level`.
- Baseline: before today's changes the full suite had 28 failures unrelated to this work (hunter, beacon, anemone
  and level-placement tests, several caused by uncommitted level-file edits). A 29th,
  `test_experiment_student.py::test_a_different_turn_rate_changes_the_episode`, appeared with the "every enemy must
  die" rule and should go away once it is undone. The work must not add failures.

## Left to the builder

Module and class names, where the registries live, the exact shape of `ExitState`, the editor's keys and layout, and
how the type list is entered in the editor.
