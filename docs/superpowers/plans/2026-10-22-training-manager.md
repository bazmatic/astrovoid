# Training Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One app, `./run-trainer.sh`, to start, stop, pause, resume and watch hunter PPO training, with the same
controls on a command line and as MCP tools for agents.

**Architecture:** A small engine package `tools/trainer/` (settings, runs and processes, control) does all the work.
Three thin layers sit on it: a standard-library web server and page, a command line (`python -m tools.trainer`), and
a stdio MCP server. The trainer `tools/ppo_neural.py` learns to record its full settings, save resume state each
iteration, pause on request and resume.

**Tech Stack:** Python 3.10 standard library, torch (already used by the trainer), the official `mcp` package
(FastMCP), plain HTML/JS/SVG for the page.

**Spec:** `docs/superpowers/specs/2026-10-22-training-manager-design.md`

## Global Constraints

- Nothing may signal, restart or replace run52's process (pid 24465 at writing) or its workers. Tests never touch
  real processes: process listings and launches are injected.
- The app never starts, stops, pauses or resumes training on its own; only on a request.
- Run data stays in `.astrovoid-local/neural/rl/` (`ppo_neural.DEFAULT_OUT`). Runs are `runN/`, launch output goes
  to `runN.log` beside them. Do not edit or delete the old `serve.py`, `page.html`, `make_page.py` there.
- One run trains at a time. Start refuses while any run is training, pausing or paused.
- Missing settings are filled from the run's own `config.json` (marked `recovered`), else from the newest run that
  recorded them (`guessed`), never from parser defaults, except the iteration total, which falls back to 1000
  (`guessed`). Recovered and guessed values do not count as changed.
- Only the `mcp` package is added (to `requirements-train.txt`). Everything else is standard library.
- Work on branch `refactor/enemy-catalogue` in place. The branch carries unrelated uncommitted work: every commit
  adds only the files its task names.
- The web server binds 127.0.0.1 (local only), default port 8765.

## Review Focus

- A run folder with no `train.log`, an empty one, or a half-written last line (crash mid-write): listing, status and
  the page keep working and count only complete lines. Test in Task 3.
- A run that died before its first checkpoint (no `iter*.npz`): it is listed, `start --from` it refuses with a clear
  message, and the next run number still skips past it. Tests in Tasks 3 and 4.
- A pause requested and then the process dies or is killed before acting on it: status must not say "pausing" for a
  run that is not training, and resume or a new start clears the stale request. Tests in Tasks 3 and 4.
- The page and an agent both press start at the same moment: only one run launches. Test in Task 4.
- `--set` with an unknown name or a value that does not parse (`speed_penalty=fast`, `levels=1-x`): a clear error and
  nothing launched. Tests in Tasks 2 and 4.

---

### Task 1: The trainer records everything, pauses on request and resumes

**Files:**
- Modify: `tools/ppo_neural.py` (`train_rl` ~line 255, `write_run_config` ~line 391, `build_parser` ~line 407, `main` ~line 470)
- Test: `tests/test_ppo_resume.py`

**Interfaces:**
- Produces, in each run folder:
  - `config.json` gains `"args"`: every parsed argument by dest (`levels` as a list or null, `panic_score` possibly
    null). Existing keys unchanged.
  - `resume.pt` (overwritten atomically after each iteration's checkpoint, write to a temp name then `os.replace`):
    full net `state_dict` including the value head, optimiser `state_dict`, `next_iteration`, `iterations`, torch RNG
    state, numpy `rng.bit_generator.state`.
  - `state.json`: `{"state": "paused", "iteration": i}` when it stops on a pause request; `{"state": "finished",
    "iteration": i}` after the last iteration. Removed when a run starts or resumes.
  - Pause request: the file `PAUSE` in the run folder. Checked at the very end of each iteration, after the
    checkpoint, `resume.pt` and the `train.log` line are written; acted on by removing it, writing `state.json` and
    returning.
- `train_rl(..., resume=False)` returns `{'last', 'history', 'paused': bool}`.
- CLI: `python -m tools.ppo_neural <all args as before> --resume` continues the run in `--out`: loads `resume.pt`, keeps
  the reference network from `--start` (the run's original start), runs iterations `next_iteration..iterations-1`,
  appends to `train.log`, does not rewrite `config.json`.

- [ ] **Step 1: Write the failing tests** in `tests/test_ppo_resume.py`, reusing `fake_rollout_factory` from `tests/test_ppo_loop.py` (import it) and a `random_policy` start saved to `tmp_path`:

```python
def test_a_paused_and_resumed_run_matches_an_uninterrupted_one(tmp_path):
    whole = ppo.train_rl(start, tmp_path / 'whole', iterations=4, episodes=6, workers=1,
                         rollout=fake_rollout_factory(), log=quiet)
    (tmp_path / 'split').mkdir()
    pausing_log = lambda line: (tmp_path / 'split' / 'PAUSE').touch() if 'iteration=1 ' in line + ' ' else None
    first = ppo.train_rl(start, tmp_path / 'split', iterations=4, episodes=6, workers=1,
                         rollout=fake_rollout_factory(), log=pausing_log)
    assert first['paused'] and len(first['history']) == 2
    assert json.loads((tmp_path / 'split' / 'state.json').read_text()) == {'state': 'paused', 'iteration': 1}
    assert not (tmp_path / 'split' / 'PAUSE').exists()
    second = ppo.train_rl(start, tmp_path / 'split', iterations=4, episodes=6, workers=1,
                          rollout=fake_rollout_factory(), log=quiet, resume=True)
    assert [h['iteration'] for h in second['history']] == [2, 3]
    assert not (tmp_path / 'split' / 'state.json').exists() or \
        json.loads((tmp_path / 'split' / 'state.json').read_text())['state'] == 'finished'
    for a, b in zip(load(whole['last']).params.values(), load(second['last']).params.values()):
        np.testing.assert_allclose(a, b, rtol=1e-5, atol=1e-6)
    assert len((tmp_path / 'split' / 'train.log').read_text().splitlines()) == 4

def test_a_finished_run_says_so_and_keeps_its_resume_state(tmp_path): ...
    # state.json == {'state': 'finished', 'iteration': 1} after iterations=2; resume.pt exists

def test_the_run_config_records_every_argument(tmp_path):
    ppo.write_run_config(ppo.build_parser().parse_args(['--out', str(tmp_path), '--iterations', '7',
                                                        '--levels', '1-3', '--speed-penalty', '2']))
    args = json.loads((tmp_path / 'config.json').read_text())['args']
    assert args['iterations'] == 7 and args['levels'] == [1, 2, 3] and args['speed_penalty'] == 2.0
    assert args['panic_score'] is None and 'workers' in args and 'rewards' in json.loads((tmp_path / 'config.json').read_text())

def test_resume_without_resume_state_refuses(tmp_path):
    with pytest.raises(FileNotFoundError):
        ppo.train_rl(start, tmp_path / 'empty', 2, episodes=6, workers=1, rollout=fake_rollout_factory(),
                     log=quiet, resume=True)
```

- [ ] **Step 2: Run them to see them fail**

Run: `./venv/bin/python -m pytest tests/test_ppo_resume.py -q`
Expected: FAIL (`train_rl() got an unexpected keyword argument 'resume'`, missing `args`).

- [ ] **Step 3: Implement** in `tools/ppo_neural.py`:
  - `write_run_config`: add `'args': {k: (list(v) if isinstance(v, tuple) else v) for k, v in vars(args).items()}`.
  - `train_rl(..., resume=False)`: on resume, load `resume.pt` (raise `FileNotFoundError` if absent), restore net,
    optimiser, both RNG states, start the loop at `next_iteration` (the `iterations` argument stays the total, so
    `kl_coefficient` and `make_jobs` see the same numbers as an uninterrupted run). `ref` is still built from `start`.
    `current` for the first resumed iteration's jobs is the last saved `iter{next_iteration-1:04d}.npz`. On a fresh
    start remove any `state.json`; on resume remove it too. After saving each iteration's checkpoint, write
    `resume.pt`; then if `PAUSE` exists, remove it, write the paused `state.json`, and leave the loop with
    `paused=True` (the `finally` still closes the pool; do not delete `iter_start.npz` only on a fresh start's end
    as now). After the last iteration write the finished `state.json`.
  - `build_parser`: `--resume` (`store_true`, help: 'carry on the run in --out from its resume state').
  - `main`: skip `write_run_config` when `--resume`; pass `resume=args.resume`; print `paused | at iteration N` when
    paused.

- [ ] **Step 4: Run the new and the existing trainer tests**

Run: `./venv/bin/python -m pytest tests/test_ppo_resume.py tests/test_ppo_loop.py tests/test_ppo_neural.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/ppo_neural.py tests/test_ppo_resume.py
git commit -m "feat: training runs record all their settings, pause on request and resume"
```

---

### Task 2: Settings: the editable list, filling a run's settings, changes, command lines

**Files:**
- Create: `tools/trainer/__init__.py` (empty docstring module), `tools/trainer/settings.py`
- Test: `tests/test_trainer_settings.py`

**Interfaces:**
- Consumes: `ppo_neural.build_parser()`, `ppo_neural.parse_levels`, the `config.json` shapes (Task 1's `args`; older
  `shaping`, `episode`, `rewards`, `start`).
- Produces:
  - `Setting` dataclass: `dest: str, flag: str, kind: str` (`'int' | 'float' | 'bool' | 'levels' | 'optional_float'`),
    `default, help: str, group: str` (`'Rewards' | 'Episodes' | 'Training'`), `label: str`.
  - `SETTINGS: list[Setting]`, built from `build_parser()` actions, excluding `start`, `out`, `resume`, `help`. Group
    and label come from a small dict keyed by dest; a dest missing from it goes in `Training` with a label made from
    the dest, so new flags appear without editing the app.
  - `Value` dataclass: `value, source: str` (`'recorded' | 'recovered' | 'guessed'`).
  - `read_settings(run_dir: Path, all_runs: list[Path]) -> dict[str, Value]`: every dest in `SETTINGS`. Order of
    sources: `config['args']` (recorded) → `config['shaping']` (recorded; `random_start` is `not fixed_start`,
    `pursue_hunter` is `not decoy_player`) → `config['episode']` (recovered: `episodes_per_iteration`→`episodes`,
    `learning_rate`→`lr`, `horizon_seconds`→`horizon`, `after_clear_seconds`→`after_clear`, `health`, `rules_share`,
    `levels`, `panic_score`, `panic_temperature`) → `config['rewards']` (recovered: a reward-row table mapping each
    `reward_summary` row name to its dest and divisor; a dest with a row table entry but no row in a run that has a
    `rewards` list is recovered as 0, because rows are only written when non-zero) → the newest run in `all_runs`
    whose config records it (guessed) → `iterations` 1000 (guessed) → parser default (guessed; only for dests no run
    ever recorded).
  - `parse_value(setting: Setting, text: str)` → typed value; raises `ValueError(f'{setting.dest}: {text!r} is not ...')`.
  - `apply_changes(base: dict[str, Value], changes: dict[str, object]) -> dict[str, Value]`: names accepted as dest
    or flag (`speed_penalty`, `speed-penalty`, `--speed-penalty`); string values parsed with `parse_value`; changed
    entries get source `'recorded'`. Unknown name → `ValueError('unknown setting: ...')`.
  - `changed(base: dict[str, Value], new: dict[str, Value]) -> list[tuple[str, object, object]]`: `(dest, old, new)`
    where the values differ.
  - `to_argv(values: dict[str, Value]) -> list[str]`: every setting explicit; `bool` → flag only when true;
    `optional_float` None → omitted; `levels` → `1-30` style ranges, None → omitted.
  - `config_args(run_dir) -> dict | None` helper reading `config.json` safely (missing or invalid → None).

- [ ] **Step 1: Write the failing tests** (`tests/test_trainer_settings.py`), building run folders in `tmp_path` with hand-written `config.json` files:

```python
def test_a_run_with_args_is_read_exactly(tmp_path): ...            # all sources 'recorded', values equal args
def test_run51_style_shaping_is_recorded_and_episode_fills_the_rest(tmp_path): ...
    # shaping speed_penalty 3.0 → recorded; episodes from episode block → 'recovered'
def test_an_old_run_recovers_rewards_and_guesses_the_rest_from_the_newest(tmp_path):
    # run40: rewards [{'name': 'Powerup collected', 'value': 15.0, ...}], no compass row; run52: args compass_reward 100
    s = read_settings(run40, [run40, run52])
    assert s['powerup_reward'] == Value(15.0, 'recovered')
    assert s['compass_reward'] == Value(0.0, 'recovered')     # no row means it was 0
    assert s['boredom_window'].source == 'guessed' and s['boredom_window'].value == run52_args['boredom_window']
    assert s['iterations'].value == 52_args_iterations         # newest run's recorded total
def test_a_run_with_no_config_takes_everything_from_the_newest(tmp_path): ...  # all 'guessed'
def test_the_iteration_total_falls_back_to_1000_when_no_run_recorded_it(tmp_path):
    assert read_settings(old, [old])['iterations'] == Value(1000, 'guessed')
def test_changes_accept_dest_or_flag_names_and_report_what_changed(tmp_path):
    new = apply_changes(base, {'speed-penalty': '2', 'levels': '1-5'})
    assert changed(base, new) == [('levels', ..., (1, 2, 3, 4, 5)), ('speed_penalty', 3.0, 2.0)]
def test_bad_names_and_values_are_refused():
    for bad in ({'speed_penalty': 'fast'}, {'levels': '1-x'}, {'no_such': '1'}, {'health': '2.5'}):
        with pytest.raises(ValueError): apply_changes(base, bad)
def test_guessed_values_are_not_counted_as_changes(tmp_path): ...
def test_the_command_line_round_trips_through_the_trainer_parser(tmp_path):
    argv = to_argv(values)
    parsed = vars(ppo.build_parser().parse_args(argv))
    assert all(parsed[d] == (tuple(v.value) if d == 'levels' and v.value else v.value) for d, v in values.items())
def test_every_parser_flag_is_a_setting():
    assert {s.dest for s in SETTINGS} == {a.dest for a in ppo.build_parser()._actions} - {'start', 'out', 'resume', 'help'}
```

- [ ] **Step 2: Run to see them fail**

Run: `./venv/bin/python -m pytest tests/test_trainer_settings.py -q`
Expected: FAIL (`No module named 'tools.trainer'`).

- [ ] **Step 3: Implement `tools/trainer/settings.py`** with the interfaces above. The reward-row table comes from `reward_summary` in `tools/ppo_neural.py` (~line 320): each row name → dest; `Wall impact` divides by `experiments.score.Weights().quotient` to get `wall_scale`; rows with no single dest (`Kills`) are skipped.

- [ ] **Step 4: Run to see them pass**

Run: `./venv/bin/python -m pytest tests/test_trainer_settings.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/trainer/__init__.py tools/trainer/settings.py tests/test_trainer_settings.py
git commit -m "feat: trainer settings: read any run's settings, apply changes, build the command line"
```

---

### Task 3: Runs and processes: what exists and what is training

**Files:**
- Create: `tools/trainer/processes.py`, `tools/trainer/runs.py`
- Test: `tests/test_trainer_runs.py`

**Interfaces:**
- Produces in `processes.py`:
  - `Process` namedtuple `(pid: int, ppid: int, command: str)`.
  - `list_processes() -> list[Process]` via `ps -axo pid=,ppid=,command=`.
  - `training(processes, root: Path) -> dict[str, int]`: run name → pid for each process whose command contains
    `tools.ppo_neural` and a `--out` naming a folder (absolute, or relative to the repo root) whose parent is `root`.
  - `descendants(pid, processes) -> list[int]`.
  - `terminate_tree(pid, processes, kill=os.kill, wait=10.0) -> None`: SIGTERM the process and its descendants, wait
    for them to go (poll `kill(pid, 0)`), SIGKILL what remains.
- Produces in `runs.py`:
  - `RL_ROOT = ppo_neural.DEFAULT_OUT`.
  - `Run` dataclass: `name, number: int, path: Path, state: str, iterations_done: int, total: int | None,
    started_from: str | None, checkpoints: list[str], pid: int | None`. `state` is one of `'training' | 'pausing' |
    'paused' | 'interrupted' | 'finished' | 'stopped'`.
  - `list_runs(root=RL_ROOT, processes=None) -> list[Run]`, oldest first by number (`processes` defaults to
    `list_processes()`). State: training (pausing if `PAUSE` exists) when a process trains it; else `state.json`'s
    state if present (`paused`, `finished`, `stopped`); else `interrupted` if `resume.pt` exists; else `stopped`.
  - `log_rows(run_dir) -> list[dict]`: complete `iteration=` lines of `train.log` parsed as in the old `serve.py`
    (numbers to float, `True`/`False` to bool); a line that does not parse is skipped.
  - `next_run_number(root) -> int`: one more than the largest `runN` folder (any contents).
  - `status(root=RL_ROOT, processes=None) -> dict`: `{'state': 'training'|'pausing'|'paused'|'interrupted'|'idle',
    'run': name or None, 'iteration': last logged iteration or None, 'iterations': total or None,
    'seconds_per_iteration': rollout_s + update_s of the last row or None, 'started': ISO time of the run's
    `config.json` mtime or None, 'latest': last row or {}}`. Idle shows the newest run.

- [ ] **Step 1: Write the failing tests** with fake run folders in `tmp_path` and fake `Process` lists:

```python
def test_a_process_with_this_out_folder_is_training(tmp_path):
    procs = [Process(10, 1, f'/v/python -m tools.ppo_neural --start x --out {tmp_path}/run3 --iterations 5'),
             Process(11, 10, 'python -c from multiprocessing.spawn import spawn_main')]
    assert training(procs, tmp_path) == {'run3': 10}
    assert descendants(10, procs) == [11]
def test_a_relative_out_folder_is_resolved_from_the_repo_root(): ...
def test_states_come_from_process_then_state_file_then_resume_state(tmp_path):
    # run1 no files → stopped; run2 resume.pt → interrupted; run3 state paused → paused;
    # run4 state finished → finished; run5 trained by a process → training; run5 + PAUSE → pausing
def test_a_stale_pause_request_on_a_dead_run_is_not_pausing(tmp_path):
    # PAUSE + resume.pt, no process → 'interrupted'
def test_a_half_written_or_missing_log_is_tolerated(tmp_path):
    # train.log with two good lines and 'policy_loss=0.1 iterat' → 2 rows; no train.log → []
def test_a_run_with_no_checkpoints_is_listed_and_numbers_continue(tmp_path):
    # run7 empty folder → listed, checkpoints == []; next_run_number == 8
def test_status_reports_the_training_run(tmp_path): ...
def test_status_is_idle_with_the_newest_run_when_nothing_trains(tmp_path): ...
def test_terminate_tree_terms_then_kills_what_is_left():
    sent = []; alive = {10, 11}
    def kill(pid, sig):
        if sig == 0:
            if pid not in alive: raise ProcessLookupError
        else: sent.append((pid, sig)); (alive.discard(pid) if pid == 11 else None)
    terminate_tree(10, procs, kill=kill, wait=0.05)
    assert (10, signal.SIGTERM) in sent and (11, signal.SIGTERM) in sent and (10, signal.SIGKILL) in sent
```

- [ ] **Step 2: Run to see them fail**

Run: `./venv/bin/python -m pytest tests/test_trainer_runs.py -q`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `processes.py` and `runs.py`** to the interfaces above.

- [ ] **Step 4: Run to see them pass, then check it against the real runs without touching them**

Run: `./venv/bin/python -m pytest tests/test_trainer_runs.py -q`
Expected: all pass.
Run: `./venv/bin/python -c "from tools.trainer import runs; print(runs.status())"`
Expected: state `training`, run `run52`, a recent iteration (read-only: only `ps` and file reads).

- [ ] **Step 5: Commit**

```bash
git add tools/trainer/processes.py tools/trainer/runs.py tests/test_trainer_runs.py
git commit -m "feat: trainer runs: list runs, their states and what is training"
```

---

### Task 4: Control: start, stop, pause, resume

**Files:**
- Create: `tools/trainer/control.py`
- Test: `tests/test_trainer_control.py`

**Interfaces:**
- Consumes: Task 2 (`read_settings`, `apply_changes`, `changed`, `to_argv`, `SETTINGS`), Task 3 (`list_runs`,
  `next_run_number`, `training`, `terminate_tree`, `list_processes`, `RL_ROOT`), Task 1's files (`PAUSE`,
  `state.json`, `resume.pt`, `--resume`).
- Produces:
  - `class TrainerError(Exception)` (message shown to people as is).
  - `Started` dataclass: `run: str, started_from: str, changes: list[tuple[str, object, object]], command: list[str]`.
  - `start(from_: str | None = None, changes: dict | None = None, root=RL_ROOT, processes=None, launch=None) -> Started`.
    `from_` is `None` (newest run with a checkpoint, its last one), `'runM'` (its last checkpoint) or
    `'runM/iterNNNN'`. Refuses with `TrainerError` when any run is training, pausing or paused (`'run52 is training;
    stop or pause it first'`), when the run or checkpoint does not exist, or when the run has no checkpoints
    (`'run7 has no checkpoints to carry on from'`). Settings: `read_settings` of the source run, then
    `apply_changes`. Holds an exclusive lock (`root / '.trainer.lock'`, created with `O_CREAT | O_EXCL`, removed in
    `finally`; a lock older than 60 s is treated as stale) from the busy check until the launch returns. The command
    is `[sys.executable, '-m', 'tools.ppo_neural', '--start', <checkpoint path>, '--out', <root/runN>, *to_argv(...)]`.
  - `launch` default: `subprocess.Popen(command, cwd=<repo root>, stdout=<root/runN.log opened for append>,
    stderr=STDOUT, stdin=DEVNULL, start_new_session=True)`; returns the pid. Tests pass a fake that records commands.
  - `stop(root=RL_ROOT, processes=None, terminate=terminate_tree) -> str`: stops the training (or pausing) run, writes
    its `state.json` `{"state": "stopped", "iteration": last}`, removes any `PAUSE`. A paused or interrupted run is
    stopped by writing `state.json` only. Nothing to stop → `TrainerError('nothing is training')`. Returns the run name.
  - `pause(root=RL_ROOT, processes=None) -> str`: touches `PAUSE` in the training run. Not training → `TrainerError`.
    A run started by pre-Task-1 trainer code (its `config.json` has no `args`, e.g. run52) →
    `TrainerError('run52 was started before pausing existed; it can only be stopped')`.
  - `resume(run: str | None = None, root=RL_ROOT, processes=None, launch=None) -> str`: run defaults to the paused or
    interrupted one. Refuses if something is training, or the run is not `paused`/`interrupted`. Removes `PAUSE`,
    launches `[sys.executable, '-m', 'tools.ppo_neural', '--start', <config args start>, '--out', <run>,
    *to_argv(recorded settings), '--resume']` with the same lock and launcher.

- [ ] **Step 1: Write the failing tests** with fake run folders, fake processes, a fake `launch` and a fake `terminate`:

```python
def test_start_carries_on_from_the_newest_runs_last_checkpoint(tmp_path):
    s = start(root=tmp_path, processes=[], launch=fake)
    assert s.run == 'run53' and s.started_from == 'run52/iter0002'
    assert fake.commands[0][3:7] == ['--start', str(tmp_path / 'run52/iter0002.npz'), '--out', str(tmp_path / 'run53')]
def test_start_from_an_older_run_and_checkpoint_with_changes(tmp_path):
    s = start('run51/iter0001', {'speed_penalty': '2'}, root=tmp_path, processes=[], launch=fake)
    assert s.changes == [('speed_penalty', 3.0, 2.0)] and '--speed-penalty' in fake.commands[0]
def test_start_refuses_while_a_run_is_training_or_paused(tmp_path): ...   # nothing launched
def test_start_refuses_a_run_without_checkpoints_and_unknown_runs(tmp_path): ...
def test_bad_settings_launch_nothing(tmp_path): ...                     # ValueError surfaced as TrainerError
def test_two_starts_at_once_launch_one_run(tmp_path):
    # the fake launch for the first call itself calls start(); the inner call raises TrainerError (lock held)
def test_pause_asks_the_training_run_to_pause(tmp_path): ...            # PAUSE created
def test_pause_refuses_a_run_started_before_pausing_existed(tmp_path): ...
def test_stop_ends_the_training_run_and_marks_it_stopped(tmp_path): ...  # terminate called with its pid; state.json
def test_resume_relaunches_the_paused_run_with_resume(tmp_path):
    # state.json paused, config args → command ends with '--resume', --out is the same run, PAUSE cleared
def test_resume_clears_a_stale_pause_on_an_interrupted_run(tmp_path): ...
```

- [ ] **Step 2: Run to see them fail**

Run: `./venv/bin/python -m pytest tests/test_trainer_control.py -q`
Expected: FAIL (import error).

- [ ] **Step 3: Implement `tools/trainer/control.py`** to the interfaces above.

- [ ] **Step 4: Run to see them pass**

Run: `./venv/bin/python -m pytest tests/test_trainer_control.py tests/test_trainer_runs.py tests/test_trainer_settings.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/trainer/control.py tests/test_trainer_control.py
git commit -m "feat: trainer control: start, stop, pause and resume runs"
```

---

### Task 5: Command line and `./run-trainer.sh`

**Files:**
- Create: `tools/trainer/__main__.py`, `run-trainer.sh` (executable, in the style of `run-hunter.sh`: `set -euo pipefail`, `cd` to its folder, `exec ./venv/bin/python -m tools.trainer "$@"`)
- Test: `tests/test_trainer_cli.py`

**Interfaces:**
- Consumes: Task 3 `status`, `list_runs`; Task 4 `start`, `stop`, `pause`, `resume`, `TrainerError`; Task 6
  `serve(port: int, open_browser: bool) -> None` (imported lazily so this task's tests do not need it).
- Produces: `main(argv: list[str] | None = None, out=sys.stdout) -> int` with subcommands:
  - none or `serve [--port 8765] [--no-browser]` → `serve(...)`.
  - `status [--json]`.
  - `runs [--json]`: per run its name, state, `iterations_done/total`, what it started from, and the settings it
    changed from that run (`settings.changed(read_settings(source), read_settings(run))`, recorded values only;
    `source` is the run folder named in its `started_from`, none when it started from outside the runs).
  - `start [--from RUN[/iterNNNN]] [--set NAME=VALUE ...]` → prints the new run, where it carries on from, and each
    change as `speed_penalty: 3.0 → 2.0` (or `no settings changed`).
  - `stop`, `pause`, `resume [RUN]`.
  - A `TrainerError` prints `error: <message>` and returns 1. Success returns 0.

- [ ] **Step 1: Write the failing tests**, monkeypatching `tools.trainer.control`/`runs` functions so nothing real runs:

```python
def test_status_json_is_the_engine_status(monkeypatch, capsys): ...
def test_start_passes_from_and_set_and_prints_the_changes(monkeypatch, capsys):
    assert main(['start', '--from', 'run51', '--set', 'speed_penalty=2', '--set', 'levels=1-5']) == 0
    assert seen == ('run51', {'speed_penalty': '2', 'levels': '1-5'})
    assert 'speed_penalty: 3.0 → 2.0' in capsys.readouterr().out
def test_a_set_without_equals_is_an_error(capsys): ...              # returns 2 (argparse) or 1, nothing started
def test_trainer_errors_print_and_return_one(monkeypatch, capsys): ...
def test_runs_lists_name_state_progress_and_source(monkeypatch, capsys): ...
```

- [ ] **Step 2: Run to see them fail**

Run: `./venv/bin/python -m pytest tests/test_trainer_cli.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `__main__.py` and `run-trainer.sh`**, then `chmod +x run-trainer.sh`.

- [ ] **Step 4: Run the tests, and the real status read-only**

Run: `./venv/bin/python -m pytest tests/test_trainer_cli.py -q` → all pass.
Run: `./run-trainer.sh status` → shows run52 training. Run: `./run-trainer.sh runs` → lists run1–run52.

- [ ] **Step 5: Commit**

```bash
git add tools/trainer/__main__.py run-trainer.sh tests/test_trainer_cli.py
git commit -m "feat: run-trainer.sh: training status, runs, start, stop, pause and resume from the command line"
```

---

### Task 6: The web app

**Files:**
- Create: `tools/trainer/server.py`, `tools/trainer/page.html`
- Test: `tests/test_trainer_server.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces:
  - `make_server(port: int, root=RL_ROOT, host='127.0.0.1') -> ThreadingHTTPServer` and `serve(port=8765,
    open_browser=True, root=RL_ROOT)`. If the port is taken (the old `serve.py` holds 8765), try the next ports up to
    +10 and print which one is used and why. Prints the URL; opens it with `webbrowser.open` when asked.
  - JSON endpoints (all `Cache-Control: no-store`):
    - `GET /api/status` → Task 3 `status()`.
    - `GET /api/runs` → list of runs (name, state, iterations_done, total, started_from, checkpoints).
    - `GET /api/runs/<name>/data` → `log_rows`; `GET /api/runs/<name>/config` → its `config.json` or `{}`.
    - `GET /api/runs/<name>/settings` → `{dest: {value, source}}`; `GET /api/settings` → the `SETTINGS` schema.
    - `POST /api/start` body `{"from": "run51/iter0003" | null, "changes": {dest: value}}` → `Started` as JSON.
    - `POST /api/stop`, `POST /api/pause`, `POST /api/resume` body `{"run": name | null}`.
    - `TrainerError` → 409 `{"error": message}`; `ValueError` → 400; unknown run → 404.
  - `GET /` → `page.html`.
- Page (`page.html`), layout A from the spec, keeping the current page's look (its CSS variables, light and dark, IBM
  Plex) and its charts, stat strip and rewards/episodes cards, ported from
  `.astrovoid-local/neural/rl/page.html` (copy the chart functions, then point them at the new endpoints):
  1. Status strip: state badge; run; `iteration N of T`; started time; seconds per iteration; buttons by state —
     training: Pause, Stop; pausing: "Pausing after this iteration…", Stop; paused or interrupted: Resume, Stop; idle:
     none. Stop needs a second click: the first turns the button into "Really stop?" for 5 s (no browser
     `confirm()` dialogs).
  2. Next run box: run select (runs with checkpoints, newest first) and checkpoint select (newest first);
     "N settings changed"; Edit settings toggles a grouped form (Rewards, Episodes, Training) filled from
     `/api/runs/<run>/settings`, each input highlighted when it differs from the run's value, a small "recovered" or
     "guessed" tag on such values; `Start runN` disabled unless the state is idle (with the reason shown). Errors from
     the API appear in the box.
  3. Charts for a selected run (a select at the top of the charts, defaulting to the status run), refreshed every
     15 s; the status polls every 5 s.

- [ ] **Step 1: Write the failing tests**, running `make_server(0, root=tmp_path)` in a thread against fake run folders, with `control`/`processes` monkeypatched so no process is listed, launched or signalled:

```python
def test_status_and_runs_are_served(server): ...
def test_run_data_skips_bad_lines_and_unknown_runs_are_404(server): ...
def test_settings_carry_their_sources(server): ...
def test_start_posts_from_and_changes_and_returns_the_new_run(server, launched): ...
def test_a_busy_trainer_is_a_409_with_the_message(server): ...
def test_bad_setting_values_are_a_400(server): ...
def test_the_page_is_served(server): ...                      # 200, text/html, contains 'id="status"'
def test_a_taken_port_moves_to_the_next_one(): ...
```

- [ ] **Step 2: Run to see them fail**

Run: `./venv/bin/python -m pytest tests/test_trainer_server.py -q` → FAIL.

- [ ] **Step 3: Implement `server.py` and `page.html`.**

- [ ] **Step 4: Run the tests, then look at the page against the real runs (read-only)**

Run: `./venv/bin/python -m pytest tests/test_trainer_server.py -q` → all pass.
Run: `./run-trainer.sh serve --port 8790 --no-browser` in the background, open `http://127.0.0.1:8790/` in a browser
tool, check: status shows run52 training with Stop (Pause refused with the "started before pausing existed" message if
clicked — do not click Stop), the Next run box shows run52 and its last checkpoint with Start disabled, charts draw,
light and dark both readable, the settings form shows guessed/recovered tags for an old run such as run40. Then stop
the server.

- [ ] **Step 5: Commit**

```bash
git add tools/trainer/server.py tools/trainer/page.html tests/test_trainer_server.py
git commit -m "feat: training manager web app: status, start, stop, pause, resume and the charts"
```

---

### Task 7: MCP server, dependency and agent notes

**Files:**
- Create: `tools/trainer/mcp_server.py`, `.mcp.json`
- Modify: `requirements-train.txt` (add `mcp>=1.2`), `README.md` (a "Training manager" section)
- Test: `tests/test_trainer_mcp.py`

**Interfaces:**
- Consumes: Tasks 3 and 4.
- Produces: a FastMCP server named `astrovoid-trainer` with tools returning plain dicts (errors as
  `{"error": message}` rather than exceptions, so agents read them):
  - `training_status()` → `runs.status()`.
  - `list_runs()` → as `/api/runs`.
  - `start_run(from_run: str | None = None, changes: dict[str, str] | None = None)` → `{run, started_from, changes:
    [{setting, old, new}]}`.
  - `stop_run()`, `pause_run()` → `{run}`; `resume_run(run: str | None = None)` → `{run}`.
  - Each tool's docstring says what it does in one or two sentences, including that start refuses while a run is
    training or paused and that pausing finishes the current iteration first.
  - `.mcp.json`: `{"mcpServers": {"astrovoid-trainer": {"command": "./venv/bin/python", "args": ["-m",
    "tools.trainer.mcp_server"]}}}`.
- README section: what `./run-trainer.sh` does, the commands, the MCP tools, and the line "Agents: manage training
  with these tools or `./run-trainer.sh`, not by launching `tools.ppo_neural` by hand."

- [ ] **Step 1: Install the dependency**

Run: `./venv/bin/pip install 'mcp>=1.2'` → installs. Add `mcp>=1.2` to `requirements-train.txt`.

- [ ] **Step 2: Write the failing tests** calling the tool functions directly with `control`/`runs` monkeypatched:

```python
def test_the_tools_are_registered():
    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    assert names == {'training_status', 'list_runs', 'start_run', 'stop_run', 'pause_run', 'resume_run'}
def test_start_run_reports_changes(monkeypatch): ...
def test_errors_come_back_as_data(monkeypatch):
    assert mcp_server.pause_run() == {'error': 'nothing is training'}
```

- [ ] **Step 3: Run to see them fail**, implement `mcp_server.py`, `.mcp.json` and the README section, run to see them pass.

Run: `./venv/bin/python -m pytest tests/test_trainer_mcp.py -q` → all pass.

- [ ] **Step 4: Check the server starts over stdio**

Run: `printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' | timeout 5 ./venv/bin/python -m tools.trainer.mcp_server`
Expected: a JSON reply naming `astrovoid-trainer`.

- [ ] **Step 5: Run every trainer test and the trainer's own tests**

Run: `./venv/bin/python -m pytest tests/test_trainer_*.py tests/test_ppo_resume.py tests/test_ppo_loop.py tests/test_ppo_neural.py -q`
Expected: all pass.

- [ ] **Step 6: Commit** (README.md also carries uncommitted Settings-screen edits from earlier; stage only this section with `git add -p README.md`)

```bash
git add tools/trainer/mcp_server.py .mcp.json requirements-train.txt tests/test_trainer_mcp.py
git add -p README.md
git commit -m "feat: training manager MCP tools for agents"
```
