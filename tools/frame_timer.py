"""Time a frame of play on chosen levels, update and draw apart, with fixed seeds.

    venv/bin/python -m tools.frame_timer --levels 1 8 9 40 --frames 600 --seed 1

Prints one row per level: level, enemies on it, the mean and 95th percentile update time, and the mean draw time, in
milliseconds. The game runs headless (dummy video and audio) on a surface the size of the real fullscreen display.

    venv/bin/python -m tools.frame_timer --levels 9 --creatures 33

adds 33 test Creatures to each level, each with six traits whose hooks do one attribute write and a Body that draws
nothing: what running creatures through the Encounter costs, apart from what their traits do.
"""
import argparse
import os
import random
import statistics
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import numpy
import pygame

import config

SCREEN_SIZE = (1352, 878)   # the real fullscreen display
WARM_UP_FRAMES = 60


def _p95(samples):
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]


def time_level(game, level, frames, seed, setup=None):
    """(enemies, update_ms_mean, update_ms_p95, draw_ms_mean) for one level."""
    random.seed(seed)
    numpy.random.seed(seed)
    game.level = level
    game.state = config.STATE_PLAYING
    game.start_level()
    game.player_has_moved = True
    if setup is not None:
        setup(game)
    enemies = len(game.roster.alive())
    for _ in range(WARM_UP_FRAMES):
        game.update(1.0)
        game.draw_game()
    updates, draws = [], []
    for _ in range(frames):
        start = time.perf_counter()
        game.update(1.0)
        middle = time.perf_counter()
        game.draw_game()
        end = time.perf_counter()
        updates.append((middle - start) * 1000.0)
        draws.append((end - middle) * 1000.0)
    return enemies, statistics.mean(updates), _p95(updates), statistics.mean(draws)


def _bench_creatures(count):
    """Put `count` test Creatures on the game's roster."""
    from dataclasses import replace

    import enemy_kinds
    from creatures.creature import Creature
    from creatures.trait import Trait

    class Touch(Trait):
        NAME = 'touch'

        def on_frame(self, c, enc, dt):
            c.touched = dt

    class Body:
        DEATH_DURATION = 1.0
        DEATH_FRICTION = 1.0

        def update(self, creature, dt, target):
            pass

        def draw(self, screen, creature):
            pass

        def update_death(self, creature, dt):
            pass

        def draw_death(self, screen, creature):
            pass

        def on_event(self, creature, name):
            pass

    kind = replace(enemy_kinds.kind('static'), body='bench')

    def setup(game):
        for i in range(count):
            pos = (40.0 + 30.0 * (i % 40), 40.0 + 30.0 * (i // 40))
            game.roster.add(Creature(kind, pos, Body(), [Touch() for _ in range(6)], level=game.level))

    return setup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--levels', type=int, nargs='+', default=[1, 8, 9, 40])
    parser.add_argument('--frames', type=int, default=600)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--creatures', type=int, default=0, help='test Creatures to add to each level')
    args = parser.parse_args(argv)

    config.SETTINGS.game.hunterPilot = 'rules'
    pygame.init()
    screen = pygame.display.set_mode(SCREEN_SIZE)
    from game import Game
    game = Game(screen)
    print(f"{'level':>5}  {'enemies':>7}  {'update_ms_mean':>14}  {'update_ms_p95':>13}  {'draw_ms_mean':>12}")
    setup = _bench_creatures(args.creatures) if args.creatures else None
    try:
        for level in args.levels:
            enemies, mean, p95, draw = time_level(game, level, args.frames, args.seed, setup)
            print(f'{level:>5}  {enemies:>7}  {mean:>14.3f}  {p95:>13.3f}  {draw:>12.3f}')
    finally:
        game._close_enemy_hunters()
        pygame.quit()


if __name__ == '__main__':
    main()
