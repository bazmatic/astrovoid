"""Replay hooks for the jelly_team task (see learning.replay). Jellies have no frozen opponent: the run's saved
horizon and arena snapshots rebuild the environment, and any other change to the scenario's rules (its
scenario_version, rewards, creature stats, the ship pilot's checksum) rejects the recording."""
from learning.replay import check_rules


def open_environment(path, manifest):
    from learning.adapters import jelly_scenario
    check_rules(path, manifest, jelly_scenario.metadata)
    return jelly_scenario.JellyEnvironment(horizon=manifest['horizon'], arenas=manifest['arenas'])


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
