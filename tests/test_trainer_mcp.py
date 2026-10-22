import asyncio
import inspect

import pytest

pytest.importorskip('mcp')

from tools.trainer import mcp_server
from tools.trainer.control import Started, TrainerError
from tools.trainer.runs import Run


def listed_tools():
    result = mcp_server.server.list_tools()
    return asyncio.run(result) if inspect.isawaitable(result) else result


def test_the_tools_are_registered_with_descriptions():
    tools = {t.name: t for t in listed_tools()}
    assert set(tools) == {'training_status', 'list_runs', 'start_run', 'stop_run', 'pause_run', 'resume_run'}
    assert 'refuses' in tools['start_run'].description and 'current iteration' in tools['pause_run'].description


def test_start_run_reports_the_new_run_and_its_changes(monkeypatch):
    seen = {}

    def start(from_=None, changes=None):
        seen['args'] = (from_, changes)
        return Started('run53', 'run51/iter0278', [('speed_penalty', 3.0, 2.0)])

    monkeypatch.setattr(mcp_server.control, 'start', start)
    assert mcp_server.start_run('run51', {'speed_penalty': '2'}) == {
        'run': 'run53', 'started_from': 'run51/iter0278',
        'changes': [{'setting': 'speed_penalty', 'old': 3.0, 'new': 2.0}]}
    assert seen['args'] == ('run51', {'speed_penalty': '2'})


def test_errors_come_back_as_data(monkeypatch):
    def pause():
        raise TrainerError('nothing is training')
    monkeypatch.setattr(mcp_server.control, 'pause', pause)
    assert mcp_server.pause_run() == {'error': 'nothing is training'}


def test_status_runs_stop_and_resume(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_server.runs, 'status', lambda: {'state': 'idle', 'run': 'run52'})
    monkeypatch.setattr(mcp_server.runs, 'list_runs', lambda: [
        Run('run52', 52, tmp_path / 'run52', 'stopped', 3, 10, 'run51/iter0001', ['iter0002'])])
    monkeypatch.setattr(mcp_server.control, 'stop', lambda: 'run52')
    monkeypatch.setattr(mcp_server.control, 'resume', lambda run=None: run)
    assert mcp_server.training_status() == {'state': 'idle', 'run': 'run52'}
    assert mcp_server.list_runs()[0] == {'name': 'run52', 'state': 'stopped', 'iterations_done': 3, 'total': 10,
                                         'started_from': 'run51/iter0001', 'checkpoints': ['iter0002']}
    assert mcp_server.stop_run() == {'run': 'run52'} and mcp_server.resume_run('run50') == {'run': 'run50'}
