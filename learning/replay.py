"""Recorded joint actions replay any registered task's episodes without resampling policies.

This module knows no task. It reads the run's config.json for the task key, and the task's replay hooks module
(`Task.replay_hooks` in learning/tasks.py) supplies what differs between tasks:

- open_environment(path, manifest) -> env      required: check the recording against the current rules (raise
                                               ValueError if they differ; check_rules below does it, given the
                                               task's metadata and, if its manifest needs more than the recorded
                                               horizon, a metadata_args(path, manifest) builder) and build the
                                               environment to replay in
- episode(job) -> dict                         optional: the fields listed for each episode (default: the job)
- outcome(manifest, events, transition, total_reward) -> dict
                                               optional: return/end etc. for a flown episode
                                               (default: return=summed step rewards, end='horizon'|'terminated')
- draw(env, screen)                            optional: draw the scene (default: the game world's own drawing)
- status(env, job) -> list[str]                optional: the watch window's text lines
                                               (default: the task, level and seconds)

The episodes file is learning.run's: jobs (reset arguments plus seed), episodes (recorded events) and actions
(each episode's per-decision joint actions). Replay resets with each job, applies the recorded actions in order and
requires the final events to equal the recorded ones exactly."""
import importlib
import json
from pathlib import Path


def record(path, iteration):
    filename='bootstrap.json' if iteration=='bootstrap' else f'iter{iteration:04d}.json'
    return json.loads((Path(path)/'episodes'/filename).read_text())


def _settings(path):
    return json.loads((Path(path)/'config.json').read_text())


def _task(settings):
    from learning.tasks import task, UNTAGGED_REPLAY_TASK
    return task(settings.get('task', UNTAGGED_REPLAY_TASK))


def _hooks(task):
    if not task.replay_hooks:
        raise ValueError(f"task '{task.key}' has no replay hooks: set Task.replay_hooks in learning/tasks.py "
                         f"to a module defining open_environment")
    hooks = importlib.import_module(task.replay_hooks)
    if not callable(getattr(hooks, 'open_environment', None)):
        raise ValueError(f"replay hooks for task '{task.key}' ({task.replay_hooks}) do not define open_environment")
    return hooks


def _recorded_horizon(path, manifest):
    from types import SimpleNamespace
    return SimpleNamespace(horizon=manifest['horizon'])


def check_rules(path, saved, metadata, effective_rules=lambda rules: rules, metadata_args=_recorded_horizon):
    """Raise ValueError unless the task's current rules (`metadata(args)`, the adapter's manifest builder) match the
    recorded manifest. Arena snapshots are immutable and replayed directly, and training hyperparameters do not
    change the scenario, so both are taken from the recording; every other rule change needs the original version.
    `effective_rules` maps a manifest to what actually governs play, for tasks whose manifests carry overridden
    defaults. `metadata_args(path, manifest)` builds the arguments `metadata` is called with; by default only the
    recorded horizon, and a task whose manifest depends on files in the run directory supplies its own."""
    current = json.loads(json.dumps(metadata(metadata_args(Path(path), saved))))
    current['arenas'] = saved['arenas']
    current['training'] = saved.get('training', {})
    now, then = effective_rules(current), effective_rules(saved)
    if now != then:
        changed = sorted(k for k in set(now) | set(then) if now.get(k) != then.get(k))
        raise ValueError(f'replay rules or schemas differ from the recorded run: {", ".join(changed)}')


def open_environment(path):
    settings = _settings(path)
    return _hooks(_task(settings)).open_environment(Path(path), settings['manifest'])


def episodes(path, iteration):
    hooks = _hooks(_task(_settings(path)))
    describe = getattr(hooks, 'episode', dict)
    return [dict(episode=i, **describe(job)) for i, job in enumerate(record(path, iteration)['jobs'])]


def _outcome(manifest, events, transition, total_reward):
    return {'return': total_reward, 'end': 'horizon' if transition.truncated else 'terminated'}


def fly(path, iteration):
    data = record(path, iteration)
    settings = _settings(path)
    hooks = _hooks(_task(settings))
    outcome = getattr(hooks, 'outcome', _outcome)
    env = hooks.open_environment(Path(path), settings['manifest'])
    rows = []
    try:
        for i, (job, expected, trace) in enumerate(zip(data['jobs'],data['episodes'],data['actions'])):
            case = dict(job); seed = case.pop('seed')
            env.reset(seed, **case)
            total = 0.
            # An episode over before its first decision records no actions; the one empty step ends it again.
            for actions in trace or [{}]:
                result = env.step({int(k):tuple(v) for k,v in actions.items()})
                total += result.reward
            actual = result.events
            comparable = json.loads(json.dumps({k:expected[k] for k in actual}))
            if json.loads(json.dumps(actual)) != comparable:
                raise ValueError(f'replay diverged in episode {i}: {actual} != {comparable}')
            rows.append({'episode': i, **{k: job[k] for k in ('level', 'seed') if k in job},
                         **outcome(settings['manifest'], actual, result, total), **actual})
        return rows
    finally:
        env.close()


def _draw_world(env, screen):
    world = env.world
    world.maze.draw(screen)
    world.roster.draw(screen)
    for target in getattr(world, 'additional_targets', ()):
        target.draw(screen)
    if getattr(world, 'ship', None) is not None:
        world.ship.draw(screen)
    for shot in getattr(world, 'projectiles', ()):
        shot.draw(screen)


def watch(path, iteration, episode, speed=1.0):
    import pygame
    import config
    from rendering.fonts import get_font
    path = Path(path)
    data, settings = record(path, iteration), _settings(path)
    task = _task(settings)
    hooks = _hooks(task)
    draw_scene = getattr(hooks, 'draw', _draw_world)
    status = getattr(hooks, 'status', lambda env, job: [
        f'{task.label.upper()} — level {job.get("level")} — {getattr(env, "frames", 0)/60:.1f}s'])
    job = data['jobs'][episode]
    pygame.init()
    screen = pygame.display.set_mode((1352,878), pygame.DOUBLEBUF)
    env = hooks.open_environment(path, settings['manifest'])
    case = dict(job); seed = case.pop('seed')
    env.reset(seed, **case)
    clock = pygame.time.Clock()
    def draw(scene):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                raise KeyboardInterrupt
        screen.fill(config.COLOR_BACKGROUND)
        draw_scene(scene, screen)
        for i, line in enumerate(status(scene, job)):
            screen.blit(get_font(20).render(line,True,(235,220,185)),(8,15+28*i))
        pygame.display.flip(); clock.tick(max(1, round(60*speed)))
    env.render_frames = draw
    try:
        for actions in data['actions'][episode] or [{}]:
            transition = env.step({int(i):tuple(a) for i,a in actions.items()})
            if transition.terminated or transition.truncated: break
    except KeyboardInterrupt:
        pass
    finally:
        env.close(); pygame.quit()
