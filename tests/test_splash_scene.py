"""The splash shows one of the game's squids swimming up to hover over the title."""
import pygame
import pytest

import config
from rendering.splash_scene import SplashScene
from states.splash_screen import SplashScreenState

SIZE = (1352, 878)


@pytest.fixture
def screen(monkeypatch):
    pygame.init()
    pygame.display.set_mode((320, 240))
    monkeypatch.setattr(config, 'SCREEN_WIDTH', SIZE[0])
    monkeypatch.setattr(config, 'SCREEN_HEIGHT', SIZE[1])
    surface = pygame.Surface(SIZE, pygame.SRCALPHA)
    surface.fill((*config.COLOR_BACKGROUND, 255))
    return surface


def run(scene, seconds):
    for _ in range(int(seconds * 60)):
        scene.update(1.0)


def squid_pixels(surface):
    return pygame.mask.from_threshold(surface, (*config.REPLAY_ENEMY_COLOR, 255), (1, 1, 1, 255)).count()


class TestSplashScene:
    def test_squid_starts_out_of_sight_below_the_screen(self, screen):
        scene = SplashScene(screen)
        assert scene.squid.y - scene.squid.radius > SIZE[1]
        scene.draw()
        assert squid_pixels(screen) == 0

    def test_squid_swims_up_and_settles_above_the_title(self, screen):
        scene = SplashScene(screen)
        run(scene, 3.0)
        squid = scene.squid
        assert abs(squid.y - scene.hover_y) < squid.radius * 0.5
        assert squid.x == SIZE[0] / 2
        assert squid.y + squid.radius < scene.title_rect().top
        before = squid.y
        run(scene, 1.0)
        assert abs(squid.y - before) < squid.radius * 0.3
        scene.draw()
        assert squid_pixels(screen) > 500

    def test_squid_jets_on_the_way_in(self, screen):
        scene = SplashScene(screen)
        scene.update(1.0)
        assert scene.squid.jet > 0.5

    def test_title_appears_once_the_squid_has_arrived(self, screen):
        scene = SplashScene(screen)
        run(scene, 1.0)
        assert scene.title_alpha == 0.0
        run(scene, 2.0)
        assert scene.title_alpha == 1.0
        assert screen.get_rect().contains(scene.title_rect())

    def test_reset_replays_the_entrance(self, screen):
        scene = SplashScene(screen)
        run(scene, 3.0)
        scene.reset()
        assert scene.squid.y - scene.squid.radius > SIZE[1]
        assert scene.title_alpha == 0.0


class TestSplashShip:
    def test_ship_is_its_in_game_size_and_starts_out_of_sight(self, screen):
        scene = SplashScene(screen)
        assert scene.ship.radius == config.SHIP_SIZE
        assert scene.ship.y - scene.ship.radius > SIZE[1]

    def test_ship_leads_the_squid_up_the_screen(self, screen):
        scene = SplashScene(screen)
        run(scene, 1.0)
        assert screen.get_rect().collidepoint(scene.ship.x, scene.ship.y)
        assert scene.ship.y < scene.squid.y - scene.squid.radius
        assert len(scene.ship.trail) == scene.ship.TRAIL_LENGTH
        # Nose first: it faces the way it is travelling
        assert scene.ship.vy < 0
        assert -180 < scene.ship.angle < 0

    def test_ship_keeps_clear_of_the_squid(self, screen):
        scene = SplashScene(screen)
        closest = min(
            (scene.update(1.0), ((scene.ship.x - scene.squid.x) ** 2 + (scene.ship.y - scene.squid.y) ** 2) ** 0.5)[1]
            for _ in range(int(scene.SHIP_FLIGHT_TIME * 60) - 1)
        )
        assert closest > scene.squid.radius

    def test_squid_leans_to_watch_the_ship_then_straightens(self, screen):
        scene = SplashScene(screen)
        run(scene, 0.8)
        assert scene.ship.x < scene.squid.x
        assert scene.squid.angle < -100
        run(scene, 1.8)
        assert scene.ship.x > scene.squid.x
        assert scene.squid.angle > -80
        run(scene, 1.6)
        assert not scene.ship_flying
        assert abs(scene.squid.angle + 90) <= scene.SQUID_SWAY + 1

    def test_ship_has_left_the_screen_wake_and_all_when_it_stops_being_drawn(self, screen):
        scene = SplashScene(screen)
        run(scene, scene.SHIP_FLIGHT_TIME + 0.1)
        assert not scene.ship_flying
        assert all(x > SIZE[0] for x, _ in scene.ship.trail)


class TestSplashScreenState:
    def test_fades_in_plays_and_hands_over_to_the_menu(self, screen, monkeypatch):
        monkeypatch.setattr(config, 'SPLASH_VIDEO_ENABLED', False)
        splash = SplashScreenState(None, screen)
        splash.enter()
        splash.update(1.0)
        splash.draw(screen)
        assert squid_pixels(screen) == 0
        frames = 1
        while not splash.should_transition and frames < 1200:
            splash.update(1.0)
            frames += 1
        assert splash.should_transition
        # The display duration includes the fade-in; the fade-out follows it
        expected = config.SPLASH_DISPLAY_DURATION - config.SPLASH_FADE_IN_DURATION + config.SPLASH_FADE_OUT_DURATION
        assert frames / 60.0 == pytest.approx(expected, abs=0.1)

    def test_a_key_press_skips_to_the_fade_out(self, screen, monkeypatch):
        monkeypatch.setattr(config, 'SPLASH_VIDEO_ENABLED', False)
        splash = SplashScreenState(None, screen)
        splash.enter()
        for _ in range(int(config.SPLASH_FADE_IN_DURATION * 60) + 2):
            splash.update(1.0)
        splash.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        assert splash.fade_out_started
        splash.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert splash.should_transition
