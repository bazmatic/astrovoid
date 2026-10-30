"""Dodge encounter construction, separate from creature mechanics and optimisation."""
import math
import random

from creatures.traits.rooted import wall_between
from creatures.traits.wallcrawl import contact
from creatures.wallcrawler_team import candidates
from learning.adapters.practice_targets import (
    PracticeTarget, TARGET_RADIUS, TARGET_SPEED_MIN, TARGET_SPEED_MAX, create_targets, spacious_start,
)

DODGE_TARGET_COUNT = 6
DODGE_BURST_SIZE = 3
DODGE_BURST_SPACING = 12
DODGE_FIRE_INTERVAL = 180
DODGE_JUMP_COST = .02
SHOOTING_SHARE = .75
AIM_WARMUP_ITERATIONS = 0  # stationary warmup completed in run137
AIM_TEAM_SIZE = 2
AIM_TARGET_DISTANCE = (120.,300.)


def setup_dodge(env, positions, seed):
    """Prefer starts with legal hops; reserve targets exposed from another landing area."""
    rng = random.Random(seed+29000)
    maze = env.world.maze
    reposition = []
    for c in env.team.members():
        trait = next(t for t in c.traits if t.NAME == 'wallCrawls')
        trial_positions = list(positions)
        rng.shuffle(trial_positions)
        original = c.get_pos()
        fallback = None
        for position in [original]+trial_positions[:60]:
            surface = contact(maze, position)
            if surface is None or not trait._attach(c, maze, surface):
                continue
            c.angle = math.degrees(math.atan2(c.wall_normal[1],c.wall_normal[0]))
            if any(target is not None and math.dist(c.get_pos(), target.get_pos()) < 180
                   for target in (env.world.ship, env.world.hunter)):
                continue
            if not spacious_start(maze, c.get_pos(), c.wall_normal):
                continue
            if any(other is not c and math.dist(c.get_pos(), other.get_pos()) < 45
                   for other in env.team.members()):
                continue
            sites = [s for s in candidates(c,env.enc) if s is not None]
            if not sites:
                continue
            if fallback is None:
                fallback = c.get_pos()
            found = None
            for site in sites:
                nx,ny = site.normal
                for _ in range(24):
                    depth,side = rng.uniform(25,100),rng.uniform(-110,110)
                    p = (site.position[0]+nx*depth-ny*side,site.position[1]+ny*depth+nx*side)
                    if not maze.is_open(p,TARGET_RADIUS+2) or wall_between(site.position,p,maze):
                        continue
                    if any(math.dist(p,other.get_pos())<TARGET_RADIUS+other.radius+10 for other in env.team.members()):
                        continue
                    outward = (p[0]-c.x)*c.wall_normal[0]+(p[1]-c.y)*c.wall_normal[1]
                    if outward > 0 and not wall_between(c.get_pos(),p,maze):
                        continue
                    if any(math.dist(p,t.get_pos())<TARGET_RADIUS*2+4 for t in reposition):
                        continue
                    found = p
                    break
                if found is not None:
                    break
            if found is not None:
                target = PracticeTarget(found,rng.uniform(0,2*math.pi),rng.uniform(TARGET_SPEED_MIN,TARGET_SPEED_MAX))
                target.reposition_target = True
                target.reposition_from = c.agent_id
                target.reposition_landing = site
                reposition.append(target)
                break
        else:
            # Some curved corridors have no concealed destination target, but still offer a hop.
            surface = contact(maze, fallback or original)
            if surface is not None:
                trait._attach(c,maze,surface)
                c.angle = math.degrees(math.atan2(c.wall_normal[1],c.wall_normal[0]))
        c.prev_x,c.prev_y = c.x,c.y
    targets = create_targets(env,seed,count=DODGE_TARGET_COUNT)
    # Replace ordinary targets; never exceed the announced count.
    for target in reposition:
        if all(math.dist(target.get_pos(),other.get_pos())>TARGET_RADIUS*2+4 for other in targets[:-1]):
            targets[-1:] = [target]
            targets.insert(0,targets.pop())
    for target in targets:
        target.burst_size = DODGE_BURST_SIZE
        target.burst_spacing = DODGE_BURST_SPACING
        target.fire_interval = DODGE_FIRE_INTERVAL
        target.fire_cooldown = rng.randint(60,120)
    return targets
