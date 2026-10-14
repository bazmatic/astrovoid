# tests/test_rules_share.py
from experiments.run import TUNE_LEVELS
from tools import ppo_neural as ppo

RULES_LEVEL = 25


def levels(jobs):
    return [job[0] for job in jobs]


def test_without_a_share_the_levels_cycle_as_before():
    jobs = ppo.make_jobs(0, len(TUNE_LEVELS) * 2, 'w.npz', 6, 1.0)
    assert levels(jobs) == list(TUNE_LEVELS) * 2


def test_a_share_of_the_episodes_fly_the_rules_level_and_the_rest_never_do():
    jobs = ppo.make_jobs(3, 100, 'w.npz', 6, 1.0, rules_share=0.25)
    flown = levels(jobs)
    assert flown.count(RULES_LEVEL) == 25
    others = [level for level in flown if level != RULES_LEVEL]
    assert RULES_LEVEL not in others and set(others) <= set(TUNE_LEVELS)


def test_the_share_is_spread_through_the_batch_not_bunched():
    flown = levels(ppo.make_jobs(0, 40, 'w.npz', 6, 1.0, rules_share=0.25))
    gaps = [i for i, level in enumerate(flown) if level == RULES_LEVEL]
    assert gaps and all(b - a in (3, 4, 5) for a, b in zip(gaps, gaps[1:]))


def test_a_full_share_is_all_rules_level_episodes():
    assert set(levels(ppo.make_jobs(0, 12, 'w.npz', 6, 1.0, rules_share=1.0))) == {RULES_LEVEL}


def test_the_reward_summary_lists_the_bounty_only_when_there_is_one():
    from argparse import Namespace
    base = dict(powerup_reward=0.0, upgrade_bonus=0.0, wall_scale=1.0, hit_scale=1.0, speed_penalty=0.0,
                still_penalty=0.0, still_speed=0.3, turn_change_penalty=0.0, reversal_penalty=0.0,
                death_penalty=0.0, health=0, rules_bounty=50.0)
    rows = {row['name']: row for row in ppo.reward_summary(Namespace(**base))}
    assert rows['Rules hunter destroyed']['sign'] == '+' and rows['Rules hunter destroyed']['value'] == 50.0
    base['rules_bounty'] = 0.0
    assert 'Rules hunter destroyed' not in {row['name'] for row in ppo.reward_summary(Namespace(**base))}
