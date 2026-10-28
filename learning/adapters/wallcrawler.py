"""Local wall-relative senses and factored actions for a communicating crawler."""
import math
import numpy as np
from learning.policy import PolicySpec, RecurrentPolicy
from creatures.wallcrawler_team import Intent, candidates, DECISION_FRAMES, RADIO_RANGE
from creatures.traits.rooted import wall_between

HEADS = (('move', 3), ('aim', 3), ('fire', 2), ('detach', 2), ('landing', 8), ('message', 8))
SELF = ('attached', 'stunned', 'returning', 'tangent_speed', 'normal_speed', 'aim_sin', 'aim_cos',
        'health', 'reload', 'stun', 'detach_cooldown', 'normal_x', 'normal_y', 'angular_velocity')
TARGET = ('present', 'tangent', 'normal', 'distance', 'tangent_velocity', 'normal_velocity')
TEAM = ('present', 'visible', 'tangent', 'normal', 'distance', 'attached', 'stunned', 'returning')
FEATURES = SELF + tuple('target_'+n for n in TARGET)
FEATURES += tuple(f'bullet{i}_{n}' for i in range(4) for n in TARGET)
FEATURES += tuple(f'teammate{i}_{n}' for i in range(5) for n in TEAM+tuple(f'message{k}' for k in range(8)))
FEATURES += tuple(f'landing{i}_{n}' for i in range(8) for n in ('present', 'tangent', 'normal', 'distance'))
SPEC = PolicySpec('wallcrawler_team', FEATURES, HEADS, version=2)
CRITIC_SIZE = 4+6*8


def vector(c, pos, velocity=(0, 0)):
    nx, ny = c.wall_normal
    tx, ty = -ny, nx
    dx, dy = pos[0]-c.x, pos[1]-c.y
    return [1, (dx*tx+dy*ty)/550, (dx*nx+dy*ny)/550, math.hypot(dx, dy)/550,
            (velocity[0]*tx+velocity[1]*ty)/8, (velocity[0]*nx+velocity[1]*ny)/8]


def observe(team, c, muted=False):
    enc = team.enc
    nx, ny = c.wall_normal
    angle = math.radians(c.angle)-math.atan2(ny, nx)
    vx,vy = ((c.x-getattr(c,'prev_x',c.x),c.y-getattr(c,'prev_y',c.y)) if c.wall_state=='attached' else (c.vx,c.vy))
    x = [int(c.wall_state == s) for s in ('attached', 'stunned', 'returning')]
    x += [(-ny*vx+nx*vy)/8, (nx*vx+ny*vy)/8, math.sin(angle), math.cos(angle),
          c.hit_points/c.max_hit_points, c.gun_charge, c.wall_stun/36, c.wall_attach_cooldown/60, nx, ny, c.wall_angular_velocity/(4*math.pi)]
    ship = enc.ship
    visible = ship is not None and ship.active and math.dist(c.get_pos(), ship.get_pos()) <= 550
    visible = visible and not wall_between(c.get_pos(), ship.get_pos(), enc.maze)
    x += vector(c, ship.get_pos(), (ship.vx-vx, ship.vy-vy)) if visible else [0]*6
    threats = [p for p in enc.world.projectiles if p.active and not p.is_enemy
               and math.dist(c.get_pos(), p.get_pos()) <= 550
               and not wall_between(c.get_pos(), p.get_pos(), enc.maze)]
    threats.sort(key=lambda p: math.dist(c.get_pos(), p.get_pos()))
    for i in range(4):
        x += vector(c, threats[i].get_pos(), (threats[i].vx-vx, threats[i].vy-vy)) if i < len(threats) else [0]*6
    inbox = team.inbox(c, muted)
    neighbours = []
    for other in team.members():
        if other is c or math.dist(c.get_pos(), other.get_pos()) > RADIO_RANGE:
            continue
        seen = not wall_between(c.get_pos(), other.get_pos(), enc.maze)
        if seen or inbox.get(other.agent_id, 0):
            neighbours.append((other, seen))
    neighbours.sort(key=lambda item: (math.dist(c.get_pos(), item[0].get_pos()), item[0].agent_id))
    for i in range(5):
        if i >= len(neighbours):
            x += [0]*16
            continue
        other, seen = neighbours[i]
        rel = vector(c, other.get_pos())
        x += [1, int(seen), *rel[1:4]]
        x += [int(seen and other.wall_state == s) for s in ('attached', 'stunned', 'returning')]
        symbol = inbox.get(other.agent_id, 0)
        x += [int(symbol == k) for k in range(8)]
    sites = candidates(c, enc) if c.wall_state == 'attached' and c.wall_attach_cooldown <= 0 else [None]*8
    for site in sites:
        x += vector(c, site.position)[:4] if site is not None else [0]*4
    attached = c.wall_state == 'attached'
    masks = {name: np.ones(size, bool) for name, size in HEADS}
    if not attached:
        masks['move'] = masks['aim'] = np.array([False, True, False])
        masks['fire'] = np.array([True, False])
    legal_sites = np.array([site is not None for site in sites])
    masks['detach'] = np.array([True, attached and c.wall_attach_cooldown <= 0 and legal_sites.any()])
    masks['landing'] = legal_sites if legal_sites.any() else np.array([True]+[False]*7)
    return np.asarray(x, np.float32), masks, sites


def intention(action):
    move, aim, fire, detach, landing, message = action
    return Intent(move-1, aim-1, bool(fire), bool(detach), landing, message)


def critic(team):
    ship = team.enc.ship
    data = [ship.x/1352, ship.y/878, ship.vx/8, ship.vy/8]
    members = team.members()
    for i in range(6):
        if i < len(members):
            c = members[i]
            data += [1, c.x/1352, c.y/878, c.vx/8, c.vy/8, c.hit_points/4,
                     float(c.wall_state == 'attached'), c.gun_charge]
        else:
            data += [0]*8
    return np.asarray(data, np.float32)


def teacher(c, enc):
    """Labels only the three existing behaviours; communication/detachment are not imitation targets."""
    target = enc.target_for(c)
    aim = 0
    fire = False
    if (target is not None and math.dist(c.get_pos(),target)<=c.gun_range
            and not wall_between(c.get_pos(),target,enc.maze)):
        desired = math.degrees(math.atan2(target[1]-c.y, target[0]-c.x))
        off = (desired-c.angle+180) % 360-180
        aim = 1 if off > 9 else (-1 if off < -9 else 0)
        outward = (target[0]-c.x)*c.wall_normal[0]+(target[1]-c.y)*c.wall_normal[1]
        fire = c.wall_state == 'attached' and outward > 0 and abs(off) < 12 and math.dist(c.get_pos(), target) <= 550
    move = int(c.walk_direction) if c.wall_state == 'attached' else 0
    return (move+1, aim+1, int(fire), 0, 0, 0)


class CrawlerDriver:
    def __init__(self, policy, greedy=True, seed=0, muted=False):
        self.policy = policy
        self.greedy, self.seed, self.muted = greedy, seed, muted
        self.states, self.rngs = {}, {}

    def decide(self, team):
        batch = {c.agent_id: observe(team, c, self.muted) for c in team.members()}
        actions = {}
        for c in team.members():
            i = c.agent_id
            state = self.states.get(i, self.policy.initial_state())
            rng = self.rngs.setdefault(i, np.random.default_rng(np.random.SeedSequence([self.seed, i])))
            action, self.states[i] = self.policy.choose(batch[i][0], state, batch[i][1], self.greedy, rng)
            actions[i] = intention(action)
        team.commit(actions, {i: v[2] for i, v in batch.items()})


def enabled(x, action, masks):
    attached = bool(x[0])
    return [attached, attached, attached, attached and bool(masks['detach'][1]),
            attached and bool(action[3]), True]


def teacher_action(env, agent_id, sampled):
    c = next(c for c in env.team.members() if c.agent_id == agent_id)
    labels = teacher(c, env.enc)
    return labels[:3]+(0, sampled[4], sampled[5])
