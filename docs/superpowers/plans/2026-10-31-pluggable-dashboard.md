# Pluggable Training Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each creature training task declares its own metrics, charts, reward rules and capabilities as data; the dashboard page and server contain no task names and draw/serve whatever the declarations resolve to.

**Architecture:** A shared, task-agnostic module (`learning/dashboard.py`) defines the descriptor dataclasses and resolves a task's layout (shared metrics + the task's own declarations + an automatic "Other" section) into JSON. Each task names a declaration module and a `Capabilities` record in its `Task` registry entry (as `replay_hooks` already does). The server serves the resolved layouts and the page's static ES modules; the page renders from them.

**Tech Stack:** Python 3.10, pytest, plain ES modules (no build, no framework, hand-rolled SVG), Node (for page tests, as `tests/test_trainer_page.py` already requires).

**Spec:** `docs/superpowers/specs/2026-10-31-pluggable-dashboard-design.md`

## Global Constraints

- Work on branch `feature/pluggable-dashboard` (branched from `feature/neural-jelly`). Never main; never push.
- No charting library, bundler, framework or build step. Charts stay hand-rolled SVG.
- Hunter and Wallcrawler: for a recorded real log, the rendered chart set (keys, titles, subtitles, relative order) and stat strip are identical to what the current `tools/trainer/page.html` renders for that log. A regression test pins this. "Other" is empty for those logs.
- Task keys, run folders, `train.log` format and `evaluation.json` are unchanged; `Task` only gains fields.
- Static handler serves only `.js` and `.css` files from one fixed folder, path-safe; existing Host/Origin checks on POST are kept; the new read endpoints are unauthenticated like `/api/runs`.
- Capabilities preserve today's behaviour exactly: actor damping Wallcrawler-only; "fresh weights" unavailable for Hunter, available for Wallcrawler and Jelly; the `'hunter'` default for untagged configs and `UNTAGGED_REPLAY_TASK` stay as named registry constants.
- Jelly reward settings default to exactly today's values (`CATCH_REWARD=10.`, `TEAM_CATCH_SHARE=.25`, `PROGRESS_REWARD=.002`, `STUCK_PENALTY=.05`, `FLANK_REWARD=.005`, `FLANK_RANGE=200`, `BUNCH_DISTANCE=40`, `BUNCH_PENALTY=.01`, `SHIP_HIT_REWARD=4`, `SHIP_KILL_REWARD=10`, `TEAM_SHIP_SHARE=.25`, `DEATH_PENALTY=5`, `TEAM_DEATH_SHARE=.25`); a default run behaves identically.
- Tests run audio-off (`SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy`; `tests/conftest.py` sets audio). Known unrelated failures: `test_inflator` blast-pop, `test_viber_sizes` vibelet radius, `test_hunter_creature_contract` frozen flight, order-dependent `test_cave_maze::test_blast_rebuilds_the_rock_once`.
- Never kill, restart, pause or stop any running process or training run (the user's dashboard on :8765 and any live run). Verify against your own server instance on another port (`./venv/bin/python -m tools.trainer serve --no-browser`, see `--help`) and stop only that instance.
- Commit with explicit paths only (never `git add -A`, never `git stash`); retry on `index.lock`.

## Review Focus

- A run whose log has no rows yet (or a missing `train.log`): layout, strip and panel render a clear empty state, no exception.
- A run whose `config.json` has no `task` key (legacy/untagged) or an unknown task key: falls back to the legacy default, shows a clear message, never a blank or broken page.
- A log key whose value is a string or boolean (e.g. `policy=iter0001.npz`, parsed as `False` today): never charted and never lands in "Other".
- A static-file request with `..`, an absolute path, an encoded separator or a non-`.js`/`.css` extension: refused, never reads outside the static folder.
- An old run whose config lacks a reward setting the panel declares: the panel shows "not recorded" for it (with the default), no crash and no wrong number.

---

### Task 1: Declaration core, task capabilities, and the tasks endpoint

**Files:**
- Create: `learning/dashboard.py`, `tests/test_dashboard_declarations.py`
- Modify: `learning/tasks.py` (new `Capabilities` dataclass; `Task` gains `dashboard: str | None = None` and `capabilities: Capabilities`; named constants `UNTAGGED_TASK = 'hunter'` next to the existing `UNTAGGED_REPLAY_TASK`), `tools/trainer/server.py` (new `GET /api/tasks`)

**Interfaces:**
- Produces in `learning/dashboard.py`:
  - `@dataclass(frozen=True) Metric(key: str, title: str, sub: str = '', unit: str = '', section: str = 'Training', higher_is_better: bool | None = None, optional: bool = False, aliases: tuple[str, ...] = (), wide: bool = False)`
  - `@dataclass(frozen=True) Layout(sections: tuple[str, ...] = (), strip: tuple[str, ...] = ())` (ordering overrides; empty = declaration order)
  - `SHARED_METRICS: tuple[Metric, ...]` (`mean_return`, `kl`, `entropy`) and `HIDDEN_KEYS: frozenset[str]` (`iteration`, `rollout_s`, `update_s`, `elapsed_s`, `policy`, gate flags, other bookkeeping)
  - `declaration(task_key: str) -> SimpleNamespace` with `.METRICS`, `.LAYOUT` (default `Layout()`), `.REWARD_RULES` (default `()`), `.cards(config) -> list[dict]` (default returns `[]`), loaded from `Task.dashboard`
  - `resolve(task_key: str) -> dict` returning JSON-able `{key, label, capabilities: {...}, metrics: [..], sections: [..], strip: [..], rewards: [..], hidden: [..]}` (`hidden` = sorted `HIDDEN_KEYS`, so the page can compute "Other"); `resolve_all() -> list[dict]`
  - `unclaimed(task_key: str, keys: Iterable[str]) -> list[str]` (numeric keys not declared, not aliased, not in `HIDDEN_KEYS`, in sorted order)
- Produces in `learning/tasks.py`: `Capabilities(fresh_weights: bool = True, actor_damping: bool = False, replay_mode: str = 'hooks', settings_scope: str = 'listed')` with `replay_mode in {'hooks','legacy_check',None}` and `settings_scope in {'listed','unclaimed'}`; `task(key)` and `TASKS` unchanged in behaviour.
- Produces endpoint: `GET /api/tasks` returns `dashboard.resolve_all()`.

- [ ] **Step 1: Write failing tests** in `tests/test_dashboard_declarations.py`: `test_resolve_shared_metrics_come_first_for_every_task`; `test_resolve_is_json_serialisable`; `test_unknown_task_raises_value_error_naming_the_task`; `test_unclaimed_ignores_hidden_declared_and_aliased_keys`; `test_a_task_without_a_dashboard_module_gets_only_shared_metrics`; `test_capabilities_defaults_and_validation` (bad `replay_mode` raises); `test_tasks_endpoint_returns_resolved_layouts` (real server on a free port, as `tests/test_trainer_server.py` does).
- [ ] **Step 2:** Run `SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy ./venv/bin/python -m pytest tests/test_dashboard_declarations.py -q` — expect FAIL (module missing).
- [ ] **Step 3:** Implement `learning/dashboard.py`, the `Task`/`Capabilities` changes (existing four fields' meaning unchanged; `capabilities` set per task in a later task, defaults here), and the endpoint in `server.py` (read-only; reuse the server's JSON helper).
- [ ] **Step 4:** Re-run the new tests and `tests/test_trainer_server.py tests/test_trainer_runs.py` — expect PASS.
- [ ] **Step 5:** Commit `feat: task dashboard declarations, capabilities and /api/tasks`.

### Task 2: Per-task metric declarations with contract and regression tests

**Files:**
- Create: `learning/adapters/hunter_dashboard.py`, `learning/adapters/crawler_dashboard.py`, `learning/adapters/jelly_dashboard.py`, `tests/fixtures/dashboard/hunter_log_keys.json`, `tests/fixtures/dashboard/crawler_log_keys.json`, `tests/fixtures/dashboard/old_page_charts.json`, `tests/test_dashboard_contract.py`
- Modify: `learning/tasks.py` (set `dashboard=` module path and `capabilities=` for `hunter`, `wallcrawler_team`, `jelly_team`)

**Interfaces:**
- Consumes: `Metric`, `Layout` from Task 1.
- Produces: each module exports `METRICS`, optional `LAYOUT`. Chart lists are transcribed from the 32 `chart({...})` calls in `tools/trainer/page.html` (L172-203) into the correct task: Wallcrawler gets its 16 (`hits_per_minute`, `mean_aim_quality`, `target_clear_rate`, `accuracy`, `precision_accuracy`, `tracking_accuracy`, `battle_stage`, `pursuit_survival`, `pursuit_accuracy`, `reversals_per_episode`, `jumps_per_episode`, `bullet_hits_taken_per_episode`, `contact_hits_taken_per_episode`, `imitation_loss`, `airborne_fraction`, `survival`), Hunter its 13 (`speed_fraction`, `powerups_per_episode`, `upgraded_fraction`, `deaths_per_episode`, `compass_follow`, `hits_per_episode`, `unaimed_shots_per_episode` (alias `free_shots_per_episode`), `panic_fraction`, `bored_fraction`, `rules_beaten`, `kills_per_min`, `wall_quotient_per_min`, `hits_taken_per_min`), each with its existing title/subtitle text verbatim and relative order preserved; shared `mean_return`, `kl`, `entropy` keep their current positions (first / last). Jelly gets the starter set (catches per minute, catch probability, stuck fraction, time to contact, team catches per minute, angular spread, bunched fraction, ship hits, Jelly deaths, survival fraction), with exact keys taken from `jelly_scenario.metrics()` / `summarise()`.
- Capabilities: `hunter`: `fresh_weights=False, actor_damping=False, replay_mode='legacy_check', settings_scope='unclaimed'`; `wallcrawler_team`: `fresh_weights=True, actor_damping=True, replay_mode='hooks', settings_scope='listed'`; `jelly_team`: `fresh_weights=True, actor_damping=False, replay_mode='hooks', settings_scope='listed'`.

- [ ] **Step 1: Write failing tests** in `tests/test_dashboard_contract.py`: `test_every_declared_wallcrawler_and_jelly_key_is_produced_by_metrics_or_shared_stats` (call each `metrics()` hook on a synthetic row set or reuse the keys the scenario tests produce; optional metrics exempt); `test_every_declared_hunter_key_is_in_the_recorded_log_fixture`; `test_other_is_empty_for_recorded_hunter_and_wallcrawler_logs` (fixtures hold real key sets taken from `.astrovoid-local/neural/rl/run83` (Hunter-era) and `run145` (Wallcrawler) `train.log` — generate them once with a script and commit only the key lists); `test_rendered_chart_set_matches_the_old_page_for_each_recorded_log` (compares `resolve()` filtered by the fixture's keys against `old_page_charts.json`, a pinned dump of the old page's `(key,title,sub)` order extracted from the pre-refactor `page.html`); `test_jelly_declares_no_wallcrawler_charts_and_no_imitation_loss`; `test_legacy_free_shots_alias_resolves_to_unaimed_shots`.
- [ ] **Step 2:** Run the file — expect FAIL.
- [ ] **Step 3:** Write the three declaration modules and the `tasks.py` registrations; generate the fixtures with a one-off script (not committed) from the real run logs.
- [ ] **Step 4:** Run the contract tests, `tests/test_dashboard_declarations.py`, `tests/test_trainer_settings.py` — expect PASS.
- [ ] **Step 5:** Commit `feat: hunter, wallcrawler and jelly dashboard declarations`.

### Task 3: Page draws from the resolved layout (still one file)

**Files:**
- Modify: `tools/trainer/page.html` (replace the hard-coded `chart({...})` list and the `team` sniff in `render()`; build the "Other" section; build the "Next run" task `<select>` from `/api/tasks`; strip from the layout), `tests/test_trainer_page.py` (update only where it slices `render`/strip; behaviours asserted stay)
- Test: `tests/test_trainer_page.py`

**Interfaces:**
- Consumes: `GET /api/tasks` (Task 1), `Metric`/`Layout` JSON shape. The page keeps `chart({title, sub, key, wide})` and the `m.l=44` margin and range behaviour.
- Produces: `render()` groups charts by `section` in declared order, draws only charts whose key (or alias) is in the last row, then an "Other" section for `unclaimed` numeric keys (computed in JS from the layout's metric/alias/hidden lists, hidden list included in the `/api/tasks` JSON as `hidden`); the stat strip = shared cells + the task's `strip` metrics; no use of `'hits_per_minute' in last`.

- [ ] **Step 1: Write failing tests** (Node, as the file already does): `test_render_draws_only_the_task_layout_charts` (Jelly layout + a Jelly log row → Jelly charts, none of the Wallcrawler titles); `test_render_puts_undeclared_numeric_keys_in_other_and_never_strings_or_booleans`; `test_render_with_no_rows_shows_an_empty_state`; `test_strip_comes_from_layout_not_data_sniff`; update existing chart-start tests only as needed to keep their assertions (`>15.0<`, `M44.0 `, the two range messages).
- [ ] **Step 2:** Run `./venv/bin/python -m pytest tests/test_trainer_page.py -q` — expect FAIL on the new tests.
- [ ] **Step 3:** Implement in `page.html`: fetch `/api/tasks` once at boot into `LAYOUTS`, pick by the viewed run's task (`LAYOUTS.find(t=>t.key===(config.task||UNTAGGED))`; unknown/untagged → clear message, fall back to shared metrics only), replace the chart literal list with a loop. Remove the hard-coded `<select id=task>` options.
- [ ] **Step 4:** Run `tests/test_trainer_page.py tests/test_trainer_server.py tests/test_dashboard_contract.py` — expect PASS. Then, against your own server instance, `curl` the page and a run's `/data` and `/api/tasks` for `run83`, `run145`, `run146`.
- [ ] **Step 5:** Commit `refactor: dashboard page draws charts and strip from the task layout`.

### Task 4: Split the page into ES modules, static handler, rewritten page tests

**Files:**
- Create: `tools/trainer/static/{api,charts,layout,strip,runs,replay,settings-form,main}.js` (+ `style.css`), `tests/trainer_js/*.test.mjs` runner support in `tests/test_trainer_page.py`
- Modify: `tools/trainer/page.html` (shell only: markup + `<script type="module" src="static/main.js">` + `<link rel="stylesheet" href="static/style.css">`), `tools/trainer/server.py` (static route `GET /static/<name>`), `tests/test_trainer_page.py` (import modules directly instead of slicing by markers)

**Interfaces:**
- Produces: each module exports pure functions plus a small `init(deps)`; `charts.js` exports `chart(spec, rows, view)`, `smooth`; `layout.js` exports `resolveLayout(layouts, config)`, `groupCharts(layout, row)`, `unclaimed(layout, row)`; `strip.js` `renderStrip(layout, status, row)`; `runs.js`, `replay.js`, `settings-form.js` hold the existing run list / replay panel / Next-run form code; `main.js` wires polling (intervals unchanged: status 5 s, runs 15 s, data 15 s, rules 60 s).
- Server: `GET /static/<name>` serves only names matching `^[A-Za-z0-9_-]+\.(js|css)$` from `tools/trainer/static/` with correct content type; anything else is 404.

- [ ] **Step 1: Write failing tests**: `test_static_serves_js_and_css_with_content_types`; `test_static_rejects_traversal_encoded_separators_absolute_paths_and_other_extensions` (`../server.py`, `%2e%2e/server.py`, `..%2fserver.py`, `/etc/passwd`, `x.html`, `x.py`); and Node module tests mirroring every behaviour the old slice tests pinned: chart range/saved start, `loadEpisodes`, start handler, `fromChanged`, `syncCreature`, `fillFrom`, `replayRuns`, the `M44.0` margin, the two range messages.
- [ ] **Step 2:** Run the page and server tests — expect FAIL.
- [ ] **Step 3:** Split `page.html` mechanically (move code, keep behaviour), add the static route, port the tests. No behaviour change.
- [ ] **Step 4:** Run `tests/test_trainer_*.py tests/test_replay_general.py tests/test_dashboard_*.py` — expect PASS; load the page from your own server and confirm all `static/*.js` return 200 and the page boots (fetch the page and check no module 404s).
- [ ] **Step 5:** Commit `refactor: split the dashboard page into ES modules with a path-safe static route`.

### Task 5: Capabilities replace task-name checks

**Files:**
- Modify: `tools/trainer/static/{runs,settings-form,replay,main}.js`, `tools/trainer/control.py` (L108-135), `tools/trainer/replay.py` (L25, L91 and the no-adapter hunter path), `tools/trainer/settings.py` (L83, L120, scoping rules), `tools/trainer/__main__.py` (L38 `--actor-scale`), `learning/tasks.py`
- Test: `tests/test_trainer_control.py`, `tests/test_trainer_settings.py`, `tests/test_trainer_server.py`, `tests/test_dashboard_declarations.py`

**Interfaces:**
- Consumes: `Capabilities` per task (Task 2). `/api/tasks` already exposes them.
- Produces: no string comparison against a task key remains in the dashboard page modules or in `tools/trainer/*.py` (the legacy `'hunter'` default for untagged configs and `UNTAGGED_REPLAY_TASK` are referenced only through the named constants in `learning/tasks.py`).

- [ ] **Step 1: Write failing tests**: `test_no_task_key_literals_in_dashboard_code` (grep the page modules and `tools/trainer/*.py` for `'hunter'`, `'wallcrawler_team'`, `'jelly_team'`, excluding the constants' definitions and tests); `test_actor_damping_allowed_only_when_capability_set` (Wallcrawler OK; Jelly and Hunter refused with today's message); `test_fresh_weights_follow_capability` (Hunter unavailable); `test_settings_scope_unclaimed_matches_todays_hunter_settings` (the Hunter's setting set is identical before/after: record the pre-change `Setting.tasks` map as a fixture); `test_replay_mode_legacy_check_runs_the_subprocess_check_for_hunter_only`; `test_hunter_replay_and_start_flows_unchanged` (existing server/control tests keep passing).
- [ ] **Step 2:** Run those tests — expect FAIL.
- [ ] **Step 3:** Replace each comparison with the capability (`fresh_weights`, `actor_damping`, `replay_mode`, `settings_scope`) read from the registry (server side) or `LAYOUTS` (page side).
- [ ] **Step 4:** Run all `tests/test_trainer_*.py tests/test_replay_general.py tests/test_dashboard_*.py tests/test_neural_jelly.py tests/test_creature_learning.py` — expect PASS.
- [ ] **Step 5:** Commit `refactor: task capabilities replace task-name checks in the dashboard and trainer`.

### Task 6: Reward rules panel and generalised rule cards

**Files:**
- Create: `tools/trainer/static/rewards.js`, `tests/test_dashboard_rewards.py`
- Modify: `learning/dashboard.py` (add `RewardRule`), `learning/adapters/{hunter,crawler,jelly}_dashboard.py` (`REWARD_RULES`, `cards(config)` for the Wallcrawler and Hunter episode text moved out of `page.html`'s `loadRules`), `tools/trainer/static/{main,layout}.js`, `tools/trainer/page.html` (pinned panel container + CSS in `style.css`), `tools/trainer/server.py` (the existing `/api/runs/<run>/config` is reused; add `GET /api/runs/<run>/rewards` returning the resolved rules with the run's recorded values and the run's current stage)

**Interfaces:**
- Produces: `@dataclass(frozen=True) RewardRule(key: str, title: str, description: str, kind: str, stages: tuple[int, ...], setting: str, default: float | None = None)` with `kind in {'reward','penalty','shaping'}`; `GET /api/runs/<run>/rewards -> {"stage": int | None, "rules": [{key, title, description, kind, stages, active: bool, value: number | null, recorded: bool}]}` (`recorded=false` and the default value when the run's config lacks the setting); `rewards.js` exports `renderRewards(payload)`. The panel is pinned beside the charts (CSS `position: sticky`), collapsible, and highlights `active` rules.

- [ ] **Step 1: Write failing tests** in `tests/test_dashboard_rewards.py`: `test_jelly_rules_list_every_reward_constant_with_its_default`; `test_rewards_endpoint_reads_values_from_the_runs_own_config` (two runs with different `catch_reward` show different values); `test_missing_setting_in_an_old_run_reports_not_recorded_with_default`; `test_active_rules_follow_the_current_stage` (stage 2 activates flank/bunch; stage 3 activates ship/death); `test_wallcrawler_rules_cover_the_old_loadrules_rows` (every reward/penalty row the old `loadRules` could show appears as a rule); plus Node tests for `renderRewards` (text and values present, inactive rules dimmed, panel has the pinned class).
- [ ] **Step 2:** Run — expect FAIL.
- [ ] **Step 3:** Implement `RewardRule`, the three tasks' rules (Wallcrawler/Hunter transcribed from `loadRules` in `page.html`, which this removes; Jelly from the constants listed in Global Constraints), the endpoint, the module and panel. Remove `loadRules` and its Wallcrawler-specific HTML from the page.
- [ ] **Step 4:** Run `tests/test_dashboard_rewards.py tests/test_trainer_page.py tests/test_trainer_server.py` — expect PASS; check the panel on your own server for `run146` (Jelly) and `run145` (Wallcrawler).
- [ ] **Step 5:** Commit `feat: pinned reward rules panel generated from each task's declarations`.

### Task 7: Jelly reward values become run settings

**Files:**
- Modify: `learning/adapters/jelly_scenario.py` (reward constants → fields read from the environment's configuration, defaults unchanged; `environment(**kwargs)`, `metadata(args)` record them; `scenario_version` bump only if default behaviour changes — it must not), `learning/tasks.py` (`jelly_team` `options` gains the setting names), `tools/ppo_neural.py` (parser arguments for the Jelly reward settings), `tools/trainer/settings.py` (labels/groups: group `Rewards`), `learning/adapters/jelly_dashboard.py` (`setting=` names)
- Test: `tests/test_neural_jelly.py`, `tests/test_trainer_settings.py`, `tests/test_dashboard_rewards.py`

**Interfaces:**
- Produces: 13 settings (`catch_reward`, `team_catch_share`, `progress_reward`, `stuck_penalty`, `flank_reward`, `flank_range`, `bunch_distance`, `bunch_penalty`, `ship_hit_reward`, `ship_kill_reward`, `team_ship_share`, `death_penalty`, `team_death_share`); names must not collide with existing parser dests (check `build_parser()` — e.g. `death_penalty` already exists for the Hunter: reuse the Jelly-specific names `jelly_death_penalty` etc. where they collide and note the final names in the report); `JellyEnvironment(..., rewards: dict | None = None)` using defaults when absent; `metadata(args)` records the values in the manifest so the rewards panel shows them; resuming with different values is rejected by the existing manifest-compatibility check.

- [ ] **Step 1: Write failing tests**: `test_default_reward_settings_reproduce_todays_behaviour` (same seed, same actions → identical rewards/events as the module constants gave; compare against values computed from the constants); `test_changed_catch_reward_changes_the_catch_payout`; `test_reward_settings_are_in_the_manifest_and_in_the_settings_form_for_jelly_only`; `test_resume_with_different_reward_values_is_rejected`; `test_rewards_panel_shows_the_changed_value_for_a_new_run`.
- [ ] **Step 2:** Run — expect FAIL.
- [ ] **Step 3:** Thread a `rewards` mapping through `JellyEnvironment`, the hooks and the parser; keep module constants as the defaults dictionary so nothing else changes.
- [ ] **Step 4:** Run `tests/test_neural_jelly.py tests/test_replay_general.py tests/test_trainer_*.py tests/test_dashboard_*.py` and the full suite once — expect only the known failures.
- [ ] **Step 5:** Commit `feat: jelly reward values are run settings with unchanged defaults`.
