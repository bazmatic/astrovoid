"""Replay hooks for the wallcrawler_team task (see learning.replay): the frozen opponent copied into the run,
the practice gun cadence the rules actually used, the episode return and the watch window's scene."""
import copy
from types import SimpleNamespace

from learning.replay import check_rules


def metadata_args(path, manifest):
    """The crawler's manifest checksums the frozen opponent learning.run copied into the run directory."""
    return SimpleNamespace(opponent=path/'opponent.npz', horizon=manifest['horizon'])


def effective_rules(manifest):
    """Compare the cadence actually used by practice, rather than its overridden default."""
    rules = copy.deepcopy(manifest)
    if rules.get('aiming_practice') and rules.get('opponent_body') == 'practice_targets':
        interval = rules.get('practice_fire_interval_frames')
        if interval is not None:
            for name, tuning in rules['creatures']['wallcrawler']['traits']:
                if name == 'gun':
                    tuning['intervalMin'] = tuning['intervalMax'] = interval
    return rules


def open_environment(path, manifest):
    from learning.adapters import crawler_scenario
    check_rules(path, manifest, crawler_scenario.metadata, effective_rules, metadata_args)
    return crawler_scenario.CrawlerEnvironment(opponent=path/'opponent.npz', horizon=manifest['horizon'],
                                               arenas=manifest['arenas'])


def episode(job):
    return dict(level=job['level'], seed=job['seed'], team_size=job['team_size'],
                opponents=job.get('opponents','hunter'), practice_stage=job.get('practice_stage','shooting'),
                neural_hunter=job.get('neural_hunter',False))


def outcome(manifest, actual, result, total_reward):
    rewards = manifest['rewards']
    ret = (actual.get('landing_reward',rewards.get('successful_landing',0.))*actual.get('successful_landings',0)
           +actual.get('trial_completion_reward',0.)
           +sum(actual.get(k,0.) for k in ('battle_alive_reward','battle_survival_bonus','battle_kill_reward',
                                           'battle_death_penalty'))
           +actual.get('jump_proximity_reward',0.)+rewards['team_hit']*actual['hits']+rewards['shot']*actual['shots']
           +rewards.get('predicted_shot_accuracy',0.)*actual.get('aim_quality_sum',0.)
           -actual.get('jump_cost',-rewards.get('voluntary_jump',0.))*actual.get('voluntary_jumps',0)
           +rewards.get('walk_reversal',0.)*actual.get('walk_reversals',0)
           +rewards.get('bullet_hit',0.)*actual.get('bullet_hits_taken',0)
           +rewards.get('contact_hit',0.)*actual.get('contact_hits_taken',0))
    end = ('battle_success' if actual.get('battle_success') else ('horizon' if result.truncated else
           ('targets_cleared' if actual.get('targets_cleared') else 'team_dead')))
    return dict(panic=0, kills=0, **{'return': ret}, end=end)


def draw(scene, screen):
    scene.world.maze.draw(screen)
    scene.world.roster.draw(screen)
    scene.opponent.draw(screen) if scene.opponent is not None else None
    for target in scene.world.additional_targets:target.draw(screen)
    if scene.world.ship is not None: scene.world.ship.draw(screen)
    for shot in scene.world.projectiles: shot.draw(screen)


def status(scene, job):
    lines = [f'WALLCRAWLER TEAM — level {job["level"]} — {scene.frames/60:.1f}s',
             f'Accepted hits {scene.hits}    shots {scene.shots}']
    for c in scene.world.roster.all():
        lines.append(f'{c.agent_id}: {c.wall_state}  radio {getattr(c,"wall_message",0)}  HP {c.hit_points}')
    return lines
