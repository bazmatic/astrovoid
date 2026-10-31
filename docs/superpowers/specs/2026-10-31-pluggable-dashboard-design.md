# Pluggable training dashboard — design

## Intent

The Training dashboard (`tools/trainer/`) draws one hard-coded list of 32 charts for every creature task. Opening a
Jelly run shows Wallcrawler charts (jumps, landings, "Demonstration rehearsal loss ... jump and landing choices")
and none of the Jelly's own metrics. Task names are also compared directly in the page and the server
(`=== 'hunter'`, `=== 'wallcrawler_team'`, sniffing for `hits_per_minute`), so every new task means editing the page,
the server and the settings code.

Make the dashboard SOLID, DRY and pluggable: each creature training task owns its own charts, and adding a task or a
metric means writing one declaration in one place, with no page or server edits.

## Goals

- Each task declares its metrics and charts as data, next to the code that produces the metrics. Shared metrics
  (return, entropy, policy drift) are declared once and added to every task.
- The page contains no task names. It draws whatever layout the server gives it.
- The server contains no task-name comparisons. Differences between tasks are fields ("capabilities") on the
  `Task` registry entry in `learning/tasks.py`.
- The page is split into small single-purpose ES modules (no framework, no build step) that the server serves as
  static files, and the page tests import those modules directly instead of slicing `page.html` by marker text.
- A Jelly run shows Jelly charts. Hunter and Wallcrawler runs show exactly the charts they show today.
- A task's reward signal rules (the list of what is rewarded and penalised, with values) are declared by the
  task, shown in a panel that is always visible beside the charts, and configurable per run (user requirement,
  added after the first draft; the details below are the assistant's reading of it and are marked as such).

## Non-goals and anti-goals

- No charting library, no bundler, no framework, no build step. The renderer stays hand-rolled SVG.
- No change to how existing charts look or behave (ranges, smoothing, legends, polling intervals).
- No redesign of the settings form or the trainer CLI/MCP beyond removing task-name checks.
- Anti-goal: a chart silently missing because of a typo in a metric key. Declarations are checked against what the
  task's `metrics()` hook actually produces.
- Anti-goal: a new metric silently dropped from the dashboard. Undeclared metrics still appear.

## Constraints

- Plain ES modules served by `tools/trainer/server.py` from a fixed static folder. The static handler must be
  path-safe (no traversal outside the folder) and keep the existing Host/Origin protection for POSTs.
- Existing tests stay meaningful. `tests/test_trainer_page.py` slices `page.html` by marker text and runs it under
  Node; it will be rewritten to import the new modules, keeping every behaviour it asserts (chart range, saved
  chart start, `loadRules`/rewards cards for Wallcrawler, replay episode list, start handler, `fromChanged`,
  `syncCreature`, `fillFrom`, `replayRuns`, the `M44.0` left margin, the "No iterations in the selected range"
  and "No data from iteration 1000" messages).
- Existing task keys, run folders, `train.log` format and `evaluation.json` are unchanged. `Task` gains fields; its
  existing fields keep their meaning.
- Hunter and Wallcrawler resolved chart lists must be provably identical to today's (same keys, titles, subtitles,
  order). A regression test pins this.
- Tests run with audio off (`SDL_AUDIODRIVER=dummy`; `tests/conftest.py` sets it).

## Design (decided with the user)

1. **Metric descriptors, declared once.** A task's dashboard module declares, for each metric it produces:
   key, title, one-line explanation, unit, section, and whether higher is better. These are plain data. The same
   descriptor drives the chart, the stat-strip formatting and its tooltip. Shared metrics are declared once in a
   shared module and prepended to every task's list.
2. **Layout is optional data on top.** By default every declared metric gets a chart in its section. A task
   writes layout (ordering, section order, a wide chart, which metrics feed the stat strip) only to override that.
3. **Undeclared metrics are not lost.** Any numeric key in a run's log that no descriptor claims goes into an
   automatic "Other" section.
4. **Per-task cards** (today's Wallcrawler-only "Active rewards / penalties / episodes" cards built by
   `loadRules`) become an optional per-task provider that returns data for the page to render; Hunter and Jelly
   may return none.
5. **Capabilities replace task-name checks.** Fields on `Task` (for example: supports fresh weights, supports
   actor damping, replay mode, applicable settings groups) replace every `=== 'hunter'` / `=== 'wallcrawler_team'`
   branch in `page.html`, `control.py`, `replay.py`, `settings.py` and `__main__.py`.
6. **The server serves one resolved description.** A tasks endpoint returns each task's label, options,
   capabilities and resolved layout; the page and the "Next run" task selector read it (no hard-coded
   `<select>` options).
7. **Declarations live in Python next to each task's metrics code** (the task's adapter or a sibling dashboard
   module named in its `Task` entry, mirroring `replay_hooks`), because that is where the metric keys are defined.
8. **Contract tests.** For every registered task, every declared key is produced by its `metrics()` hook (or the
   shared training stats); a Hunter/Wallcrawler "no regression" test compares resolved layouts to today's lists.
9. **Starter Jelly set** (easy to extend later): catches per minute, catch probability, stuck fraction, time to
   contact, team catches per minute, angular (flank) spread, bunched fraction, ship hits, Jelly deaths,
   survival fraction. Per-stage (`stageN_*`) charts are a later addition.
11. **Reward rules, declared per task (assistant's reading of the user's requirement).** Each task declares its
    reward signal rules as data: key, title, description, kind (reward / penalty / shaping), the stages in which it
    applies, and the name of the run setting that holds its value. The dashboard shows them as a panel that stays
    on screen next to the charts (pinned, collapsible), using the values recorded in the viewed run's own
    config/manifest (what that run actually trained with, not today's code), and highlights the rules active at
    the run's current stage. This generalises today's Wallcrawler-only "Active rewards / penalties / episodes"
    cards (`loadRules`), which this replaces.
12. **Reward values are run settings (assistant's reading).** "Configurable" means each reward value is a named
    setting in the "Next run" form, recorded in the run's config, and read by the environment, as the Hunter's
    and Wallcrawler's reward settings already are. The Jelly's reward constants (`CATCH_REWARD`,
    `TEAM_CATCH_SHARE`, `PROGRESS_REWARD`, `STUCK_PENALTY`, flank/bunch shaping, ship hit/kill rewards, death
    penalties; currently module constants in `learning/adapters/jelly_scenario.py`) become settings whose defaults
    are exactly today's values, so default behaviour and existing results are unchanged. Resuming a run with
    different reward values is rejected by the existing manifest-compatibility check; a new run may change them.
10. **Staging**, each stage working and reviewable: (a) descriptors, resolved-layout endpoint, page draws from it,
    Hunter/Wallcrawler moved over unchanged, Jelly starter set; (b) split the page into ES modules and rewrite
    the page tests; (c) capabilities replace task-name checks across page and server; (d) reward rules declared
    per task, shown in the pinned panel, and the Jelly's reward constants become run settings.

## Left to the builder

- Module names/file layout of the static folder and of the dashboard declarations; exact descriptor field names.
- The capability set and names; the resolved-layout JSON shape.
- How `kl`/`entropy`/loss keys are classified as shared versus task-specific (the survey could not confirm which
  `stats` keys the team tasks emit).
- How legacy keys are handled (e.g. the `free_shots_per_episode` → `unaimed_shots_per_episode` rename in the page).
- How the page's polling, chart-range state (localStorage per run) and rendering are divided among modules.

## Calls I made (not discussed with the user)

- Python declarations co-located with each task's metrics code (the user agreed the shape; location is mine).
- Hunter's metrics are written by `tools/ppo_neural.py`, not an adapter `metrics()` hook; its declaration lives
  with the hunter adapter/dashboard module and the contract test for Hunter checks against a recorded sample of
  real log keys instead.
- Settings labels/groups are not redesigned; only the task-name checks around them are replaced.
- Work is on a new branch, `feature/pluggable-dashboard`, branched from `feature/neural-jelly`, because it needs
  the `jelly_team` task.
- **What "exactly the charts they show today" means.** Each task gets its own chart set, so Hunter no longer
  carries Wallcrawler-only chart slots and vice versa (that is the point of the change). The regression test pins
  the *rendered* chart set: for a recorded real Hunter log and a recorded real Wallcrawler log, the charts drawn
  (keys, titles, subtitles, and relative order) are identical to what the current page draws for the same log.
  Shared charts (`mean_return`, `kl`, `entropy`, `survival` where genuinely shared) keep their current relative
  positions within each task's list.
- **Contract tests.** For Wallcrawler and Jelly, declared keys are checked against what `metrics()` and the shared
  training stats produce. For Hunter (no `metrics()` hook; log written by `tools/ppo_neural.py`) the check uses a
  small committed fixture of real log keys taken from an existing Hunter run. Keys that only appear conditionally
  (after a curriculum stage, with bootstrap) are marked optional in the declaration, so absence does not fail.
- **The automatic "Other" section.** It shows numeric log keys that no descriptor claims, excluding a shared
  "hidden" list (bookkeeping and timing keys such as `iteration`, `rollout_s`, `update_s`, `elapsed_s`, `policy`,
  gate flags). For the recorded Hunter and Wallcrawler logs "Other" must be empty: any key the old page did not
  chart is either declared (with its chart absent from the layout if it was not charted before) or on the hidden
  list. The legacy `free_shots_per_episode` is declared as an alias of `unaimed_shots_per_episode`.
- **Stat strip.** Task-declared. Shared cells ("Iterations", "Last iteration (s)", "Game time") are always
  present; the rest are the task's headline metrics. Hunter and Wallcrawler strips stay identical to today's;
  Jelly's headline metrics are catches per minute and stuck fraction. The `hits_per_minute` data sniff is
  removed.
- **Jelly starter set.** The builder finds the exact keys in `jelly_scenario.metrics()` and writes titles,
  explanations, units and higher-is-better flags. `kl` and `entropy` are shared for every task. `imitation_loss`
  and its Wallcrawler-worded "Demonstration rehearsal loss" chart are declared by the Wallcrawler only; Jelly
  does not declare it (imitation bootstrap is off by default).
- **Capabilities preserve today's behaviour exactly.** Actor damping stays Wallcrawler-only (Jelly unchanged).
  "Fresh weights" stays unavailable for Hunter and available for Wallcrawler and Jelly. Which replay path a task
  uses becomes a replay-mode capability: 'hooks' (the task's replay hooks, `--check` before watching), 'builtin' (the
  Hunter's built-in path, no pre-watch check) or None (not replayable). The Hunter default for settings scoping ("every
  setting that is not another task's option") becomes an explicit per-task settings rule. The `'hunter'` default
  for untagged run configs and `UNTAGGED_REPLAY_TASK` are legacy data defaults, not task comparisons: they stay,
  but as named constants in the task registry.
- **Branch base.** Confirmed: `feature/pluggable-dashboard` is branched from `feature/neural-jelly` and contains
  `jelly_team`.
- **New endpoint and static files.** The tasks/layout endpoint is read-only and unauthenticated like `/api/runs`;
  Host/Origin checks remain on POST. The static handler serves only `.js` and `.css` files from the fixed folder.
- **Per-task cards.** The provider returns structured data (title, rows of label/value/description) that the page
  renders with one generic card renderer. The card markup may change as long as the same text and values appear;
  the page tests are rewritten to assert on that. Hunter's "Episodes" card also becomes a provider (Hunter's own
  default), so no card logic stays in the page.
- Reward rules (items 11-12): where the user said "list of what reward signal rules are in place for the
  training", I read it as a per-task, per-run list shown in a pinned panel; "configurable" as editable per run in
  the "Next run" form with today's values as defaults. If the user meant something else (for example a schedule of
  values changing over a run), this section changes.
