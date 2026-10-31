import json
import threading
import urllib.request

import pytest

from learning import dashboard
from learning.tasks import TASKS, Capabilities, Task
from tools.trainer import server as server_module

SHARED = [m.key for m in dashboard.SHARED_METRICS]


def test_resolve_shared_metrics_come_first_for_every_task():
    for key in TASKS:
        assert [m['key'] for m in dashboard.resolve(key)['metrics']][:3] == ['mean_return', 'kl', 'entropy']


def test_resolve_is_json_serialisable():
    resolved = dashboard.resolve_all()
    assert json.loads(json.dumps(resolved)) == resolved
    assert resolved[0]['hidden'] == sorted(dashboard.HIDDEN_KEYS)
    assert {'key', 'label', 'capabilities', 'metrics', 'sections', 'strip', 'rewards', 'hidden'} <= set(resolved[0])


def test_unknown_task_raises_value_error_naming_the_task():
    with pytest.raises(ValueError, match='nonesuch'):
        dashboard.resolve('nonesuch')


def test_unclaimed_ignores_hidden_declared_and_aliased_keys(monkeypatch):
    extra = dashboard.Metric('hits', 'Hits', aliases=('hits_old',))
    monkeypatch.setattr(dashboard, 'declaration', lambda key: __import__('types').SimpleNamespace(METRICS=(extra,)))
    keys = ['iteration', 'rollout_s', 'kl', 'hits', 'hits_old', 'zeta', 'alpha']
    assert dashboard.unclaimed('hunter', keys) == ['alpha', 'zeta']


def test_a_task_without_a_dashboard_module_gets_only_shared_metrics():
    assert TASKS['hunter'].dashboard is None
    declared = dashboard.declaration('hunter')
    assert declared.METRICS == () and declared.REWARD_RULES == () and declared.cards({}) == []
    assert declared.LAYOUT == dashboard.Layout()
    resolved = dashboard.resolve('hunter')
    assert [m['key'] for m in resolved['metrics']] == SHARED and resolved['rewards'] == []


def test_capabilities_defaults_and_validation():
    assert Capabilities() == Capabilities(True, False, 'hooks', 'listed')
    assert Task('t', 'm', 'T').capabilities == Capabilities() and Task('t', 'm', 'T').dashboard is None
    Capabilities(replay_mode=None)
    Capabilities(replay_mode='legacy_check', settings_scope='unclaimed')
    with pytest.raises(ValueError):
        Capabilities(replay_mode='bogus')
    with pytest.raises(ValueError):
        Capabilities(settings_scope='bogus')


def test_tasks_endpoint_returns_resolved_layouts(tmp_path):
    httpd = server_module.make_server(0, root=tmp_path, processes=lambda: [], launch=lambda *a: None)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{httpd.server_address[1]}/api/tasks') as response:
            body = json.loads(response.read())
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert body == dashboard.resolve_all()
    assert [t['key'] for t in body] == list(TASKS)
