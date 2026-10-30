"""Audit escape demonstrations with matched, real-physics jump/no-jump replays.

Run with SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m
learning.validate_crawler_teacher --out /tmp/crawler-teacher.json
"""
import argparse
import json
import random
from pathlib import Path

from learning.adapters.crawler_scenario import CrawlerEnvironment, HOLDOUT_LEVELS
from learning.adapters.wallcrawler import teacher, teacher_action


def branch(case, prefix, actions, actor, jump, seconds=6, end_frame=None):
    """Replay the identical prefix, changing only this actor's detach decision."""
    # Scenario reset and production creature traits use Python's global RNG.
    # A counterfactual must not change the parent encounter's future randomness.
    state = random.getstate()
    env = CrawlerEnvironment(horizon=60)
    try:
        env.reset(**case)
        for decision in prefix:
            env.step(decision)
        c = next(c for c in env.team.members() if c.agent_id == actor)
        from creatures.traits.rooted import wall_between
        import math
        visible={i for i,t in enumerate(env.world.additional_targets)
                 if t.active and math.dist(c.get_pos(),t.get_pos())<=c.gun_range and
                 not wall_between(c.get_pos(),t.get_pos(),env.world.maze)}
        contact_context=[]
        original_contact=env.contact_hit
        def trace_contact(body):
            if body is c and c.active:
                nearby=[i for i,t in enumerate(env.world.additional_targets) if t.active and
                        math.dist(c.get_pos(),t.get_pos())<=c.radius+t.radius+2]
                contact_context.append(dict(frame=env.frames,nearby_targets=nearby,
                                             visible_at_launch=[i in visible for i in nearby]))
            original_contact(body)
        env.contact_hit=trace_contact
        start = c.get_pos()
        before = env.agent_contact_hits[actor]
        before_jumps = env.agent_jumps[actor]
        first = dict(actions)
        a = first[actor]
        first[actor] = a[:3] + (int(jump),) + a[4:]
        result = env.step(first)
        launched = env.agent_jumps[actor]>before_jumps
        deadline = end_frame if end_frame is not None else env.frames + seconds * 60 - 6
        landed = False
        max_distance = 0.
        while True:
            max_distance = max(max_distance, math.dist(start, c.get_pos()))
            if not landed and launched and c.active and c.wall_state == 'attached' and max_distance > c.radius * 3:
                landed = True
                # An escape must survive the landing's actual jump cooldown too.
                deadline = min(deadline, env.frames + 60)
            if not c.active or env.frames >= deadline or result.terminated or result.truncated:
                break
            # No additional jumps: isolate whether the demonstrated launch itself works.
            result = env.step({other.agent_id: teacher(other, env.enc)
                               for other in env.team.members()})
        return dict(alive=bool(c.active), contacts=env.agent_contact_hits[actor]-before,
                    launched=launched, landed=landed, distance=max_distance, frames=env.frames,
                    state=c.wall_state, contact_context=contact_context)
    finally:
        env.close()
        random.setstate(state)


def audit(case, horizon=12):
    env = CrawlerEnvironment(horizon=horizon)
    prefix, demonstrations = [], []
    legal_ticks = 0
    preparation_ticks = 0
    try:
        snapshot = env.reset(**case)
        while True:
            actions = {i: teacher_action(env, i, (1, 1, 0, 0, 0, 0))
                       for i in snapshot.observations}
            legal_ticks += sum(bool(m['detach'][1]) for m in snapshot.masks.values())
            preparation_ticks += sum(c.wall_state=='attached' and actions[c.agent_id][0]==1 and
                                     actions[c.agent_id][:3]!=teacher(c,env.enc)[:3]
                                     for c in env.team.members())
            for actor, action in actions.items():
                if action[3]:
                    jumped = branch(case, prefix, actions, actor, True)
                    stayed = branch(case, prefix, actions, actor, False, end_frame=jumped['frames'])
                    demonstrations.append(dict(actor=actor, frame=env.frames,
                        landing=action[4], jump=jumped, no_jump=stayed,
                        safe=jumped['launched'] and jumped['alive'] and jumped['contacts'] == 0,
                        avoided_contact=(jumped['launched'] and jumped['alive'] and jumped['contacts'] == 0 and
                                         (not stayed['alive'] or stayed['contacts'] > 0))))
            result = env.step(actions)
            prefix.append(actions)
            snapshot = result.snapshot
            if result.terminated or result.truncated:
                break
        return dict(case=case, legal_ticks=legal_ticks, preparation_ticks=preparation_ticks, demonstrations=demonstrations,
                    alive=result.events['alive'], contacts=result.events['contact_hits_taken'],
                    seconds=result.events['seconds'])
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seeds', type=int, nargs='+', default=[1000,1001])
    options = parser.parse_args()
    rows = []
    for level in HOLDOUT_LEVELS:
        for seed in options.seeds:
            row = audit(dict(seed=seed, level=level, team_size=2,
                             opponents='practice', practice_stage='pursuit'))
            rows.append(row)
            print(f'level {level} seed {seed}: alive {row["alive"]}/2, '
                  f'jumps {len(row["demonstrations"])}', flush=True)
    demos = [d for row in rows for d in row['demonstrations']]
    summary = dict(crawlers=2*len(rows), survivors=sum(r['alive'] for r in rows),
                   preparation_ticks=sum(r['preparation_ticks'] for r in rows),
                   demonstrations=len(demos), safe=sum(d['safe'] for d in demos),
                   avoided_contacts=sum(d['avoided_contact'] for d in demos),
                   landed=sum(d['jump']['landed'] for d in demos))
    # A pass requires both coverage and safe, useful escapes; zero jumps never passes.
    summary['passed'] = bool(all(row['demonstrations'] for row in rows) and
                             all(d['safe'] and d['avoided_contact'] and d['jump']['landed']
                                 for d in demos))
    options.out.write_text(json.dumps(dict(summary=summary, cases=rows), indent=2)+'\n')
    print(json.dumps(summary), flush=True)
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
