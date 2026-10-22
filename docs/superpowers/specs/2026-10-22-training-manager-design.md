# Training manager: design

## Intent

Hunter RL training is run today by asking an agent to type a long `python -m tools.ppo_neural …` command, and is
watched on a small dashboard (`serve.py` + `page.html`) that lives in the git-ignored `.astrovoid-local/neural/rl/`.
The player wants a proper app to manage training: one command opens it, and from it they can start, stop, pause
and resume runs and watch them. Agents must be able to do everything the page does, through MCP tools and a command
line. The code moves into the repo so it can be versioned and improved.

## Goals

- One command, `./run-trainer.sh`, starts the app and opens it in the browser.
- See whether training is running, paused or idle, and the current run's progress.
- Start a run. The default is to carry on from the newest run's last checkpoint with its settings; the player can
  instead pick any older run and any of its checkpoints, and change settings before starting.
- Stop a run (it is finished), pause a run (it will continue later) and resume a paused run.
- The existing charts, for the running run or any older one.
- Agents can do all of the above through MCP tools and through the command line, and see what the page sees.

## Non-goals

- More than one run training at a time. One run already uses the whole machine.
- Managing anything other than PPO training of the neural hunter (`tools/ppo_neural.py`). Not DAgger, the lab or
  `train_neural.py`.
- Remote access. It runs on this machine, for this machine.
- Deleting or archiving old runs, installing a checkpoint as the game's pilot. Possible later.

## Anti-goals

- The app must never start, restart or stop training on its own. Every start, stop, pause and resume is a request
  from the player or an agent. (The player has asked to be consulted before training is restarted.)
- Moving to the app must not interrupt a run that is training (run52 is training as this is written).
- The page, the command line and the MCP tools must never disagree about what is happening.
- A paused run must come back as the same run: same folder, iteration numbers carrying on, one continuous line on
  the charts, and training behaving as if it had never stopped.

## What exists now

- Runs live in `.astrovoid-local/neural/rl/runN/` (run1 to run52). Each holds `iterNNNN.npz` (one checkpoint per
  iteration, the network only), `train.log` (one `key=value …` line per iteration, which the dashboard reads) and
  `config.json` (written at start by `write_run_config`: the rewards summary, episode settings, `start`, and from
  run51 on the full `shaping` settings, `decision_frames` and `turn_rate`). Agents launch training with `nohup`,
  sending output to `.astrovoid-local/neural/rl/runN.log`.
- A new run carries on with `--start runM/iterNNNN.npz --out runN …` and about 25 more flags.
- `.astrovoid-local/neural/rl/serve.py` (52 lines, standard library) serves `page.html` (120 lines, plain JS and SVG
  charts) on port 8765 and is running now. It reads the newest `run*/train.log` on every request and serves it as
  `/data.json`, and that run's `config.json` as `/config.json`. `make_page.py` bakes a static copy.
- In `tools/ppo_neural.py` the training loop (around line 260) builds `net` and a frozen reference `ref` from the
  start checkpoint, a fresh Adam optimiser, seeds torch and numpy, and runs `range(iterations)`. The KL coefficient
  depends on `iteration` and `iterations`. Only the network is saved each iteration; the optimiser state, the RNG
  state and the iteration counter are not, so nothing can resume today.

## Decided

### Shape

- One engine module in the repo, `tools/trainer/` (exact layout is the builder's), that knows about runs: list them,
  read their settings and progress, find what is training, start, stop, pause, resume. Everything else is a thin
  layer over it:
  - the web app (server and page), replacing `serve.py` and `page.html`;
  - the command line, `./run-trainer.sh <command>`;
  - an MCP server.
- Python, standard library, as now. The only new dependency is the official `mcp` Python package for the MCP server,
  added to `requirements-train.txt`.
- Run data stays where it is, in `.astrovoid-local/neural/rl/`. The old `serve.py`, `page.html` and `make_page.py`
  there are left alone (they are git-ignored and the running server uses them); the player retires them.

### The page (layout A, chosen from mockups)

One page, top to bottom:

1. **Status strip.** Training: the run, its iteration, when it started, seconds per iteration, and **Pause** and
   **Stop** buttons. Paused: the run and the iteration it paused at, with **Resume** and **Stop**. Idle: "Idle" and
   the last run's final iteration.
2. **Next run box,** always visible. "Carry on from [run] at [checkpoint]", defaulting to the newest run and its
   last checkpoint. Choosing another run fills the settings from that run's `config.json`. **Edit settings** opens
   every setting, grouped (Rewards, Episodes, Training), filled from the chosen run; any that differ from it are
   highlighted, and the box shows a count ("2 settings changed"). **Start runN** uses the next free run number. It
   is disabled while a run is training or paused.
3. **Charts,** as the current page draws them, for the running run by default, with a way to view any older run.

### Starting

- A start launches `python -m tools.ppo_neural` as a background process that outlives the app, the browser and the
  agent session, with output to `.astrovoid-local/neural/rl/runN.log` as agents do now.
- Settings come from the chosen run, with the requested changes applied. The command line built is equivalent to
  what agents write by hand today.
- Starting refuses while any run is training or paused.
- The start reports which settings differ from the run it carries on from, on the page, in the command line and in
  the MCP reply.
- Runs before run51 did not record every setting (runs 1–21 have no `config.json`; runs 22–50 have only the rewards
  summary, the episode block and `start`). *Design call:* a setting missing from the chosen run is filled, in order,
  from what can be recovered from its own `config.json` (the rewards summary and episode block), marked
  *recovered*; otherwise from the newest run that recorded it, marked *guessed*. Never from `ppo_neural`'s parser
  defaults, which are far from what recent runs use (compass reward 0, health 0, no panic score, …) and would quietly
  switch off most of today's shaping. Guessed and recovered settings are marked wherever settings are shown, and are
  not counted as "changed".
- *Design call:* every new run records its full settings in `config.json`, including the ones not recorded today:
  the iteration total (`--iterations`), `--workers`, `--lr`, `--levels` and anything else the command line carried,
  so a run can be carried on from or resumed exactly. The iteration total is an editable setting. Carrying on from a
  run defaults to that run's total; where it was never recorded, 1000 (what run52 uses), marked guessed.

### Stopping, pausing, resuming

- **Stop** ends the run now. The run is finished. The checkpoints written so far are kept, so at most the iteration in
  progress is lost.
- **Pause** asks the run to finish the iteration in progress, save, and exit (20–40 s at current speeds). The status
  shows the run as pausing, then paused.
- **Resume** relaunches the same run into the same folder. Iterations carry on from where they stopped, `train.log`
  is appended to, and training continues exactly as if uninterrupted. This needs the trainer to save, with each
  iteration, what it does not save now: the optimiser state, the iteration reached, the RNG state, and anything else
  the loop depends on (the reference network is the run's original start, recorded in `config.json`; the KL schedule
  needs the original iteration total). The trainer gets a resume option to load it.
- Only a paused run can be resumed. Any run, paused or stopped, can be carried on from as a new run.
- *Design call:* a run whose process ended without a pause or stop (a crash, a reboot, killed by hand) and that has
  resume state is shown as **Interrupted**, and can be resumed like a paused run, from its last saved iteration.
  Runs with no resume state (everything before this change) that are not training count as stopped.

### Seeing what is running

- The engine finds training by looking at the machine's processes, not only at what it launched. A run started by
  hand or by an agent with the old command is seen, and can be stopped. (Pausing it needs the trainer change, so
  only runs started by the new trainer code can be paused.)

### Command line

`./run-trainer.sh` alone starts the app on port 8765 (the old server's port; the builder handles the old server still
holding it) and opens the browser. With a command:

- `status`: run, state, iteration, seconds per iteration, the latest scores. `--json` for machines.
- `start [--from runM | --from runM/iterNNNN] [--set name=value …]`: refuses if something is training or paused.
- `stop`, `pause`, `resume`.
- `runs`: each run, what it started from, what it changed, how far it got, its state.

### MCP

- A stdio MCP server that Claude Code launches itself, registered in the repo's `.mcp.json`, so it works whether or
  not the app is open.
- Tools mirror the command line: `training_status`, `start_run` (where to carry on from, and a map of setting
  changes), `stop_run`, `pause_run`, `resume_run`, `list_runs`. Replies are structured data. `start_run` answers with
  the new run's name and the changed settings.

### Where it is built

On the current branch, `refactor/enemy-catalogue`, in this working copy (the player's decision). The trainer change
targets this branch's `tools/ppo_neural.py`, which is well ahead of `main`. Run52 is training from this working copy:
nothing in the build may signal, restart or replace its process or its workers, and the trainer change only takes
effect for runs started after it.

### Agent notes

There is no CLAUDE.md or AGENTS.md in the repo. Add a short note (README section, or a CLAUDE.md) telling agents to
manage training through the MCP tools or `./run-trainer.sh`, not by launching `tools.ppo_neural` by hand.

## Left to the builder

- Module layout, names, and how the page gets data (polling interval, endpoints).
- How a pause request reaches the trainer (a request file in the run folder checked between iterations, a signal
  handler, or similar), and how the engine records a run's state (training, pausing, paused, stopped).
- The list of editable settings. Preferably derived from `ppo_neural`'s argument parser so new flags appear without
  touching the app; a setting's group and label can come from a small table.
- How the extra resume state is stored. Keep disk use in mind: runs already take 3.9 GB, so per-iteration optimiser
  files should not pile up (keeping only the latest is fine).
- Tests: the engine (listing runs, building start commands, refusing a second start, state detection) and the
  trainer's resume (a resumed run matches an uninterrupted one).
