"""Each task's dashboard declaration against what its runs really log, and against the charts the old page drew."""
import json
from pathlib import Path

import pytest

from learning import dashboard
from learning.adapters import crawler_scenario, jelly_scenario
from learning.tasks import TASKS, Task

FIXTURES = Path(__file__).parent / 'fixtures' / 'dashboard'
# What learning.run merges into every team-task log row besides the adapter's metrics(): its own bookkeeping and the
# stats learning.ppo.update_team returns (team runs log no kl).
TEAM_RUN_KEYS = {'iteration', 'update_s', 'mean_return', 'rollout_s', 'team_size', 'elapsed_s'}
TEAM_STATS = {'policy_loss', 'value_loss', 'entropy', 'imitation_loss'}
CURRICULUM_KEYS = {'battle_stage'}   # learning.run adds it when the adapter runs a curriculum


def fixture_keys(name):
    return set(json.loads((FIXTURES / f'{name}_log_keys.json').read_text())['keys'])


OLD_PAGE = json.loads((FIXTURES / 'old_page_charts.json').read_text())



def declared(task_key):
    return dashboard.declaration(task_key).METRICS


def crawler_rows(stages=(None,)):
    return [dict(seconds=30., hits=3, shots=10, alive=2, team_size=2, practice_stage=stage) for stage in stages]


def jelly_rows(stages=(1,)):
    return [dict(seconds=60., team_size=1 if stage == 1 else 2, catches=2, stuck_seconds=1., time_to_contact=12.,
                 survival_fraction=.5, time_to_ship_kill=None, stage=stage) for stage in stages]


@pytest.mark.parametrize('task_key, plain, rich', [
    ('wallcrawler_team', lambda: crawler_scenario.metrics(crawler_rows()),
     lambda: crawler_scenario.metrics(crawler_rows(('precision', 'tracking', 'pursuit')))),
    ('jelly_team', lambda: jelly_scenario.metrics(jelly_rows()),
     lambda: jelly_scenario.metrics(jelly_rows((1, 2, 3)))),
])
def test_every_declared_wallcrawler_and_jelly_key_is_produced_by_metrics_or_shared_stats(task_key, plain, rich):
    metrics = declared(task_key)
    assert metrics
    always = set(plain()) | TEAM_RUN_KEYS | TEAM_STATS
    sometimes = always | set(rich()) | CURRICULUM_KEYS
    assert [m.key for m in metrics if not m.optional and m.key not in always] == []
    assert [m.key for m in metrics if m.key not in sometimes] == []
    # Optional means conditional: a key the plain row always has must not hide behind optional.
    assert [m.key for m in metrics if m.optional and m.key in always] == []


def test_every_declared_hunter_key_is_in_the_recorded_log_fixture():
    keys = fixture_keys('hunter')
    metrics = declared('hunter')
    assert [m.key for m in metrics if not m.optional and m.key not in keys] == []


@pytest.mark.parametrize('task_key, log', [('hunter', 'hunter'), ('wallcrawler_team', 'crawler')])
def test_other_is_empty_for_recorded_hunter_and_wallcrawler_logs(task_key, log):
    assert dashboard.unclaimed(task_key, fixture_keys(log)) == []


@pytest.mark.parametrize('task_key, log', [('hunter', 'hunter'), ('wallcrawler_team', 'crawler')])
def test_rendered_chart_set_matches_the_old_page_for_each_recorded_log(task_key, log):
    keys = fixture_keys(log)
    legacy = {'free_shots_per_episode': 'unaimed_shots_per_episode'}   # the old page's one rename
    shown = keys | {new for old, new in legacy.items() if old in keys}
    old = [c for c in OLD_PAGE if c['key'] in shown]   # the old page drew a chart iff its key was in the last row
    new = [dict(key=m['key'], title=m['title'], sub=m['sub']) for m in dashboard.charted(task_key, keys)]
    assert new == old


def test_legacy_free_shots_alias_resolves_to_unaimed_shots():
    assert dashboard.unclaimed('hunter', ['free_shots_per_episode']) == []
    assert [m['key'] for m in dashboard.charted('hunter', ['free_shots_per_episode'])] == ['unaimed_shots_per_episode']


def test_a_plain_task_keeps_undeclared_numeric_metrics(monkeypatch):
    monkeypatch.setitem(TASKS, 'plain', Task('plain', 'learning.adapters.hunter', 'Plain'))
    assert dashboard.unclaimed('plain', ['hits', 'shots', 'score', 'episodes']) == ['episodes', 'hits', 'score', 'shots']


def test_a_tasks_hidden_keys_do_not_hide_another_tasks_metrics():
    # Wallcrawler hides raw hit and shot counts; those remain available as new charts for other tasks.
    assert dashboard.unclaimed('wallcrawler_team', ['hits', 'shots']) == []
    assert dashboard.unclaimed('hunter', ['hits', 'shots']) == ['hits', 'shots']
    assert dashboard.unclaimed('jelly_team', ['hits', 'shots']) == ['hits', 'shots']


def test_other_is_empty_for_the_recorded_jelly_log():
    # A new Jelly log key turns up in "Other" on the page; to keep it out, declare it in jelly_dashboard.METRICS
    # (a chart) or add it to jelly_dashboard.HIDDEN. This pins today's fixture only.
    assert dashboard.unclaimed('jelly_team', fixture_keys('jelly')) == []
