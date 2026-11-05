"""Render a demo movie of a trained creature from a training run's recorded episodes.

    python -m tools.demo_video RUN [--out DIR] [--iteration N] [--clips N] [--seconds MIN MAX] [--list]

RUN is a run directory, or a name under .astrovoid-local/neural/rl. Episodes replay from their recorded actions through
the task's replay hooks (the dashboard's Watch button path), are drawn offscreen and joined with ffmpeg. One group of
clips per lesson/stage, each with a title card. `--list` shows which episode each clip would use without rendering.
See docs/demo-video.md for the optional replay hooks that tune a creature's video.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SIZE, SCREEN, FPS = (1280, 832), (1352, 878), 60
SUCCESS_KEYS = ('success', 'battle_success')       # truthy = a good episode
SCORE_KEYS = ('catches', 'kills', 'hits')          # otherwise higher is better, and zero is not a demo
DEFAULT_SECONDS = (3., 25.)


def label_of(hooks, job):
    """The clip group a job belongs to: the hook's `lesson`, else the job's own lesson/practice_stage/stage."""
    described = getattr(hooks, 'episode', lambda j: {})(job)
    for key in ('lesson', 'practice_stage'):
        if isinstance(described.get(key) or job.get(key), str):
            return str(described.get(key) or job[key]).replace('_', ' ').capitalize()
    return f'Stage {job["stage"]}' if 'stage' in job else 'Demo'


def quality(hooks, row):
    """None when the episode is not worth showing, else a number (higher is better)."""
    if hasattr(hooks, 'showcase'):
        return hooks.showcase(row)
    for key in SUCCESS_KEYS:
        if key in row:
            return float(bool(row[key])) or None
    for key in SCORE_KEYS:
        if row.get(key):
            return float(row[key])
    return None


def pick_episodes(run, hooks, newest, seconds, clips):
    """{label: [(iteration, index, job, row)]}: for each group the newest `clips` good episodes of a readable length."""
    ranges = getattr(hooks, 'CLIP_SECONDS', {})
    picks = {}
    for iteration in range(newest, -1, -1):
        path = run/'episodes'/f'iter{iteration:04d}.json'
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for i, (job, row) in enumerate(zip(data['jobs'], data['episodes'])):
            label = label_of(hooks, job)
            low, high = ranges.get(label, seconds)
            length = row.get('seconds')
            if (len(picks.get(label, ())) < clips and quality(hooks, row)
                    and (length is None or low <= length <= high)):
                picks.setdefault(label, []).append((iteration, i, job, row))
    return picks


def order(hooks, picks):
    known = [l for l in getattr(hooks, 'LESSONS', ()) if l in picks]
    return known+sorted(l for l in picks if l not in known)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('run'); p.add_argument('--out', default='demo-video')
    p.add_argument('--iteration', type=int, help='newest iteration to draw episodes from (default: two before the last)')
    p.add_argument('--clips', type=int, default=1, help='clips per lesson')
    p.add_argument('--seconds', type=float, nargs=2, default=DEFAULT_SECONDS, metavar=('MIN', 'MAX'))
    p.add_argument('--list', action='store_true', help='show the chosen episodes and stop')
    args = p.parse_args(argv)
    run = Path(args.run)
    if not run.is_dir():
        run = Path('.astrovoid-local/neural/rl')/args.run
    from learning import replay
    settings = replay._settings(run); task = replay._task(settings); hooks = replay._hooks(task)
    iterations = [int(f.stem[4:]) for f in (run/'episodes').glob('iter*.json') if f.stem[4:].isdigit()]
    if not iterations:
        raise SystemExit(f'{run} recorded no episodes, so there is nothing to replay')
    newest = args.iteration if args.iteration is not None else max(max(iterations)-2, 0)
    picks = pick_episodes(run, hooks, newest, tuple(args.seconds), args.clips)
    if not picks:
        raise SystemExit('no good episodes found; try --seconds, an earlier --iteration, or a showcase() hook')
    labels = order(hooks, picks)
    for label in labels:
        for iteration, i, job, row in picks[label]:
            print(f'{label}: iteration {iteration} episode {i}' + (f" ({row['seconds']:.1f} s)" if 'seconds' in row else ''))
    if args.list:
        return

    import pygame
    import config
    from rendering.fonts import get_font
    out = Path(args.out); frames = out/'frames'
    shutil.rmtree(frames, ignore_errors=True); frames.mkdir(parents=True)
    pygame.init()
    screen = pygame.display.set_mode(SCREEN)
    draw_scene = getattr(hooks, 'draw', replay._draw_world)
    count = 0

    def save(surface):
        nonlocal count
        pygame.image.save(surface, str(frames/f'{count:06d}.png')); count += 1

    def card(text, sub, hold):
        surface = pygame.Surface(SIZE); surface.fill((14, 16, 24))
        for font, line, colour, dy in ((get_font(44), text, (240, 230, 200), -18), (get_font(26), sub, (150, 160, 175), 34)):
            image = font.render(line, True, colour); surface.blit(image, image.get_rect(center=(SIZE[0]//2, SIZE[1]//2+dy)))
        for _ in range(hold):
            save(surface)

    card(task.label, f'Trained policy, {run.name}', 110)
    for label in labels:
        for iteration, episode, job, row in picks[label]:
            data = replay.record(run, iteration)
            env = hooks.open_environment(run, settings['manifest'])
            case = dict(job); seed = case.pop('seed'); env.reset(seed, **case)
            focus = hooks.focus(env) if hasattr(hooks, 'focus') else None      # (x, y, width) to crop to, else the whole arena
            card(label, f"{row['seconds']:.0f} s episode, recorded from training" if 'seconds' in row else 'Recorded from training', 60)

            def draw(scene):
                screen.fill(config.COLOR_BACKGROUND)
                draw_scene(scene, screen)
                if focus:
                    width = min(SCREEN[0], focus[2]); height = width*SCREEN[1]/SCREEN[0]
                    x = min(max(focus[0]-width/2, 0), SCREEN[0]-width); y = min(max(focus[1]-height/2, 0), SCREEN[1]-height)
                    view = screen.subsurface(pygame.Rect(int(x), int(y), int(width), int(height)))
                else:
                    view = screen
                frame = pygame.transform.smoothscale(view, SIZE)
                frame.blit(get_font(34).render(label, True, (240, 230, 200)), (20, SIZE[1]-56))
                save(frame)
            env.render_frames = draw
            try:
                for actions in data['actions'][episode] or [{}]:
                    step = env.step({int(i): tuple(a) for i, a in actions.items()})
                    if step.terminated or step.truncated:
                        break
            finally:
                env.close()
            last = pygame.image.load(str(frames/f'{count-1:06d}.png'))
            for _ in range(45):
                save(last)
    card(' · '.join(labels), '', 90)
    movie = out/f'{task.key}-demo.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(frames/'%06d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', str(movie)], check=True)
    shutil.rmtree(frames)
    print(movie)


if __name__ == '__main__':
    main()
