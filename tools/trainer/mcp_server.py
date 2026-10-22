"""MCP tools for agents to manage hunter training: python -m tools.trainer.mcp_server (stdio, see .mcp.json).

The same engine as ./run-trainer.sh and the training manager page, so all three always agree."""
import functools

from mcp.server.mcpserver import MCPServer

from tools.trainer import control, runs
from tools.trainer.control import TrainerError
from tools.trainer.server import run_json

server = MCPServer('astrovoid-trainer', instructions=(
    'Manage hunter PPO training runs (in .astrovoid-local/neural/rl). Use these tools rather than launching '
    'tools.ppo_neural by hand. One run trains at a time.'))


def _errors_as_data(tool):
    """A TrainerError comes back as {'error': message}, which an agent reads, rather than as a failed call."""
    @functools.wraps(tool)
    def wrapped(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except TrainerError as e:
            return {'error': str(e)}
    return wrapped


@server.tool()
@_errors_as_data
def training_status() -> dict:
    """What training is doing now: state (training, pausing, paused, interrupted or idle), the run, its iteration
    and total, seconds per iteration, and the latest iteration's numbers (score, kills per minute, deaths, ...)."""
    return runs.status()


@server.tool()
@_errors_as_data
def list_runs() -> list:
    """Every run, oldest first: name, state, iterations done, total, what it carried on from, its checkpoints."""
    return [run_json(run) for run in runs.list_runs()]


@server.tool()
@_errors_as_data
def start_run(from_run: str | None = None,
              changes: dict[str, str | int | float | bool | list[int]] | None = None) -> dict:
    """Start a new run. It carries on from `from_run` ('run51' for its last checkpoint, or 'run51/iter0200'),
    by default the newest run's last checkpoint, with that run's settings and `changes` applied
    ({'speed_penalty': '2', 'levels': '1-20'}). It refuses while a run is training, paused or interrupted.
    Returns the new run and the settings it changed."""
    started = control.start(from_=from_run, changes=changes)
    return {'run': started.run, 'started_from': started.started_from,
            'changes': [{'setting': d, 'old': o, 'new': n} for d, o, n in started.changes]}


@server.tool()
@_errors_as_data
def stop_run() -> dict:
    """End the training run now (or a paused or interrupted one). It is finished; its checkpoints are kept."""
    return {'run': control.stop()}


@server.tool()
@_errors_as_data
def pause_run() -> dict:
    """Pause the training run: it finishes its current iteration, saves, and exits (20-40 s). Resume it later
    with resume_run. Runs started before pausing existed can only be stopped."""
    return {'run': control.pause()}


@server.tool()
@_errors_as_data
def resume_run(run: str | None = None) -> dict:
    """Carry on a paused or interrupted run (by default the latest) in its own folder, as if it never stopped."""
    return {'run': control.resume(run=run)}


if __name__ == '__main__':
    server.run('stdio')
