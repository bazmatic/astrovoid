# Neural Jelly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and ship a neural Jelly that hunts opposite-allegiance targets through caves without sticking, and flanks as a team.

**Architecture:** A new modular task `jelly_team` modelled on `wallcrawler_team`: an adapter (`learning/adapters/jelly.py`) for features/heads/driver, a scenario module (`learning/adapters/jelly_scenario.py`) for environment, rewards and curriculum, and a team-level driver on the `Encounter` (`creatures/jelly_team.py`) like `WallcrawlerTeam`, loaded in the game from a weights path with scripted fallback. All Jellies share one recurrent policy; coordination is by observing teammates only (no messages).

**Tech Stack:** Python, pygame, NumPy inference (`learning/policy.py`), Torch training (`learning/ppo.py`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-31-neural-jelly-design.md`

## Global Constraints

- Task key `jelly_team`; adapter module `learning.adapters.jelly_scenario`; replay module `learning.replay`.
- Heads: continuous `heading` and continuous `accel` (each width 2, listed in `PolicySpec.continuous`); the consumer applies `tanh`. Policy chooses acceleration (accelerate or decelerate), never a target speed; speed is integrated and clamped to `[0, max_speed]`, so a Jelly can brake to a stop. Current speed is a policy input.
- No Jelly-to-Jelly messages. Teammates are observed (position, heading, speed) in fixed nearest-N slots.
- Wall sensing: 16 rays via `hunter.senses.ray_distances`.
- Target rule: nearest living creature of the opposite `allegiance`, plus ship and hunter as today.
- Scripted Jelly (`aggressive`) stays the default; the neural kind is opt-in; missing/invalid weights fall back to scripted behaviour. Jelly HP, contact damage and visuals unchanged.
- Training uses the game's collision code; `bouncesOffWalls` is collision response only.
- Bump `SPEC.version` and the scenario version on any rule change; extend `tests/test_creature_learning.py`.
- Work on a feature branch, not `main`.

## Review Focus

- Jelly spawned with zero teammates (team of one): observation slots are zero-filled and nothing divides by zero.
- Target is None (no opposite-allegiance creature alive): Jelly holds/decelerates instead of raising.
- Target inside a wall pocket unreachable by line of sight: Jelly does not oscillate against the wall (stuck-time metric stays low).
- Dead teammates mid-episode: slots drop out and dead agents are masked in trajectories.
- Corrupt, missing or wrong-spec weights file: game starts, scripted Jelly behaviour is used, one warning logged.

---

### Task 1: Allegiance-based targeting

**Files:**
- Modify: `creatures/encounter.py` (`Encounter.target_for`, ~L150)
- Test: `tests/test_creature_learning.py` (or `tests/test_jelly_creature.py`)

**Interfaces:**
- Produces: `Encounter.target_for(creature) -> Optional[Tuple[float,float]]` now also considers living `self.world.roster.alive()` creatures whose `allegiance` differs from `creature.allegiance` (excluding itself), in addition to ship/hunter/`additional_targets`.
- Constraint: existing behaviour for enemies with no opposite-allegiance creature present is unchanged. Confirm which allegiance strings are valid (`enemy_kinds.py` `ALLEGIANCES`; the training adapter uses `'ally'`) and treat any non-equal allegiance as opposite.

- [ ] **Step 1: Write failing tests**: `test_enemy_targets_nearest_ally_creature_over_farther_ship` (ally creature at 100px, ship at 400px; assert target is the ally's `get_pos()`); `test_target_for_unchanged_without_allied_creatures`; `test_target_for_ignores_same_allegiance_and_self`.
- [ ] **Step 2:** `pytest tests/test_creature_learning.py -k target -v` — expect FAIL.
- [ ] **Step 3:** Extend `target_for` to build the candidate list from ship/hunter/`additional_targets` plus opposite-allegiance roster creatures, returning the nearest `get_pos()`.
- [ ] **Step 4:** Run the same tests plus `pytest tests/test_jellyfish.py tests/test_jelly_creature.py -v` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: target nearest opposite-allegiance creature"`.

### Task 2: JellyTeam, Intent and the neural brain trait

**Files:**
- Create: `creatures/jelly_team.py`, `creatures/traits/neural_jelly.py`
- Modify: `creatures/registry.py` (add `neural_jelly.NeuralJelly` to the `TRAITS` tuple), `creatures/encounter.py` (call `get_jelly_team(self).before_frame()` when any active creature has the neural trait, mirroring the wallcrawler hook at ~L60), `config/enemies.json` (new kind `neural_jelly`: copy of `aggressive` with `chase`, `drift`, `keepsApart` replaced by `neuralJelly`)
- Test: `tests/test_neural_jelly.py`

**Interfaces:**
- Produces: `Intent(heading: float = 0., accel: float = 0.)` dataclass (`heading` in radians relative to world, `accel` in `[-1, 1]` after tanh); `JellyTeam(enc)` with `members() -> list[Creature]`, `commit(intents: dict[int, Intent])`, `before_frame()`, `external: bool`, `driver`; `get_jelly_team(enc) -> JellyTeam` (cached on the encounter); `MAX_SPEED`, `ACCEL_RATE`, `DECISION_FRAMES` constants.
- Behaviour: each frame the creature's velocity is advanced by `accel * ACCEL_RATE` along `heading`, speed clamped to `[0, MAX_SPEED]` (deceleration reduces speed along the current motion; at zero it stays still). Policy is read from `enc.world.jelly_policy`; if it is None, `NeuralJelly` falls back to the scripted `Chase`+`Drift` behaviour.

- [ ] **Step 1: Write failing tests** with the `team_scene`-style helper from `tests/test_creature_learning.py`: `test_commit_accelerates_and_clamps_speed`; `test_negative_accel_brakes_to_a_stop_and_stays`; `test_without_policy_jelly_chases_like_scripted`; `test_single_jelly_team_has_one_member`.
- [ ] **Step 2:** `pytest tests/test_neural_jelly.py -v` — expect FAIL.
- [ ] **Step 3:** Implement `creatures/jelly_team.py` and the trait (`NAME = 'neuralJelly'`), following `creatures/wallcrawler_team.py` and `creatures/traits/brains.py` for structure; the driver is created lazily in `before_frame` when `world.jelly_policy` is set, importing `JellyDriver` from the adapter.
- [ ] **Step 4:** Run `pytest tests/test_neural_jelly.py tests/test_jelly_creature.py -v` and the registry `validate()` test — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: neural jelly brain trait and team"`.

### Task 3: Jelly adapter (features, heads, driver)

**Files:**
- Create: `learning/adapters/jelly.py`
- Test: `tests/test_neural_jelly.py`

**Interfaces:**
- Consumes: `Intent`, `JellyTeam` (Task 2); `PolicySpec`, `RecurrentPolicy` (`learning/policy.py`); `ray_distances` (`hunter/senses.py:56`).
- Produces (mirror `learning/adapters/wallcrawler.py`):
  - `HEADS = (('heading', 2), ('accel', 2))`; `FEATURES` = self (speed, heading as sin/cos, wall rays ×16 normalised by reach), target (`present`, bearing sin/cos relative to heading, distance, closing speed), teammates ×4 (`present`, relative bearing sin/cos, distance, heading sin/cos, speed), plus the Jelly's own relative velocity; `SPEC = PolicySpec('jelly_team', FEATURES, HEADS, version=1, continuous=('heading', 'accel'))`; `CRITIC_SIZE: int`.
  - `observe(team, c) -> (np.float32 vec, masks: dict[str, np.ndarray], sites)`
  - `intention(action) -> Intent(heading=math.tanh(h) * math.pi, accel=math.tanh(a))` — heading is an absolute world angle in `(-pi, pi)`.
  - `critic(team, focal_agent=None) -> np.float32 vec`
  - `enabled(x, action, masks) -> list[bool]` (both heads always enabled)
  - `teacher(c, enc) -> (heading_act, accel_act)` scripted label: toward target, accel +1 unless blocked
  - `class JellyDriver(policy, greedy=True, seed=0)` with `decide(team)` (per-agent GRU state and rng, then `team.commit`)
  - `load_policy(path)`: raises `ValueError` unless `policy.spec == SPEC`.

- [ ] **Step 1: Write failing tests**: `test_observation_length_matches_spec` (`len(observe(...)[0]) == len(SPEC.features)`); `test_team_of_one_zero_fills_teammate_slots`; `test_no_target_sets_present_zero_and_does_not_raise`; `test_wall_rays_see_adjacent_wall`; `test_driver_commits_one_intent_per_member` (use `random_policy(SPEC)`); `test_load_policy_rejects_wrong_spec`.
- [ ] **Step 2:** `pytest tests/test_neural_jelly.py -v` — expect FAIL.
- [ ] **Step 3:** Implement the adapter; copy the per-agent state handling from `CrawlerDriver`.
- [ ] **Step 4:** Run the tests — expect PASS. Also run `pytest tests/test_creature_learning.py -v` to confirm nothing regressed.
- [ ] **Step 5: Commit** `git commit -m "feat: jelly adapter"`.

### Task 4: Stage 1 scenario — navigation to a moving target, registered as a task

**Files:**
- Create: `learning/adapters/jelly_scenario.py`
- Modify: `learning/tasks.py` (add `'jelly_team': Task('jelly_team', 'learning.adapters.jelly_scenario', 'Jelly team', dict(horizon=60.0, workers=4, iterations=10000), ('budget_seconds','bootstrap_episodes','seed'), 'learning.replay')`)
- Test: `tests/test_neural_jelly.py`

**Interfaces:**
- Consumes: Task 3 adapter; `learning.environment` `Snapshot`/`Transition`; `practice_targets.PracticeTarget` (firing disabled via `firing_enabled=False`) and `create_targets`.
- Produces: `JellyEnvironment(horizon=60.0, arenas=None)` with `reset(seed, level=11, team_size=1, stage=1) -> Snapshot`, `step(actions) -> Transition(snapshot, reward, terminated, truncated, info, agent_rewards=...)`, `snapshot()`, `close()`; and the module hooks required by `docs/modular-training.md` step 3: `SPEC`, `CRITIC_SIZE`, `INITIAL_STAGE = 1`, `IMITATION_HEADS = ('heading','accel')`, `environment(**kwargs)`, `metadata(args)`, `training_cases(iteration, count, stage, bootstrap=False)`, `validation_cases()`, `evaluation_cases()`, `metrics(rows)`, `selection_score(summary)`, `promote(stage, summary)`, `compare(a, b)`. `TRAIN_LEVELS` / `HOLDOUT_LEVELS` follow the crawler scenario's split and include real-game cave levels.
- Reward (stage 1): catch (contact with a target) gives the contacting Jelly `CATCH_REWARD` and the team `TEAM_CATCH_SHARE` of it; the target respawns elsewhere and the episode continues to the horizon; small per-step distance-progress shaping; penalty `STUCK_PENALTY` when displacement over a window falls below threshold while accelerating. Constants live at the top of the module like `crawler_scenario.py:15-34`; values are the builder's.
- Info dict includes `catches`, `seconds`, `stuck_seconds`.

- [ ] **Step 1: Write failing tests**: `test_reset_and_step_are_deterministic_for_a_seed`; `test_contact_with_target_rewards_only_contacting_jelly_more`; `test_target_respawns_after_catch_and_episode_continues`; `test_step_after_end_raises`; `test_task_registry_has_jelly_team`; `test_manager_can_start_fresh_jelly_team` (copy of the crawler `start(...)` test at `tests/test_creature_learning.py:193`).
- [ ] **Step 2:** `pytest tests/test_neural_jelly.py -v` — expect FAIL.
- [ ] **Step 3:** Implement the environment by following `CrawlerEnvironment` (`crawler_scenario.py:71`) with `teacher` as the scripted action source; implement the hooks, with `promote` advancing stage 1 → 2 when held-out `catches` per minute beats the scripted-Jelly baseline and `stuck_seconds` is lower.
- [ ] **Step 4:** Run the tests; then a smoke training run through the trainer (`astrovoid-trainer` MCP or `python -m learning.run` with `--task jelly_team --budget_seconds 60`) and confirm a checkpoint is written — expect no exceptions.
- [ ] **Step 5: Commit** `git commit -m "feat: jelly_team task with stage 1 navigation scenario"`.

### Task 5: Stage 2 — flanking reward and curriculum

**Files:**
- Modify: `learning/adapters/jelly_scenario.py`
- Test: `tests/test_neural_jelly.py`

**Interfaces:**
- Consumes: Task 4 environment. Produces: `flank_spread(positions, target) -> float` (angular spread of Jellies around the target in `[0, 1]`: 0 all on one bearing, 1 evenly spread), used for a shaped team reward and the `angular_spread` metric; `training_cases` now mixes `team_size` 2–4 at stage 2.
- Reward: team reward proportional to `flank_spread` while within `FLANK_RANGE` of the target; penalty for Jellies within `BUNCH_DISTANCE` of each other.

- [ ] **Step 1: Write failing tests**: `test_flank_spread_is_zero_for_collinear_bearing_and_one_for_even_ring`; `test_single_jelly_has_spread_zero_without_error`; `test_bunching_penalty_applies_only_below_bunch_distance`; `test_stage2_cases_have_team_size_2_to_4`.
- [ ] **Step 2:** Run `pytest tests/test_neural_jelly.py -k flank -v` — expect FAIL.
- [ ] **Step 3:** Implement `flank_spread`, the reward terms and the stage-2 case mix; `promote` advances 2 → 3 when held-out `angular_spread` and `catches` beat the stage-1 policy's results in team scenes.
- [ ] **Step 4:** Run the tests — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: jelly flanking reward and stage 2 curriculum"`.

### Task 6: Stage 3 — training ship that hunts back

**Files:**
- Create: `learning/adapters/training_ship.py`
- Modify: `learning/adapters/jelly_scenario.py`
- Test: `tests/test_neural_jelly.py`

**Interfaces:**
- Produces: `TrainingShip(position, level, *, speed_scale=.6, fire_interval_scale=2., damage_scale=.5)` with `get_pos()`, `step(maze, jellies)`, `take_hit(shot)`, `alive`, `hit_points`. It acts like the normal ship (moves toward the nearest Jelly, fires at it in range with line of sight) at reduced speed, rate and damage. Reuse the existing hunter/ship logic where possible (check `hunter/` for a scripted pilot before writing one).
- Scenario: stage 3 adds the ship per spec; a Jelly dying is penalised (`DEATH_PENALTY`), damaging the ship is rewarded; the episode ends when the ship dies, all Jellies die, or on timeout. The ship is appended to `world.additional_targets` so `Encounter.target_for` sees it.

- [ ] **Step 1: Write failing tests**: `test_training_ship_is_slower_and_weaker_than_normal`; `test_ship_hit_kills_one_hp_jelly`; `test_episode_ends_when_all_jellies_die`; `test_episode_ends_when_ship_dies`; `test_jelly_death_is_penalised`.
- [ ] **Step 2:** Run those tests — expect FAIL.
- [ ] **Step 3:** Implement the ship and the stage-3 environment branch; `promote` stays at stage 3 (final).
- [ ] **Step 4:** Run the tests — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: hunting training ship for jelly stage 3"`.

### Task 7: Evaluation, game wiring, docs

**Files:**
- Modify: `learning/adapters/jelly_scenario.py` (`compare`, `selection_score`, `metrics`), `game.py` (~L123-130: `JELLY_POLICY` env var → `self.jelly_policy = load_policy(path)`, same `except (ValueError, OSError, KeyError)` warn-and-None pattern as `WALLCRAWLER_POLICY`; expose as `world.jelly_policy`), `docs/modular-training.md` (add the Jelly task to the task list), `docs/creature-training.md` (short scenario note)
- Test: `tests/test_neural_jelly.py`

**Interfaces:**
- `compare(a, b) -> dict(mean_extra_catches, lower_95, upper_95)` bootstrap, same shape as `crawler_scenario.compare`. `selection_score(summary)` is a hard gate: returns the lowest score unless real-game cave arena results beat the scripted-Jelly baseline for catch rate and stuck time. `metrics(rows)` reports catch rate, time to contact, stuck time, angular spread, Jelly survival.

- [ ] **Step 1: Write failing tests**: `test_corrupt_weights_file_leaves_policy_none_and_game_starts`; `test_wrong_spec_weights_fall_back_to_scripted`; `test_selection_score_rejects_policy_that_loses_on_cave_arenas`; `test_compare_returns_interval_keys`.
- [ ] **Step 2:** Run those tests — expect FAIL.
- [ ] **Step 3:** Implement the above; document the new task and the `neural_jelly` kind.
- [ ] **Step 4:** Run the full suite `pytest -q` — expect PASS.
- [ ] **Step 5:** Run a real-display check of a trained or random policy with `neural_jelly` Jellies in a cave level (see memory: dummy SDL hides rendering bugs; real fullscreen is 1352x878) and confirm no stuck Jellies and the scripted Jelly is unchanged.
- [ ] **Step 6: Commit** `git commit -m "feat: jelly evaluation gate, game wiring and docs"`.
