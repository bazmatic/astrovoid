"""Runs one hunter episode headlessly on the real game, faster than real time."""
import asyncio
import os
import random
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from hunter.jev_pilot import JevPilot
from hunter.model import HunterSettings, PilotResult
from hunter.rule_params import DEFAULT
from hunter.rules_pilot import RulesClient

FPS = 60
IDLE_AFTER_SECONDS = 20.0
DAMAGE_IMMUNITY_SECONDS = HunterSettings().damage_immunity  # one hit per window, as in the game
SCREEN = (1352, 878)


@dataclass(frozen=True)
class EpisodeResult:
    level: int
    seed: int
    enemies_at_start: int
    elapsed: float
    kills: int
    wall_hits: int
    hits_taken: int
    idle_seconds: float
    end: str  # 'cleared' or 'horizon'
    enemies_spawned: int = 0  # enemies that appeared during the episode (spawners, eggs)


class EventCounter:
    """Turns per-frame observations into event counts."""

    def __init__(self):
        self.kills = 0
        self.spawned = 0
        self.wall_hits = 0
        self.hits_taken = 0
        self.idle_seconds = 0.0
        self._alive = None
        self._in_wall = False
        self._last_hit = None
        self._last_kill = 0.0
        self._last_tick = None

    def observe(self, enemies):
        """The enemies alive this frame. One alive before and not now was killed; a new one spawned.

        Tracking the enemies themselves, not their number, keeps a boss that dies and splits into
        two in one frame (net +1) from looking like a spawn and no kill.
        """
        current = list(enemies)
        if self._alive is not None:
            now_ids = {id(enemy) for enemy in current}
            before_ids = {id(enemy) for enemy in self._alive}
            died = sum(1 for enemy in self._alive if id(enemy) not in now_ids)
            born = sum(1 for enemy in current if id(enemy) not in before_ids)
            if died:
                self.kills += died
                self._last_kill = self._last_tick if self._last_tick is not None else 0.0
            self.spawned += born
        # Holding the objects keeps their ids from being reused by new enemies.
        self._alive = current

    def wall(self, hit):
        if hit and not self._in_wall:
            self.wall_hits += 1
        self._in_wall = bool(hit)

    def hit_taken(self, now):
        """A damage call at `now`: it counts once per immunity window, so a held contact is few hits."""
        if self._last_hit is None or now - self._last_hit >= DAMAGE_IMMUNITY_SECONDS:
            self.hits_taken += 1
            self._last_hit = now

    def tick(self, now):
        """Time passes: seconds beyond IDLE_AFTER_SECONDS since the last kill are idle."""
        if self._last_tick is not None and now - self._last_kill > IDLE_AFTER_SECONDS:
            self.idle_seconds += now - self._last_tick
        self._last_tick = now


class SyncWorker:
    """The PilotWorker interface, answering at once from the rules pilot."""

    def __init__(self, params, clock):
        self.pilot = JevPilot(RulesClient(params), params)
        self.clock = clock
        self._result = None
        self.busy = False

    def submit(self, observation):
        decision = asyncio.run(self.pilot.decide(observation))
        self._result = PilotResult(observation.generation, observation.snapshot_at,
                                   self.clock(), decision)
        return True

    def poll(self):
        result, self._result = self._result, None
        return result

    def cancel(self):
        self._result = None

    def close(self):
        pass

    def join(self, timeout=0):
        pass


_game = None
_saved = {}


def _make_game():
    """One Game per process: real play scale, no sound, a throwaway profile file."""
    import pygame
    import config
    from game import Game
    from profiles import ProfileManager
    # `game` is both a module and a package name in this repo, so patch Game's own globals.
    namespace = Game.__init__.__globals__
    pygame.init()
    pygame.display.set_mode(SCREEN)
    _saved.update(width=config.SCREEN_WIDTH, height=config.SCREEN_HEIGHT,
                  splash=config.SPLASH_ENABLED, sound=namespace['SoundManager'],
                  profiles=namespace['ProfileManager'], namespace=namespace)
    config.SCREEN_WIDTH, config.SCREEN_HEIGHT = SCREEN
    config.SPLASH_ENABLED = False
    scratch = Path(tempfile.mkdtemp(prefix='rules-lab-')) / 'profiles.json'
    namespace['SoundManager'] = Mock
    namespace['ProfileManager'] = lambda: ProfileManager(scratch)
    # A stray AUTOPLAY or START_LEVEL in the shell must not steer the harness's Game.
    with mock.patch.dict(os.environ):
        os.environ.pop('AUTOPLAY', None)
        os.environ.pop('START_LEVEL', None)
        return Game(pygame.display.get_surface())


def reset():
    """Undo the process-wide changes _make_game made and drop the cached Game (for tests)."""
    global _game
    if _game is not None:
        import config
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT = _saved['width'], _saved['height']
        config.SPLASH_ENABLED = _saved['splash']
        _saved['namespace']['SoundManager'] = _saved['sound']
        _saved['namespace']['ProfileManager'] = _saved['profiles']
    _game = None


def _active_enemies(game):
    return list(game.entity_manager.get_all_active_enemies())


_OVERRIDDEN = ('_summon_hunter', '_jev_beacon_drop_allowed', '_hunter_sees_player')


def _clear_overrides(game):
    """The episode's per-instance overrides must not outlive it on the reused Game."""
    for name in _OVERRIDDEN:
        game.__dict__.pop(name, None)


def run_episode(level, seed, params=DEFAULT, horizon=90.0):
    global _game
    import config
    if _game is None:
        _game = _make_game()
    game = _game
    _clear_overrides(game)
    now = [1000.0]
    clock = lambda: now[0]

    game.level, game.state = level, config.STATE_PLAYING
    game.start_level()
    random.seed(seed)
    game.player_has_moved = True
    game.ship.game_started = True
    # The player is parked, hidden from the hunter, and can neither fail nor finish the level.
    game.scoring.calculate_current_potential_score = lambda *a, **k: {
        'potential_score': 1000, 'score_percentage': 1.0}
    game.maze.check_exit_reached = lambda *a, **k: False
    game._hunter_sees_player = lambda: False
    game.hunter_worker = SyncWorker(params, clock)
    game._summon_hunter((game.ship.x, game.ship.y))
    hunter, controller = game.hunter, game.hunter_controller
    controller.clock = clock
    # This hunter is the episode's hunter: picking up a Jev beacon (which would summon a new one
    # with a real-clock controller) must not replace it, and no new beacon may drop.
    game._summon_hunter = lambda near: None
    game._jev_beacon_drop_allowed = lambda: False
    # The hunter stays indestructible, as in the game; hits are counted, not suffered.
    settings = replace(HunterSettings(), thrust_multiplier=params.thrust_multiplier,
                       sensor_range_fraction=params.sensor_range_fraction)
    hunter.settings = controller.settings = settings
    # The perception reads its own copy of the settings (how far the hunter sees).
    game.hunter_perception.settings = settings

    counter = EventCounter()

    original_wall = hunter.check_wall_collision

    def counting_wall(*args, **kwargs):
        hit = original_wall(*args, **kwargs)
        counter.wall(hit)
        return hit
    hunter.check_wall_collision = counting_wall

    original_damage = hunter.take_damage

    def counting_damage():
        counter.hit_taken(elapsed)
        return original_damage()
    hunter.take_damage = counting_damage

    alive = _active_enemies(game)
    start_enemies = len(alive)
    counter.observe(alive)
    end = 'horizon'
    elapsed = 0.0
    for _ in range(int(horizon * FPS)):
        now[0] += 1 / FPS
        elapsed += 1 / FPS
        game.update(1.0)
        if game.hunter is not hunter or game.hunter_controller is not controller:
            raise RuntimeError('hunter was replaced during the episode')
        alive = _active_enemies(game)
        counter.observe(alive)
        counter.tick(elapsed)
        if start_enemies and not alive:
            end = 'cleared'
            break
    game._close_hunter()
    _clear_overrides(game)
    return EpisodeResult(level, seed, start_enemies, elapsed, counter.kills, counter.wall_hits,
                         counter.hits_taken, counter.idle_seconds, end, counter.spawned)
