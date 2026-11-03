"""Exact recorded-action replay with physics/schema checks."""
from types import SimpleNamespace
from learning.replay import check_rules
from learning.inchworm_rewards import recovered_settings


def metadata_args(path,manifest):
    return SimpleNamespace(horizon=manifest['horizon'],**recovered_settings({'manifest':manifest}))


def open_environment(path,manifest):
    from learning.adapters import inchworm_scenario as scenario
    check_rules(path,manifest,scenario.metadata,metadata_args=metadata_args)
    return scenario.environment(horizon=manifest['horizon'],arenas=manifest['arenas'],
                                **scenario.environment_options(manifest))


def draw(env,screen):
    import pygame
    for wall in env.world.maze.walls:
        if wall.active:
            pygame.draw.line(screen,(110,130,145),wall.start,wall.end,3)
    goal = env.world.worm_goal
    if goal is not None:
        pygame.draw.circle(screen,(100,200,240),goal,10,2)
    env.world.roster.draw(screen)


def status(env,job):
    from learning.adapters.inchworm_scenario import STAGES
    return [f'INCHWORM — {STAGES[env.stage-1]} — {env.frames/60:.1f}s',
            f'Bites {env.bites}   Goal distance {env.distance():.1f}   Success {env.success}']
