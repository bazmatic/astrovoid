"""Each task's dashboard declaration against what its runs really log, and against the charts the old page drew."""
import json
from pathlib import Path

import pytest

from learning import dashboard
from learning.adapters import crawler_scenario, jelly_scenario
from learning.tasks import TASKS, Capabilities

FIXTURES = Path(__file__).parent / 'fixtures' / 'dashboard'
# What learning.run merges into every team-task log row besides the adapter's metrics(): its own bookkeeping and the
# stats learning.ppo.update_team returns (team runs log no kl).
TEAM_RUN_KEYS = {'iteration', 'update_s', 'mean_return', 'rollout_s', 'team_size', 'elapsed_s'}
TEAM_STATS = {'policy_loss', 'value_loss', 'entropy', 'imitation_loss'}
CURRICULUM_KEYS = {'battle_stage'}   # learning.run adds it when the adapter runs a curriculum


def fixture_keys(name):
    return set(json.loads((FIXTURES / f'{name}_log_keys.json').read_text())['keys'])


OLD_PAGE = json.loads((FIXTURES / 'old_page_charts.json').read_text())
WALLCRAWLER_CHARTS = ['hits_per_minute', 'mean_aim_quality', 'target_clear_rate', 'accuracy', 'precision_accuracy',
                      'tracking_accuracy', 'battle_stage', 'pursuit_survival', 'pursuit_accuracy',
                      'reversals_per_episode', 'jumps_per_episode', 'bullet_hits_taken_per_episode',
                      'contact_hits_taken_per_episode', 'imitation_loss', 'airborne_fraction', 'survival']


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


@pytest.mark.parametrize('task_key, log', [('wallcrawler_team', 'crawler'), ('jelly_team', 'jelly')])
def test_every_declared_team_key_appears_in_a_real_log(task_key, log):
    assert [m.key for m in declared(task_key) if m.key not in fixture_keys(log)] == []


def test_every_declared_hunter_key_is_in_the_recorded_log_fixture():
    keys = fixture_keys('hunter')
    metrics = declared('hunter')
    assert len(metrics) == 13
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
    assert len(new) >= 10


def test_each_old_chart_is_declared_by_exactly_one_place_with_its_text_verbatim():
    owners = {}
    for metric in dashboard.SHARED_METRICS:
        owners.setdefault(metric.key, []).append(('shared', metric))
    for task_key in ('hunter', 'wallcrawler_team'):
        for metric in declared(task_key):
            owners.setdefault(metric.key, []).append((task_key, metric))
    for chart in OLD_PAGE:
        (owner, metric), = owners[chart['key']]
        assert (metric.title, metric.sub) == (chart['title'], chart['sub'])
    assert [m.key for m in declared('wallcrawler_team')] == WALLCRAWLER_CHARTS
    assert sorted(owners) == sorted(c['key'] for c in OLD_PAGE)


def test_jelly_declares_no_wallcrawler_charts_and_no_imitation_loss():
    keys = [m.key for m in declared('jelly_team')]
    assert keys and 'imitation_loss' not in keys
    assert set(keys).isdisjoint(WALLCRAWLER_CHARTS)
    assert set(keys).isdisjoint(m.key for m in declared('hunter'))
    assert {'catches_per_minute', 'catch_probability', 'stuck_fraction', 'time_to_contact', 'team_catches_per_minute',
            'angular_spread', 'bunched_fraction', 'ship_hits', 'jelly_deaths', 'survival_fraction'} == set(keys)
    assert all(m.sub and m.higher_is_better is not None for m in declared('jelly_team'))


def test_jelly_charts_render_in_its_sections_with_policy_drift_last():
    keys = fixture_keys('jelly')
    rendered = [m['key'] for m in dashboard.charted('jelly_team', keys)]
    assert rendered[0] == 'mean_return' and rendered[-1] == 'entropy'
    assert set(rendered) == {m.key for m in declared('jelly_team')} | {'mean_return', 'entropy'}   # Jelly logs no kl


def test_legacy_free_shots_alias_resolves_to_unaimed_shots():
    unaimed, = [m for m in declared('hunter') if m.key == 'unaimed_shots_per_episode']
    assert unaimed.aliases == ('free_shots_per_episode',)
    assert dashboard.unclaimed('hunter', ['free_shots_per_episode']) == []
    assert [m['key'] for m in dashboard.charted('hunter', ['free_shots_per_episode'])] == ['unaimed_shots_per_episode']


def test_task_capabilities():
    assert TASKS['hunter'].capabilities == Capabilities(False, False, 'legacy_check', 'unclaimed')
    assert TASKS['wallcrawler_team'].capabilities == Capabilities(True, True, 'hooks', 'listed')
    assert TASKS['jelly_team'].capabilities == Capabilities(True, False, 'hooks', 'listed')
    assert {key: spec.dashboard for key, spec in TASKS.items()} == {
        'hunter': 'learning.adapters.hunter_dashboard', 'wallcrawler_team': 'learning.adapters.crawler_dashboard',
        'jelly_team': 'learning.adapters.jelly_dashboard'}
