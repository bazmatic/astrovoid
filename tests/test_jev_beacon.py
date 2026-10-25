import math
import random
from types import SimpleNamespace
from unittest.mock import Mock
import pygame
import pytest
import config
import level_config
import level_rules
import creatures
from tests.creature_parts import encounter, world
from entities.jev_beacon import JevBeacon
from entities.powerup_crystal import PowerupCrystal
from entities.projectile import Projectile
from game_handlers.collision_handler import CollisionHandler
from hunter.spawn import nearest_hunter_spawn
from tests.test_hunter_integration import game  # noqa: F401 - pytest fixture
from tests.test_hunter_spawn import open_maze


def beacons(game):
    return [c for c in game.powerup_crystals if isinstance(c, JevBeacon)]


def shoot(handler, pickups, allowed):
    """Kill one enemy with a player shot and return what it dropped."""
    enemy = creatures.build('patrol', (100, 100))
    shot = Projectile((100, 100), 0)
    stand_in = world(collision_handler=handler, powerup_crystals=pickups, jev_beacon_allowed=lambda: allowed)
    encounter(enemy, world_=stand_in).shoot(shot)
    assert not enemy.active
    return pickups


@pytest.fixture
def handler():
    return CollisionHandler(Mock(), Mock(), Mock())


def test_summoned_hunter_takes_the_nearest_safe_cell_clear_of_the_player():
    player = SimpleNamespace(x=250, y=250, radius=config.SHIP_SIZE)
    # The player sits on the pickup point, so the hunter takes a neighbouring cell
    pos = nearest_hunter_spawn((250, 250), open_maze(), player)
    assert math.dist(pos, (250, 250)) == 100
    assert nearest_hunter_spawn((440, 440), open_maze(), player) == (450, 450)
    assert nearest_hunter_spawn((440, 440), open_maze(blocked=[(4, 4)]), player) in ((350, 450), (450, 350))


def test_a_level_without_a_hunter_has_no_beacon(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: False)
    game.start_level()
    assert game.hunter is None
    assert not beacons(game)


@pytest.mark.parametrize('hunter_entry, level, allowed', [
    (None, 4, True),
    (None, 3, False),  # Before the hunter's first level
    (None, 6, True),  # Bosses or not
    (False, 6, False),  # The level file forbids a hunter
    ({'spawn_cell': [1, 1]}, 2, True),  # The level file places one
])
def test_which_levels_allow_a_beacon(monkeypatch, hunter_entry, level, allowed):
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: hunter_entry)
    monkeypatch.setattr(config, 'HUNTER_FIRST_LEVEL', 4)
    # Drops do not follow the schedule that places beacons
    monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 5)
    assert level_config.level_allows_jev_beacon(level) == allowed


def test_no_beacon_drops_on_a_level_that_forbids_the_hunter(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: False)
    game.start_level()
    assert not game.jev_beacon_allowed()


def test_a_kill_drops_a_beacon_in_place_of_a_crystal(handler, monkeypatch):
    monkeypatch.setattr(config, 'JEV_BEACON_SPAWN_CHANCE', 1.0)
    monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 1.0)
    dropped = shoot(handler, [], allowed=True)
    assert [type(p) for p in dropped] == [JevBeacon]
    assert dropped[0].get_pos() == (100, 100)


def test_a_kill_drops_no_beacon_when_not_allowed(handler, monkeypatch):
    monkeypatch.setattr(config, 'JEV_BEACON_SPAWN_CHANCE', 1.0)
    monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 1.0)
    assert [type(p) for p in shoot(handler, [], allowed=False)] == [PowerupCrystal]


def test_only_one_beacon_lies_on_the_field(handler, monkeypatch):
    monkeypatch.setattr(config, 'JEV_BEACON_SPAWN_CHANCE', 1.0)
    monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 1.0)
    dropped = shoot(handler, [JevBeacon((300, 300))], allowed=True)
    assert [type(p) for p in dropped] == [JevBeacon, PowerupCrystal]


def test_beacon_drops_follow_the_configured_chance(handler, monkeypatch):
    assert 0 < config.JEV_BEACON_SPAWN_CHANCE < config.POWERUP_CRYSTAL_SPAWN_CHANCE
    monkeypatch.setattr(config, 'JEV_BEACON_SPAWN_CHANCE', 0.25)
    monkeypatch.setattr(config, 'POWERUP_CRYSTAL_SPAWN_CHANCE', 0.0)
    random.seed(7)
    drops = sum(len(shoot(handler, [], allowed=True)) for _ in range(2000))
    assert 420 < drops < 580


def test_beacon_does_not_look_like_a_gun_crystal():
    pygame.init()
    drawn = []
    for pickup in (JevBeacon((40, 40)), PowerupCrystal((40, 40))):
        pickup.rotation_angle = pickup.pulse_phase = 0.0
        pickup.age = pickup.SPAWN_FRAMES
        surface = pygame.Surface((80, 80))
        pickup.draw(surface)
        drawn.append(pygame.image.tostring(surface, 'RGB'))
    assert drawn[0] != drawn[1]
    assert any(drawn[0])


def test_placed_beacon_lies_a_third_of_the_way_to_the_exit(game, monkeypatch):
    monkeypatch.setattr(level_config, 'level_has_hunter', lambda _: True)
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: None)
    game.level = 4
    game.start_level()
    beacon = beacons(game)[0]
    start, exit_pos = game.maze.start_pos, (game.maze.exit.x, game.maze.exit.y)
    third = (start[0] + (exit_pos[0] - start[0]) / 3, start[1] + (exit_pos[1] - start[1]) / 3)
    cell = math.hypot(game.maze.cell_size_x, game.maze.cell_size_y)
    assert math.dist(beacon.get_pos(), third) <= cell
    # Well clear of the exit portal, which would hide it
    assert math.dist(beacon.get_pos(), exit_pos) > 3 * cell


def test_earned_beacons_have_no_free_pickup_and_unlock_after_most_enemies_die(game, monkeypatch):
    from tests.test_exit_policies_game import level_file
    monkeypatch.setattr(level_config, 'load_level_config',
                        level_file({'hunter': {'earned': True}}, static=10))
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: {'earned': True})
    monkeypatch.setattr(level_config, 'get_level_enemy_counts', lambda _: level_rules.EnemyCounts(
        total=10, static=10, patrol=0, aggressive=0, replay=0, flocker=0, flighthouse=0, egg=0))
    game.level = 10
    game.start_level()
    assert level_config.level_allows_jev_beacon(10)
    assert not level_config.level_has_hunter(10)
    assert not beacons(game)
    assert game.hunter_unlock_kills == 7
    game.collision_handler.level_kills = 6
    assert not game.jev_beacon_allowed()
    game.collision_handler.level_kills = 7
    assert game.jev_beacon_allowed()


def test_the_campaign_has_no_starting_beacons_and_teaches_basics_without_an_ally():
    for level in range(1, 31):
        assert not level_config.level_has_hunter(level)
        layout = level_config.get_level_layout(level)
        assert layout is None or layout.beacon is None
    assert not any(level_config.level_allows_jev_beacon(level) for level in range(1, 10))


def test_earned_beacon_drop_plays_one_arrival_fanfare(handler, monkeypatch):
    monkeypatch.setattr(config, 'JEV_BEACON_SPAWN_CHANCE', 1.0)
    pickups = []
    shoot(handler, pickups, True)
    assert len([p for p in pickups if isinstance(p, JevBeacon)]) == 1
    handler.sound_manager.play_beacon_arrival.assert_called_once()
    shoot(handler, pickups, True)
    handler.sound_manager.play_beacon_arrival.assert_called_once()


def test_beacon_arrival_is_immediate_larger_than_the_pickup_and_fades():
    beacon = JevBeacon((160, 140))
    before = random.getstate()
    surface = pygame.Surface((320, 280), pygame.SRCALPHA)
    beacon.draw(surface)
    assert surface.get_bounding_rect().width > beacon.radius * 5
    first = pygame.image.tostring(surface, 'RGBA')
    surface.fill((0, 0, 0, 0))
    beacon.age = beacon.ARRIVAL_FRAMES
    beacon.draw(surface)
    assert pygame.image.tostring(surface, 'RGBA') != first
    assert random.getstate() == before


def test_fanfare_respects_mute_and_does_not_change_randomness(monkeypatch):
    from sounds import sound_manager as audio
    pygame.mixer.init()
    manager = audio.SoundManager.__new__(audio.SoundManager)
    monkeypatch.setattr(audio, '_audible', lambda: False)
    manager.play_beacon_arrival()
    assert not hasattr(manager, 'beacon_arrival_sound')
    monkeypatch.setattr(audio, '_audible', lambda: True)
    before = random.getstate()
    manager.play_beacon_arrival()
    sound = manager.beacon_arrival_sound
    assert 1.9 < sound.get_length() < 2.0
    manager.play_beacon_arrival()
    assert manager.beacon_arrival_sound is sound
    assert random.getstate() == before


def test_beacon_stays_put_and_cannot_be_collected_until_formed():
    beacon = JevBeacon((300, 300))
    assert not beacon.check_circle_collision((300, 300), 20)
    assert beacon.active and beacon.spawn_scale == 0
    beacon.update(beacon.FORMATION_FRAMES - 1, (301, 300))
    assert beacon.get_pos() == (300, 300)
    assert not beacon.formed
    beacon.update(1, (301, 300))
    assert beacon.formed
    assert beacon.check_circle_collision((300, 300), 20)


def test_arrival_light_paths_start_on_each_boundary_and_share_a_destination():
    from rendering.beacon_arrival import light_paths
    bounds = pygame.Rect(200, 0, 1152, 878)
    target = (830, 450)
    paths = list(light_paths(bounds, target))
    assert len(paths) == 16
    for start, control, finish in paths:
        assert start[0] in (bounds.left, bounds.right-1) or start[1] in (bounds.top, bounds.bottom-1)
        assert finish == target
