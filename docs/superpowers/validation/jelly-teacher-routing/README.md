# Jelly teacher route finding — 2026-10-31

The teacher reuses `hunter.maze_route.MazeRoutes.route` and the existing body-clearance geometry. It selects a visible waypoint towards the quarry, slows for corners, and brakes when no route is available. Route searches now check live gates separately from cached static-wall connectivity. Policy observations and default imitation settings are unchanged.

## Held-out navigation benchmark

Six `jelly_scenario.evaluation_cases(1)` episodes, each 60 seconds; one Jelly, original reward settings, levels 15/20/23, seeds 1000/1001. The old teacher is the implementation at main commit `c1d3a42`. The scripted baseline uses `JellyEnvironment(scripted=True)`. No optimizer or student policy is involved in these scores.

| Level | Seed | Old teacher catches | Routed teacher catches | Scripted Jelly catches |
|---|---:|---:|---:|---:|
| 15 | 1000 | 1 | 4 | 3 |
| 15 | 1001 | 0 | 0 | 0 |
| 20 | 1000 | 0 | 0 | 2 |
| 20 | 1001 | 0 | 0 | 0 |
| 23 | 1000 | 1 | 5 | 10 |
| 23 | 1001 | 1 | 8 | 10 |
| **Catches/minute** | | **0.50** | **2.83** | **4.17** |

For a current-teacher reproduction, run this loop with dummy SDL audio/video and the repository venv:

```python
from learning.adapters import jelly, jelly_scenario as scenario

env = scenario.JellyEnvironment(horizon=60)
try:
    for case in scenario.evaluation_cases(1):
        case = dict(case)
        seed = case.pop('seed')
        env.reset(seed, **case)
        while True:
            actions = {c.agent_id: jelly.teacher(c, env.enc) for c in env.team.members()}
            result = env.step(actions)
            if result.terminated or result.truncated:
                break
        print(case['level'], seed, result.events['catches'])
finally:
    env.close()
```

This is a small navigation benchmark, not proof of imitation learning quality or team/ship-fight performance. The cell graph can still report no route around gates or disconnected pockets. A teacher with maze knowledge can also choose actions a student with local observations cannot infer immediately. Bootstrap remains off pending a separate student experiment.

## Verification

- `tests/test_neural_jelly.py tests/test_replay_general.py tests/test_jelly_reward_settings.py tests/test_run_selection_gate.py tests/test_hunter_perception.py tests/test_senses.py`: **118 passed**.
- Subsequently added live gate close/reopen regression in the existing perception suite: `tests/test_hunter_perception.py -k route`: **2 passed**.
- New motion tests navigate a body around a wall and a gate without clipping either, and verify braking for an unreachable target and recovery after a wall opens.
- Existing demonstration collection, policy loading, rewards, replay and selection checks passed. No full-suite rerun or real-display game check; no rendering changes.
- No training process or dashboard was restarted for this change.
