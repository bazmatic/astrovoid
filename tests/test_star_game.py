"""The game keeps the star tally: kills and crystals by the player and the Jev hunter, par, and the finish."""
import pytest

import config
import level_config
from tests.test_exit_policies_game import game, kill, level_file, start  # noqa: F401  (the game fixture)


def shoot(game, enemy, source='player'):
    from entities.projectile import Projectile
    game.projectiles.append(Projectile((enemy.x, enemy.y), 0.0, source=source))


def reach_exit(game):
    game.player_has_moved = True
    game.ship.x, game.ship.y = game.maze.exit.get_pos()
    game.update(1.0)


def test_player_kills_are_counted(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(patrol=2))
    start(game, 3)
    for enemy in game.enemies:
        shoot(game, enemy)
    game.update(1.0)
    assert game.star_tally().kills == 2
    assert game.star_tally().alive == 0


def test_hunter_kills_and_pickups_count(game, monkeypatch):
    from entities.hunter_ship import HunterShip
    from entities.powerup_crystal import PowerupCrystal
    monkeypatch.setattr(level_config, 'load_level_config', level_file(patrol=1))
    start(game, 3)
    shoot(game, game.enemies[0], source='hunter')
    game.update(1.0)
    assert game.star_tally().kills == 1
    crystal = PowerupCrystal((300.0, 300.0))
    hunter = HunterShip((300.0, 300.0))
    assert game.collision_handler.handle_hunter_crystal_collision(hunter, crystal)
    assert game.collision_handler.level_crystals_collected == 1


def test_the_beacon_is_not_a_crystal(game, monkeypatch):
    from entities.jev_beacon import JevBeacon
    monkeypatch.setattr(level_config, 'load_level_config', level_file())
    start(game, 3)
    game.powerup_crystals.append(JevBeacon((300.0, 300.0)))
    assert game.star_tally().crystals_left == 0


def test_enemies_that_appear_are_counted_but_do_not_extend_par(game, monkeypatch):
    from entities.baby import Baby
    monkeypatch.setattr(level_config, 'load_level_config', level_file(egg=1))
    start(game, 3)
    par, alive = game.base_par_seconds, game.star_tally().alive
    game.babies.extend(Baby((300.0, 300.0), game.command_recorder) for _ in range(2))
    assert game.star_tally().alive == alive + 2
    assert game.base_par_seconds == par


def test_a_dropped_crystal_adds_to_par(game, monkeypatch):
    from entities.powerup_crystal import PowerupCrystal
    monkeypatch.setattr(level_config, 'load_level_config', level_file())
    start(game, 3)
    game.powerup_crystals.append(PowerupCrystal((300.0, 300.0)))
    assert game.star_tally().par_seconds == game.base_par_seconds + 3
    assert game.star_tally().crystals_left == 1


def test_no_route_falls_back_to_the_straight_line(game, monkeypatch):
    walled_in = {'seed': 1, 'maze': {'grid_size': 12},
                 'layout': {'start': [2, 2], 'exit': [8, 8],
                            'walls': [[7, 8], [9, 8], [8, 7], [8, 9]]}}
    monkeypatch.setattr(level_config, 'load_level_config', lambda level: walled_in)
    start(game, 3)
    assert game.base_par_seconds > 0


def test_the_tally_is_frozen_when_the_exit_is_reached(game, monkeypatch):
    from entities.baby import Baby
    monkeypatch.setattr(level_config, 'load_level_config', level_file())
    start(game, 3)
    reach_exit(game)
    assert game.finish_tally is not None
    alive = game.finish_tally.alive
    game.babies.append(Baby((300.0, 300.0), game.command_recorder))
    game.update(1.0)
    assert game.finish_tally.alive == alive


def test_restarting_resets_the_tally(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file(patrol=1))
    start(game, 3)
    shoot(game, game.enemies[0])
    game.update(1.0)
    assert game.star_tally().kills == 1
    start(game, 3)
    assert game.star_tally().kills == 0
    assert game.finish_tally is None


def test_completion_records_the_star_count(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file())
    start(game, 3)
    reach_exit(game)
    for _ in range(200):
        if game.state == config.STATE_LEVEL_COMPLETE:
            break
        game.update(1.0)
    assert game.state == config.STATE_LEVEL_COMPLETE
    assert game.star_animation.num_stars == 5
    assert game.profile_manager.get_active_profile().bests[3].stars == 5
    assert game.star_lines[0] == 'FINISHED'
