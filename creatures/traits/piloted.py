"""A pilot decides controls; propulsion and weapons act on the Creature itself."""
from time import monotonic

import config
from creatures.trait import Trait
from hunter.flight import HunterFlight, NeuralPilot, WorkerPilot
from hunter.surroundings import ProtagonistSurroundings

MODES = ('jev', 'rules', 'neural')


class Pilot(Trait):
    NAME = 'pilot'
    REQUIRES = ('thrusters', 'gun')
    LIVE = ('flight', 'pilot_worker', 'pilot_setup')

    def __init__(self, mode):
        if mode not in MODES:
            raise ValueError(f'pilot: mode must be one of {MODES}, not {mode!r}')
        self.mode = mode

    def on_spawn(self, c, enc):
        setup = getattr(c, 'pilot_setup', None)
        c.flight = c.pilot_worker = None
        if setup is not None:
            pilot, surroundings, owns = setup.pilot, setup.surroundings, setup.owns_worker
        else:
            surroundings, owns = ProtagonistSurroundings(enc.world), True
            if self.mode == 'neural':
                policy = enc.world.enemy_policy()
                if policy is None:
                    c.controls.gun_enabled = False
                    return
                pilot = NeuralPilot(policy, config.SETTINGS.game.neuralDecisionFrames)
            else:
                pilot = WorkerPilot(enc.world.rules_worker(), monotonic)
        c.pilot_worker = getattr(pilot, 'worker', None)
        c.flight = HunterFlight(c, pilot, surroundings, encounter=enc, owns_worker=owns)

    def on_frame(self, c, enc, dt):
        if c.flight is not None:
            c.flight.decide()

    def on_event(self, c, name, enc):
        flight = getattr(c, 'flight', None)
        if flight is not None:
            flight._event(c, name)

    def on_death(self, c, enc):
        self.on_close(c, enc)

    def on_close(self, c, enc):
        flight = getattr(c, 'flight', None)
        if flight is not None:
            flight._shutdown()
        c.flight = c.pilot_worker = c.pilot_setup = None
