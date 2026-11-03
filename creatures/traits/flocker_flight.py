"""Head articulation and optional learned flight/perching for ordinary Flockers."""
import math
from creatures.trait import Trait
from creatures.flocker_team import Intent, get_flocker_team, clamp, offset, visible, HEAD_RATE, HEAD_LIMIT


class FlockerFlight(Trait):
    NAME = 'flockerFlight'
    REQUIRES = ('thrusters', 'gun')
    LIVE = ('flocker_target', 'flocker_surface')

    def on_spawn(self, c, enc):
        c.flocker_intent = Intent()
        c.flocker_head = 0.
        c.flocker_throttle = 0.
        c.flocker_perched = False
        c.flocker_surface = None
        c.flocker_normal = (0., -1.)
        c.flocker_quiet = 0.
        c.flocker_attach_cooldown = 0.
        c.flocker_perch_paid = False
        c.flocker_target = None
        c.flocker_perch_attempts = 0
        c.flocker_hard_landings = 0
        c.flocker_alarm_since = None
        c.flocker_wake_latency = 0

    def on_frame(self, c, enc, dt):
        team = get_flocker_team(enc)
        if team.legacy:
            c.flocker_aim_enabled = False
            return
        c.flocker_aim_enabled = True
        c.flocker_attach_cooldown = max(0., c.flocker_attach_cooldown-dt)
        seen = visible(enc, c)
        c.flocker_quiet = 0. if seen or team.alerted(c) else c.flocker_quiet+dt
        if c.flocker_perched and not getattr(c.flocker_surface, 'active', False):
            team.release(c)
        if team.neural:
            intent = c.flocker_intent
            slots = team.targets(c)
            requested = slots[intent.target-1] if 1 <= intent.target <= 4 else None
            if requested is not None:
                c.flocker_target = requested
            elif all(c.flocker_target is not t for t in seen):
                c.flocker_target = min(seen, key=lambda t: math.dist(c.get_pos(), t.get_pos()), default=None)
            c.controls.heading = None
            c.controls.turn = clamp(intent.turn)
            c.controls.thrust = clamp(intent.throttle, 0., 1.)
            c.flocker_head = clamp(c.flocker_head+clamp(intent.head)*HEAD_RATE*dt, -HEAD_LIMIT, HEAD_LIMIT)
            c.controls.aim = c.flocker_target.get_pos() if c.flocker_target is not None else None
            c.controls.fire = intent.fire and c.flocker_target is not None and math.dist(c.get_pos(), c.flocker_target.get_pos()) <= c.gun_range
            if intent.perch == 1:
                team.attach(c)
        else:
            if c.controls.aim is not None:
                desired = offset(math.degrees(math.atan2(c.controls.aim[1]-c.y, c.controls.aim[0]-c.x))-c.angle)
                delta = offset(clamp(desired, -HEAD_LIMIT, HEAD_LIMIT)-c.flocker_head)
                c.flocker_head = clamp(c.flocker_head+clamp(delta, -HEAD_RATE*dt, HEAD_RATE*dt), -HEAD_LIMIT, HEAD_LIMIT)
        if c.flocker_perched:
            c.controls.turn, c.controls.thrust = 0., 0.
            c.vx = c.vy = 0.
        c.flocker_throttle = clamp(c.controls.thrust, 0., 1.)

    def on_event(self, c, name, enc):
        if name == 'hit_wall':
            c.flocker_hard_landings += 1

    def on_death(self, c, enc):
        get_flocker_team(enc).forget(c)
