# Exit and Ammo Policies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each level names when its exit opens and whether ammo runs out, through small pluggable policy classes; the side panel tells the player what opens the exit; enemies get new display names; the "boss level" idea is removed.

**Architecture:** A new `policies/` package holds one generic registry, the exit policies and the ammo policies. Policies are small frozen dataclasses behind two Protocols and read only a plain `ExitState`, never `Game`. `level_config` turns a level file's `exit_policy` / `ammo_policy` keys (or, for levels without a file, the generation rules in `level_rules`) into policy objects. `Game` asks the exit policy each frame, the ship asks the ammo policy on each shot, and a new `rendering/exit_panel.py` draws the policy's own text.

**Tech Stack:** Python 3, pygame, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-exit-and-ammo-policies-design.md`

## Global Constraints

- Run tests with `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider <paths>`.
- The full suite has known failures unrelated to this work. Task 0 records them. After each task, the full suite must not fail any test outside that list.
- The working tree holds the user's own uncommitted edits (`levels/*.json`, `config/settings.json`, `assets/neural/hunter.npz`, untracked `levels/26.json`, `.codegraph/`). Never `git add -A` or `git add .`. Stage only the files a task names. Task 5 has its own rule for level files.
- Policy JSON keys are top level: `"exit_policy": {"type": ...}` and `"ammo_policy": {"type": ...}`. Exit type names: `always_open`, `timer` (setting `seconds`), `type_cleared` (setting `enemy_types`), `all_cleared`. Ammo type names: `limited`, `unlimited`.
- Defaults when a level file names no policy: exit `always_open`, ammo `limited`.
- A bad policy entry logs one warning per level and falls back to the default. It must never raise into the game.
- Internal enemy names (`static`, `patrol`, …) never change. Only display names change.
- The friendly hunter's names ("Rules hunter", "Neural hunter" in pilot menus and so on) do not change.
- Match the surrounding code: short docstrings, a comment only where the reason isn't obvious, the existing naming style.
- End every commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **An exit that opens and then has an enemy appear** (a squiddler from a dying boss, a squidlet hatching) must stay open. Pinned in Task 6 (`test_the_exit_stays_open_once_opened`).
2. **A hand-edited level file with `"seconds": "60"`, `true`, a negative number, or `enemy_types: ["dragon"]`** must warn and play as `always_open`, not crash. Pinned in Task 2 (registry tests) and Task 4 (`test_a_bad_exit_policy_warns_once_and_falls_back`).
3. **Time spent before the first move, or on the quit-confirmation screen,** must not count toward a `timer` exit. Pinned in Task 6 (`test_the_timer_waits_for_the_first_move`).
4. **A long plural on the EXIT panel** (`KILL SQUIDDLER BOSSES, SQUIDLETS`) must fit the 200-pixel panel and not spill onto the maze. Pinned in Task 7 (`test_long_text_stays_inside_the_panel`).
5. **Restarting a level** (death, or a replay from the level-complete screen) must reset the exit to shut and the timer to zero. Pinned in Task 6 (`test_restarting_a_level_shuts_the_exit_and_resets_the_timer`).

---

## File Structure

| File | Responsibility |
|---|---|
| `enemy_names.py` (new) | The one table of enemy display names, singular and plural. |
| `policies/__init__.py` (new) | Empty package marker. |
| `policies/registry.py` (new) | `PolicyError`, and the generic `PolicyRegistry` mapping a type name to a policy class. |
| `policies/exit.py` (new) | `ExitState`, the `ExitPolicy` Protocol, four exit policy classes, `EXIT_POLICIES`. |
| `policies/ammo.py` (new) | The `AmmoPolicy` Protocol, `LimitedAmmo`, `UnlimitedAmmo`, `AMMO_POLICIES`. |
| `rendering/exit_panel.py` (new) | Draws the EXIT block in the side panel. |
| `level_config.py` | Adds `get_level_exit_policy` / `get_level_ammo_policy`; removes `is_boss_level`. |
| `level_rules.py` | Adds `generated_exit_policy` / `generated_ammo_policy` (JSON dicts). |
| `game_handlers/entity_manager.py` | Adds `ENEMY_LISTS` and `active_counts()`. |
| `editor/generated.py` | Uses `ENEMY_LISTS` instead of its own `_LISTS`. |
| `entities/ship.py` | `ammo_policy` replaces `infinite_ammo`. |
| `game.py` | Wires both policies, the play clock and the panel; drops `boss_level` and today's every-enemy-must-die rule. |
| `editor/model.py`, `editor/files.py`, `rendering/level_editor.py` | Show, change and save both policies; labels come from `enemy_names`. |
| `GLOSSARY.md` | The new enemy names. |

---

### Task 0: Commit today's earlier work and record the baseline

**Files:**
- Modify: `game.py` (the `exit_locked` block in `update`, about line 765)
- Commit: `game.py`, `game_handlers/collision_handler.py`, `tests/test_boss_levels.py`, the spec, this plan

The working tree already holds the per-kill power bonus, `CollisionHandler.player_kills`, and the scoring fix in `reset_scoring_to_profile_state`, with their tests. It also holds the "every enemy must die" exit rule, which the spec says to undo.

- [ ] **Step 1: Restore the original exit rule** in `game.py`. Replace the `exit_locked` block with what's in `git show HEAD:game.py` (eggs alive, or a boss level with any enemy alive), including its comment. Also restore the two tests in `tests/test_boss_levels.py` that were rewritten today: rename `test_enemies_hold_an_ordinary_level_exit_shut` back to `test_enemies_do_not_hold_an_ordinary_level_exit_shut` and `test_an_ordinary_level_with_no_enemies_has_an_open_exit` back to `test_an_ordinary_level_has_an_open_exit`, with their bodies from `git show HEAD:tests/test_boss_levels.py`. Keep the two tests added at the end of the file: `test_every_kill_gives_the_player_a_power_bonus` and `test_a_kill_counts_on_the_games_score`.

- [ ] **Step 2: Run the full suite and save the baseline**

Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest -q -p no:cacheprovider 2>&1 | grep -E '^FAILED' | sort > docs/superpowers/plans/.baseline-failures.txt; wc -l docs/superpowers/plans/.baseline-failures.txt`
Expected: 28 lines. `tests/test_boss_levels.py` and `tests/test_experiment_student.py` are not in the list. If the count differs, read the list. It's only a problem if a failure involves `game.py`, the collision handler or scoring.

- [ ] **Step 3: Commit**

```bash
git add game.py game_handlers/collision_handler.py tests/test_boss_levels.py \
  docs/superpowers/specs/2026-10-16-exit-and-ammo-policies-design.md docs/superpowers/plans/2026-10-16-exit-and-ammo-policies.md
git commit -m "fix: kills give a power bonus and count on the score

The collision handler kept the ScoringSystem the game replaced at start-up,
so kills never reached the score.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(The baseline file stays untracked. Delete it after Task 8.)

---

### Task 1: Enemy display names

**Files:**
- Create: `enemy_names.py`
- Modify: `rendering/level_editor.py:35-39` (`LABELS`)
- Modify: `GLOSSARY.md` (a new `### Enemies` section after `### Things in the maze`)
- Test: `tests/test_enemy_names.py` (new); `tests/test_level_editor.py:197-198`

**Interfaces:**
- Produces: `enemy_names.ENEMY_NAMES: Dict[str, Tuple[str, str]]` (kind → (singular, plural)); `enemy_names.name(kind: str) -> str`; `enemy_names.plural(kind: str) -> str`; `enemy_names.KINDS: Tuple[str, ...]` = `level_layout.ENEMY_TYPES + ('baby',)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_enemy_names.py`

```python
import enemy_names
from level_layout import ENEMY_TYPES

def test_every_enemy_kind_has_a_name_and_a_plural():
    assert set(enemy_names.ENEMY_NAMES) == set(ENEMY_TYPES) | {'baby'}
    assert enemy_names.KINDS == ENEMY_TYPES + ('baby',)

def test_the_names_chosen_for_the_game():
    expected = {'static': ('Urchin', 'Urchins'), 'patrol': ('Crab', 'Crabs'), 'aggressive': ('Jelly', 'Jellies'),
                'replay': ('Squiddler', 'Squiddlers'), 'flocker': ('Flocker', 'Flockers'),
                'flighthouse': ('Flighthouse', 'Flighthouses'), 'egg': ('Egg', 'Eggs'),
                'baby': ('Squidlet', 'Squidlets'), 'anemone': ('Anemone', 'Anemones'),
                'split_boss': ('Squiddler Boss', 'Squiddler Bosses'), 'mother_boss': ('Mother', 'Mothers'),
                'rules_hunter': ('Terminator', 'Terminators'), 'neural_hunter': ('Viber', 'Vibers')}
    assert enemy_names.ENEMY_NAMES == expected
    assert enemy_names.name('static') == 'Urchin' and enemy_names.plural('aggressive') == 'Jellies'
```

In `tests/test_level_editor.py:198`, change the expectation to `LABELS['neural_hunter'] == 'Viber'`, and add `assert LABELS['wall'] == 'Wall' and LABELS['beacon'] == 'Jev beacon'`.

- [ ] **Step 2: Run them to see them fail**

Run: `… pytest tests/test_enemy_names.py tests/test_level_editor.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'enemy_names'`.

- [ ] **Step 3: Implement** `enemy_names.py`, with the table exactly as in the test. Then build `LABELS` in `rendering/level_editor.py` as `{'wall': 'Wall', **{kind: name(kind) for kind in ENEMY_TYPES}, 'start': 'Start', 'exit': 'Exit', 'beacon': 'Jev beacon'}`. Add a `### Enemies` section to `GLOSSARY.md` with one entry per enemy in the file's existing format: the display name in bold, a line saying what it is, `_Code name_: <internal name>`. Add a line stating that the friendly hunter keeps "Rules hunter" / "Neural hunter".

- [ ] **Step 4: Run the tests to see them pass**

Run: `… pytest tests/test_enemy_names.py tests/test_level_editor.py -q`
Expected: all pass.

- [ ] **Step 5: Commit** `enemy_names.py rendering/level_editor.py GLOSSARY.md tests/test_enemy_names.py tests/test_level_editor.py` with message `feat: new display names for the enemies`.

---

### Task 2: The policy registry and the exit policies

**Files:**
- Create: `policies/__init__.py`, `policies/registry.py`, `policies/exit.py`
- Test: `tests/test_exit_policies.py` (new)

**Interfaces:**
- Consumes: `enemy_names.KINDS`, `enemy_names.plural` (Task 1).
- Produces:
  - `policies.registry.PolicyError(ValueError)`.
  - `policies.registry.PolicyRegistry(family: str)` with:
    - `register(cls) -> cls`, a class decorator keyed by `cls.name`; it raises `ValueError` on a duplicate name.
    - `parse(data: Any) -> policy`. `data` must be a dict with a str `type` naming a registered class, which is built with `cls.from_json(data)`. It raises `PolicyError` on anything else.
    - `names() -> Tuple[str, ...]`, in registration order.
    - `starter(name: str) -> policy`, which calls `cls.starter()`.
  - `policies.exit.ExitState`: a frozen dataclass with `elapsed_seconds: float` and `active: Mapping[str, int]` (enemy kind → number alive), plus `left(kinds: Optional[Iterable[str]] = None) -> int`, which sums `active` over `kinds`, or over all kinds when `None`.
  - `policies.exit.ExitPolicy` Protocol:
    - `name: ClassVar[str]`
    - `is_open(state: ExitState) -> bool`
    - `describe(state: ExitState) -> List[str]`, the HUD lines while shut
    - `label() -> str`, a one-line summary for the editor
    - `to_json() -> Dict[str, Any]`, which includes `"type"`
    - `@classmethod from_json(data: Mapping) -> Self`
    - `@classmethod starter() -> Self`
  - Classes (frozen dataclasses), each decorated with `@EXIT_POLICIES.register`:
    - `AlwaysOpen()`, name `always_open`
    - `OpenAfterTime(seconds: float)`, name `timer`
    - `TypeCleared(enemy_types: Tuple[str, ...])`, name `type_cleared`
    - `AllCleared()`, name `all_cleared`
  - `policies.exit.EXIT_POLICIES: PolicyRegistry`, and `policies.exit.DEFAULT_EXIT_POLICY = AlwaysOpen()`.

- [ ] **Step 1: Write the failing tests** in `tests/test_exit_policies.py`

```python
import pytest
from policies.exit import EXIT_POLICIES, AlwaysOpen, OpenAfterTime, TypeCleared, AllCleared, ExitState
from policies.registry import PolicyError

def state(seconds=0.0, **active):
    return ExitState(seconds, active)

def test_always_open_is_open_with_enemies_about():
    assert AlwaysOpen().is_open(state(0, egg=3))

def test_the_timer_opens_at_its_time():
    policy = OpenAfterTime(60)
    assert not policy.is_open(state(59.9)) and policy.is_open(state(60.0))
    assert policy.describe(state(17.2)) == ['OPENS IN', '0:43']        # rounds the wait up
    assert OpenAfterTime(125).describe(state(0)) == ['OPENS IN', '2:05']

def test_type_cleared_waits_only_for_its_types():
    policy = TypeCleared(('egg',))
    assert not policy.is_open(state(egg=1, static=4)) and policy.is_open(state(static=4, baby=2))
    assert policy.describe(state(egg=3)) == ['KILL EGGS', '3 LEFT']
    assert TypeCleared(('egg', 'baby')).describe(state(egg=1, baby=2)) == ['KILL EGGS, SQUIDLETS', '3 LEFT']

def test_all_cleared_waits_for_every_enemy():
    assert not AllCleared().is_open(state(baby=1)) and AllCleared().is_open(state())
    assert AllCleared().describe(state(egg=2, static=5)) == ['KILL ALL', '7 LEFT']

def test_labels_for_the_editor():
    assert [p.label() for p in (AlwaysOpen(), OpenAfterTime(60), TypeCleared(('egg', 'baby')), AllCleared())] == \
           ['Always open', 'Timer 60s', 'Kill Eggs, Squidlets', 'Kill all']

@pytest.mark.parametrize('data', [{'type': 'always_open'}, {'type': 'timer', 'seconds': 60},
                                  {'type': 'type_cleared', 'enemy_types': ['egg', 'mother_boss']},
                                  {'type': 'all_cleared'}])
def test_a_policy_survives_a_round_trip_through_json(data):
    assert EXIT_POLICIES.parse(data).to_json() == data

@pytest.mark.parametrize('data', [None, [], {}, {'type': 'sometimes'}, {'type': 7},
                                  {'type': 'timer'}, {'type': 'timer', 'seconds': -1},
                                  {'type': 'timer', 'seconds': '60'}, {'type': 'timer', 'seconds': True},
                                  {'type': 'type_cleared'}, {'type': 'type_cleared', 'enemy_types': []},
                                  {'type': 'type_cleared', 'enemy_types': ['dragon']},
                                  {'type': 'type_cleared', 'enemy_types': 'egg'}])
def test_bad_entries_are_refused(data):
    with pytest.raises(PolicyError):
        EXIT_POLICIES.parse(data)

def test_the_registry_lists_and_starts_every_policy():
    assert EXIT_POLICIES.names() == ('always_open', 'timer', 'type_cleared', 'all_cleared')
    assert EXIT_POLICIES.starter('timer') == OpenAfterTime(60)
    assert EXIT_POLICIES.starter('type_cleared') == TypeCleared(('egg',))

def test_registering_a_name_twice_is_refused():
    with pytest.raises(ValueError):
        EXIT_POLICIES.register(AllCleared)
```

- [ ] **Step 2: Run them to see them fail**

Run: `… pytest tests/test_exit_policies.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'policies'`.

- [ ] **Step 3: Implement `policies/registry.py` and `policies/exit.py`** to the interfaces above.
  - Timer text: `OPENS IN`, then `m:ss` of `math.ceil(seconds - elapsed)`, never below 0. `seconds` must be an `int` or `float`, not a `bool`, and at least 0. `to_json` writes an int when the value is whole, so `60` round-trips as `60`. `starter()` is `OpenAfterTime(60)`.
  - `TypeCleared` text: `KILL ` followed by the upper-cased plurals joined with `, `, then `{n} LEFT`. `enemy_types` must be a non-empty list of names in `enemy_names.KINDS`. It's stored as a tuple, and `to_json` writes a list. `starter()` is `TypeCleared(('egg',))`.
  - `AllCleared` text: `KILL ALL`, then `{n} LEFT`.
  - `AlwaysOpen.describe` returns `[]`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `… pytest tests/test_exit_policies.py -q`
Expected: all pass.

- [ ] **Step 5: Commit** `policies/ tests/test_exit_policies.py` with message `feat: exit policies behind a registry`.

---

### Task 3: Ammo policies on the ship

**Files:**
- Create: `policies/ammo.py`
- Modify: `entities/ship.py:49` (the attribute), `:178-185` (`fire`), `:672-681` (the ammo gauge)
- Test: `tests/test_ammo_policies.py` (new); `tests/test_ship.py:~203` (the helper that sets `infinite_ammo`)

**Interfaces:**
- Consumes: `PolicyRegistry`, `PolicyError` (Task 2).
- Produces:
  - `policies.ammo.AmmoPolicy` Protocol: `name: ClassVar[str]`, `charges_for_shots() -> bool`, `label() -> str`, `to_json() -> Dict`, `from_json(data) -> Self`, `starter() -> Self`.
  - `LimitedAmmo()`: name `limited`, charges `True`, label `Limited ammo`.
  - `UnlimitedAmmo()`: name `unlimited`, charges `False`, label `Unlimited ammo`.
  - `AMMO_POLICIES: PolicyRegistry`, and `DEFAULT_AMMO_POLICY = LimitedAmmo()`.
  - `Ship.ammo_policy: AmmoPolicy`, which defaults to `LimitedAmmo()`. `Ship.infinite_ammo` is removed.

- [ ] **Step 1: Write the failing tests.** In `tests/test_ammo_policies.py`:
  - `test_limited_ammo_runs_out`: a `Ship((100.0, 100.0))` with `ship.ammo = 1` fires once, then `fire()` returns `None`.
  - `test_unlimited_ammo_never_runs_out`: with `ship.ammo_policy = UnlimitedAmmo()` and `ship.ammo = 0`, five `fire()` calls each return projectiles, and `ship.ammo` stays `0`.
  - `test_ammo_policies_round_trip`: for each of `{'type': 'limited'}` and `{'type': 'unlimited'}`, `AMMO_POLICIES.parse(d).to_json() == d`.
  - `test_a_bad_ammo_policy_is_refused`: `{'type': 'lots'}` raises `PolicyError`.
  - `test_the_names`: `AMMO_POLICIES.names() == ('limited', 'unlimited')`.

  Take the ship and sound-manager setup from the existing `tests/test_ship.py` (the `ship.sound_manager` must be a `Mock`). In `tests/test_ship.py`, change the helper that sets `ship.infinite_ammo = infinite` to set `ship.ammo_policy = UnlimitedAmmo() if infinite else LimitedAmmo()`.

- [ ] **Step 2: Run them to see them fail**

Run: `… pytest tests/test_ammo_policies.py tests/test_ship.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'policies.ammo'`.

- [ ] **Step 3: Implement** `policies/ammo.py`. In `Ship`:
  - `fire` charges ammo only when `self.ammo_policy.charges_for_shots()`.
  - The ammo gauge shows `∞` when it doesn't.
  - Update the two comments that mention boss levels to talk about the ammo policy instead.

  `game.py:331` still sets `infinite_ammo`. Replace that line with `self.ship.ammo_policy = UnlimitedAmmo() if self.boss_level else LimitedAmmo()` for now; Task 6 replaces it again.

- [ ] **Step 4: Run the tests to see them pass**

Run: `… pytest tests/test_ammo_policies.py tests/test_ship.py tests/test_boss_levels.py -q`
Expected: all pass. The boss-level ammo tests use `game.ship.infinite_ammo`; change those asserts to `not game.ship.ammo_policy.charges_for_shots()` (or the positive form). Do the same for `tests/test_layout_play.py:89`, keeping its `played.boss_level` part for now.

- [ ] **Step 5: Commit** `policies/ammo.py entities/ship.py game.py tests/test_ammo_policies.py tests/test_ship.py tests/test_boss_levels.py tests/test_layout_play.py` with message `feat: ammo policies replace the ship's infinite-ammo flag`.

---

### Task 4: Levels name their policies

**Files:**
- Modify: `level_config.py` (two new functions next to `get_level_layout`), `level_rules.py` (two new functions next to `is_boss_level`)
- Test: `tests/test_level_policies.py` (new)

**Interfaces:**
- Consumes: `EXIT_POLICIES`, `DEFAULT_EXIT_POLICY`, `AMMO_POLICIES`, `DEFAULT_AMMO_POLICY`, `PolicyError`.
- Produces:
  - `level_rules.generated_exit_policy(level: int) -> Optional[Dict]`:
    - `{'type': 'all_cleared'}` when `is_boss_level(level)`;
    - otherwise `{'type': 'type_cleared', 'enemy_types': ['egg']}` when `get_enemy_counts(level).egg > 0`;
    - otherwise `None`.
  - `level_rules.generated_ammo_policy(level: int) -> Optional[Dict]`: `{'type': 'unlimited'}` when `is_boss_level(level)`, otherwise `None`.
  - `level_config.get_level_exit_policy(level: int) -> ExitPolicy` and `level_config.get_level_ammo_policy(level: int) -> AmmoPolicy`. When the level has a file, they use the file's key; when it has none, they use the `level_rules` function above. A missing key or `None` gives the default. An entry the registry refuses logs `'Level %d: ignoring its %s: %s'` once per (level, family, message), in the same way as `_warned_layouts`, and gives the default.

- [ ] **Step 1: Write the failing tests** in `tests/test_level_policies.py`. Use `monkeypatch.setattr(level_config, 'load_level_config', ...)` in the way `tests/test_boss_levels.py` does.
  - `test_a_file_without_policies_gets_the_defaults`: `{'seed': 1}` gives `AlwaysOpen()` and `LimitedAmmo()`.
  - `test_a_file_names_its_policies`: `{'exit_policy': {'type': 'timer', 'seconds': 30}, 'ammo_policy': {'type': 'unlimited'}}` gives `OpenAfterTime(30)` and `UnlimitedAmmo()`.
  - `test_a_bad_exit_policy_warns_once_and_falls_back` (caplog): `{'exit_policy': {'type': 'timer', 'seconds': 'soon'}}` gives `AlwaysOpen()` on two calls, with exactly one warning record that contains `Level 9`.
  - `test_a_generated_boss_level_must_be_cleared_with_unlimited_ammo`: with `load_level_config` returning `None`, level 30 gives `AllCleared()` and `UnlimitedAmmo()`.
  - `test_a_generated_level_with_eggs_needs_the_eggs_dead`: with `load_level_config` returning `None`, pick the first level in 27..60 that isn't a boss level and has `level_rules.get_enemy_counts(level).egg > 0`. Assert it gives `TypeCleared(('egg',))`.
  - `test_a_generated_level_without_eggs_or_bosses_is_open`: with `load_level_config` returning `None`, pick a level that is neither a boss level nor has eggs (search 1..60). Assert it gives `AlwaysOpen()`.
  - `test_generated_bosses_fall_on_the_rules_boss_levels`: with `load_level_config` returning `None`, for levels 1..120, `level_rules.is_boss_level(level)` equals `(level_config.get_level_split_boss_count(level) + level_config.get_level_mother_boss_count(level) + level_config.get_level_rules_hunter_count(level) + level_config.get_level_neural_hunter_count(level)) > 0`. This pins the generated levels to today's rule. If it fails, stop and report: generated levels would then not play as they do today.

- [ ] **Step 2: Run them to see them fail**

Run: `… pytest tests/test_level_policies.py -q`
Expected: FAIL with `AttributeError: module 'level_config' has no attribute 'get_level_exit_policy'`.

- [ ] **Step 3: Implement** the four functions.

- [ ] **Step 4: Run the tests to see them pass**

Run: `… pytest tests/test_level_policies.py -q`
Expected: all pass.

- [ ] **Step 5: Commit** `level_config.py level_rules.py tests/test_level_policies.py` with message `feat: levels name their exit and ammo policies`.

---

### Task 5: Write the policies into today's level files

**Files:**
- Modify: every `levels/N.json` whose behaviour today needs a policy

**Rule for level files:** these files hold the user's uncommitted edits. Before Step 1, run `git status --short levels/`. If any file there is modified or untracked, stop and ask the user to commit their level edits first, or to say that this commit may include them. Don't stage level files until they've answered.

- [ ] **Step 1: Run a one-off migration script** from the scratchpad, not committed. For each `levels/N.json`:
  - If `level_config.is_boss_level(N)` (still present until Task 6): set `exit_policy = {'type': 'all_cleared'}` and `ammo_policy = {'type': 'unlimited'}`.
  - Otherwise, if `level_config.get_level_egg_count(N) > 0`: set `exit_policy = {'type': 'type_cleared', 'enemy_types': ['egg']}`.
  - Otherwise, leave the file alone.

  Write with `editor.files._write(path, data)` so the formatting matches what the editor writes. Print the list of levels changed. The spec expects boss files 6, 12, 18, 24, 25, 26 and egg files including 13, 14, 17, 19–23, but the script's output is what counts.

- [ ] **Step 2: Check that only the two keys changed.** For each changed file, load `git show HEAD:levels/N.json` (or the pre-script copy for the untracked `levels/26.json`), drop `exit_policy` and `ammo_policy` from the new JSON, and assert the two are equal. Also run `git diff --stat levels/` and confirm that only the files listed in Step 1 changed. If the line counts suggest the re-serialization reformatted the whole file, re-read the diff to confirm the only real change is the added keys.

- [ ] **Step 3: Check the result through the loader:** `venv/bin/python -c "import level_config as c; [print(n, c.get_level_exit_policy(n).to_json(), c.get_level_ammo_policy(n).to_json()) for n in range(1, 27)]"`. Expected: every boss file shows `all_cleared` / `unlimited`, every egg file shows `type_cleared` / `limited`, and the rest show `always_open` / `limited`.

  This is a one-off check rather than a permanent test (my call): a permanent test would stop a designer from changing a level's policy later.

- [ ] **Step 4: Commit** only the changed level files, with message `chore: level files name the exit and ammo policies they play by today`.

---

### Task 6: The game uses the policies, and boss levels go away

**Files:**
- Modify: `game_handlers/entity_manager.py` (add `ENEMY_LISTS`, `active_counts`)
- Modify: `editor/generated.py:5-7` (use `ENEMY_LISTS` without `babies`)
- Modify: `game.py`:
  - `:162` (`boss_level`)
  - `:329-331` in `start_level`
  - the `exit_locked` block in `update` (about line 765)
- Modify: `level_config.py`: remove `is_boss_level`; `level_allows_jev_beacon` becomes `level >= config.HUNTER_FIRST_LEVEL` when the file has no override; update the `level_has_hunter` docstring.
- Test: `tests/test_boss_levels.py` → `git mv` it to `tests/test_exit_policies_game.py` and rewrite it. Also update `tests/test_hunter_integration.py:71`, `tests/test_jev_beacon.py:111,169`, `tests/test_layout_play.py:89`, `tests/test_level_arc.py:40`, `tests/test_level_layout.py:83`, `tests/test_neural_hunter.py:87,133` and `tests/test_rules_hunter_level.py:31-46`.

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces:
  - `entity_manager.ENEMY_LISTS: Dict[str, Optional[str]]`: the list attribute → its enemy kind, where `None` means "use `enemy.type`", as `editor/generated.py`'s `_LISTS` has it today, plus `'babies': 'baby'`.
  - `EntityManager.active_counts() -> Dict[str, int]`: active enemies per kind, with kinds that have none left out.
  - On `Game`:
    - `exit_policy: ExitPolicy`
    - `exit_opened: bool`
    - `play_seconds: float`
    - `exit_state() -> ExitState`, built from `play_seconds` and `entity_manager.active_counts()`
  - `Game.boss_level` and `level_config.is_boss_level` no longer exist.

- [ ] **Step 1: Rewrite the game tests** in `tests/test_exit_policies_game.py`. Keep the file's `level_file`, `game`, `start` and `kill` helpers, and give `level_file` a `policies` keyword that is merged into the returned dict. Delete the tests about classifying boss levels and about hunters on boss levels (`test_without_a_file_every_sixth_level_is_a_boss_level` through `test_no_hunter_on_a_boss_level_made_by_a_level_file`). Keep the hunter tests that don't depend on boss levels, the endless-arena test, the maze-complexity test, and the two kill tests. Replace every exit and ammo test with these:
  - `test_an_exit_with_no_policy_is_open_whatever_is_alive`: `level_file(split_boss=1, egg=2)`, started on level 6, has its exit activated.
  - `test_all_cleared_holds_the_exit_until_every_enemy_is_dead`: `split_boss=1, replay=2` with `all_cleared`. The exit is shut while any are alive; kill the boss and it's still shut; kill the replay ships, update, and it's open.
  - `test_type_cleared_needs_only_its_types_dead`: `egg=2, static=2` with `type_cleared ['egg']`. Shut; kill the eggs, update, and it's open while the statics live.
  - `test_the_timer_waits_for_the_first_move`: `timer 1` second. Run `game.update(1.0)` 120 times with `player_has_moved` False: still shut. Set `game.player_has_moved = True` and run 61 updates: open.
  - `test_the_exit_stays_open_once_opened`: `all_cleared` with `replay=1`. Kill it, update, and the exit is open. Append a `ReplayEnemyShip((600.0, 400.0), game.command_recorder)` to `game.replay_enemies` and update: still open.
  - `test_restarting_a_level_shuts_the_exit_and_resets_the_timer`: `all_cleared` with `replay=1`. Kill it, update, and it's open. `start(game, 3)` again: shut, and `game.play_seconds == 0.0`.
  - `test_the_ammo_policy_comes_from_the_level_file`: `ammo_policy unlimited` gives `not game.ship.ammo_policy.charges_for_shots()`; no key gives limited.
  - `test_a_jev_beacon_can_lie_on_a_level_with_a_boss`: `level_file(split_boss=1)` on level 6 with `HUNTER_LEVEL_INTERVAL` monkeypatched to 1 gives `level_config.level_allows_jev_beacon(6)` True, and a beacon in `game.powerup_crystals`.

  In the other test files, drop the `is_boss_level` monkeypatches. They no longer matter, because a beacon is allowed whenever the file says nothing. `tests/test_jev_beacon.py:111` is parametrized on `boss`: assert that the beacon rule ignores it, or drop the parameter. Replace every `is_boss_level(...)` or `played.boss_level` assert with the fact it stood for: a boss count (`get_level_split_boss_count`, `get_level_rules_hunter_count`, `get_level_neural_hunter_count`), or `exit_policy` / `ammo_policy`. The exception is `tests/test_level_arc.py:40`: move it to `level_rules.is_boss_level` for levels without a file, or drop it if the arc is all files. One more case: `tests/test_rules_hunter_level.py:37` asserts level 26 isn't a boss level. That level is now migrated to `all_cleared`, so assert that instead.

- [ ] **Step 2: Run them to see them fail**

Run: `… pytest tests/test_exit_policies_game.py -q`
Expected: FAIL with `AttributeError` on `exit_policy` / `play_seconds`.

- [ ] **Step 3: Implement.**
  - `start_level` sets `exit_policy` from `level_config.get_level_exit_policy`, `ship.ammo_policy` from `get_level_ammo_policy`, `exit_opened = False` and `play_seconds = 0.0`.
  - `update` replaces the `exit_locked` block. When `self.player_has_moved and not self.game_frozen`, it adds `dt / config.FPS` to `play_seconds`; dt is in frames at `config.FPS`, see `LevelEditor.update`. Then, if not `exit_opened` and `exit_policy.is_open(self.exit_state())`, it sets `exit_opened = True`. Then `self.maze.exit.set_activated(self.exit_opened, self.sound_manager)` while `self.maze.exit.active`.
  - Delete `boss_level` and its comment, `level_config.is_boss_level`, and the boss clause in `level_allows_jev_beacon`.
  - `editor/generated.py` builds its list from `ENEMY_LISTS`, skipping `'babies'`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `… pytest tests/test_exit_policies_game.py tests/test_jev_beacon.py tests/test_hunter_integration.py tests/test_layout_play.py tests/test_level_arc.py tests/test_level_layout.py tests/test_neural_hunter.py tests/test_rules_hunter_level.py tests/test_level_editor.py -q`
Expected: no failures outside the baseline file. Then run the full suite and compare it against `docs/superpowers/plans/.baseline-failures.txt`: there must be no new names. Also run `grep -rn "is_boss_level\|boss_level\b\|infinite_ammo" --include='*.py' . | grep -v venv`. The only remaining hits should be `level_rules.is_boss_level` and its callers in `level_rules.py` and the tests.

- [ ] **Step 5: Commit** the files named in this task, including the `git mv`, with message `feat: the level's exit policy decides when the exit opens; no more boss levels`.

---

### Task 7: The EXIT panel

**Files:**
- Create: `rendering/exit_panel.py`
- Modify: `game.py`, in `draw_game` right after `self.ship.draw_ui(...)` (about line 1340)
- Test: `tests/test_exit_panel.py` (new)

**Interfaces:**
- Consumes: `Game.exit_policy`, `Game.exit_opened`, `Game.exit_state()` (Task 6).
- Produces: `rendering.exit_panel.draw_exit_panel(screen: pygame.Surface, lines: Sequence[str], is_open: bool, top: int = EXIT_PANEL_TOP) -> pygame.Rect`, which returns the area it drew. `EXIT_PANEL_TOP = 740`. That puts it below the gun-upgrade bar, whose label sits at y=690 in `Ship.draw_ui`.

- [ ] **Step 1: Write the failing tests** in `tests/test_exit_panel.py`. Use `pygame.init()` and a `pygame.Surface((1352, 878))` filled with `config.COLOR_BACKGROUND`.
  - `test_a_shut_exit_shows_what_is_left`: `draw_exit_panel(surface, ['KILL EGGS', '3 LEFT'], False)` returns a rect with `top >= EXIT_PANEL_TOP`, and some pixel in that rect differs from the background.
  - `test_an_open_exit_says_open_in_the_exit_colour`: `draw_exit_panel(surface, [], True)` draws at least one pixel equal to `config.COLOR_EXIT`. Turn antialiasing off for this check, or look for pixels close to it, whichever fits how the font renders.
  - `test_long_text_stays_inside_the_panel`: the returned rect for `['KILL SQUIDDLER BOSSES, SQUIDLETS', '12 LEFT']` has `right <= config.UI_ZONE_WIDTH`, and every pixel at x ≥ `UI_ZONE_WIDTH` is still the background.

- [ ] **Step 2: Run them to see them fail**

Run: `… pytest tests/test_exit_panel.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement.**
  - Draw a small `EXIT` label in `(150, 160, 195)` with `get_font(18)`, centred on `config.UI_ZONE_WIDTH // 2`.
  - Below it, draw each line with `get_font(24)`, or `OPEN` alone in `config.COLOR_EXIT` when `is_open`.
  - Shut-colour lines are the builder's choice. `(255, 150, 50)` matches the mockup.
  - A line wider than `UI_ZONE_WIDTH - 24` is shrunk with `pygame.transform.smoothscale`, as the score readings in `Ship.draw_ui` are.

  In `draw_game`, inside the same `if not self.exit_explosion_active:` block, call `draw_exit_panel(self.screen, [] if self.exit_opened else self.exit_policy.describe(self.exit_state()), self.exit_opened)`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `… pytest tests/test_exit_panel.py -q`
Expected: all pass.

- [ ] **Step 5: Check it on the real display.** The dummy SDL driver hides alpha and layout problems. Run the game fullscreen (1352×878) on level 13 (eggs) and level 6 (all cleared), and take screenshots. Confirm the EXIT block sits clear of the gun-upgrade bar, the readings and the bottom edge, and that it turns to `OPEN` when the exit opens. If it overlaps, move `EXIT_PANEL_TOP` and say so in the commit.

- [ ] **Step 6: Commit** `rendering/exit_panel.py game.py tests/test_exit_panel.py` with message `feat: the side panel shows what opens the exit`.

---

### Task 8: The editor shows, changes and saves the policies

**Files:**
- Modify: `editor/model.py` (`EditorModel.__init__`, new methods)
- Modify: `editor/files.py` (`save_layout`)
- Modify: `rendering/level_editor.py`: `_open_level`, `_edit_key`, `_save`, and the hint drawing
- Test: `tests/test_editor_model.py`, `tests/test_editor_files.py` (or wherever `save_layout` is tested today; check with `grep -ln save_layout tests/`), `tests/test_level_editor.py`

**Interfaces:**
- Consumes: `EXIT_POLICIES`, `AMMO_POLICIES`, `OpenAfterTime`, `TypeCleared`, `level_config.get_level_exit_policy` / `get_level_ammo_policy`.
- Produces:
  - `EditorModel(level, layout, exit_policy=DEFAULT_EXIT_POLICY, ammo_policy=DEFAULT_AMMO_POLICY)`, with attributes `exit_policy` and `ammo_policy`.
  - `EditorModel.cycle_exit_policy()` and `EditorModel.cycle_ammo_policy()`: step to the next name in the registry's `names()`, wrapping, and use `starter()`.
  - `EditorModel.adjust_timer(delta: int) -> bool`: only for `OpenAfterTime`, never below 10 seconds; returns False if nothing changed.
  - `EditorModel.toggle_exit_type(kind: str) -> bool`: only for `TypeCleared` and an enemy kind; it refuses to remove the last type.
  - Every change sets `dirty`.
  - `files.save_layout(path, layout, defaults, extra: Optional[Mapping] = None)`: writes `extra`'s keys beside `layout`.

- [ ] **Step 1: Write the failing tests.**
  - Model, in `tests/test_editor_model.py`:
    - cycling from `AlwaysOpen()` gives `OpenAfterTime(60)`, then `TypeCleared(('egg',))`, then `AllCleared()`, then `AlwaysOpen()`;
    - `adjust_timer(10)` on `OpenAfterTime(60)` gives `OpenAfterTime(70)`;
    - `adjust_timer(-60)` gives `OpenAfterTime(10)`;
    - `adjust_timer` on `AllCleared()` returns False;
    - `toggle_exit_type('baby')` on `TypeCleared(('egg',))` gives `('egg', 'baby')`; toggling `'egg'` and then `'baby'` refuses the second;
    - each change sets `dirty`.
  - Files: `save_layout(..., extra={'exit_policy': {'type': 'all_cleared'}})` writes that key and keeps the others; `revert_layout` on a file it didn't create leaves `exit_policy` in place.
  - Editor, in `tests/test_level_editor.py` with its existing fixtures:
    - pressing `K_e` changes `model.exit_policy`;
    - pressing `K_a` changes `model.ammo_policy`;
    - `K_s` writes both policies' `to_json()` into the saved file;
    - opening level 6 starts the model with `AllCleared()` and `UnlimitedAmmo()` (from Task 5's migration).

- [ ] **Step 2: Run them to see them fail**

Run: `… pytest tests/test_editor_model.py tests/test_level_editor.py -q` (plus the files test)
Expected: FAIL with `TypeError` / `AttributeError` on the new names.

- [ ] **Step 3: Implement.**
  - Keys: `E` cycles the exit policy, `A` cycles ammo, `-` / `=` adjust the timer by 10 seconds, and `T` toggles the palette's selected enemy kind into or out of a `type_cleared` list. A refused key `_say`s why, for example `"Timer only"` or `"Keep at least one type"`.
  - `_open_level` reads both policies from `level_config`. For a level with no file, that gives the generation rules' policies, so saving such a level keeps how it plays.
  - `_save` passes `extra={'exit_policy': model.exit_policy.to_json(), 'ammo_policy': model.ammo_policy.to_json()}`.
  - Draw `Exit: {label}   Ammo: {label}` and the four key hints in the editor's existing hint style.
  - Reverting a file the editor created still deletes the whole file, policies included (my call): the level then plays by the generation rules again.

- [ ] **Step 4: Run the tests to see them pass**, then run the full suite and compare it with the baseline file.

Run: `… pytest tests/test_editor_model.py tests/test_level_editor.py -q`, then the full suite.
Expected: no failures outside the baseline.

- [ ] **Step 5: Commit** `editor/model.py editor/files.py rendering/level_editor.py` and the test files, with message `feat: the level editor sets a level's exit and ammo policies`. Then delete `docs/superpowers/plans/.baseline-failures.txt`.
