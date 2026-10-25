"""Temporary comic size and one-hit vulnerability, independent of enemy health/traits."""
import config


class Inflation:
    SHRINK_FRAMES = 15.0

    def __init__(self):
        self.remaining = 0.0
        self.multiplier = 1.0
        self.shrink_frames = self.SHRINK_FRAMES

    @property
    def active(self):
        return self.remaining > 0

    @property
    def scale(self):
        return 1+(self.multiplier-1)*min(1.0,self.remaining/self.shrink_frames)

    def update(self, dt):
        self.remaining = max(0.0,self.remaining-dt)

    def on_hit(self, creature, shot, encounter):
        if self.active:
            creature.hit_points = 0
            creature.emit('hit',encounter)
            encounter.kill(creature,shot)
            return True
        definition = getattr(shot,'definition',None)
        duration = getattr(definition,'inflation_seconds',0.0)
        if duration > 0:
            self.remaining = duration*config.FPS
            self.shrink_frames = min(self.SHRINK_FRAMES,self.remaining/4)
            self.multiplier = definition.inflation_scale
            creature.emit('inflated',encounter)
            encounter.world.sound_manager.play_inflation()
            return True
        return False
