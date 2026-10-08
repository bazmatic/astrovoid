"""The hunter flies to powerup crystals, collects them, and its guns are upgraded by them."""
import json

import pytest

import config
from entities.hunter_ship import HunterShip
from entities.enemy import Enemy
from entities.jev_beacon import JevBeacon
from entities.powerup_crystal import PowerupCrystal
from entities.ship import Ship
from game_handlers.fire_rate_calculator import calculate_fire_cooldown
from hunter.jev_pilot import PILOT_QUESTIONS, navigation_course, worked_burn
from hunter.model import ACTIONS, NEUTRAL, FiringSolution
from hunter.perception import HunterPerception
from hunter.pilot_sensors import pilot_state
from maze.wall_segment import WallSegment
from tests.test_hunter_burn_choice import decide, ship_at
from tests.test_hunter_controller import Worker
from tests.test_hunter_integration import game, summon  # noqa: F401 - pytest fixture
from tests.test_hunter_perception import maze

LINED_UP = FiringSolution(0.0, True)
FIRE = ACTIONS['none_coast_fire']


def observe(ship, powerups, enemies=(), player=None, walls=()):
    world = maze()
    world.walls = [WallSegment(a, b, 3) for a, b in walls]
    return HunterPerception().observe(ship, world, player, list(enemies), [], NEUTRAL, 0, 1,
                                      powerups=powerups)


def raw(ship, powerups, **kwargs):
    return json.loads(observe(ship, powerups, **kwargs).state_json)


def reading(ship, powerups, **kwargs):
    return pilot_state(raw(ship, powerups, **kwargs))


def upgraded(level):
    ship = HunterShip((200, 200))
    for _ in range(level):
        ship.collect_powerup()
    return ship


# --- seeing powerups ---

def test_a_powerup_in_sight_is_sensed_nearest_first():
    ship = ship_at((500, 500))
    seen = raw(ship, [PowerupCrystal((800, 500)), PowerupCrystal((500, 600))])['visible_powerups']
    assert [p['position'] for p in seen] == [[500, 600], [800, 500]]
    assert seen[0]['distance'] == 100
    assert seen[0]['bearing'] == 90


def test_a_powerup_behind_a_wall_out_of_range_or_collected_is_not_sensed():
    ship = ship_at((500, 500))
    hidden = raw(ship, [PowerupCrystal((700, 500))], walls=[((600, 0), (600, 1000))])
    assert hidden['visible_powerups'] == []
    assert raw(ship, [PowerupCrystal((990, 500))])['visible_powerups'] == []
    collected = PowerupCrystal((600, 500))
    collected.die()
    assert raw(ship, [collected])['visible_powerups'] == []


def test_no_powerups_given_means_none_sensed():
    ship = ship_at((500, 500))
    state = json.loads(HunterPerception().observe(ship, maze(), None, [], [], NEUTRAL, 0, 1).state_json)
    assert state['visible_powerups'] == []
    assert pilot_state(state)['collect_powerup'] is None


# --- the goal the pilot is given ---

def test_collect_powerup_points_at_the_nearest_powerup_with_a_course_onto_it():
    ship = ship_at((500, 500), heading=0.0)
    goal = reading(ship, [PowerupCrystal((500, 700)), PowerupCrystal((800, 500))])['collect_powerup']
    assert goal['distance_metres'] == 200
    assert goal['heading_degrees'] == 90
    assert goal['direction'] == 'right'
    assert goal['degrees_off_nose'] == 90
    assert goal['course']['burn_needed']
    assert goal['course']['burn_heading_degrees'] == pytest.approx(90, abs=1)


def test_collecting_outranks_following_the_player():
    ship = ship_at((500, 500), heading=0.0)
    player = Ship((100, 500))
    state = reading(ship, [PowerupCrystal((500, 700))], player=player)
    assert state['follow_player']['course'] is not None
    assert navigation_course(state) == state['collect_powerup']['course']
    without = reading(ship, [], player=player)
    assert navigation_course(without) == without['follow_player']['course']


def test_braking_and_fighting_still_come_before_collecting():
    fast = ship_at((500, 500), heading=0.0, velocity=(8.0, 0.0))
    state = reading(fast, [PowerupCrystal((500, 600))], walls=[((620, 0), (620, 1000))])
    assert state['motion']['brake']['speed_state'] == 'too_fast'
    assert navigation_course(state)['burn_heading_degrees'] == state['motion']['brake']['burn_heading_degrees']
    still = ship_at((500, 500), heading=0.0)
    fighting = reading(still, [PowerupCrystal((500, 600))], enemies=[Enemy((800, 500), 'static')])
    assert fighting['engage'] is not None
    assert worked_burn(fighting) == fighting['engage']


def test_a_course_decision_flies_the_course_onto_the_powerup():
    ship = ship_at((500, 500), heading=0.0)
    observation = observe(ship, [PowerupCrystal((500, 700))], player=Ship((100, 500)))
    action = decide(observation, 'course', 'burn')
    assert action.burn_heading == pytest.approx(90, abs=1)
    assert action.burn_frames > 0


def test_the_pilot_is_told_that_collecting_a_powerup_is_a_goal():
    for name in ('turn', 'thrust'):
        question = PILOT_QUESTIONS[name]
        assert '`collect_powerup` is your job' in question['instructions']
        assert 'collect_powerup.course' in question['instructions']
    assert 'collect_powerup.course' in PILOT_QUESTIONS['turn']['criteria']['course']
    assert 'collect_powerup.course' in PILOT_QUESTIONS['thrust']['criteria']['burn']


# --- what a powerup does for the hunter ---

def burst_starts(ship, frames=120):
    """Frames on which the held trigger starts a new burst."""
    starts = []
    for frame in range(frames):
        fresh = not ship.burst_remaining
        if ship.step(1, FIRE, LINED_UP) and fresh:
            starts.append(frame)
    return starts


def test_a_new_hunter_has_no_upgrade_and_fires_single_shots():
    ship = HunterShip((200, 200))
    assert ship.get_gun_upgrade_level() == 0
    shots = ship.step(1, FIRE, LINED_UP)
    assert len(shots) == 1
    assert not shots[0].is_upgraded


def test_the_first_powerup_shortens_the_wait_between_bursts():
    def wait(ship):
        starts = burst_starts(ship)
        return starts[1] - starts[0]
    plain, quick = HunterShip((200, 200)), upgraded(1)
    assert wait(quick) < wait(plain)
    ratio = calculate_fire_cooldown(quick) / calculate_fire_cooldown(plain)
    assert quick.fire_interval == pytest.approx(plain.settings.fire_interval * ratio)
    shots = upgraded(1).step(1, FIRE, LINED_UP)
    assert len(shots) == 1 and shots[0].is_upgraded


def test_the_second_powerup_fires_a_three_way_spread():
    ship = upgraded(2)
    ship.angle = 30.0
    shots = ship.step(1, FIRE, LINED_UP)
    spread = config.UPGRADED_PROJECTILE_SPREAD_ANGLE
    assert sorted(shot.angle for shot in shots) == [30.0 - spread, 30.0, 30.0 + spread]
    assert all(shot.source == 'hunter' and shot.is_upgraded for shot in shots)


def test_powerups_beyond_the_third_make_bigger_faster_shots():
    third, fifth = upgraded(3).step(1, FIRE, LINED_UP)[0], upgraded(5).step(1, FIRE, LINED_UP)[0]
    assert fifth.radius > third.radius
    assert (fifth.vx ** 2 + fifth.vy ** 2) > (third.vx ** 2 + third.vy ** 2)


# --- in the game ---

def crystal_on(target):
    return PowerupCrystal((target.x, target.y))


def playing(game):
    game.hunter_worker = Worker()
    game.start_level()
    summon(game)
    # Well clear of the player, so a crystal by the hunter is the hunter's alone.
    game.hunter.x, game.hunter.y = game.maze.position_calculator.grid_center_to_screen(7, 7)
    game.powerup_crystals = []


def test_the_hunter_collects_a_powerup_it_touches(game):
    playing(game)
    crystal = crystal_on(game.hunter)
    game.powerup_crystals = [crystal]
    game._update_powerup_crystals(1)
    assert not crystal.active
    assert game.hunter.get_gun_upgrade_level() == 1
    # It is the hunter's powerup, not the player's.
    assert game.ship.get_gun_upgrade_level() == 0
    assert game.scoring.powerup_crystals_collected == 0


def test_the_player_gets_a_powerup_both_ships_touch(game):
    playing(game)
    game.hunter.x, game.hunter.y = game.ship.x, game.ship.y
    game.powerup_crystals = [crystal_on(game.ship)]
    game._update_powerup_crystals(1)
    assert game.ship.get_gun_upgrade_level() == 1
    assert game.hunter.get_gun_upgrade_level() == 0


def test_the_hunter_leaves_a_jev_beacon_alone(game):
    playing(game)
    beacon = JevBeacon((game.hunter.x, game.hunter.y))
    game.powerup_crystals = [beacon]
    hunter = game.hunter
    game._update_powerup_crystals(1)
    assert beacon.active
    assert game.hunter is hunter
    assert hunter.get_gun_upgrade_level() == 0


def test_the_pilot_is_shown_powerups_but_not_beacons(game):
    playing(game)
    x, y = game.hunter.x, game.hunter.y
    game.powerup_crystals = [PowerupCrystal((x + 60, y)), JevBeacon((x - 60, y))]
    game.player_has_moved = True
    game._update_hunter(1)
    state = json.loads(game.hunter_worker.sent[-1].state_json)
    assert [p['position'] for p in state['visible_powerups']] == [[x + 60, y]]


def test_a_newly_summoned_hunter_starts_without_upgrades(game):
    playing(game)
    game.hunter.collect_powerup()
    game._summon_hunter((game.ship.x, game.ship.y))
    assert game.hunter.get_gun_upgrade_level() == 0


# --- flying there ---

@pytest.mark.parametrize('offset', [(300, 0), (0, 300), (-250, -150), (-300, 40)])
def test_a_pilot_obeying_the_rules_reaches_the_powerup(offset):
    """The real ship on the real readings, decisions landing one round trip late."""
    from tests.test_hunter_wall_follow import rule_following_pilot
    ship, world, perception = ship_at((500, 500), heading=0.0), maze(), HunterPerception()
    crystal = PowerupCrystal((500 + offset[0], 500 + offset[1]))
    player = Ship((500, 440))  # Alongside: with no powerup the hunter would hold station.
    action, pending = NEUTRAL, None
    for frame in range(20 * config.FPS):
        if pending is not None and frame >= pending[0]:
            action, pending = pending[1], None
        if pending is None:
            observation = perception.observe(ship, world, player, [], [], action, frame / config.FPS, 1,
                                             powerups=[crystal])
            state = json.loads(observation.state_json)
            pending = (frame + 27, rule_following_pilot(pilot_state(state), state))
        ship.step(1, action)
        if crystal.check_circle_collision(ship.get_pos(), ship.radius):
            break
    assert not crystal.active, f'still {((ship.x - crystal.x) ** 2 + (ship.y - crystal.y) ** 2) ** .5:.0f} m away'
    assert frame < 12 * config.FPS
