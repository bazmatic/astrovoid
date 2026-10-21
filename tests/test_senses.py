import math
import numpy as np
import pytest
from types import SimpleNamespace
import creatures
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
    enemy = creatures.build('patrol', (700, 500), 1)
    v = sense(ship, world(), [enemy])
    assert value(v, 'enemy0_present') == 1.0
    assert value(v, 'enemy0_sin') == pytest.approx(0.0, abs=1e-6)
    assert value(v, 'enemy0_cos') == pytest.approx(1.0)
    assert 0 < value(v, 'enemy0_dist') < 1
    assert value(v, 'enemies_present') == 1.0


def test_right_of_the_nose_is_a_positive_sine():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    south = creatures.build('patrol', (500, 700), 1)       # y grows downward: south is to the right of an east-facing nose
    assert value(sense(ship, world(), [south]), 'enemy0_sin') > 0.9


def test_enemies_are_listed_nearest_first_and_capped_at_six():
    ship = HunterShip((500, 500))
    enemies = [creatures.build('patrol', (500 + 40 * (i + 1), 500), 1) for i in range(9)]
    v = sense(ship, world(), enemies)
    dists = [value(v, f'enemy{i}_dist') for i in range(6)]
    assert dists == sorted(dists) and all(d > 0 for d in dists)
    assert dists[0] == pytest.approx(value(sense(ship, world(), enemies[:1]), 'enemy0_dist'))


def test_an_enemy_behind_a_wall_is_not_sensed_but_still_counts_as_present():
    ship = HunterShip((500, 500))
    wall = WallSegment((600, 300), (600, 700), 3)
    v = sense(ship, world([wall]), [creatures.build('patrol', (700, 500), 1)])
    assert value(v, 'enemy0_present') == 0.0
    assert value(v, 'enemies_present') == 1.0


def test_dead_enemies_are_neither_sensed_nor_present():
    ship = HunterShip((500, 500))
    enemy = creatures.build('patrol', (700, 500), 1)
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


def test_a_crystal_seen_and_then_lost_from_view_is_remembered_until_collected():
    ship = HunterShip((500, 500))
    senses = Senses(HunterSettings())
    crystal = SimpleNamespace(x=560.0, y=500.0, vx=0.0, vy=0.0, active=True)
    sense(ship, world(), powerups=[crystal], senses=senses, now=1.0)
    gone = sense(ship, world(), powerups=[], senses=senses, now=11.0)     # out of the list: not in view
    assert value(gone, 'powerup0_present') == 0.0
    assert value(gone, 'powerup_memory0_present') == 1.0
    assert value(gone, 'powerup_memory0_dist') > 0 and value(gone, 'powerup_memory0_age') == pytest.approx(10.0 / 90.0)
    crystal.active = False
    assert value(sense(ship, world(), powerups=[], senses=senses, now=12.0), 'powerup_memory0_present') == 0.0


def test_a_crystal_in_sight_is_not_also_in_memory_and_old_memories_expire():
    ship = HunterShip((500, 500))
    senses = Senses(HunterSettings())
    crystal = SimpleNamespace(x=560.0, y=500.0, vx=0.0, vy=0.0, active=True)
    seen = sense(ship, world(), powerups=[crystal], senses=senses, now=1.0)
    assert value(seen, 'powerup0_present') == 1.0 and value(seen, 'powerup_memory0_present') == 0.0
    late = sense(ship, world(), powerups=[], senses=senses, now=1.0 + 91.0)
    assert value(late, 'powerup_memory0_present') == 0.0


def test_the_compass_points_at_the_nearest_crystal_even_behind_a_wall():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    wall = WallSegment((530, 400), (530, 600), 3)
    near = SimpleNamespace(x=560.0, y=500.0, vx=0.0, vy=0.0, active=True)         # behind the wall
    far = SimpleNamespace(x=500.0, y=900.0, vx=0.0, vy=0.0, active=True)
    v = sense(ship, world([wall]), powerups=[far, near])
    assert value(v, 'powerup0_present') == 1.0 and abs(value(v, 'powerup0_cos')) < 1e-6   # sight sees only the one due south
    assert value(v, 'crystal_compass_present') == 1.0
    assert value(v, 'crystal_compass_cos') == pytest.approx(1.0, abs=1e-4)        # straight ahead, to the near one
    assert 0.0 < value(v, 'crystal_compass_dist') < 1.0


def test_the_compass_is_empty_when_no_crystal_is_left():
    ship = HunterShip((500, 500))
    gone = SimpleNamespace(x=560.0, y=500.0, vx=0.0, vy=0.0, active=False)
    assert value(sense(ship, world(), powerups=[gone]), 'crystal_compass_present') == 0.0
    assert value(sense(ship, world()), 'crystal_compass_present') == 0.0


def test_the_enemy_compass_points_along_the_corridors_to_an_enemy_behind_a_wall():
    ship = HunterShip((550, 450))
    ship.angle = 0.0
    wall = WallSegment((600, 0), (600, 800), 3)                  # open only below y=800
    enemy = creatures.build('patrol', (650, 450), 1)              # just the other side, due east
    v = sense(ship, world([wall]), enemies=[enemy])
    assert value(v, 'enemy0_present') == 0.0                     # not seen
    assert value(v, 'enemy_compass_present') == 1.0
    assert value(v, 'enemy_compass_sin') == pytest.approx(1.0, abs=1e-3)   # round the end of the wall: due south
    assert value(v, 'enemy_compass_dist') > 100 / 1000          # the route, longer than the straight line


def test_the_enemy_compass_points_straight_at_an_enemy_in_sight():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = creatures.build('patrol', (700, 500), 1)
    v = sense(ship, world(), enemies=[enemy])
    assert value(v, 'enemy_compass_present') == 1.0
    assert value(v, 'enemy_compass_cos') == pytest.approx(1.0, abs=1e-4)
    assert value(v, 'enemy_compass_dist') == pytest.approx(200 / 1000, abs=1e-3)


def test_the_enemy_compass_picks_the_nearest_enemy_by_route_not_straight_line():
    ship = HunterShip((150, 150))
    ship.angle = 0.0
    wall = WallSegment((250, 0), (250, 900), 3)
    behind = creatures.build('patrol', (350, 150), 1)            # 200 away in a line, but round a long wall
    open_ = creatures.build('patrol', (150, 650), 1)             # 500 away, in the open
    v = sense(ship, world([wall]), enemies=[behind, open_])
    assert value(v, 'enemy_compass_sin') == pytest.approx(1.0, abs=1e-3)   # due south, to the open one
    assert value(v, 'enemy_compass_dist') == pytest.approx(500 / 1000, abs=1e-3)


def test_the_enemy_compass_is_empty_when_no_enemy_is_left():
    ship = HunterShip((500, 500))
    gone = creatures.build('patrol', (700, 500), 1)
    gone.active = False
    assert value(sense(ship, world(), enemies=[gone]), 'enemy_compass_present') == 0.0
    assert value(sense(ship, world()), 'enemy_compass_present') == 0.0


def test_a_hit_is_sensed_once_with_its_force_in_the_hunters_frame():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    ship.register_hit(-4.0, 0.0)                 # shoved backwards by half of top speed
    senses = Senses(HunterSettings())
    v = sense(ship, world(), senses=senses)
    assert value(v, 'hit_present') == 1.0
    assert value(v, 'hit_fwd') == pytest.approx(-4.0 / ship.max_speed) and value(v, 'hit_side') == pytest.approx(0.0, abs=1e-6)
    assert value(sense(ship, world(), senses=senses), 'hit_present') == 0.0        # read once, then cleared


def test_with_several_hits_at_once_only_the_strongest_is_sensed():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    ship.register_hit(1.0, 0.0)
    ship.register_hit(0.0, 3.0)                  # the strongest: a sideways shove
    ship.register_hit(-0.5, 0.5)
    v = sense(ship, world())
    assert value(v, 'hit_fwd') == pytest.approx(0.0, abs=1e-6)
    assert value(v, 'hit_side') == pytest.approx(3.0 / ship.max_speed)


def test_a_hit_is_clipped_to_top_speed_and_follows_the_heading():
    ship = HunterShip((500, 500))
    ship.angle = 90.0                             # facing south
    ship.register_hit(0.0, 50.0)                  # shoved south, far beyond top speed
    v = sense(ship, world())
    assert value(v, 'hit_fwd') == 1.0


def test_a_bullet_collision_registers_a_hit_on_the_hunter():
    from utils.math_utils import apply_circle_collision_physics
    ship = HunterShip((500, 500))
    bullet = SimpleNamespace(x=490.0, y=500.0, vx=6.0, vy=0.0, radius=3, mass=None)
    apply_circle_collision_physics(ship, bullet, 0.3)
    hit = ship.take_hit()
    assert hit is not None and hit[0] > 0 and ship.take_hit() is None


def test_the_energy_sense_falls_as_a_mortal_hunter_is_hurt():
    from dataclasses import replace
    settings = replace(HunterSettings(), indestructible=False, health=10)
    ship = HunterShip((500, 500), settings)
    senses = Senses(settings)
    assert value(sense(ship, world(), senses=senses), 'health') == 1.0
    ship.health = 4
    assert value(sense(ship, world(), senses=senses), 'health') == pytest.approx(0.4)


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
    enemy = creatures.build('patrol', (700, 500), 1)
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
    enemy = creatures.build('patrol', (700, 500), 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    senses.reset()
    v = sense(ship, world([WallSegment((600, 300), (600, 700), 3)]), [enemy], senses=senses, now=1.0)
    assert value(v, 'memory0_present') == 0.0


def test_a_remembered_position_now_in_plain_view_and_empty_is_dropped():
    ship = HunterShip((500, 500))
    ship.angle = 0.0
    enemy = creatures.build('patrol', (700, 500), 1)
    senses = Senses(HunterSettings())
    sense(ship, world(), [enemy], senses=senses, now=0.0)
    enemy.x = 500.0; enemy.y = 800.0                      # it moved away; its old spot is visible and empty
    v = sense(ship, world(), [], senses=senses, now=1.0)
    assert value(v, 'memory0_present') == 0.0


def test_senses_are_cheap():
    import time
    ship = HunterShip((500, 500))
    w = world([WallSegment((100 + 50 * i, 100), (100 + 50 * i, 900), 3) for i in range(16)])
    enemies = [creatures.build('patrol', (300 + 40 * i, 500), 1) for i in range(12)]
    senses = Senses(HunterSettings())
    start = time.perf_counter()
    for k in range(200):
        senses.observe(ship, w, enemies, [], [], None, IDLE, k / 10)
    assert (time.perf_counter() - start) / 200 < 0.004      # generous: the target is 1 ms on a quiet machine


def boxed_world(strong=(), hit_points=4):
    """The hunter's cell (5, 5) walled in on all four sides by single blocks, with faces all round each block."""
    blocks = {(4, 5): hit_points, (6, 5): hit_points, (5, 4): hit_points, (5, 6): hit_points}
    walls = []
    for x, y in blocks:
        l, t, r, b = x * 100, y * 100, x * 100 + 100, y * 100 + 100
        walls += [WallSegment((l, t), (r, t), 3), WallSegment((r, t), (r, b), 3),
                  WallSegment((r, b), (l, b), 3), WallSegment((l, b), (l, t), 3)]
    w = world(walls)
    w.blocks, w.strong_cells = blocks, frozenset(strong)
    return w


def test_a_sealed_in_hunter_is_pointed_at_the_wall_to_shoot_through():
    ship = HunterShip((550, 550))
    ship.angle = 0.0
    enemy = creatures.build('patrol', (850, 550), 1)              # due east, beyond the east block
    v = sense(ship, boxed_world(), enemies=[enemy])
    assert value(v, 'enemy_compass_cos') == pytest.approx(1.0, abs=1e-3)


def test_each_hit_on_that_wall_shortens_the_compass_distance():
    ship = HunterShip((550, 550))
    enemy = creatures.build('patrol', (850, 550), 1)
    full = value(sense(ship, boxed_world(hit_points=3), enemies=[enemy]), 'enemy_compass_dist')   # 900 px: under the cap
    worn = value(sense(ship, boxed_world(hit_points=2), enemies=[enemy]), 'enemy_compass_dist')
    assert worn == pytest.approx(full - 2 * 100 / 1000, abs=1e-3)   # two cells of route per hit point


def test_strong_walls_are_never_shot_through():
    ship = HunterShip((550, 550))
    ship.angle = 0.0
    enemy = creatures.build('patrol', (850, 550), 1)
    v = sense(ship, boxed_world(strong=[(6, 5)]), enemies=[enemy])
    assert value(v, 'enemy_compass_cos') < 0.5                    # out through the north or south block instead


def test_each_enemy_in_sight_shows_how_many_hits_it_has_left():
    ship = HunterShip((500, 500))
    tough = creatures.build('patrol', (600, 500), 1)
    tough.hit_points = 20
    weak = creatures.build('patrol', (500, 700), 1)
    weak.hit_points = 1
    v = sense(ship, world(), enemies=[tough, weak])
    assert value(v, 'enemy0_hits') == pytest.approx(1.0)                          # the nearer, at the cap
    assert value(v, 'enemy1_hits') == pytest.approx(math.log(2) / math.log(21), abs=1e-6)
    assert value(v, 'enemy2_hits') == 0.0                                         # an empty slot
