"""The neural Jelly brain: a shared policy picks each Jelly's heading and acceleration (see creatures.jelly_team).
With no policy it chases and drifts exactly like the scripted Jelly."""
from creatures.jelly_team import Intent, advance, get_jelly_team
from creatures.trait import Trait
from creatures.traits.brains import Chase
from creatures.traits.propulsion import Drift


class NeuralJelly(Trait):
    """Moves by its team's latest Intent: turning toward the wanted heading at a bounded rate, accelerating or braking,
    its speed between zero and the Jelly maximum. Without a policy it is a Chase brain with Drift at `speed`."""
    NAME = 'neuralJelly'

    def __init__(self, speed='aggressive_speed'):
        self.chase = Chase()
        self.drift = Drift(speed)

    def on_spawn(self, c, enc):
        self.chase.on_spawn(c, enc)
        self.drift.on_spawn(c, enc)
        c.jelly_intent = Intent()
        c.jelly_facing = None

    def on_frame(self, c, enc, dt):
        if get_jelly_team(enc).neural:
            advance(c, c.jelly_intent, dt)
            c.controls.heading = c.angle
            return
        c.jelly_facing = None
        self.chase.on_frame(c, enc, dt)
        self.drift.on_frame(c, enc, dt)
