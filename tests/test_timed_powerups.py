"""Powerups wear off, top up the ammo instead of making it endless, and add up rather than multiply."""
import pygame
import pytest

import config
from entities.hunter_ship import HunterShip
from entities.ship import Ship
from hunter.model import ACTIONS

DURATION_FRAMES = int(config.POWERUP_DURATION_SECONDS * config.FPS)
COAST = ACTIONS['none_coast_hold']


def ship_with(crystals):
    ship = Ship((200.0, 200.0))
    for _ in range(crystals):
        ship.activate_gun_upgrade()
    return ship


def run(ship, frames):
    for _ in range(frames):
        ship.update(1.0)


class TestWearingOff:
    def test_a_powerup_lasts_its_duration_and_no_longer(self):
        ship = ship_with(1)
        run(ship, DURATION_FRAMES - 1)
        assert ship.get_gun_upgrade_level() == 1
        run(ship, 1)
        assert ship.get_gun_upgrade_level() == 0
        assert ship.rotation_speed_multiplier == 1.0

    def test_another_crystal_restarts_the_clock_for_all_of_them(self):
        ship = ship_with(1)
        run(ship, DURATION_FRAMES - 10)
        ship.activate_gun_upgrade()
        run(ship, DURATION_FRAMES - 1)
        assert ship.get_gun_upgrade_level() == 2
        run(ship, 1)
        assert ship.get_gun_upgrade_level() == 0

    def test_time_left_runs_from_full_to_nothing(self):
        ship = ship_with(1)
        assert ship.get_gun_upgrade_time_left() == 1.0
        run(ship, DURATION_FRAMES // 2)
        assert ship.get_gun_upgrade_time_left() == pytest.approx(0.5, abs=0.01)
        run(ship, DURATION_FRAMES)
        assert ship.get_gun_upgrade_time_left() == 0.0

    def test_the_gun_goes_back_to_single_plain_shots(self):
        ship = ship_with(2)
        assert len(ship.fire()) == 3
        run(ship, DURATION_FRAMES)
        shots = ship.fire()
        assert len(shots) == 1 and not shots[0].is_upgraded

    def test_the_hunters_powerups_wear_off_too(self):
        hunter = HunterShip((200.0, 200.0))
        hunter.collect_powerup()
        hunter.collect_powerup()
        for _ in range(DURATION_FRAMES - 1):
            hunter.step(1, COAST)
        assert hunter.get_gun_upgrade_level() == 2
        hunter.step(1, COAST)
        hunter.step(1, COAST)
        assert hunter.get_gun_upgrade_level() == 0


class TestAmmo:
    def test_a_crystal_tops_up_the_ammo(self):
        ship = Ship((200.0, 200.0))
        ship.ammo = 10
        ship.activate_gun_upgrade()
        assert ship.ammo == 10 + config.POWERUP_AMMO_REFILL

    def test_a_top_up_never_overfills(self):
        ship = Ship((200.0, 200.0))
        ship.ammo = config.INITIAL_AMMO - 1
        ship.activate_gun_upgrade()
        assert ship.ammo == config.INITIAL_AMMO

    def test_shots_still_cost_ammo_but_less_of_it(self):
        ship = ship_with(1)
        before = ship.ammo
        ship.fire()
        cost = before - ship.ammo
        assert 0 < cost < config.AMMO_CONSUMPTION_PER_SHOT
        assert cost == config.AMMO_CONSUMPTION_PER_SHOT * config.POWERUP_AMMO_COST_MULTIPLIER

    def test_a_spread_costs_no_more_than_a_single_shot(self):
        single, spread = ship_with(1), ship_with(2)
        before = (single.ammo, spread.ammo)
        single.fire()
        assert len(spread.fire()) == 3
        assert before[0] - single.ammo == before[1] - spread.ammo

    def test_an_upgraded_gun_can_run_dry(self):
        ship = ship_with(3)
        ship.ammo = 0
        assert ship.fire() is None

    def test_the_gauge_counts_ammo_while_upgraded(self):
        pygame.init()
        pygame.display.set_mode((1352, 878))

        def hud(ammo):
            ship = ship_with(1)
            ship.ammo = ammo
            screen = pygame.Surface((1352, 878))
            ship.draw_ui(screen, pygame.font.Font(None, 24))
            return pygame.image.tostring(screen, "RGB")

        assert hud(40) != hud(8)

    def test_the_hud_shows_the_time_running_out(self):
        pygame.init()
        pygame.display.set_mode((1352, 878))

        def hud(frames):
            ship = ship_with(1)
            ship.gun_upgrade_timer -= frames
            screen = pygame.Surface((1352, 878))
            ship.draw_ui(screen, pygame.font.Font(None, 24))
            return pygame.image.tostring(screen, "RGB")

        assert hud(0) != hud(DURATION_FRAMES // 2)
