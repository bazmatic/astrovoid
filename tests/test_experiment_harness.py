import pytest
from experiments import harness
from experiments.harness import EpisodeResult, run_episode
from hunter.rule_params import RuleParams


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    harness.reset()


def test_an_episode_returns_a_result_for_the_request():
    result = run_episode(13, 0, horizon=3.0)
    assert isinstance(result, EpisodeResult)
    assert (result.level, result.seed) == (13, 0)
    assert result.end in ('cleared', 'horizon')
    assert 0 < result.elapsed <= 3.0 + 1 / 60
    assert result.enemies_at_start > 0
    assert min(result.kills, result.wall_hits, result.hits_taken, result.idle_seconds) >= 0


def test_the_same_episode_twice_is_identical():
    first = run_episode(13, 1, horizon=6.0)
    second = run_episode(13, 1, horizon=6.0)
    assert first == second


def test_an_episode_does_not_depend_on_what_ran_before():
    alone = run_episode(14, 0, horizon=6.0)
    run_episode(13, 1, horizon=6.0)
    run_episode(18, 0, horizon=6.0)
    assert run_episode(14, 0, horizon=6.0) == alone


def test_params_reach_the_pilot(monkeypatch):
    seen = {}
    original = harness.SyncWorker.__init__

    def spy(self, params, clock):
        seen['params'] = params
        original(self, params, clock)
    monkeypatch.setattr(harness.SyncWorker, '__init__', spy)
    run_episode(13, 0, params=RuleParams(pulse_frames=9.0), horizon=1.0)
    assert seen['params'].pulse_frames == 9.0


def test_a_short_horizon_ends_an_episode_at_the_horizon():
    result = run_episode(13, 0, horizon=2.0)
    assert result.end == 'horizon'
    assert result.elapsed == pytest.approx(2.0, abs=0.05)


def test_the_hunter_cannot_die_and_the_episode_runs_on_after_hits(monkeypatch):
    # In the real game the hunter is indestructible; the lab keeps it so and counts the hits.
    result = run_episode(26, 0, horizon=15.0)
    assert result.end in ('cleared', 'horizon')
    assert result.hits_taken > 0
    assert not hasattr(result, 'died')


def test_a_cleared_level_ends_the_episode_as_cleared(monkeypatch):
    from game import Game
    original = Game.update
    state = {'frames': 0}

    def clear_after_ten_frames(self, dt):
        original(self, dt)
        state['frames'] += 1
        if state['frames'] == 10:
            for enemy in list(self.entity_manager.get_all_active_enemies()):
                enemy.active = False
    monkeypatch.setattr(Game, 'update', clear_after_ten_frames)
    result = run_episode(13, 0, horizon=5.0)
    assert result.end == 'cleared'
    assert result.kills == result.enemies_at_start
    assert result.elapsed < 1.0


def test_counting_helpers_count_events_not_frames():
    counter = harness.EventCounter()
    for hit in (False, True, True, True, False, True):
        counter.wall(hit)
    assert counter.wall_hits == 2


def test_kill_counter_ignores_spawns_and_counts_drops():
    counter = harness.EventCounter()
    counter.enemies(10)
    counter.enemies(12)   # two spawned
    counter.enemies(11)   # one died
    counter.enemies(11)
    counter.enemies(8)    # three died at once
    assert counter.kills == 4


def test_idle_time_starts_after_twenty_seconds_without_a_kill():
    counter = harness.EventCounter()
    counter.enemies(5)
    for second in range(40):
        counter.tick(now=float(second))
    assert counter.idle_seconds == pytest.approx(19.0, abs=1.0)
    counter.enemies(4)
    counter.tick(now=40.0)
    before = counter.idle_seconds
    counter.tick(now=45.0)
    assert counter.idle_seconds == before


def test_hits_are_counted_one_per_immunity_window():
    counter = harness.EventCounter()
    for now in (0.0, 0.1, 0.2, 0.4, 0.5, 0.6, 1.05, 1.2):
        counter.hit_taken(now)
    # 0.0 lands; 0.1-0.4 are inside its 0.5 s window; 0.5 lands; 0.6 is inside; 1.05 lands; 1.2 is inside.
    assert counter.hits_taken == 3


def test_a_contact_held_for_many_frames_is_few_hits():
    counter = harness.EventCounter()
    for frame in range(60):
        counter.hit_taken(frame / 60)   # one second of overlap
    assert counter.hits_taken == 2
