"""A queued burst: schedules rounds; the gun emits each round's projectiles."""
import config
from creatures.trait import Trait


def cancel_burst(c):
    """Drop any queued rounds and a round offered to the gun this frame."""
    c.burst_remaining = 0
    c.burst_round_due = False


class BurstFire(Trait):
    """Queue rounds on an aligned trigger. An aligned queue finishes after release; an unaligned released
    trigger or a disabled gun cancels it. Each fired event consumes one round, regardless of volley size.
    Durations are seconds; on_frame receives frame units. State belongs to the Creature, so a trait can be shared.
    """
    NAME = 'burstFire'
    REQUIRES = ('gun',)

    def __init__(self, rounds=3, spacing=0.05, interval=0.25):
        if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 1 or spacing < 0 or interval <= 0:
            raise ValueError('burstFire: rounds must be a positive integer, spacing >= 0 and interval > 0')
        self.rounds, self.spacing, self.interval = rounds, spacing, interval

    def on_spawn(self, c, enc):
        c.fire_remaining = 0.0
        c.base_fire_interval = c.fire_interval = self.interval
        cancel_burst(c)

    def on_frame(self, c, enc, dt):
        c.fire_remaining = max(0.0, c.fire_remaining - dt / config.FPS)
        controls = c.controls
        if not controls.gun_enabled:
            cancel_burst(c)
            return
        ready = c.fire_remaining <= 1e-9
        if controls.fire and ready and controls.on_target and not c.burst_remaining:
            c.burst_remaining = self.rounds
        if c.burst_remaining and not controls.on_target and not controls.fire:
            cancel_burst(c)
        c.burst_round_due = bool(c.burst_remaining and ready and controls.on_target)

    def on_event(self, c, name, enc):
        if name == 'fired' and c.burst_round_due:
            c.burst_remaining -= 1
            c.fire_remaining = (self.spacing if c.burst_remaining else
                                getattr(c, 'fire_interval', self.interval))
            c.burst_round_due = False
