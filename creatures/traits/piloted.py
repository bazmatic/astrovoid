"""A pilot: the creature follows a craft, a hunter ship its pilot flies exactly as it flies the allied hunter."""
import time
from dataclasses import replace

import config
from entities.hunter_ship import HunterShip
from creatures.trait import Trait
from hunter.flight import HunterFlight, NeuralPilot, WorkerPilot
from hunter.settings_for import hunter_settings_for
from hunter.surroundings import ProtagonistSurroundings

MODES = ('rules', 'neural')


class Pilot(Trait):
    """A `mode` pilot ('rules' or 'neural') flies a craft that hunts only the level's protagonist, and the creature
    follows it. Its shots are its allegiance's, at `shotStrength`, in its kind's colour.

    Each frame a push the creature took since the last (a blast, a gate, a ram) goes to the craft, which the pilot
    feels as a hit; the craft flies a frame; and the creature takes its place, speed, heading and engine. A neural pilot
    with no model installed never flies. It keeps `craft`, `flight` and `pilot_worker`; the last two are let go when it
    dies or the encounter closes."""
    NAME = 'pilot'
    LIVE = ('flight', 'pilot_worker')

    def __init__(self, mode: str, shotStrength: float = 1.0):
        if mode not in MODES:
            raise ValueError(f'pilot: mode must be one of {MODES}, not {mode!r}')
        self.mode, self.shot_strength = mode, shotStrength

    def on_spawn(self, c, enc):
        craft = HunterShip(c.get_pos(), replace(hunter_settings_for(self.mode), indestructible=True))
        craft.radius, craft.angle, craft.vx, craft.vy = c.radius, c.angle, c.vx, c.vy
        craft.SHOT_SOURCE = 'enemy' if c.allegiance == 'enemy' else 'hunter'
        craft.SHOT_STRENGTH = self.shot_strength
        craft.COLOR = tuple(c.kind.tuning.get('color', HunterShip.COLOR))
        c.craft, c.pilot_thrusting, c.pilot_worker, c.flight = craft, False, None, None
        if self.mode == 'rules':
            c.pilot_worker = enc.world.rules_worker()
            pilot = WorkerPilot(c.pilot_worker, time.monotonic)
        else:
            policy = enc.world.enemy_policy()
            if policy is None:
                return
            pilot = NeuralPilot(policy, config.SETTINGS.game.neuralDecisionFrames)
        c.flight = HunterFlight(craft, pilot, ProtagonistSurroundings(enc.world))

    def on_frame(self, c, enc, dt):
        if c.flight is None:
            return
        craft = c.craft
        if (c.vx, c.vy) != (craft.vx, craft.vy):
            craft.register_hit(c.vx - craft.vx, c.vy - craft.vy)
        craft.x, craft.y, craft.vx, craft.vy = c.x, c.y, c.vx, c.vy
        for shot in c.flight.fly(dt):
            enc.add_shot(shot)
        c.x, c.y, c.vx, c.vy, c.angle = craft.x, craft.y, craft.vx, craft.vy, craft.angle
        c.pilot_thrusting = craft.pilot_thrusting

    def on_death(self, c, enc):
        self._close(c)

    def on_close(self, c, enc):
        self._close(c)

    def _close(self, c):
        """Stop the pilot and its worker, once."""
        flight, worker = getattr(c, 'flight', None), getattr(c, 'pilot_worker', None)
        c.flight = c.pilot_worker = None
        if flight is not None:
            flight.close()
        close = getattr(worker, 'close', None)   # the lab's synchronous worker has nothing to close
        if close is not None:
            close()
