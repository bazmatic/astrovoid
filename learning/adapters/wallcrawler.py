"""Local wall-relative senses and factored actions for a communicating crawler."""
import math
import numpy as np
from learning.policy import PolicySpec, RecurrentPolicy
from creatures.wallcrawler_team import Intent, candidates, DECISION_FRAMES, RADIO_RANGE
from creatures.traits.rooted import wall_between

HEADS = (('move', 3), ('aim', 2), ('fire', 2), ('detach', 2), ('landing', 8), ('message', 8))
SELF = ('attached', 'stunned', 'returning', 'tangent_speed', 'normal_speed', 'aim_sin', 'aim_cos',
        'health', 'reload', 'stun', 'detach_cooldown', 'normal_x', 'normal_y', 'angular_velocity')
TARGET = ('present', 'tangent', 'normal', 'distance', 'tangent_velocity', 'normal_velocity')
TEAM = ('present', 'visible', 'tangent', 'normal', 'distance', 'attached', 'stunned', 'returning')
FEATURES = SELF + tuple(f'{role}_{n}' for role in ('player', 'hunter') for n in TARGET)
FEATURES += tuple(f'target{i}_{n}' for i in range(6) for n in TARGET+('radius',))
FEATURES += tuple(f'bullet{i}_{n}' for i in range(4) for n in TARGET)
FEATURES += tuple(f'teammate{i}_{n}' for i in range(5) for n in TEAM+tuple(f'message{k}' for k in range(8)))
FEATURES += tuple(f'landing{i}_{n}' for i in range(8) for n in ('present', 'tangent', 'normal', 'distance'))
SPEC = PolicySpec('wallcrawler_team', FEATURES, HEADS, version=5, continuous=('aim',))
LEGACY_SPEC = PolicySpec('wallcrawler_team', FEATURES,
                         tuple((name,3 if name=='aim' else size) for name,size in HEADS), version=4)
CRITIC_SIZE = 2*5+24*5+6*8


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
    for target in (enc.ship, enc.hunter):
        visible = (target is not None and target.active and not getattr(target, 'observer', False)
                   and math.dist(c.get_pos(), target.get_pos()) <= c.gun_range
                   and not wall_between(c.get_pos(), target.get_pos(), enc.maze))
        x += vector(c, target.get_pos(), (target.vx-vx, target.vy-vy)) if visible else [0]*6
    practice = [target for target in [enc.ship,enc.hunter]+list(getattr(enc.world,'additional_targets',()))
                if target is not None and target.active and not getattr(target,'observer',False) and math.dist(c.get_pos(),target.get_pos()) <= c.gun_range
                and not wall_between(c.get_pos(),target.get_pos(),enc.maze)]
    practice.sort(key=lambda target:math.dist(c.get_pos(),target.get_pos()))
    for i in range(6):
        target=practice[i] if i<len(practice) else None
        x += vector(c,target.get_pos(),(target.vx-vx,target.vy-vy))+[getattr(target,'radius',9)/550] if target is not None else [0]*7
    threats = [p for p in enc.world.projectiles if p.active and not p.is_enemy
               and math.dist(c.get_pos(), p.get_pos()) <= c.gun_range
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
        masks['move'] = np.array([False, True, False])
    if c.wall_state=='stunned':
        masks['aim'] = np.zeros(2, bool)
        masks['fire'] = np.array([True, False])
    legal_sites = np.array([site is not None for site in sites])
    masks['detach'] = np.array([True, attached and c.wall_attach_cooldown <= 0 and legal_sites.any()])
    masks['landing'] = legal_sites if legal_sites.any() else np.array([True]+[False]*7)
    return np.asarray(x, np.float32), masks, sites


def intention(action, legacy=False):
    move, aim, fire, detach, landing, message = action
    return Intent(int(move)-1, aim-1 if legacy else math.tanh(float(aim)), bool(fire),
                  bool(detach), int(landing), int(message))


def critic(team, focal_agent=None):
    data = []
    for target in (team.enc.ship, team.enc.hunter):
        data += ([1, target.x/1352, target.y/878, target.vx/8, target.vy/8]
                 if target is not None and target.active and not getattr(target, 'observer', False) else [0]*5)
    targets = list(getattr(team.enc.world,'additional_targets',()))[:24]
    for i in range(24):
        target = targets[i] if i<len(targets) else None
        data += [1,target.x/1352,target.y/878,target.vx/8,target.vy/8] if target is not None and target.active else [0]*5
    members = team.members()
    if focal_agent is not None:
        members = sorted(members,key=lambda c:(c.agent_id!=focal_agent,c.agent_id))
    for i in range(6):
        if i < len(members):
            c = members[i]
            data += [1, c.x/1352, c.y/878, c.vx/8, c.vy/8, c.hit_points/4,
                     float(c.wall_state == 'attached'), c.gun_charge]
        else:
            data += [0]*8
    return np.asarray(data, np.float32)


def teacher(c, enc):
    """Scripted movement, aim and fire labels; escape labels are supplied separately."""
    target = enc.target_for(c)
    aim = 0
    fire = False
    if (target is not None and math.dist(c.get_pos(),target)<=c.gun_range
            and not wall_between(c.get_pos(),target,enc.maze)):
        desired = math.degrees(math.atan2(target[1]-c.y, target[0]-c.x))
        off = (desired-c.angle+180) % 360-180
        aim = 20. if off > 9 else (-20. if off < -9 else 0.)
        outward = (target[0]-c.x)*c.wall_normal[0]+(target[1]-c.y)*c.wall_normal[1]
        fire = c.wall_state != 'stunned' and (c.wall_state!='attached' or outward > 0) and abs(off) < 12 and math.dist(c.get_pos(), target) <= c.gun_range
    move = int(c.walk_direction) if c.wall_state == 'attached' else 0
    return (move+1, aim, int(fire), 0, 0, 0)


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
            masks = dict(batch[i][1])
            legacy = self.policy.spec == LEGACY_SPEC
            if legacy:
                masks['aim'] = np.ones(3,bool) if c.wall_state=='attached' else np.array([False,True,False])
            action, self.states[i] = self.policy.choose(batch[i][0], state, masks, self.greedy, rng)
            actions[i] = intention(action,legacy=legacy)
        team.commit(actions, {i: v[2] for i, v in batch.items()})


def enabled(x, action, masks):
    attached = bool(x[0])
    return [attached and np.count_nonzero(masks['move'])>1, not bool(x[1]), not bool(x[1]), attached and bool(masks['detach'][1]),
            attached and bool(action[3]), True]


def teacher_action(env, agent_id, sampled):
    c = next(c for c in env.team.members() if c.agent_id == agent_id)
    labels = teacher(c, env.enc)
    action=labels[:3]+(0, sampled[4], sampled[5])
    if getattr(env,'practice_stage',None)=='pursuit':
        from learning.adapters.crawler_jump_teacher import defensive_jump
        action=defensive_jump(env,c,action)
    return action


def load_policy(path):
    """Gameplay may use the current actuator or an unchanged legacy categorical pilot."""
    policy = RecurrentPolicy.load(path)
    if policy.spec not in (SPEC, LEGACY_SPEC):
        raise ValueError('checkpoint task or observation/action schema does not match')
    return policy


def load_transfer_policy(path):
    """Keep the recurrent backbone and discrete controls; seed the new aim actuator."""
    policy = load_policy(path)
    if policy.spec == SPEC:
        return policy
    from learning.continuous import INITIAL_LOG_STD
    params = {key:value.copy() for key,value in policy.params.items()}
    old_w, old_b = params['aim_w'], params['aim_b']
    params['aim_w'] = np.stack(((old_w[2]-old_w[0])*.5, np.zeros_like(old_w[0])))
    params['aim_b'] = np.array([(old_b[2]-old_b[0])*.5, INITIAL_LOG_STD],np.float32)
    return RecurrentPolicy(params, policy.mean.copy(), policy.scale.copy(), SPEC)
