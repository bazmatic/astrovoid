"""The anemone is rooted to the spot and pulls the player's ship toward it."""
import math
from types import SimpleNamespace

import pytest

import config
import creatures
import enemy_kinds
from creatures.traits.combat import flinch
from entities.anemone import pull_acceleration
from entities.ship import Ship
from tests.creature_parts import encounter, world

POS = (400.0, 300.0)
PEAK = 0.12
REACH = 140.0
RADII = (14.0, 8.0)  # anemone, ship
CONTACT = sum(RADII)


def pull_at(distance, angle=0.0):
    ship_pos = (POS[0] + math.cos(angle) * distance, POS[1] + math.sin(angle) * distance)
    return pull_acceleration(POS, RADII[0], ship_pos, RADII[1], REACH, PEAK)


PULLS = dict(enemy_kinds.kind('anemone').traits)['pullsShip']


def open_maze(walls=(), cell=(40.0, 40.0)):
    return SimpleNamespace(cell_size_x=cell[0], cell_size_y=cell[1], walls=list(walls), spatial_grid=None,
                           is_open=lambda pos, radius: True)


def wall(start, end, active=True):
    return SimpleNamespace(start=start, end=end, active=active)


def ship_at(distance, angle=0.0, shield=False):
    ship = Ship((POS[0] + math.cos(angle) * distance, POS[1] + math.sin(angle) * distance))
    if shield:
        ship.activate_shield()
    else:
        ship.deactivate_shield()
    return ship


def rooted(ship, maze=None):
    """An anemone at POS, set up on a level with this ship (an open maze by default); the Encounter is returned too."""
    anemone = creatures.build('anemone', POS)
    enc = encounter(anemone, world_=world(ship=ship, maze=maze or open_maze()))
    enc.ready()
    return anemone, enc


def pull(ship, maze=None, before=lambda anemone, enc: None):
    """The change in the ship's velocity from one frame beside an anemone."""
    anemone, enc = rooted(ship, maze)
    before(anemone, enc)
    vx, vy = ship.vx, ship.vy
    enc.step(1.0)
    return (ship.vx - vx, ship.vy - vy)


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
        anemone, _ = rooted(ship_at(500.0), open_maze(cell=(50.0, 30.0)))
        assert anemone.reach_px == pytest.approx(PULLS['reachCells'] * 40.0)

    def test_pulls_a_ship_in_clear_view(self):
        ax, ay = pull(ship_at(80.0))
        assert ax < 0 and ay == pytest.approx(0.0)

    def test_peak_is_a_fraction_of_ship_thrust(self):
        ax, ay = pull(ship_at(enemy_kinds.kind('anemone').tuning['size'] + config.SHIP_SIZE))
        assert math.hypot(ax, ay) == pytest.approx(PULLS['strength'] * config.SHIP_THRUST_FORCE)
        assert math.hypot(ax, ay) < config.SHIP_THRUST_FORCE

    def test_wall_between_blocks_the_pull(self):
        assert pull(ship_at(80.0), open_maze([wall((440.0, 200.0), (440.0, 400.0))])) == (0.0, 0.0)

    def test_destroyed_wall_does_not_block(self):
        assert pull(ship_at(80.0), open_maze([wall((440.0, 200.0), (440.0, 400.0), active=False)])) != (0.0, 0.0)

    def test_flinching_anemone_does_not_pull(self):
        assert pull(ship_at(80.0), before=lambda anemone, enc: flinch(anemone, 10, enc)) == (0.0, 0.0)

    def test_shield_blocks_the_pull(self):
        assert pull(ship_at(80.0, shield=True)) == (0.0, 0.0)

    def test_dead_anemone_does_not_pull(self):
        assert pull(ship_at(80.0), before=lambda anemone, enc: anemone.die()) == (0.0, 0.0)

    def test_inactive_ship_is_not_pulled(self):
        ship = ship_at(80.0)
        ship.active = False
        assert pull(ship) == (0.0, 0.0)


class TestPullingTheShip:
    def test_pull_cannot_push_the_ship_past_its_speed_cap(self):
        ship = ship_at(80.0)
        ship.vx = -ship.max_speed
        pull(ship)
        assert math.hypot(ship.vx, ship.vy) == pytest.approx(ship.max_speed)

    def test_no_pull_resets_the_reading_used_for_drawing(self):
        anemone, enc = rooted(ship_at(80.0))
        enc.step(1.0)
        assert anemone.pull_fraction > 0
        flinch(anemone, 10, enc)
        enc.step(1.0)
        assert anemone.pull_fraction == 0.0

    def test_burning_straight_out_from_the_surface_escapes(self):
        ship = ship_at(enemy_kinds.kind('anemone').tuning['size'] + config.SHIP_SIZE + 1)
        anemone, enc = rooted(ship)
        ship.angle = 0.0  # Nose pointing directly away
        start = ship.x
        for _ in range(120):
            ship.apply_thrust()
            enc.step(1.0)
            ship.x += ship.vx
            ship.y += ship.vy
        assert ship.x - start > anemone.reach_px * 0.5

    def test_coasting_past_bends_the_path_inward(self):
        ship = Ship((POS[0] - 120.0, POS[1] - 70.0))
        ship.deactivate_shield()
        ship.vx, ship.vy = 3.0, 0.0
        _, enc = rooted(ship)
        for _ in range(60):
            enc.step(1.0)
            ship.x += ship.vx
            ship.y += ship.vy
        assert ship.vy > 0.2  # Drawn down toward the anemone below its path


class TestFlinchAndDamage:
    def test_starts_with_full_hit_points_and_not_flinching(self):
        anemone, _ = rooted(ship_at(500.0))
        assert anemone.hit_points == anemone.max_hit_points == 4
        assert anemone.flinch_timer == 0.0

    def test_a_flinch_wears_off(self):
        anemone, enc = rooted(ship_at(500.0))
        flinch(anemone, 30, enc)
        for _ in range(29):
            enc.step(1.0)
        assert anemone.flinch_timer > 0
        enc.step(1.0)
        assert anemone.flinch_timer == 0

    def test_shorter_flinch_does_not_cut_a_longer_one(self):
        anemone, enc = rooted(ship_at(500.0))
        flinch(anemone, 90, enc)
        flinch(anemone, 20, enc)
        assert anemone.flinch_timer == 90

    def test_it_never_moves(self):
        anemone, enc = rooted(ship_at(500.0))
        anemone.apply_momentum(5.0, 5.0)
        anemone.vx = anemone.vy = 3.0
        anemone.x += 9
        enc.step(1.0)
        assert anemone.get_pos() == POS
        assert (anemone.vx, anemone.vy) == (0.0, 0.0)
