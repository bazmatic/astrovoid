"""Recorded joint actions replay the team encounter without resampling policies."""
import json
from pathlib import Path
import time


def record(path, iteration):
    filename='bootstrap.json' if iteration=='bootstrap' else f'iter{iteration:04d}.json'
    return json.loads((Path(path)/'episodes'/filename).read_text())


def episodes(path, iteration):
    data = record(path, iteration)
    return [dict(episode=i, level=job['level'], seed=job['seed'], team_size=job['team_size'], opponents=job.get('opponents','hunter'),practice_stage=job.get('practice_stage','shooting'),neural_hunter=job.get('neural_hunter',False))
            for i, job in enumerate(data['jobs'])]


def _effective_rules(manifest):
    """Compare the cadence actually used by practice, rather than its overridden default."""
    import copy
    rules = copy.deepcopy(manifest)
    if rules.get('aiming_practice') and rules.get('opponent_body') == 'practice_targets':
        interval = rules.get('practice_fire_interval_frames')
        if interval is not None:
            for name, tuning in rules['creatures']['wallcrawler']['traits']:
                if name == 'gun':
                    tuning['intervalMin'] = tuning['intervalMax'] = interval
    return rules


def open_environment(path):
    from types import SimpleNamespace
    from learning.adapters.crawler_scenario import CrawlerEnvironment, metadata
    path = Path(path)
    saved = json.loads((path/'config.json').read_text())['manifest']
    current = json.loads(json.dumps(metadata(SimpleNamespace(opponent=path/'opponent.npz',horizon=saved['horizon']))))
    # Arena snapshots are immutable and replayed directly. Other rule changes require the original version.
    current['arenas'] = saved['arenas']
    current['training'] = saved.get('training', {})
    if _effective_rules(current) != _effective_rules(saved):
        raise ValueError('replay rules, schemas or opponent differ from the recorded run')
    return CrawlerEnvironment(opponent=path/'opponent.npz',horizon=saved['horizon'],arenas=saved['arenas'])


def fly(path, iteration):
    data = record(path, iteration)
    env = open_environment(path)
    rewards = json.loads((Path(path)/'config.json').read_text())['manifest']['rewards']
    rows = []
    try:
        for i, (job, expected, trace) in enumerate(zip(data['jobs'],data['episodes'],data['actions'])):
            case = dict(job); seed = case.pop('seed')
            env.reset(seed, **case)
            for actions in trace:
                result = env.step({int(k):tuple(v) for k,v in actions.items()})
            actual = result.events
            comparable = json.loads(json.dumps({k:expected[k] for k in actual}))
            if json.loads(json.dumps(actual)) != comparable:
                raise ValueError(f'replay diverged in episode {i}: {actual} != {comparable}')
            rows.append(dict(episode=i,level=job['level'],seed=job['seed'],panic=0,
                             kills=0,**{'return':actual.get('landing_reward',rewards.get('successful_landing',0.))*actual.get('successful_landings',0)+actual.get('trial_completion_reward',0.)+sum(actual.get(k,0.) for k in ('battle_alive_reward','battle_survival_bonus','battle_kill_reward','battle_death_penalty'))+actual.get('jump_proximity_reward',0.)+rewards['team_hit']*actual['hits']+rewards['shot']*actual['shots']+rewards.get('predicted_shot_accuracy',0.)*actual.get('aim_quality_sum',0.)-actual.get('jump_cost',-rewards.get('voluntary_jump',0.))*actual.get('voluntary_jumps',0)+rewards.get('walk_reversal',0.)*actual.get('walk_reversals',0)+rewards.get('bullet_hit',0.)*actual.get('bullet_hits_taken',0)+rewards.get('contact_hit',0.)*actual.get('contact_hits_taken',0)},
                             end='horizon' if result.truncated else ('targets_cleared' if actual.get('targets_cleared') else 'team_dead'),**actual))
        return rows
    finally:
        env.close()


def watch(path, iteration, episode, speed=1.0):
    import pygame
    import config
    from learning.adapters.crawler_scenario import CrawlerEnvironment
    from rendering.fonts import get_font
    path = Path(path)
    data, settings = record(path, iteration), json.loads((path/'config.json').read_text())
    job = data['jobs'][episode]
    pygame.init()
    screen = pygame.display.set_mode((1352,878), pygame.DOUBLEBUF)
    env = open_environment(path)
    case = dict(job); seed = case.pop('seed')
    env.reset(seed, **case)
    clock = pygame.time.Clock()
    def draw(scene):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                raise KeyboardInterrupt
        screen.fill(config.COLOR_BACKGROUND)
        scene.world.maze.draw(screen)
        scene.world.roster.draw(screen)
        scene.opponent.draw(screen) if scene.opponent is not None else None
        for target in scene.world.additional_targets:target.draw(screen)
        if scene.world.ship is not None: scene.world.ship.draw(screen)
        for shot in scene.world.projectiles: shot.draw(screen)
        lines = [f'WALLCRAWLER TEAM — level {job["level"]} — {scene.frames/60:.1f}s',
                 f'Accepted hits {scene.hits}    shots {scene.shots}']
        for c in scene.world.roster.all():
            lines.append(f'{c.agent_id}: {c.wall_state}  radio {getattr(c,"wall_message",0)}  HP {c.hit_points}')
        for i, line in enumerate(lines):
            screen.blit(get_font(20).render(line,True,(235,220,185)),(8,15+28*i))
        pygame.display.flip(); clock.tick(max(1, round(60*speed)))
    env.render_frames = draw
    try:
        for actions in data['actions'][episode]:
            transition = env.step({int(i):tuple(a) for i,a in actions.items()})
            if transition.terminated or transition.truncated: break
    except KeyboardInterrupt:
        pass
    finally:
        env.close(); pygame.quit()
