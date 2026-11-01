"""Replay hooks for the jelly_team task (see learning.replay). Jellies have no frozen opponent: the run's saved
horizon and arena snapshots rebuild the environment, and any other change to the scenario's rules (its
scenario_version, rewards, creature stats, the ship pilot's checksum) rejects the recording."""
from types import SimpleNamespace

from learning.replay import check_rules
from learning import jelly_rewards


def metadata_args(path, manifest):
    """learning.run copies the trainer's --opponent file into every run and the manifest records its checksum, so the
    rules are rebuilt against that copy even though no Jelly flies against it."""
    return SimpleNamespace(opponent=path/'opponent.npz', horizon=manifest['horizon'],
                           **jelly_rewards.recovered_settings({'manifest': manifest}))


def open_environment(path, manifest):
    from learning.adapters import jelly_scenario
    check_rules(path, manifest, jelly_scenario.metadata, metadata_args=metadata_args)
    return jelly_scenario.JellyEnvironment(horizon=manifest['horizon'], arenas=manifest['arenas'],
                                          **jelly_scenario.environment_options(manifest))


def outcome(manifest, events, transition, total_reward):
    end = ('horizon' if transition.truncated else 'ship_killed' if events.get('ship_kills') else 'team_dead')
    return {'return': total_reward, 'end': end}


def status(env, job):
    e = env.events()
    lines = [f'JELLY TEAM — stage {env.stage} — level {job["level"]} — {env.frames/60:.1f}s',
             f'Catches {e["catches"]}    ship hits {e["ship_hits"]}    alive {e["alive"]}/{env.team_size}']
    for c in env.team.members():
        lines.append(f'{c.agent_id}: return {env.agent_returns[c.agent_id]:.2f}')
    return lines


ROUTE_COLOUR, WAYPOINT_COLOUR = (70, 150, 200), (255, 215, 60)


def draw(env, screen):
    """The game's own drawing, plus each Jelly's route to its target (blue) and the waypoint it is steering for
    (yellow): what the policy senses as its compass."""
    import pygame
    from learning.replay import _draw_world
    from learning.adapters.jelly import route_guide
    _draw_world(env, screen)
    for c in env.team.members():
        target = env.enc.target_entity_for(c)
        if target is None:
            continue
        guide = route_guide(c, env.enc, target.get_pos())
        if len(guide.path) > 1:
            pygame.draw.lines(screen, ROUTE_COLOUR, False, guide.path, 2)
        if guide.waypoint is not None:
            pygame.draw.line(screen, WAYPOINT_COLOUR, c.get_pos(), guide.waypoint, 2)
            pygame.draw.circle(screen, WAYPOINT_COLOUR, guide.waypoint, 6, 2)
