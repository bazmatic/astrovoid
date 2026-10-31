"""A task without custom declarations still has useful shared training charts."""
from learning import dashboard
from learning.tasks import TASKS, Task


def test_a_task_without_a_dashboard_module_gets_only_shared_metrics(monkeypatch):
    monkeypatch.setitem(TASKS, 'plain', Task('plain', 'learning.adapters.hunter', 'Plain'))
    charts = dashboard.charted('plain', ['mean_return', 'kl', 'entropy'])
    assert [chart['key'] for chart in charts] == ['mean_return', 'kl', 'entropy']
    assert dashboard.rewards('plain', {}, {})['rules'] == []
