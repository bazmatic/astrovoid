"""What a neural Jelly senses, and how its policy's two continuous outputs become a heading and an acceleration.
Jellies share no messages: each sees only its own motion, the walls, its target and its nearest teammates."""
import math
import numpy as np
from hunter.senses import RAYS, ray_distances
from learning.policy import PolicySpec, RecurrentPolicy
from creatures.jelly_team import Intent, MAX_SPEED
from creatures.traits.rooted import wall_between

RAY_REACH = 550.           # px: how far a wall ray sees, as the crawler's senses do
DISTANCE_SCALE = 1600.     # px: about the arena diagonal, so a distance stays within [0, 1]
CLOSING_SCALE = 8.         # px per frame: closing speeds against fast ships, clipped to [-1, 1]
TEAMMATES = 4
BLOCK_DISTANCE = 30.       # px: the teacher brakes when a wall is this close along the way to its target
FULL = 3.                  # pre-tanh activation the teacher uses for "full" (tanh(3) ~ 0.995)

HEADS = (('heading', 2), ('accel', 2))
SELF = ('speed', 'heading_sin', 'heading_cos', 'velocity_forward', 'velocity_side') + tuple(f'ray_{i}' for i in range(RAYS))
TARGET = ('present', 'bearing_sin', 'bearing_cos', 'distance', 'closing_speed')
TEAM = ('present', 'bearing_sin', 'bearing_cos', 'distance', 'heading_sin', 'heading_cos', 'speed')
FEATURES = SELF + tuple(f'target_{n}' for n in TARGET)
FEATURES += tuple(f'teammate{i}_{n}' for i in range(TEAMMATES) for n in TEAM)
SPEC = PolicySpec('jelly_team', FEATURES, HEADS, version=1, continuous=('heading', 'accel'))
CRITIC_TARGETS = 4
CRITIC_MEMBERS = 8
CRITIC_SIZE = 2*5 + CRITIC_TARGETS*5 + CRITIC_MEMBERS*7


def facing(c):
    """The Jelly's facing in world radians: its steered facing, else its direction of motion, else its angle."""
    f = getattr(c, 'jelly_facing', None)
    if f is not None:
        return f
    return math.atan2(c.vy, c.vx) if (c.vx or c.vy) else math.radians(c.angle)


def clip(v, lo=-1., hi=1.):
    return max(lo, min(hi, v))


def walls_near(maze, origin, reach):
    grid = getattr(maze, 'spatial_grid', None)
    walls = list(grid.get_nearby_walls(origin, reach)) if grid is not None else list(maze.walls)
    walls = [w for w in walls + list(getattr(maze, 'gate_segments', ())) if getattr(w, 'active', True)]
    starts = np.array([w.start for w in walls], dtype=float).reshape(-1, 2)
    ends = np.array([w.end for w in walls], dtype=float).reshape(-1, 2)
    return starts, ends


def rays(c, maze, heading, reach=RAY_REACH):
    starts, ends = walls_near(maze, c.get_pos(), reach)
    return ray_distances(c.get_pos(), math.degrees(heading), starts, ends, reach)


def relative(c, f, pos):
    """Bearing sin/cos relative to facing f and normalised distance to pos."""
    dx, dy = pos[0]-c.x, pos[1]-c.y
    d = math.hypot(dx, dy)
    bearing = math.atan2(dy, dx) - f
    if d == 0:
        return 0., 1., 0.
    return math.sin(bearing), math.cos(bearing), min(1., d/DISTANCE_SCALE)


def observe(team, c):
    enc = team.enc
    f = facing(c)
    cf, sf = math.cos(f), math.sin(f)
    x = [min(1., math.hypot(c.vx, c.vy)/MAX_SPEED), sf, cf,
         clip((c.vx*cf+c.vy*sf)/MAX_SPEED), clip((-c.vx*sf+c.vy*cf)/MAX_SPEED)]
    x += list(rays(c, team.maze, f)/RAY_REACH)
    entity = enc.target_entity_for(c)
    if entity is None:
        x += [0.]*len(TARGET)
    else:
        pos = entity.get_pos()
        bs, bc, d = relative(c, f, pos)
        dx, dy = pos[0]-c.x, pos[1]-c.y
        dist = math.hypot(dx, dy) or 1.
        tvx, tvy = getattr(entity, 'vx', 0.), getattr(entity, 'vy', 0.)
        closing = -((tvx-c.vx)*dx + (tvy-c.vy)*dy)/dist
        x += [1., bs, bc, d, clip(closing/CLOSING_SCALE)]
    others = sorted((o for o in team.members() if o is not c),
                    key=lambda o: (math.dist(c.get_pos(), o.get_pos()), o.agent_id))[:TEAMMATES]
    for i in range(TEAMMATES):
        if i >= len(others):
            x += [0.]*len(TEAM)
            continue
        o = others[i]
        bs, bc, d = relative(c, f, o.get_pos())
        of = facing(o) - f
        x += [1., bs, bc, d, math.sin(of), math.cos(of), min(1., math.hypot(o.vx, o.vy)/MAX_SPEED)]
    masks = {name: np.ones(size, bool) for name, size in HEADS}
    return np.asarray(x, np.float32), masks, ()


def intention(action):
    h, a = action
    return Intent(heading=math.tanh(float(h))*math.pi, accel=math.tanh(float(a)))


def critic(team, focal_agent=None):
    enc = team.enc
    world = enc.world

    def body(t):
        return [1., clip(t.x/1352, -2, 2), clip(t.y/878, -2, 2),
                clip(getattr(t, 'vx', 0.)/8), clip(getattr(t, 'vy', 0.)/8)]

    data = []
    for t in (world.ship, world.hunter):
        data += body(t) if t is not None and t.active and not getattr(t, 'observer', False) else [0.]*5
    members = team.members()
    allegiance = members[0].allegiance if members else 'enemy'
    others = [t for t in getattr(world, 'additional_targets', ()) if t.active]
    others += [o for o in enc.roster.alive() if o.allegiance != allegiance]
    for i in range(CRITIC_TARGETS):
        data += body(others[i]) if i < len(others) else [0.]*5
    if focal_agent is not None:
        members = sorted(members, key=lambda c: (c.agent_id != focal_agent, c.agent_id))
    for i in range(CRITIC_MEMBERS):
        if i < len(members):
            c = members[i]
            f = facing(c)
            data += [1., clip(c.x/1352, -2, 2), clip(c.y/878, -2, 2),
                     clip(c.vx/MAX_SPEED), clip(c.vy/MAX_SPEED), math.sin(f), math.cos(f)]
        else:
            data += [0.]*7
    return np.asarray(data, np.float32)


def teacher(c, enc):
    """Scripted pre-tanh labels: head straight for the target at full accel, braking when a wall blocks the way;
    with no target, hold the facing and coast."""
    pos = enc.target_for(c)
    if pos is None:
        return math.atanh(clip(math.remainder(facing(c), 2*math.pi)/math.pi, -.999, .999)), 0.
    desired = math.atan2(pos[1]-c.y, pos[0]-c.x)
    heading = math.atanh(clip(desired/math.pi, -.999, .999))
    ahead = float(rays(c, enc.maze, desired, BLOCK_DISTANCE*2)[0])
    blocked = ahead < BLOCK_DISTANCE and ahead < math.dist(c.get_pos(), pos) and wall_between(c.get_pos(), pos, enc.maze)
    return heading, -FULL if blocked else FULL


def enabled(x, action, masks):
    return [True, True]


class JellyDriver:
    def __init__(self, policy, greedy=True, seed=0):
        self.policy = policy
        self.greedy, self.seed = greedy, seed
        self.states, self.rngs = {}, {}

    def decide(self, team):
        members = team.members()
        batch = {c.agent_id: observe(team, c) for c in members}
        intents = {}
        for c in members:
            i = c.agent_id
            state = self.states.get(i, self.policy.initial_state())
            rng = self.rngs.setdefault(i, np.random.default_rng(np.random.SeedSequence([self.seed, i])))
            action, self.states[i] = self.policy.choose(batch[i][0], state, batch[i][1], self.greedy, rng)
            intents[i] = intention(action)
        team.commit(intents)


def load_policy(path):
    policy = RecurrentPolicy.load(path)
    if policy.spec != SPEC:
        raise ValueError('checkpoint task or observation/action schema does not match')
    return policy
