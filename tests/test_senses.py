import math
import numpy as np
import pytest
from types import SimpleNamespace
from entities.enemy import Enemy
from entities.hunter_ship import HunterShip
from hunter.model import HunterSettings
from hunter.senses import (FEATURE_NAMES, SENSE_SIZE, Senses, blocked, ray_distances)
from maze.wall_segment import WallSegment
from tests.test_hunter_perception import maze

IDLE = (1, 0, 0)   # last controls: no turn, coast, no trigger


def world(walls=()):
    w = maze()
    w.walls = list(walls)
    from utils.spatial_grid import SpatialGrid
    w.spatial_grid = SpatialGrid(1000, 1000, 100)
    w.spatial_grid.add_walls(w.walls)
    return w


def sense(hunter, w, enemies=(), bullets=(), powerups=(), player=None, now=0.0, senses=None):
    senses = senses or Senses(HunterSettings())
    return senses.observe(hunter, w, list(enemies), list(bullets), list(powerups), player, IDLE, now)


def value(vector, name):
    return float(vector[FEATURE_NAMES.index(name)])


def bullet(x, y, vx=0.0, vy=0.0, enemy=True):
    return SimpleNamespace(x=x, y=y, vx=vx, vy=vy, active=True, is_enemy=enemy, radius=3)


def test_names_are_unique_and_the_vector_has_that_length():
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES) == SENSE_SIZE
    assert sense(HunterShip((500, 500)), world()).shape == (SENSE_SIZE,)


def test_nothing_around_is_finite_and_zeroed():
    v = sense(HunterShip((500, 500)), world())
    assert v.dtype == np.float32 and np.isfinite(v).all()
    for name in FEATURE_NAMES:
        if name.startswith(('enemy', 'bullet', 'powerup', 'player', 'memory')):
            assert value(v, name) == 0.0, name
    assert value(v, 'enemies_present') == 0.0


def test_no_solved_quantity_is_in_the_layout():
    banned = ('lead', 'burn', 'safe', 'stopping', 'course', 'aim', 'retrograde')
    assert not [n for n in FEATURE_NAMES if any(b in n for b in banned)]


def test_rays_measure_the_distance_to_walls_relative_to_the_nose():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    wall_ahead = WallSegment((600, 400), (600, 600), 3)           # 100 px due east
    v = sense(ship, world([wall_ahead]))
    reach = HunterSettings().sensor_range(world())
    assert value(v, 'ray_0') == pytest.approx(100 / reach, abs=1e-3)
    assert value(v, 'ray_8') == pytest.approx(1.0)                # behind: nothing in range
    ship.angle = 90.0                                             # now facing south, the wall is on the left
    v = sense(ship, world([wall_ahead]))
    assert value(v, 'ray_12') == pytest.approx(100 / reach, abs=1e-3)   # ray 12 = 270 degrees = left of the nose


def test_ray_distances_and_blocked_direct():
    starts = np.array([[600.0, 400.0]]); ends = np.array([[600.0, 600.0]])
    d = ray_distances((500.0, 500.0), 0.0, starts, ends, 800.0)
    assert d[0] == pytest.approx(100.0) and d[8] == pytest.approx(800.0) and len(d) == 16
    assert list(blocked((500.0, 500.0), np.array([[700.0, 500.0], [400.0, 500.0]]), starts, ends)) == [True, False]
    empty = np.zeros((0, 2))
    assert list(ray_distances((0.0, 0.0), 0.0, empty, empty, 50.0)) == [50.0] * 16
    assert list(blocked((0.0, 0.0), np.array([[10.0, 0.0]]), empty, empty)) == [False]


def test_an_enemy_ahead_has_geometry_in_the_hunters_frame():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = Enemy((700, 500), 'patrol', 1)
    v = sense(ship, world(), [enemy])
    assert value(v, 'enemy0_present') == 1.0
    assert value(v, 'enemy0_sin') == pytest.approx(0.0, abs=1e-6)
    assert value(v, 'enemy0_cos') == pytest.approx(1.0)
    assert 0 < value(v, 'enemy0_dist') < 1
    assert value(v, 'enemies_present') == 1.0


def test_right_of_the_nose_is_a_positive_sine():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    south = Enemy((500, 700), 'patrol', 1)       # y grows downward: south is to the right of an east-facing nose
    assert value(sense(ship, world(), [south]), 'enemy0_sin') > 0.9


def test_enemies_are_listed_nearest_first_and_capped_at_six():
    ship = HunterShip((500, 500))
    enemies = [Enemy((500 + 40 * (i + 1), 500), 'patrol', 1) for i in range(9)]
    v = sense(ship, world(), enemies)
    dists = [value(v, f'enemy{i}_dist') for i in range(6)]
    assert dists == sorted(dists) and all(d > 0 for d in dists)
    assert dists[0] == pytest.approx(value(sense(ship, world(), enemies[:1]), 'enemy0_dist'))


def test_an_enemy_behind_a_wall_is_not_sensed_but_still_counts_as_present():
    ship = HunterShip((500, 500))
    wall = WallSegment((600, 300), (600, 700), 3)
    v = sense(ship, world([wall]), [Enemy((700, 500), 'patrol', 1)])
    assert value(v, 'enemy0_present') == 0.0
    assert value(v, 'enemies_present') == 1.0


def test_dead_enemies_are_neither_sensed_nor_present():
    ship = HunterShip((500, 500))
    enemy = Enemy((700, 500), 'patrol', 1)
    enemy.active = False
    v = sense(ship, world(), [enemy])
    assert value(v, 'enemy0_present') == 0.0 and value(v, 'enemies_present') == 0.0


def test_only_enemy_bullets_are_sensed_with_their_relative_velocity():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    incoming = bullet(700, 500, vx=-6.0)                 # coming straight at the nose
    friendly = bullet(600, 500, vx=6.0, enemy=False)
    v = sense(ship, world(), bullets=[incoming, friendly])
    assert value(v, 'bullet0_present') == 1.0 and value(v, 'bullet1_present') == 0.0
    assert value(v, 'bullet0_relfwd') < -0.5            # closing fast along the nose


def test_the_player_appears_only_when_given():
    ship = HunterShip((500, 500))
    player = SimpleNamespace(x=600.0, y=500.0, vx=0.0, vy=0.0, active=True)
    assert value(sense(ship, world(), player=player), 'player_present') == 1.0
    assert value(sense(ship, world()), 'player_present') == 0.0


def test_a_powerup_in_sight_is_sensed():
    ship = HunterShip((500, 500))
    crystal = SimpleNamespace(x=560.0, y=500.0, vx=0.0, vy=0.0, active=True)
    v = sense(ship, world(), powerups=[crystal])
    assert value(v, 'powerup0_present') == 1.0 and value(v, 'powerup0_dist') > 0


def test_own_motion_is_in_the_hunters_frame():
    ship = HunterShip((500, 500))
    ship.angle = 90.0
    ship.vx, ship.vy = 0.0, 4.0                          # moving south while facing south: straight ahead
    v = sense(ship, world())
    assert value(v, 'fwd_speed') > 0.4 and value(v, 'side_speed') == pytest.approx(0.0, abs=1e-6)
    assert value(v, 'heading_sin') == pytest.approx(1.0)


def test_last_controls_are_echoed():
    senses = Senses(HunterSettings())
    v = senses.observe(HunterShip((500, 500)), world(), [], [], [], None, (2, 1, 1), 0.0)
    assert value(v, 'last_turn_right') == 1.0 and value(v, 'last_turn_left') == 0.0
    assert value(v, 'last_thrust') == 1.0 and value(v, 'last_fire') == 1.0


def test_an_enemy_seen_then_hidden_is_remembered_with_its_age_then_forgotten():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = Enemy((700, 500), 'patrol', 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    hidden = world([WallSegment((600, 300), (600, 700), 3)])
    v = sense(ship, hidden, [enemy], senses=senses, now=3.0)
    assert value(v, 'memory0_present') == 1.0
    assert value(v, 'memory0_age') == pytest.approx(3.0 / 10.0, abs=1e-3)
    v = sense(ship, hidden, [enemy], senses=senses, now=11.0)
    assert value(v, 'memory0_present') == 0.0                      # older than ten seconds
    enemy.active = False
    sense(ship, world(), [enemy], senses=senses, now=12.0)
    assert value(sense(ship, hidden, [enemy], senses=senses, now=12.5), 'memory0_present') == 0.0


def test_reset_clears_memory():
    ship = HunterShip((500, 500))
    enemy = Enemy((700, 500), 'patrol', 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    senses.reset()
    v = sense(ship, world([WallSegment((600, 300), (600, 700), 3)]), [enemy], senses=senses, now=1.0)
    assert value(v, 'memory0_present') == 0.0


def test_a_remembered_position_now_in_plain_view_and_empty_is_dropped():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = Enemy((700, 500), 'patrol', 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    enemy.x = 500.0; enemy.y = 800.0                      # it moved away; its old spot is visible and empty
    v = sense(ship, world(), [], senses=senses, now=1.0)
    assert value(v, 'memory0_present') == 0.0


def test_senses_are_cheap():
    import time
    ship = HunterShip((500, 500))
    w = world([WallSegment((100 + 50 * i, 100), (100 + 50 * i, 900), 3) for i in range(16)])
    enemies = [Enemy((300 + 40 * i, 500), 'patrol', 1) for i in range(12)]
    senses = Senses(HunterSettings())
    start = time.perf_counter()
    for k in range(200):
        senses.observe(ship, w, enemies, [], [], None, IDLE, k / 10)
    assert (time.perf_counter() - start) / 200 < 0.004      # generous: the target is 1 ms on a quiet machine
