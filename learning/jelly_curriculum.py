"""Navigation lessons, independent of the Jelly's solo/team/combat stages."""
from copy import deepcopy

LESSONS = ('open', 'barrier', 'cave')
MIN_EPISODES = 192
MIN_SUCCESS = .7
MAX_IDLE = .1
EPISODE_SECONDS = {'open': 10., 'barrier': 20.}
ARENAS = {
    'open': {'maze': {'complexity': 'empty', 'grid_size': 10}},
    'barrier': {'maze': {'complexity': 'empty', 'grid_size': 10},
                'layout': {'walls': [[5, y] for y in range(2, 7)], 'start': [2, 2], 'exit': [7, 7], 'enemies': []}},
}


def metadata():
    return dict(lessons=list(LESSONS), arenas=deepcopy(ARENAS), episode_seconds=dict(EPISODE_SECONDS),
                minimum_episodes=MIN_EPISODES, minimum_catch_probability=MIN_SUCCESS,
                maximum_idle_fraction=MAX_IDLE, reachable_spawns=True)


def initial(horizon, environment):
    return dict(stage=0, episodes=0, successes=0, idle_seconds=0., seconds=0.,
                horizon=horizon, environment=environment)


def advance(state, summary):
    state = dict(state)
    if state['stage'] >= 2:
        return state
    for field, key in (('episodes', 'episodes'), ('idle_seconds', 'idle_seconds'), ('seconds', 'seconds')):
        state[field] += summary.get(key, 0)
    state['successes'] += summary.get('catch_probability', 0.) * summary.get('episodes', 0)
    if state['episodes'] >= MIN_EPISODES:
        ready = (state['successes'] / state['episodes'] >= MIN_SUCCESS
                 and state['idle_seconds'] / max(state['seconds'], 1e-9) <= MAX_IDLE)
        state.update(stage=state['stage'] + int(ready), episodes=0, successes=0, idle_seconds=0., seconds=0.)
    return state


def cases(cases, state):
    lesson = LESSONS[state['stage']]
    return [dict(case, lesson=lesson) for case in cases]
