import math
import random
from types import SimpleNamespace
from unittest.mock import Mock
import pygame
import pytest
import config
import level_config
from entities.enemy import Enemy
from entities.jev_beacon import JevBeacon
from entities.powerup_crystal import PowerupCrystal
from entities.projectile import Projectile
from game_handlers.collision_handler import CollisionHandler
from hunter.spawn import nearest_hunter_spawn
from tests.test_hunter_controller import Worker
from tests.test_hunter_integration import game, summon  # noqa: F401 - game is a fixture
from tests.test_hunter_spawn import open_maze


def beacons(game):
    return [c for c in game.powerup_crystals if isinstance(c, JevBeacon)]


def shoot(handler, pickups, allowed):
    """Kill one enemy with a player shot and return what it dropped."""
    enemy = Enemy((100, 100), 'patrol')
    shot = Projectile((100, 100), 0)
    handler.handle_projectile_enemy_collisions(
        shot, [enemy], [], [], [], [], [], [], [], pickups, jev_beacon_allowed=allowed)
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


def test_a_hunter_level_starts_with_a_beacon_and_no_hunter(game):
    game.start_level()
    assert game.hunter is None
    placed = beacons(game)
    assert len(placed) == 1
    assert placed[0].get_pos() == game.maze.position_calculator.grid_center_to_screen(4, 4)
    assert game.hunter_worker is not None  # The pilot is warmed up ready for the summons


def test_a_level_without_a_hunter_has_no_beacon(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: False)
    game.start_level()
    assert game.hunter is None
    assert not beacons(game)


def test_collecting_the_beacon_summons_the_hunter_beside_it(game):
    game.hunter_worker = Worker()
    game.start_level()
    beacon = beacons(game)[0]
    game.ship.x, game.ship.y = beacon.get_pos()
    game._update_powerup_crystals(1)
    assert not beacon.active
    assert game.hunter is not None and game.hunter.active
    reach = math.hypot(game.maze.cell_size_x, game.maze.cell_size_y)
    assert 0 < math.dist(game.hunter.get_pos(), (game.ship.x, game.ship.y)) <= reach
    assert game.hunter_controller is not None and game.hunter_perception is not None
    # It is not a gun crystal
    assert game.ship.gun_upgrade_level == 0


def test_a_beacon_can_drop_only_while_no_hunter_flies(game):
    game.hunter_worker = Worker()
    game.start_level()
    assert game._jev_beacon_drop_allowed()
    beacon = beacons(game)[0]
    game.ship.x, game.ship.y = beacon.get_pos()
    game._update_powerup_crystals(1)
    assert not game._jev_beacon_drop_allowed()
    game.hunter.active = False
    assert game._jev_beacon_drop_allowed()


def test_a_second_beacon_replaces_a_dead_hunter(game):
    game.hunter_worker = Worker()
    game.start_level()
    game.ship.x, game.ship.y = beacons(game)[0].get_pos()
    game._update_powerup_crystals(1)
    dead = game.hunter
    dead.active = False
    game.powerup_crystals.append(JevBeacon((game.ship.x, game.ship.y)))
    game._update_powerup_crystals(1)
    assert game.hunter is not dead and game.hunter.active


@pytest.mark.parametrize('hunter_entry, level, boss, allowed', [
    (None, 4, False, True),
    (None, 3, False, False),  # Before the hunter's first level
    (None, 6, True, False),  # Boss level
    (False, 6, False, False),  # The level file forbids a hunter
    ({'spawn_cell': [1, 1]}, 2, False, True),  # The level file places one
])
def test_which_levels_allow_a_beacon(monkeypatch, hunter_entry, level, boss, allowed):
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: hunter_entry)
    monkeypatch.setattr(level_config, 'is_boss_level', lambda _: boss)
    monkeypatch.setattr(config, 'HUNTER_FIRST_LEVEL', 4)
    # Drops do not follow the schedule that places beacons
    monkeypatch.setattr(config, 'HUNTER_LEVEL_INTERVAL', 5)
    assert level_config.level_allows_jev_beacon(level) == allowed


def test_no_beacon_drops_on_a_level_that_forbids_the_hunter(game, monkeypatch):
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: False)
    game.start_level()
    assert not game._jev_beacon_drop_allowed()


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
    monkeypatch.setattr(level_config, 'get_level_hunter_config', lambda _: None)
    monkeypatch.setattr(level_config, 'is_boss_level', lambda _: False)
    game.level = 4
    game.start_level()
    beacon = beacons(game)[0]
    start, exit_pos = game.maze.start_pos, (game.maze.exit.x, game.maze.exit.y)
    third = (start[0] + (exit_pos[0] - start[0]) / 3, start[1] + (exit_pos[1] - start[1]) / 3)
    cell = math.hypot(game.maze.cell_size_x, game.maze.cell_size_y)
    assert math.dist(beacon.get_pos(), third) <= cell
    # Well clear of the exit portal, which would hide it
    assert math.dist(beacon.get_pos(), exit_pos) > 3 * cell
