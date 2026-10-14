"""Runs one hunter episode headlessly on the real game, faster than real time."""
import asyncio
import math
import os
import random
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from entities.hunter_ship import HunterShip
from hunter.flight import HunterFlight, NeuralPilot, WorkerPilot
from hunter.jev_pilot import JevPilot
from hunter.model import HunterSettings, PilotResult
from hunter.rule_params import DEFAULT
from hunter.rules_pilot import RulesClient
from hunter.spawn import nearest_hunter_spawn

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
    end: str  # 'cleared', 'horizon' or (a mortal hunter) 'died'
    enemies_spawned: int = 0  # enemies that appeared during the episode (spawners, eggs)
    wall_impulse: float = 0.0  # speed the walls took from the hunter, summed over collision frames, in top speeds


class EventCounter:
    """Turns per-frame observations into event counts."""

    def __init__(self):
        self.kills = 0
        self.spawned = 0
        self.wall_hits = 0
        self.wall_impulse = 0.0
        self.hits_taken = 0
        self.idle_seconds = 0.0
        self.powerups = 0          # crystals the hunter collected
        self.died = False          # the (mortal) hunter was destroyed
        self.cleared = False       # every enemy is dead: nothing is left to kill, so waiting is not idling
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

    def wall(self, hit, impulse=0.0):
        """A wall collision check: `hit` if the hunter touched a wall, `impulse` the speed that took from it.

        A new contact is one hit; every frame of contact adds its impulse, so a hard crash costs a lot, a glancing
        scrape little, and pushing into a wall adds up while it lasts.
        """
        if hit and not self._in_wall:
            self.wall_hits += 1
        if hit:
            self.wall_impulse += impulse
        self._in_wall = bool(hit)

    def hit_taken(self, now):
        """A damage call at `now`: it counts once per immunity window, so a held contact is few hits."""
        if self._last_hit is None or now - self._last_hit >= DAMAGE_IMMUNITY_SECONDS:
            self.hits_taken += 1
            self._last_hit = now

    def tick(self, now):
        """Time passes: seconds beyond IDLE_AFTER_SECONDS since the last kill are idle."""
        if self._last_tick is not None and not self.cleared and now - self._last_kill > IDLE_AFTER_SECONDS:
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


def _random_cell_centre(game, level, seed):
    """The centre of an open maze cell picked from (level, seed), without touching the global random stream."""
    maze = game.maze
    cells = [(col, row) for row in range(maze.grid_height) for col in range(maze.grid_width)
             if not maze.grid[row][col]]
    col, row = random.Random(f'start-{level}-{seed}').choice(cells)
    return maze.position_calculator.grid_center_to_screen(col, row)


def _loose_crystals(game):
    """The powerup crystals still lying in the maze (not the Jev beacon)."""
    from entities.jev_beacon import JevBeacon
    return [c for c in game.powerup_crystals if c.active and not isinstance(c, JevBeacon)]


def _active_enemies(game):
    return list(game.entity_manager.get_all_active_enemies())


_OVERRIDDEN = ('_summon_hunter', '_jev_beacon_drop_allowed', '_hunter_sees_player')


def _clear_overrides(game):
    """The episode's per-instance overrides must not outlive it on the reused Game."""
    for name in _OVERRIDDEN:
        game.__dict__.pop(name, None)


def load_student_policy(student):
    from experiments.student import load_policy
    return load_policy(student)


def _run_episode(level, seed, params=DEFAULT, horizon=90.0, hide_player=True, trace=None,
                student=None, recorder=None, labeller=None, on_result=None, random_start=False, after_clear=0.0,
                 pursue_hunter=False, health=0):
    """One episode. `hide_player=False` lets the hunter see the parked player (the lab's default hides it).

    `random_start` starts the hunter in an open cell chosen from (level, seed) instead of beside the player.
    `health` above zero makes the hunter mortal: it survives that many hits, and the episode ends 'died' when it
    is destroyed (0 keeps it indestructible: hits are counted, not suffered).
    `pursue_hunter` makes enemies chase the hunter alone: the parked player is no target (and, as with `hide_player`,
    the hunter does not see it). Without it the parked ship is a decoy for whichever enemies are nearer to it.
    `after_clear` keeps flying that many more seconds once the last enemy is dead (less if no crystal is left to
    collect); the result still reports the time of the last kill.
    `trace`, if given, is called each frame with (seconds, game, hunter) for diagnostics.
    """
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
    if hide_player or pursue_hunter:
        game._hunter_sees_player = lambda: False
    if pursue_hunter:
        game.ship.observer = True
    # The lab's pilot answers synchronously on the episode clock. The game holds the same worker, so it never
    # warms up a real one of its own.
    game.hunter_worker = SyncWorker(params, clock)
    if student is None:
        pilot = WorkerPilot(game.hunter_worker, clock)
    else:
        if load_student_policy(student) is None:
            raise ValueError(f'student weights unusable: {student.weights}')
        from experiments.student import load_policy
        import numpy as np
        pilot = NeuralPilot(load_policy(student), student.decision_frames, greedy=student.greedy,
                            rng=None if student.greedy else np.random.default_rng(student.sample_seed))
    # Unless `health` says otherwise the hunter stays indestructible: hits are counted, not suffered.
    settings = replace(HunterSettings(), thrust_multiplier=params.thrust_multiplier,
                       sensor_range_fraction=params.sensor_range_fraction,
                       turn_rate_multiplier=(params.turn_rate_multiplier if student is None
                                             else student.turn_rate))
    if health > 0:
        import config
        settings = replace(settings, indestructible=False, health=health,
                           wall_energy=config.SETTINGS.game.neuralWallEnergy)
    near = _random_cell_centre(game, level, seed) if random_start else (game.ship.x, game.ship.y)
    game._close_hunter()
    flight = HunterFlight(HunterShip(nearest_hunter_spawn(near, game.maze, game.ship), settings),
                          pilot, game.hunter_surroundings)
    game.hunter_flight = flight
    hunter = flight.ship
    # This hunter is the episode's hunter: picking up a Jev beacon (which would summon a new one
    # with a real-clock controller) must not replace it, and no new beacon may drop.
    game._summon_hunter = lambda near: None
    game._jev_beacon_drop_allowed = lambda: False

    counter = EventCounter()

    original_wall = hunter.check_wall_collision

    def counting_wall(*args, **kwargs):
        vx, vy = hunter.vx, hunter.vy
        hit = original_wall(*args, **kwargs)
        counter.wall(hit, math.hypot(hunter.vx - vx, hunter.vy - vy) / max(hunter.max_speed, 1e-6))
        return hit
    hunter.check_wall_collision = counting_wall

    original_damage = hunter.take_damage

    def counting_damage():
        counter.hit_taken(elapsed)
        return original_damage()
    hunter.take_damage = counting_damage

    original_collect = hunter.collect_powerup

    def counting_collect():
        counter.powerups += 1
        return original_collect()
    hunter.collect_powerup = counting_collect

    if recorder is not None:
        original_step = hunter.step

        def recording_step(dt, action, solution=None):
            before = hunter.angle
            shots = original_step(dt, action, solution)
            recorder.add_frame(rotation=((hunter.angle - before + 180.0) % 360.0) - 180.0,
                               engine=bool(hunter.pilot_thrusting), trigger=bool(action.fire or shots))
            return shots
        hunter.step = recording_step
        recorder.begin(game, hunter, settings)

    alive = _active_enemies(game)
    start_enemies = len(alive)
    counter.observe(alive)
    end = 'horizon'
    elapsed = 0.0
    cleared_at = None
    for frame in range(int((horizon + after_clear) * FPS)):
        now[0] += 1 / FPS
        elapsed += 1 / FPS
        if recorder is not None:
            recorder.before_frame(game, hunter)
        if labeller is not None:
            labeller.before_frame(game, hunter, frame)
        game.update(1.0)
        if recorder is not None:
            recorder.after_frame()
        if game.hunter_flight is not flight:
            raise RuntimeError('hunter was replaced during the episode')
        alive = _active_enemies(game)
        counter.observe(alive)
        counter.tick(elapsed)
        if health > 0 and not hunter.active:
            counter.died = True
        if recorder is not None and hasattr(recorder, 'counted'):
            recorder.counted(counter, elapsed)
        if trace is not None:
            trace(elapsed, game, hunter)
        if counter.died:
            end = 'died'
            break
        if start_enemies and not alive:
            if cleared_at is None:
                cleared_at = elapsed
                counter.cleared = True
                end = 'cleared'
            if (elapsed - cleared_at >= after_clear or not _loose_crystals(game)):
                break
        elif cleared_at is None and elapsed >= horizon:
            break
    game._close_hunter()
    _clear_overrides(game)
    result = EpisodeResult(level, seed, start_enemies, elapsed if cleared_at is None or counter.died else cleared_at, counter.kills, counter.wall_hits,
                           counter.hits_taken, counter.idle_seconds, end, counter.spawned, counter.wall_impulse)
    if on_result is not None:
        on_result(result)
    return result


def run_episode(*args, low_graphics=True, **kwargs):
    """One episode (see _run_episode). Tentacle physics is off unless asked for: nothing in the game reads it."""
    import config
    previous = config.SETTINGS.game.lowGraphics
    config.SETTINGS.game.lowGraphics = low_graphics
    try:
        return _run_episode(*args, **kwargs)
    finally:
        config.SETTINGS.game.lowGraphics = previous
