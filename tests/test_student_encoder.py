import json
import math
import numpy as np
import pytest
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from hunter.model import NEUTRAL
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from hunter.student.encoder import FEATURE_NAMES, encode
from tests.test_hunter_perception import maze


def real_state(heading=10, enemies=()):
    ship = HunterShip((150, 150))
    ship.vx, ship.vy, ship.angle = 3, 1, heading
    obs = HunterPerception().observe(ship, maze(), None, list(enemies), [], NEUTRAL, 0, 1)
    return pilot_state(json.loads(obs.state_json))


def feature(vector, name):
    return float(vector[FEATURE_NAMES.index(name)])


def test_feature_names_are_unique_and_match_vector_length():
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)
    assert encode({}).shape == (len(FEATURE_NAMES),)


def test_empty_state_encodes_to_zeros():
    vector = encode({})
    assert vector.dtype == np.float32
    assert not vector.any()


def test_nothing_in_sight_is_finite_with_every_block_absent():
    state = {'engage': None, 'collect_powerup': None, 'follow_player': None,
             'wall_follow': None, 'visible_contacts': [], 'remembered_contacts': [],
             'hostile_projectiles': [], 'motion': {'brake': {}}, 'space': {}}
    vector = encode(state)
    assert np.isfinite(vector).all()
    assert feature(vector, 'engage.present') == 0
    assert feature(vector, 'enemies.visible') == 0
    assert feature(vector, 'enemy0.present') == 0


def test_real_pilot_state_encodes_finite_with_enemy_aim():
    state = real_state(enemies=[Enemy((250, 150), 'patrol', 1)])
    vector = encode(state)
    assert vector.shape == (len(FEATURE_NAMES),)
    assert np.isfinite(vector).all()
    assert feature(vector, 'enemies.any_aim') == 1
    assert feature(vector, 'enemy0.has_aim') == 1
    assert feature(vector, 'enemy0.distance') == pytest.approx(100)


def test_extra_enemies_and_projectiles_are_ignored():
    def enemy(i):
        return {'allegiance': 'enemy', 'distance_metres': 50 + i, 'aim': None,
                'degrees_off_nose_at_next_decision': 0.0}
    def shot(i):
        return {'allegiance': 'enemy', 'distance_metres': 10 * (10 - i), 'degrees_off_nose': 5.0}
    few = encode({'visible_contacts': [enemy(i) for i in range(3)],
                  'hostile_projectiles': [shot(i) for i in range(3)]})
    many = encode({'visible_contacts': [enemy(i) for i in range(9)],
                   'hostile_projectiles': [shot(i) for i in range(9)]})
    assert few.shape == many.shape
    # Nine shots sit at 100, 90, ... 20 metres: the nearest slot holds the 20, whatever the order.
    assert feature(many, 'projectile0.distance') == 20
    assert feature(many, 'projectile2.distance') == 40
    assert feature(many, 'projectiles.visible') == 9


def test_angle_features_are_linear_for_thresholds_and_continuous_across_180():
    plus = encode({'follow_player': {'degrees_off_nose_at_next_decision': 179.0}})
    minus = encode({'follow_player': {'degrees_off_nose_at_next_decision': -179.0}})
    assert feature(plus, 'follow.off_nose_next.linear') == pytest.approx(179 / 180)
    assert feature(minus, 'follow.off_nose_next.linear') == pytest.approx(-179 / 180)
    # Opposite on the linear feature, neighbours on cos/sin.
    assert feature(plus, 'follow.off_nose_next.cos') == pytest.approx(
        feature(minus, 'follow.off_nose_next.cos'))
    assert feature(plus, 'follow.off_nose_next.sin') == pytest.approx(
        -feature(minus, 'follow.off_nose_next.sin'))
    assert abs(feature(plus, 'follow.off_nose_next.sin')) == pytest.approx(
        math.sin(math.radians(1)), abs=1e-6)


def test_enums_are_one_hot_and_unknown_values_are_all_zero():
    state = {'motion': {'brake': {'speed_state': 'too_fast', 'thrust_effect': 'slows'}}}
    vector = encode(state)
    assert feature(vector, 'brake.speed_state.too_fast') == 1
    assert feature(vector, 'brake.speed_state.slow') == 0
    assert feature(vector, 'brake.thrust_effect.slows') == 1
    odd = encode({'motion': {'brake': {'speed_state': 'warp'}}})
    assert not any(feature(odd, f'brake.speed_state.{s}') for s in ('slow', 'cruising', 'too_fast'))
