# Replay hooks

`learning/replay.py` replays any registered task's recorded training episodes. It contains no task code: it
reads the run's `config.json` for the task key (runs recorded before the key was written are taken as
`learning.tasks.UNTAGGED_REPLAY_TASK`, the Wallcrawler team), and asks that task's **replay hooks module** for
everything that differs between tasks. A task opts in by naming the module in `learning/tasks.py`:

```python
Task('jelly_team', 'learning.adapters.jelly_scenario', 'Jelly team', ..., replay_module='learning.replay',
     replay_hooks='learning.adapters.jelly_replay')
```

`replay_module` stays `learning.replay` for every replayable task; it is what `Task.replay()` returns to the
callers (`tools/watch_episode.py`, `tools/trainer/replay.py`). A task with no `replay_hooks`, or a hooks module
without `open_environment`, fails with a `ValueError` naming the task and the missing hook.

## The contract

| Hook | Required | Purpose | Default |
|---|---|---|---|
| `open_environment(path, manifest) -> env` | yes | Check the recording against the current rules (raise `ValueError` if they differ) and build the environment to replay in, from the run directory and its saved manifest. | — |
| `episode(job) -> dict` | no | The fields listed for each episode by `episodes()`. | the job as recorded |
| `outcome(manifest, events, transition, total_reward) -> dict` | no | The return, end reason and any other fields of a flown episode's row. | `return` = summed step rewards, `end` = `horizon` or `terminated` |
| `draw(env, screen)` | no | Draw the scene in the watch window. | the game world's own drawing: maze, roster, additional targets, ship, projectiles |
| `status(env, job) -> list[str]` | no | The watch window's text lines. | task label, level and seconds |

`learning.replay.check_rules(path, manifest, metadata, effective_rules=identity)` is the shared rules check for
`open_environment`: it builds the current manifest with the task adapter's `metadata(args)`, takes the arena
snapshots and training hyperparameters from the recording, and raises
`replay rules, schemas or opponent differ from the recorded run: <changed keys>` on any other difference.
`effective_rules` maps a manifest to what actually governs play (the Wallcrawler compares the practice gun cadence
used, not its overridden default).

## Exactness

The episodes file is `learning.run`'s: `jobs` (reset arguments plus `seed`), `episodes` (recorded events) and
`actions` (each episode's per-decision joint actions, from the environment's `action_trace`). `fly(path, iteration)`
resets with each job, applies the recorded actions in order and requires the final events to equal the recorded
ones exactly (`replay diverged in episode N` otherwise). Rows are `episode`, `level`, `seed`, the outcome fields and
the events. `watch(path, iteration, episode, speed)` flies one episode in a 1352x878 window.

## Registered hooks

- `learning/adapters/crawler_replay.py` (`wallcrawler_team`): the frozen opponent `opponent.npz` copied into the
  run, the effective practice gun cadence, the crawler's reward formula and end reasons, its scene (with the
  opponent) and per-crawler status lines.
- `learning/adapters/jelly_replay.py` (`jelly_team`): no opponent; the saved horizon and arenas rebuild
  `JellyEnvironment`, and a changed `scenario_version` or any other rule rejects the recording. Return is the summed
  team reward; ends are `horizon`, `ship_killed` or `team_dead`. Draws the default world drawing plus each Jelly's route (blue) and the waypoint it steers for (yellow).
