"""The anemone is rooted to the spot and pulls the player's ship toward it."""
import math
from types import SimpleNamespace

import pytest

import config
from entities.anemone import Anemone, pull_acceleration
from entities.ship import Ship

POS = (400.0, 300.0)
PEAK = 0.12
REACH = 140.0
RADII = (14.0, 8.0)  # anemone, ship
CONTACT = sum(RADII)


def pull_at(distance, angle=0.0):
    ship_pos = (POS[0] + math.cos(angle) * distance, POS[1] + math.sin(angle) * distance)
    return pull_acceleration(POS, RADII[0], ship_pos, RADII[1], REACH, PEAK)


def open_maze(walls=()):
    return SimpleNamespace(cell_size_x=40.0, cell_size_y=40.0, walls=list(walls), spatial_grid=None)


def wall(start, end, active=True):
    return SimpleNamespace(start=start, end=end, active=active)


def ship_at(distance, angle=0.0):
    return Ship((POS[0] + math.cos(angle) * distance, POS[1] + math.sin(angle) * distance))


class TestPullMaths:
    def test_no_pull_at_or_beyond_reach(self):
        assert pull_at(REACH) == (0.0, 0.0)
        assert pull_at(REACH + 50) == (0.0, 0.0)

    def test_peak_pull_at_the_surface(self):
        ax, ay = pull_at(CONTACT)
        assert math.hypot(ax, ay) == pytest.approx(PEAK)

    def test_never_stronger_than_the_peak(self):
        ax, ay = pull_at(CONTACT * 0.5)
        assert math.hypot(ax, ay) == pytest.approx(PEAK)

    def test_strength_falls_off_linearly(self):
        halfway = (CONTACT + REACH) / 2
        assert math.hypot(*pull_at(halfway)) == pytest.approx(PEAK / 2)

    @pytest.mark.parametrize('angle', [0.0, 1.0, math.pi, 4.2])
    def test_always_points_at_the_anemone(self, angle):
        ax, ay = pull_at(80.0, angle)
        # The ship sits out along `angle`, so the pull points back the other way
        strength = math.hypot(ax, ay)
        assert (ax / strength, ay / strength) == pytest.approx((-math.cos(angle), -math.sin(angle)))

    def test_no_pull_at_the_exact_centre(self):
        assert pull_acceleration(POS, RADII[0], POS, RADII[1], REACH, PEAK) == (0.0, 0.0)

    def test_no_pull_when_reach_is_inside_the_body(self):
        assert pull_acceleration(POS, 14.0, (POS[0] + 15, POS[1]), 8.0, 20.0, PEAK) == (0.0, 0.0)


class TestPullConditions:
    def test_reach_is_a_number_of_maze_cells(self):
        maze = SimpleNamespace(cell_size_x=50.0, cell_size_y=30.0, walls=[], spatial_grid=None)
        assert Anemone(POS).reach(maze) == pytest.approx(config.ANEMONE_REACH_CELLS * 40.0)

    def test_pulls_a_ship_in_clear_view(self):
        ax, ay = Anemone(POS).pull_on(ship_at(80.0), open_maze())
        assert ax < 0 and ay == pytest.approx(0.0)

    def test_peak_is_a_fraction_of_ship_thrust(self):
        anemone = Anemone(POS)
        ship = ship_at(anemone.radius + config.SHIP_SIZE)
        ax, ay = anemone.pull_on(ship, open_maze())
        assert math.hypot(ax, ay) == pytest.approx(
            config.ANEMONE_PULL_THRUST_FRACTION * config.SHIP_THRUST_FORCE)
        assert math.hypot(ax, ay) < config.SHIP_THRUST_FORCE

    def test_wall_between_blocks_the_pull(self):
        maze = open_maze([wall((440.0, 200.0), (440.0, 400.0))])
        assert Anemone(POS).pull_on(ship_at(80.0), maze) == (0.0, 0.0)

    def test_destroyed_wall_does_not_block(self):
        maze = open_maze([wall((440.0, 200.0), (440.0, 400.0), active=False)])
        assert Anemone(POS).pull_on(ship_at(80.0), maze) != (0.0, 0.0)

    def test_stunned_anemone_does_not_pull(self):
        anemone = Anemone(POS)
        anemone.stun(10)
        assert anemone.pull_on(ship_at(80.0), open_maze()) == (0.0, 0.0)

    def test_shield_blocks_the_pull(self):
        ship = ship_at(80.0)
        ship.activate_shield()
        assert Anemone(POS).pull_on(ship, open_maze()) == (0.0, 0.0)

    def test_dead_anemone_does_not_pull(self):
        anemone = Anemone(POS)
        anemone.die()
        assert anemone.pull_on(ship_at(80.0), open_maze()) == (0.0, 0.0)

    def test_inactive_ship_is_not_pulled(self):
        ship = ship_at(80.0)
        ship.active = False
        assert Anemone(POS).pull_on(ship, open_maze()) == (0.0, 0.0)


class TestPullingTheShip:
    def test_pull_changes_the_ships_velocity_toward_the_anemone(self):
        anemone, ship = Anemone(POS), ship_at(80.0)
        ship.deactivate_shield()
        anemone.pull_ship(ship, open_maze())
        assert ship.vx < 0
        assert 0.0 < anemone.pull_fraction <= 1.0
        assert math.cos(anemone.pull_angle) == pytest.approx(1.0)  # The ship is to its right

    def test_pull_cannot_push_the_ship_past_its_speed_cap(self):
        anemone, ship = Anemone(POS), ship_at(80.0)
        ship.deactivate_shield()
        ship.vx = -ship.max_speed
        anemone.pull_ship(ship, open_maze())
        assert math.hypot(ship.vx, ship.vy) == pytest.approx(ship.max_speed)

    def test_no_pull_resets_the_reading_used_for_drawing(self):
        anemone, ship = Anemone(POS), ship_at(80.0)
        ship.deactivate_shield()
        anemone.pull_ship(ship, open_maze())
        anemone.stun(10)
        anemone.pull_ship(ship, open_maze())
        assert anemone.pull_fraction == 0.0

    def test_burning_straight_out_from_the_surface_escapes(self):
        anemone = Anemone(POS)
        ship = ship_at(anemone.radius + config.SHIP_SIZE + 1)
        ship.deactivate_shield()
        ship.angle = 0.0  # Nose pointing directly away
        start = ship.x
        for _ in range(120):
            ship.apply_thrust()
            anemone.pull_ship(ship, open_maze())
            ship.x += ship.vx
            ship.y += ship.vy
        assert ship.x - start > anemone.reach(open_maze()) * 0.5

    def test_coasting_past_bends_the_path_inward(self):
        anemone = Anemone(POS)
        ship = Ship((POS[0] - 120.0, POS[1] - 70.0))
        ship.deactivate_shield()
        ship.vx, ship.vy = 3.0, 0.0
        for _ in range(60):
            anemone.pull_ship(ship, open_maze())
            ship.x += ship.vx
            ship.y += ship.vy
        assert ship.vy > 0.2  # Drawn down toward the anemone below its path


class TestStunAndDamage:
    def test_starts_with_full_hit_points_and_unstunned(self):
        anemone = Anemone(POS)
        assert anemone.hit_points == anemone.max_hit_points == config.ANEMONE_HIT_POINTS == 4
        assert not anemone.is_stunned

    def test_dies_on_the_fourth_hit(self):
        anemone = Anemone(POS)
        assert [anemone.take_damage() for _ in range(4)] == [False, False, False, True]

    def test_stun_wears_off(self):
        anemone = Anemone(POS)
        anemone.stun(30)
        for _ in range(29):
            anemone.update(1.0)
        assert anemone.is_stunned
        anemone.update(1.0)
        assert not anemone.is_stunned

    def test_shorter_stun_does_not_cut_a_longer_one(self):
        anemone = Anemone(POS)
        anemone.stun(90)
        anemone.stun(20)
        assert anemone.stun_timer == 90

    def test_it_never_moves(self):
        anemone = Anemone(POS)
        anemone.apply_momentum(5.0, 5.0)
        anemone.vx = anemone.vy = 3.0
        anemone.x += 9
        anemone.update(1.0)
        assert anemone.get_pos() == POS
        assert (anemone.vx, anemone.vy) == (0.0, 0.0)
        assert anemone.check_wall_collision([]) is False
