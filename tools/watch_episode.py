"""Replay a training episode: list an iteration's episodes by how much the hunter panicked, or watch one in a window.

    python -m tools.watch_episode RUN ITERATION            # fly the iteration's episodes, the most panic first
    python -m tools.watch_episode RUN ITERATION EPISODE    # watch that episode in the game window (Esc to stop)

Episodes are not recorded but they are reproducible: each is fixed by its level, its seed, and the checkpoint and dice
seed it flew with, which the run's config.json and checkpoints give back. RUN is a run directory written by
tools.ppo_neural (it needs the 'shaping' its config.json has kept since panic was added).
"""
import argparse
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np


def episode_jobs(run, iteration):
    """The iteration's jobs, (level, seed, spec) each, exactly as training made them, and the run's shaping."""
    from tools.ppo_neural import make_jobs
    config = json.loads((Path(run) / 'config.json').read_text())
    if 'shaping' not in config:
        raise SystemExit(f'{run}/config.json has no shaping: the run predates replays')
    episode = config['episode']
    weights = Path(run) / f'iter{iteration - 1:04d}.npz' if iteration else Path(config['start'])
    levels = tuple(episode['levels']) if episode.get('levels') else None
    jobs = make_jobs(iteration, episode['episodes_per_iteration'], weights, config.get('decision_frames', 6),
                     config.get('turn_rate', 1.0), episode.get('rules_share', 0.0), levels)
    return jobs, config['shaping']


def _fly(item):
    job, shaping = item
    from experiments import run
    run._use_dummy_drivers()
    from experiments.rollout import fly_rollout
    level, seed, spec = job
    flown = fly_rollout(level, seed, spec, **shaping)
    temperatures = flown['temperatures']
    return (level, float((temperatures > 1.0).mean()) if len(temperatures) else 0.0, float(flown['rewards'].sum()),
            flown['result'].kills, flown['result'].end, len(temperatures) * spec.decision_frames / 60.0)


def fly_all(run, iteration, workers):
    """Each of the iteration's episodes flown again: (level, panic share, return, kills, end, seconds)."""
    jobs, shaping = episode_jobs(run, iteration)
    with ProcessPoolExecutor(workers) as pool:
        return list(pool.map(_fly, [(job, shaping) for job in jobs]))


def find(run, iteration, workers):
    rows = fly_all(run, iteration, workers)
    print(f'{"episode":>7} {"level":>5} {"panic":>6} {"return":>7} {"kills":>5} {"seconds":>7}  end')
    for index, (level, panic, ret, kills, end, seconds) in sorted(enumerate(rows), key=lambda r: -r[1][1]):
        if panic > 0:
            print(f'{index:7d} {level:5d} {100 * panic:5.0f}% {ret:7.1f} {kills:5d} {seconds:7.1f}  {end}')
    print(f'{sum(1 for r in rows if r[1] > 0)} of {len(rows)} episodes panicked')


def _open_window():
    """The window the replay is shown in: a function that shows the game's screen, or None to show it as it is.

    The game world is as big as its screen (1352x878), and a replay must keep that size to fly as training did.
    On a smaller desktop the game draws on its full-size screen, hidden, and each frame is shown shrunk in a
    window that fits.
    """
    import pygame
    from experiments import harness
    from utils.window_size import fit_window_size
    pygame.init()
    sizes = pygame.display.get_desktop_sizes()
    size = fit_window_size(harness.SCREEN, sizes[0] if sizes else None)
    if size == harness.SCREEN:
        return None
    from unittest import mock
    from pygame._sdl2.video import Renderer, Texture, Window
    set_mode = pygame.display.set_mode
    with mock.patch.object(pygame.display, 'set_mode', lambda size, flags=0, *a, **k: set_mode(size, flags | pygame.HIDDEN)):
        harness._game = harness._make_game()
    window = Window('Episode replay', size=size)
    renderer = Renderer(window)

    def show():
        renderer.clear()
        Texture.from_surface(renderer, pygame.display.get_surface()).draw(dstrect=(0, 0, *size))
        renderer.present()
    return show


def watch(run, iteration, episode, speed):
    import pygame
    from experiments.rollout import fly_rollout
    jobs, shaping = episode_jobs(run, iteration)
    level, seed, spec = jobs[episode]
    show = _open_window()
    clock, font, flip = pygame.time.Clock(), None, pygame.display.flip

    def frame(seconds, game, hunter):
        nonlocal font
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.WINDOWCLOSE) or (event.type == pygame.KEYDOWN
                                                                     and event.key == pygame.K_ESCAPE):
                raise SystemExit
        stub = game.scoring.calculate_current_potential_score
        if not getattr(stub, 'for_drawing', False):
            # The harness stands in a bare score; the HUD reads a couple more fields from it.
            def for_drawing(*a, **k):
                return {'max_score': 1000, 'final_score': 0, **stub(*a, **k)}
            for_drawing.for_drawing = True
            game.scoring.calculate_current_potential_score = for_drawing
        pygame.display.flip = lambda: None          # the overlay goes on before the frame is shown
        # Drawing draws random numbers (sparks, debris): put them back, or the episode would play out differently.
        states = random.getstate(), np.random.get_state()
        try:
            game.draw()
        finally:
            pygame.display.flip = flip
            random.setstate(states[0])
            np.random.set_state(states[1])
        font = font or pygame.font.SysFont(None, 34)
        temperature = getattr(game.hunter_flight.controller, 'temperature', 1.0)
        panic = temperature > 1.0
        text = f'run {Path(run).name}  iteration {iteration}  episode {episode}  level {level}  {seconds:5.1f} s'
        if panic:
            text += f'   PANIC (temperature {temperature:g})'
        label = font.render(text, True, (255, 255, 255))
        screen = pygame.display.get_surface()
        pygame.draw.rect(screen, (190, 30, 30) if panic else (20, 20, 30), (0, 0, label.get_width() + 24, 40))
        screen.blit(label, (12, 8))
        (show or flip)()
        clock.tick(60 * speed)

    # Training skips the tentacles' drag physics; a watched episode needs it, or they hang where they started.
    flown = fly_rollout(level, seed, spec, trace=frame, low_graphics=False, **shaping)
    temperatures = flown['temperatures']
    print(f'episode {episode}: level {level}, {flown["result"].end}, kills {flown["result"].kills}, '
          f'return {flown["rewards"].sum():.1f}, panic {100 * float((temperatures > 1.0).mean()):.0f}%')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run')
    parser.add_argument('iteration', type=int)
    parser.add_argument('episode', type=int, nargs='?')
    parser.add_argument('--speed', type=float, default=1.0, help='playback speed when watching')
    parser.add_argument('--workers', type=int, default=8, help='processes when finding')
    args = parser.parse_args(argv)
    if args.episode is None:
        find(args.run, args.iteration, args.workers)
    else:
        watch(args.run, args.iteration, args.episode, args.speed)


if __name__ == '__main__':
    main(sys.argv[1:])
