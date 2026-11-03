"""Flocker decisions, local delayed signals and physical wall attachment.

The actor sees only local observations. Membership and messages are committed together,
so roster iteration order cannot leak a teammate's current decision.
"""
from dataclasses import dataclass
import math

DECISION_FRAMES = 6
SIGHT_RANGE = 550.
RADIO_RANGE = 300.
ALERT_FRAMES = 60
HEAD_RATE = 3.                    # degrees per simulation frame
HEAD_LIMIT = 90.
IDLE_FRAMES = 60


def clamp(value, low=-1., high=1.):
    return max(low, min(high, float(value)))


def offset(angle):
    return (angle + 180.) % 360. - 180.


@dataclass(frozen=True)
class Intent:
    turn: float = 0.
    throttle: float = 0.
    head: float = 0.
    fire: bool = False
    target: int = 0
    message: int = 0
    perch: int = 0                 # 0: hold, 1: request attachment, 2: release


def is_flocker(c):
    return any(t.NAME == 'flockerFlight' for t in c.traits)


def candidates(enc, c):
    targets = list(getattr(enc.world, 'additional_targets', ()))
    targets += [o for o in enc.creatures() if o is not c and o.allegiance != c.allegiance]
    if c.allegiance == 'enemy':
        targets += [getattr(enc.world, n, None) for n in ('ship', 'hunter')]
    unique = []
    for t in targets:
        if t is not None and t.active and not getattr(t, 'observer', False) and all(t is not o for o in unique):
            unique.append(t)
    return unique


def visible(enc, c):
    from creatures.traits.rooted import wall_between
    maze = enc.maze
    return [t for t in candidates(enc, c) if math.dist(c.get_pos(), t.get_pos()) <= SIGHT_RANGE
            and (maze is None or not wall_between(c.get_pos(), t.get_pos(), maze))]


def muzzle(c):
    """World mouth position and direction, also used by FlockerBody's head transform."""
    body = math.radians(c.angle)
    head = math.radians(c.angle + getattr(c, 'flocker_head', 0.))
    scale = c.radius * .7
    pivot = (c.x + math.cos(body)*scale*.48, c.y + math.sin(body)*scale*.48)
    return (pivot[0] + math.cos(head)*scale*.72, pivot[1] + math.sin(head)*scale*.72), math.degrees(head)


class FlockerTeam:
    def __init__(self, enc):
        self.enc, self.maze = enc, enc.maze
        self.frames = 0
        self.external = False
        self.muted = False
        self.legacy = False
        self.driver = None
        self._next_id = 0
        self.messages = {}
        self.pending = {}
        self.alerts = {}
        self.slots = {}

    @property
    def neural(self):
        return self.external or self.driver is not None

    def members(self):
        members = [c for c in self.enc.creatures() if c.active and is_flocker(c)]
        for c in members:
            if not hasattr(c, 'agent_id'):
                c.agent_id = self._next_id
            self._next_id = max(self._next_id, c.agent_id + 1)
        return sorted(members, key=lambda c: c.agent_id)

    def targets(self, c):
        """Stable visible slots: keep occupants until lost, refill holes by distance."""
        seen = visible(self.enc, c)
        old = self.slots.get(c.agent_id, [None]*4)
        slots = [t if any(t is s for s in seen) else None for t in old]
        for t in sorted(seen, key=lambda t: math.dist(c.get_pos(), t.get_pos())):
            if all(t is not s for s in slots) and None in slots:
                slots[slots.index(None)] = t
        self.slots[c.agent_id] = slots
        return slots

    def received(self, c):
        if self.muted:
            return {}
        return {i: symbol for i, (symbol, pos) in self.messages.items() if i != c.agent_id
                and math.dist(c.get_pos(), pos) <= RADIO_RANGE}

    def alerted(self, c):
        return not self.muted and any(i != c.agent_id and self.frames-report[0] <= ALERT_FRAMES
            and math.dist(c.get_pos(), report[1]) <= RADIO_RANGE
            for i, report in self.alerts.items())

    def target_report(self, c):
        """Latest local, direct-sighting snapshot; never a live target reference."""
        if self.muted:
            return None
        reports = [(report[0],i,report) for i,report in self.alerts.items()
                   if i!=c.agent_id and len(report)==4 and self.frames-report[0]<=ALERT_FRAMES
                   and math.dist(c.get_pos(),report[1])<=RADIO_RANGE]
        if not reports:
            return None
        _,_,report = max(reports,key=lambda entry:(entry[0],-entry[1]))
        return dict(position=report[2],velocity=report[3],age_frames=self.frames-report[0])

    def commit(self, intents):
        for c in self.members():
            c.flocker_intent = intents.get(c.agent_id, Intent())
            self.pending[c.agent_id] = (c.flocker_intent.message, c.get_pos())

    def prepare_decision(self):
        """Deliver prior signals once, before either the trainer or game observes this decision."""
        if self.frames % DECISION_FRAMES or getattr(self, '_prepared_frame', None) == self.frames:
            return
        self._prepared_frame = self.frames
        members = self.members()
        live = {c.agent_id for c in members}
        self.messages, self.pending = {i:p for i,p in self.pending.items() if i in live}, {}
        self.alerts = {i:a for i,a in self.alerts.items() if i in live and self.frames-a[0] <= ALERT_FRAMES}
        for i,report in getattr(self, '_sightings', {}).items():
            if i in live:
                self.alerts[i] = report
        self._sightings = {}
        for c in members:
            seen = visible(self.enc,c)
            if seen:
                target = min(seen,key=lambda t:(t is not c.flocker_target,math.dist(c.get_pos(),t.get_pos())))
                self._sightings[c.agent_id] = (self.frames,c.get_pos(),tuple(target.get_pos()),
                                               (getattr(target,'vx',0.),getattr(target,'vy',0.)))

    def before_frame(self):
        members = self.members()
        live = {c.agent_id for c in members}
        self.slots = {i:s for i,s in self.slots.items() if i in live}
        self.prepare_decision()
        for c in members:
            if c.flocker_perched and (visible(self.enc,c) or self.alerted(c)):
                if c.flocker_alarm_since is None:
                    c.flocker_alarm_since = self.frames
        if self.frames % DECISION_FRAMES == 0:
            if not self.external and self.driver is None:
                policy = getattr(self.enc.world, 'flocker_policy', None)
                if policy is not None:
                    from learning.adapters.flocker import FlockerDriver
                    self.driver = FlockerDriver(policy)
            if self.driver is not None and not self.external:
                self.driver.decide(self)
            for c in members:
                alarm = bool(visible(self.enc,c)) or self.alerted(c)
                if alarm:
                    c.flocker_quiet = 0.
                    c.flocker_perch_paid = False
                if c.flocker_perched and (alarm or c.flocker_intent.perch == 2):
                    self.release(c)
        self.frames += 1

    def release(self, c):
        if c.flocker_alarm_since is not None:
            c.flocker_wake_latency = max(c.flocker_wake_latency, self.frames-c.flocker_alarm_since)
        c.flocker_alarm_since = None
        c.flocker_perched = False
        c.flocker_surface = None
        c.flocker_attach_cooldown = 12.
        c.emit('takeoff', self.enc)

    def forget(self, c):
        if not hasattr(c, 'agent_id'):
            return  # A projectile can kill a newcomer before its first team decision.
        for mapping in (self.messages, self.pending, self.alerts, self.slots, getattr(self, '_sightings', {})):
            mapping.pop(c.agent_id, None)
        if self.driver is not None:
            self.driver.states.pop(c.agent_id, None)
            self.driver.rngs.pop(c.agent_id, None)

    def attach(self, c):
        from creatures.traits.wallcrawl import contact, clear
        if (self.maze is None or c.flocker_perched or c.flocker_quiet < IDLE_FRAMES
                or c.flocker_attach_cooldown > 0 or math.hypot(c.vx, c.vy) > c.max_speed*.25):
            return False
        surface = contact(self.maze, c.get_pos())
        if surface is None or abs(surface[3]-c.radius) > 5:
            return False
        c.flocker_perch_attempts += 1
        wall, foot, normal, _ = surface
        gap = c.radius + .5
        pos = (foot[0]+normal[0]*gap, foot[1]+normal[1]*gap)
        if not clear(self.maze, pos, c.radius):
            return False
        if any(o is not c and math.dist(pos, o.get_pos()) < c.radius+o.radius+2 for o in self.members()):
            return False
        c.x, c.y = pos
        c.prev_x, c.prev_y = pos
        c.vx = c.vy = 0.
        c.angle = math.degrees(math.atan2(normal[1], normal[0]))
        c.flocker_perched, c.flocker_surface, c.flocker_normal = True, wall, normal
        c.emit('perched', self.enc)
        return True


def get_flocker_team(enc):
    team = getattr(enc, 'flocker_team', None)
    if team is None or team.maze is not enc.maze:
        team = enc.flocker_team = FlockerTeam(enc)
    return team
