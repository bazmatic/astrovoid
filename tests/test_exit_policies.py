import pytest

from policies.exit import EXIT_POLICIES, AllCleared, AlwaysOpen, ExitState, OpenAfterTime, TypeCleared
from policies.registry import PolicyError


def state(seconds=0.0, **active):
    return ExitState(seconds, active)


def test_always_open_is_open_with_enemies_about():
    assert AlwaysOpen().is_open(state(0, egg=3))


def test_the_timer_opens_at_its_time():
    policy = OpenAfterTime(60)
    assert not policy.is_open(state(59.9)) and policy.is_open(state(60.0))
    assert policy.describe(state(17.2)) == ['OPENS IN', '0:43']        # rounds the wait up
    assert OpenAfterTime(125).describe(state(0)) == ['OPENS IN', '2:05']


def test_type_cleared_waits_only_for_its_types():
    policy = TypeCleared(('egg',))
    assert not policy.is_open(state(egg=1, static=4)) and policy.is_open(state(static=4, baby=2))
    assert policy.describe(state(egg=3)) == ['KILL EGGS', '3 LEFT']
    assert TypeCleared(('egg', 'baby')).describe(state(egg=1, baby=2)) == ['KILL EGGS, SQUIDLETS', '3 LEFT']


def test_all_cleared_waits_for_every_enemy():
    assert not AllCleared().is_open(state(baby=1)) and AllCleared().is_open(state())
    assert AllCleared().describe(state(egg=2, static=5)) == ['KILL ALL', '7 LEFT']


def test_labels_for_the_editor():
    assert [p.label() for p in (AlwaysOpen(), OpenAfterTime(60), TypeCleared(('egg', 'baby')), AllCleared())] == \
           ['Always open', 'Timer 60s', 'Kill Eggs, Squidlets', 'Kill all']


@pytest.mark.parametrize('data', [{'type': 'always_open'}, {'type': 'timer', 'seconds': 60},
                                  {'type': 'type_cleared', 'enemy_types': ['egg', 'mother_boss']},
                                  {'type': 'all_cleared'}])
def test_a_policy_survives_a_round_trip_through_json(data):
    assert EXIT_POLICIES.parse(data).to_json() == data


@pytest.mark.parametrize('data', [None, [], {}, {'type': 'sometimes'}, {'type': 7},
                                  {'type': 'timer'}, {'type': 'timer', 'seconds': -1},
                                  {'type': 'timer', 'seconds': '60'}, {'type': 'timer', 'seconds': True},
                                  {'type': 'timer', 'seconds': float('inf')},
                                  {'type': 'type_cleared'}, {'type': 'type_cleared', 'enemy_types': []},
                                  {'type': 'type_cleared', 'enemy_types': ['dragon']},
                                  {'type': 'type_cleared', 'enemy_types': 'egg'}])
def test_bad_entries_are_refused(data):
    with pytest.raises(PolicyError):
        EXIT_POLICIES.parse(data)


def test_the_registry_lists_and_starts_every_policy():
    assert EXIT_POLICIES.names() == ('always_open', 'timer', 'type_cleared', 'all_cleared')
    assert EXIT_POLICIES.starter('timer') == OpenAfterTime(60)
    assert EXIT_POLICIES.starter('type_cleared') == TypeCleared(('egg',))


def test_registering_a_name_twice_is_refused():
    with pytest.raises(ValueError):
        EXIT_POLICIES.register(AllCleared)


def test_a_kind_named_twice_counts_once():
    policy = EXIT_POLICIES.parse({'type': 'type_cleared', 'enemy_types': ['egg', 'egg']})
    assert policy == TypeCleared(('egg',))
    assert policy.describe(state(egg=3)) == ['KILL EGGS', '3 LEFT']
