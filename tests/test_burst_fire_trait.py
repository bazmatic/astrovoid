"""Burst firing is reusable without a pilot or a hunter body."""
from dataclasses import replace

import pytest

from creatures.traits.burst_fire import BurstFire
from creatures.traits.combat import Gun
from tests.creature_parts import creature, encounter


def gunner(rounds=3, spacing=0.05, interval=0.25, **gun):
    c = creature([BurstFire(rounds, spacing, interval), Gun(cadence='burst', aimMode='nose', **gun)])
    enc = encounter(c)
    c.controls.on_target = c.controls.gun_enabled = True
    return c, enc


def fire_frames(c, enc, frames=30, trigger=lambda n: n == 1, aligned=lambda n: True, dt=1):
    fired = []
    for frame in range(1, frames + 1):
        c.controls.fire, c.controls.on_target = trigger(frame), aligned(frame)
        before = len(enc.world.projectiles)
        enc.step(dt)
        if len(enc.world.projectiles) > before:
            fired.append(frame)
    return fired


def test_a_non_pilot_creature_fires_one_three_round_burst():
    c, enc = gunner()
    assert fire_frames(c, enc) == [1, 4, 7]


def test_held_trigger_reloads_between_bursts():
    c, enc = gunner()
    assert fire_frames(c, enc, trigger=lambda _: True) == [1, 4, 7, 22, 25, 28]


def test_releasing_the_trigger_while_unaligned_cancels_the_rest():
    c, enc = gunner()
    assert fire_frames(c, enc, aligned=lambda n: n == 1) == [1]
    assert c.burst_remaining == 0


def test_a_held_unaligned_trigger_waits_until_its_nose_is_on_target():
    c, enc = gunner()
    assert fire_frames(c, enc, frames=12, trigger=lambda _: True, aligned=lambda n: n >= 5) == [5, 8, 11]


def test_disabling_the_gun_cancels_a_queue():
    c, enc = gunner()
    c.controls.fire = True
    enc.step(1)
    c.controls.gun_enabled = False
    enc.step(1)
    assert c.burst_remaining == 0
    assert len(enc.world.projectiles) == 1


@pytest.mark.parametrize('dt, expected', [(0.5, [1, 7, 13]), (1.0, [1, 4, 7]), (2.0, [1, 3, 5])])
def test_round_spacing_is_in_seconds(dt, expected):
    c, enc = gunner()
    assert fire_frames(c, enc, frames=13, dt=dt) == expected


def test_a_single_round_profile_has_no_extra_queued_shots():
    c, enc = gunner(rounds=1)
    assert fire_frames(c, enc, trigger=lambda _: True) == [1, 16]


def test_sharing_the_trait_does_not_share_a_burst():
    burst = BurstFire()
    a, b = [creature([burst, Gun(cadence='burst', aimMode='nose')]) for _ in range(2)]
    enc = encounter(a, b)
    for c in (a, b):
        c.controls.on_target = True
    a.controls.fire = True
    enc.step(1)
    assert (a.burst_remaining, b.burst_remaining) == (2, 0)
    assert len(enc.world.projectiles) == 1


@pytest.mark.parametrize('params', [{'rounds': 0}, {'rounds': 1.5}, {'spacing': -1}, {'interval': 0}])
def test_invalid_burst_numbers_are_rejected(params):
    with pytest.raises(ValueError, match='burstFire'):
        BurstFire.from_params(params)


def test_burst_guns_require_the_scheduling_trait():
    from dataclasses import replace
    import enemy_kinds
    from creatures.registry import validate
    kind = replace(enemy_kinds.kind('static'), traits=(('gun', {'cadence': 'burst'}),))
    with pytest.raises(ValueError, match='requires.*burstFire'):
        validate({'static': kind})


def test_a_spread_volley_consumes_one_round_and_keeps_its_allegiance():
    c, enc = gunner(upgrades=True)
    c.kind = replace(c.kind, tuning={**c.kind.tuning, 'color': (80, 120, 240)})
    enc.ready()
    c.gun_upgrade_level = 2
    c.upgrade_remaining = 10
    c.angle = 90
    c.controls.fire = True
    enc.step(1)
    assert len(enc.world.projectiles) == 3
    assert c.burst_remaining == 2
    assert all(s.source == 'enemy' and s.is_enemy for s in enc.world.projectiles)
    assert all(s.dynamic_color == tuple(c.kind.tuning['color']) for s in enc.world.projectiles)


@pytest.mark.parametrize('cadence, aim', [('rapid', 'nose'), ('burst', 'automatic')])
def test_unknown_gun_modes_are_rejected(cadence, aim):
    with pytest.raises(ValueError, match='gun'):
        Gun.from_params({'cadence': cadence, 'aimMode': aim})


def test_a_burst_without_a_gun_is_rejected():
    import enemy_kinds
    from creatures.registry import validate
    kind = replace(enemy_kinds.kind('static'), traits=(('burstFire', {}),))
    with pytest.raises(ValueError, match='requires.*gun'):
        validate({'static': kind})


def test_a_target_aimed_gun_can_use_the_same_burst_scheduler():
    c = creature([BurstFire(), Gun(cadence='burst')])
    enc = encounter(c)
    c.controls.aim = (500, 100)
    c.controls.on_target = True
    assert fire_frames(c, enc, frames=12) == [1, 4, 7]
    assert all(s.angle == 0 for s in enc.world.projectiles)


def test_gun_upgrades_expire_and_change_the_wait_between_bursts():
    import config
    c, enc = gunner(rounds=1, upgrades=True)
    enc.ready()
    c.emit('pickup', enc)
    c.upgrade_remaining = 2 / config.FPS
    c.controls.fire = True
    enc.step(1)
    assert c.gun_upgrade_level == 1
    assert enc.world.projectiles[0].is_upgraded
    first_wait = c.fire_remaining
    enc.step(1)
    assert c.gun_upgrade_level == 0
    assert first_wait < c.base_fire_interval
    for _ in range(30):
        enc.step(1)
    assert not enc.world.projectiles[-1].is_upgraded
    assert c.fire_interval == c.base_fire_interval


def test_a_burst_cannot_be_silently_ignored_by_a_reload_gun():
    import enemy_kinds
    from creatures.registry import validate
    kind = replace(enemy_kinds.kind('static'), traits=(('burstFire', {}), ('gun', {})))
    with pytest.raises(ValueError, match='burst.*cadence'):
        validate({'static': kind})
