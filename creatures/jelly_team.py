"""The neural Jellies of one encounter: the shared physical limits on their motion, and the policy driver that sets
each one's Intent. Jellies coordinate only through what they observe; there is no message channel."""
from dataclasses import dataclass
import math

DECISION_FRAMES = 6
MAX_SPEED = 2.5                 # px per frame: the scripted Jelly's top speed at the hardest levels
ACCEL_RATE = 0.1                # px per frame, per frame, at full accel or full brake
TURN_RATE = math.radians(8.)    # radians per frame the Jelly's facing may turn toward the wanted heading


@dataclass(frozen=True)
class Intent:
    heading: float = 0.   # radians, world frame
    accel: float = 0.     # [-1, 1]: positive accelerates along the facing, negative brakes the current motion


def is_neural(c):
    return any(t.NAME == 'neuralJelly' for t in c.traits)


def jellies(enc):
    return [c for c in enc.creatures() if c.active and is_neural(c)]


def advance(c, intent, dt=1.):
    """One frame of motion under an intent: the facing turns toward the wanted heading at TURN_RATE, positive accel
    pushes along the facing, negative accel brakes the current motion, and speed stays in [0, MAX_SPEED]."""
    facing = getattr(c, 'jelly_facing', None)
    if facing is None:
        facing = math.atan2(c.vy, c.vx) if (c.vx or c.vy) else intent.heading
    turn = (intent.heading - facing + math.pi) % (2 * math.pi) - math.pi
    facing += max(-TURN_RATE, min(TURN_RATE, turn)) * dt
    c.jelly_facing = facing
    accel = max(-1., min(1., intent.accel))
    if accel >= 0:
        c.vx += math.cos(facing) * accel * ACCEL_RATE * dt
        c.vy += math.sin(facing) * accel * ACCEL_RATE * dt
    speed = math.hypot(c.vx, c.vy)
    if accel < 0 and speed > 0:
        slower = max(0., speed + accel * ACCEL_RATE * dt)
        c.vx, c.vy = c.vx * slower / speed, c.vy * slower / speed
        speed = slower
    if speed > MAX_SPEED:
        c.vx, c.vy = c.vx * MAX_SPEED / speed, c.vy * MAX_SPEED / speed
    c.x += c.vx * dt
    c.y += c.vy * dt
    c.angle = math.degrees(facing) % 360


class JellyTeam:
    def __init__(self, enc):
        self.enc = enc
        self.maze = enc.maze
        self.frames = 0
        self.external = False
        self.driver = None
        self._next_id = 0

    @property
    def neural(self):
        """Whether the Jellies follow intents (a policy or an external trainer) rather than scripted chasing."""
        return self.external or self.driver is not None

    def members(self):
        members = jellies(self.enc)
        for c in members:
            if not hasattr(c, 'agent_id'):
                c.agent_id = self._next_id
                self._next_id += 1
        return sorted(members, key=lambda c: c.agent_id)

    def commit(self, intents):
        for c in self.members():
            c.jelly_intent = intents.get(c.agent_id, Intent(heading=getattr(c, 'jelly_facing', None) or 0.))

    def before_frame(self):
        if not self.external and self.frames % DECISION_FRAMES == 0:
            if self.driver is None:
                policy = getattr(self.enc.world, 'jelly_policy', None)
                if policy is not None:
                    from learning.adapters.jelly import JellyDriver
                    self.driver = JellyDriver(policy)
            if self.driver is not None:
                self.driver.decide(self)
        self.frames += 1


def get_jelly_team(enc):
    team = getattr(enc, 'jelly_team', None)
    if team is None or team.maze is not enc.maze:
        team = enc.jelly_team = JellyTeam(enc)
    return team
