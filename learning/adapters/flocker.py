"""Local Flocker observations and mixed continuous/discrete policy actions."""
import math
import zipfile
import numpy as np
from hunter.senses import RAYS
from learning.adapters.jelly import rays, relative
from learning.policy import PolicySpec, RecurrentPolicy
from creatures.flocker_team import Intent, clamp, muzzle, offset, visible
from learning.flocker_aim import intercept_point
from learning.flocker_threat import threats, DANGER_MARGIN

HEADS = (('turn', 2), ('throttle', 2), ('head', 2), ('fire', 2), ('target', 5), ('message', 8), ('perch', 3))
SELF = ('vx', 'vy', 'heading_sin', 'heading_cos', 'throttle', 'reload', 'head_sin', 'head_cos',
        'perched', 'normal_sin', 'normal_cos', 'quiet', 'alert') + tuple(f'ray{i}' for i in range(RAYS))
TARGET = ('present', 'bearing_sin', 'bearing_cos', 'distance', 'vx', 'vy', 'selected',
          'aim_sin', 'aim_cos', 'lead_present', 'lead_sin', 'lead_cos', 'body_vx', 'body_vy',
          'facing_sin', 'facing_cos', 'immune', 'health')
THREATS = 2
THREAT = ('present', 'bearing_sin', 'bearing_cos', 'distance', 'vx', 'vy', 'miss', 'time')
TEAM = ('present', 'bearing_sin', 'bearing_cos', 'distance', 'heading_sin', 'heading_cos',
        'vx', 'vy', 'head_sin', 'head_cos', 'reload', 'perched') + tuple(f'message{i}' for i in range(8))
FEATURES = SELF + tuple(f'target{i}_{n}' for i in range(4) for n in TARGET)
FEATURES += tuple(f'teammate{i}_{n}' for i in range(8) for n in TEAM)
REPORT = ('report_present','report_bearing_sin','report_bearing_cos','report_distance','report_vx','report_vy','report_age')
FEATURES += REPORT + ('health',) + tuple(f'threat{i}_{n}' for i in range(THREATS) for n in THREAT)
SPEC = PolicySpec('flocker_team', FEATURES, HEADS, version=5, continuous=('turn', 'throttle', 'head'))
CRITIC_SIZE = 8*9 + 4*5 + 4*5 + 8


def aim_error(c, point):
    """sin/cos of the angle from where the muzzle points to `point`: zero error is (0, 1); the sign says which way to turn."""
    origin, heading = muzzle(c)
    error = math.radians(offset(math.degrees(math.atan2(point[1]-origin[1], point[0]-origin[0])) - heading))
    return math.sin(error), math.cos(error)


def lead_error(c, target, maze):
    """The same error towards where a shot must go to meet the moving target (the aim reward's intercept point);
    flagged absent, and the straight-at-it error, when no shot can reach it."""
    point = intercept_point(c, target, maze)
    return (0., *aim_error(c, target.get_pos())) if point is None else (1., *aim_error(c, point))


def facing_error(c, t):
    """sin/cos of how far target `t`'s heading is from pointing at bird `c`: (0, 1) means it is aimed straight at it."""
    angle = getattr(t, 'angle', None)
    if angle is None:
        return 0., 0.
    error = math.radians(angle)-math.atan2(c.y-t.y, c.x-t.x)
    return math.sin(error), math.cos(error)


def hit_points(c):
    return min(1., max(0., getattr(c, 'hit_points', 1.)/max(getattr(c, 'max_hit_points', 1.), .01)))


def observe(team, c):
    f = math.radians(c.angle)
    cf, sf = math.cos(f), math.sin(f)
    speed = max(c.max_speed, .01)
    h = math.radians(c.flocker_head)
    nx, ny = c.flocker_normal
    x = [clamp((c.vx*cf+c.vy*sf)/speed), clamp((-c.vx*sf+c.vy*cf)/speed), sf, cf,
         c.flocker_throttle, c.gun_charge, math.sin(h), math.cos(h), float(c.flocker_perched),
         ny, nx, min(1., c.flocker_quiet/60.), float(team.alerted(c))]
    x += list(rays(c, team.maze, f)/550.) if team.maze is not None else [1.]*RAYS
    targets = team.targets(c)
    for t in targets:
        if t is None:
            x += [0.]*len(TARGET)
        else:
            tvx, tvy = getattr(t,'vx',0.), getattr(t,'vy',0.)
            x += [1., *relative(c, f, t.get_pos()), clamp(tvx/8), clamp(tvy/8), float(t is c.flocker_target),
                  *aim_error(c, t.get_pos()), *lead_error(c, t, team.maze),
                  clamp((tvx*cf+tvy*sf)/8), clamp((-tvx*sf+tvy*cf)/8), *facing_error(c, t),
                  min(1., getattr(t, 'immunity_remaining', 0.)/max(getattr(t, 'damage_immunity', .5), .01)),
                  min(1., max(0., getattr(t, 'health', 0))/10.)]
    messages = team.received(c)
    others = sorted((o for o in team.members() if o is not c and math.dist(o.get_pos(), c.get_pos()) <= 550.),
                    key=lambda o: (math.dist(c.get_pos(),o.get_pos()),o.agent_id))[:8]
    for i in range(8):
        if i >= len(others):
            x += [0.]*len(TEAM)
        else:
            o = others[i]
            angle = math.radians(o.angle-c.angle)
            head = math.radians(o.angle+o.flocker_head-c.angle)
            symbol = messages.get(o.agent_id)
            x += [1., *relative(c, f, o.get_pos()), math.sin(angle), math.cos(angle),
                  clamp(o.vx/8), clamp(o.vy/8), math.sin(head), math.cos(head), o.gun_charge,
                  float(o.flocker_perched)] + [float(symbol == j) for j in range(8)]
    report = team.target_report(c)
    x += ([1.,*relative(c,f,report['position']),clamp(report['velocity'][0]/8),
           clamp(report['velocity'][1]/8),min(1.,report['age_frames']/60.)] if report else [0.]*len(REPORT))
    x.append(hit_points(c))
    incoming = threats(team.enc, c, THREATS)
    for i in range(THREATS):
        if i >= len(incoming):
            x += [0.]*len(THREAT)
            continue
        shot, frames, miss = incoming[i]
        ux, uy = shot.vx-c.vx, shot.vy-c.vy
        x += [1., *relative(c, f, (shot.x, shot.y)), clamp((ux*cf+uy*sf)/16), clamp((-ux*sf+uy*cf)/16),
              clamp(miss/(c.radius+getattr(shot, 'radius', 0.)+DANGER_MARGIN)/4), min(1., frames/60.)]
    masks = {name: np.ones(size, bool) for name,size in HEADS}
    masks['target'] = np.array([True]+[t is not None for t in targets])
    masks['fire'][1] = any(t is not None and math.dist(c.get_pos(),t.get_pos()) <= c.gun_range for t in targets) and c.gun_cooldown <= 6
    masks['perch'][1] = not c.flocker_perched and c.flocker_quiet >= 60 and not team.alerted(c)
    masks['perch'][2] = c.flocker_perched
    if c.flocker_perched:
        masks['turn'][:] = False
        masks['throttle'][:] = False
    return np.asarray(x, np.float32), masks, ()


def intention(action, perched=False):
    turn, throttle, head, fire, target, message, perch = action
    return Intent(0. if perched else math.tanh(float(turn)), 0. if perched else (math.tanh(float(throttle))+1.)*.5,
                  math.tanh(float(head)), bool(fire), int(target), int(message), int(perch))


def enabled(x, action, masks):
    return [bool(masks[n].any()) if n in SPEC.continuous else bool(masks[n].sum()>1) for n,_ in HEADS]


def critic(team, focal_agent=None):
    members = sorted(team.members(), key=lambda c: (c.agent_id != focal_agent, c.agent_id))
    data = []
    for i in range(8):
        if i < len(members):
            c = members[i]
            f = math.radians(c.angle)
            data += [1., c.x/1600, c.y/1600, c.vx/8, c.vy/8, math.sin(f), math.cos(f), c.gun_charge, float(c.flocker_perched)]
        else:
            data += [0.]*9
    from creatures.flocker_team import candidates
    targets = candidates(team.enc, members[0]) if members else []
    for i in range(4):
        t = targets[i] if i < len(targets) else None
        data += [1.,t.x/1600,t.y/1600,getattr(t,'vx',0.)/8,getattr(t,'vy',0.)/8] if t else [0.]*5
    # Appended after the original blocks so a critic from an earlier version keeps its weights by column.
    from learning.flocker_threat import hostile_shots
    anchor = members[0] if members else None
    shots = sorted(hostile_shots(team.enc), key=lambda s: math.hypot(s.x-anchor.x, s.y-anchor.y))[:4] if anchor else []
    for i in range(4):
        s = shots[i] if i < len(shots) else None
        data += [1., s.x/1600, s.y/1600, s.vx/8, s.vy/8] if s else [0.]*5
    data += [hit_points(members[i]) if i < len(members) else 0. for i in range(8)]
    return np.asarray(data, np.float32)


class FlockerDriver:
    def __init__(self, policy, greedy=True, seed=0):
        self.policy, self.greedy, self.seed = policy, greedy, seed
        self.states, self.rngs = {}, {}

    def decide(self, team):
        members = team.members()
        batch = {c.agent_id: observe(team,c) for c in members}
        live = set(batch)
        self.states = {i:s for i,s in self.states.items() if i in live}
        self.rngs = {i:r for i,r in self.rngs.items() if i in live}
        intents = {}
        for c in members:
            i = c.agent_id
            rng = self.rngs.setdefault(i, np.random.default_rng(np.random.SeedSequence([self.seed,i])))
            action, self.states[i] = self.policy.choose(batch[i][0], self.states.get(i,self.policy.initial_state()),
                                                       batch[i][1], self.greedy, rng)
            intents[i] = intention(action, c.flocker_perched)
        team.commit(intents)


def load_transfer_policy(path):
    """Keep learned behaviour; new report inputs begin with zero weights."""
    old = RecurrentPolicy.load(path)
    if old.spec==SPEC:
        return old
    if (old.spec.task!=SPEC.task or old.spec.version not in (2,3,4,5)
        or old.spec.heads!=SPEC.heads or old.spec.continuous!=SPEC.continuous):
        raise ValueError('checkpoint is not a compatible Flocker policy')
    where = {name:i for i,name in enumerate(old.spec.features)}
    embed = np.zeros((old.params['embed_w'].shape[0],len(FEATURES)),np.float32)
    mean,scale = np.zeros(len(FEATURES),np.float32),np.ones(len(FEATURES),np.float32)
    for i,name in enumerate(FEATURES):
        if name in where:
            j=where[name]
            embed[:,i],mean[i],scale[i]=old.params['embed_w'][:,j],old.mean[j],old.scale[j]
    return RecurrentPolicy(dict(old.params,embed_w=embed),mean,scale,SPEC)


def load_policy(path):
    try:
        return RecurrentPolicy.load(path, SPEC)
    except zipfile.BadZipFile as exc:
        raise ValueError(f'damaged Flocker policy archive: {exc}') from exc
