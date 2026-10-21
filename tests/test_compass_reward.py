import numpy as np
import pytest
from experiments import rollout
from hunter.senses import FEATURE_NAMES, SENSE_SIZE


class _Counter:
    kills = wall_impulse = hits_taken = spawned = powerups = 0
    idle_seconds = 0.0
    died = False
    rules_beaten = False


def sense(dist=None, seen=False, bearing=0.0):
    s = np.zeros(SENSE_SIZE, np.float32)
    s[FEATURE_NAMES.index('enemies_present')] = 1.0
    if dist is not None:
        s[FEATURE_NAMES.index('enemy_compass_present')] = 1.0
        s[FEATURE_NAMES.index('enemy_compass_dist')] = dist
        s[FEATURE_NAMES.index('enemy_compass_sin')] = np.sin(np.radians(bearing))
        s[FEATURE_NAMES.index('enemy_compass_cos')] = np.cos(np.radians(bearing))
    if seen:
        s[FEATURE_NAMES.index('enemy0_present')] = 1.0
    return s


def rewards(senses, reward=10.0):
    recorder = rollout.RolloutRecorder(6, compass_reward=reward)
    recorder._start_enemies = 1
    for step, s in enumerate(senses):
        recorder.senses.append(s)
        recorder.controls.append((1, 0, 0))
        recorder._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0])
        recorder.counted(_Counter(), step / 10.0)
    return recorder.arrays()[2]


def test_closing_on_the_compass_pays_and_backing_off_costs():
    r = rewards([sense(0.50), sense(0.48), sense(0.49)])
    assert r.tolist() == pytest.approx([0.2, -0.1, 0.0], abs=1e-5)


def test_nothing_is_paid_while_an_enemy_is_in_sight_or_with_no_compass():
    assert not rewards([sense(0.50, seen=True), sense(0.48)]).any()
    assert not rewards([sense(None), sense(0.48), sense(None)]).any()


def test_a_jump_when_the_nearest_enemy_changes_is_not_paid():
    assert not rewards([sense(0.10), sense(0.60)]).any()          # the near one died: the next is far off


def test_no_compass_reward_by_default():
    assert not rewards([sense(0.50), sense(0.48)], reward=0.0).any()


def test_following_counts_blind_steps_with_the_compass_near_the_nose():
    senses = [sense(0.5, bearing=10), sense(0.5, bearing=-40), sense(0.5, bearing=60), sense(0.5, seen=True), sense(None)]
    assert rollout.compass_following(np.asarray(senses)) == (3, 2)


def bored_rewards(cells, seen=(), penalty=6.0, window=10.0):
    """Rewards for an episode with the hunter in `cells` at each decision (0.1 s apart), with only boredom on."""
    recorder = rollout.RolloutRecorder(6, boredom_penalty=penalty, boredom_window=window)
    recorder._start_enemies = 1
    for step, cell in enumerate(cells):
        recorder.senses.append(sense(0.5, seen=step in seen))
        recorder.controls.append((1, 0, 0))
        recorder._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0])
        recorder._cells.append(cell)
        recorder.counted(_Counter(), step / 10.0)
    return recorder.arrays()[2]


def test_staying_in_one_cell_gets_boring_after_a_second():
    r = bored_rewards([(0, 0)] * 15)
    assert not r[:10].any()                                       # passing through takes a moment: no penalty
    assert r[10:].tolist() == pytest.approx([-0.6] * 5)           # 6 points a second, 0.1 s a step


def test_new_cells_are_never_boring_and_a_return_after_the_window_is_new_again():
    assert not bored_rewards([(i, 0) for i in range(30)]).any()
    loop = [(i, 0) for i in range(5)] * 3                         # back to the start every 0.5 s... then 1.5 s later
    back = bored_rewards([(0, 0)] + [(i, 1) for i in range(20)] + [(0, 0)], window=1.5)
    assert bored_rewards(loop)[10:].sum() < 0 and not back.any()


def test_no_boredom_while_an_enemy_is_in_sight_or_by_default():
    assert not bored_rewards([(0, 0)] * 15, seen=set(range(15))).any()
    assert not bored_rewards([(0, 0)] * 15, penalty=0.0).any()


def test_boredom_counts_blind_steps_spent_in_recently_visited_cells():
    recorder = rollout.RolloutRecorder(6, boredom_window=10.0)
    assert recorder.bored_steps(np.asarray([sense(0.5)] * 15), [(0, 0)] * 15) == (15, 5)


def test_a_hit_on_the_compass_wall_pays_but_an_equal_jump_away_does_not():
    def paid(dists):
        recorder = rollout.RolloutRecorder(6, compass_reward=10.0)
        recorder.compass_hit_cap = 0.11                        # one hit point: 0.1 maze widths shorter, with headroom
        recorder._start_enemies = 1
        for step, d in enumerate(dists):
            recorder.senses.append(sense(d))
            recorder.controls.append((1, 0, 0))
            recorder._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0])
            recorder.counted(_Counter(), step / 10.0)
        return recorder.arrays()[2]
    assert paid([0.6, 0.5]).tolist() == pytest.approx([1.0, 0.0], abs=1e-5)
    assert not paid([0.5, 0.6]).any()


def test_shots_fired_with_no_enemy_in_sight_cost_the_shot_price():
    recorder = rollout.RolloutRecorder(6, shot_price=2.0)
    recorder._start_enemies = 1
    for step, (seen, shots) in enumerate([(False, 1), (True, 2), (False, 0), (False, 3)]):
        recorder.senses.append(sense(0.5, seen=seen))
        recorder.controls.append((1, 0, 0))
        recorder._events.append([0, 0, 0, 0.0, 0.0, 0.0, 0, 0.0, 0, 0])
        recorder._shots.append(shots)
        recorder.counted(_Counter(), step / 10.0)
    assert recorder.arrays()[2].tolist() == pytest.approx([-2.0, 0.0, 0.0, -6.0])
