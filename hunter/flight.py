"""A Creature's pilot lifetime, observations and single-frame stepping.

The pilot decides controls; reusable traits own propulsion, bursts, projectiles and energy. step(dt) places shots
through the Creature's Encounter world. Enemy encounters call the same traits directly, without a second step.
Pause invalidates pending decisions without advancing timers; closing releases listeners and owned workers.
"""
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from hunter.controller import HunterController
from hunter.fire_control import find_firing_solution
from hunter.model import FiringSolution
from hunter.neural.controller import NeuralController
from hunter.perception import HunterPerception
from hunter.senses import Senses


@dataclass(frozen=True)
class WorkerPilot:
    """Jev or the rules pilot: decisions come back from a pilot worker, which the caller owns and closes."""
    worker: Any
    clock: Callable[[], float] = time.monotonic

    def controller(self, settings):
        return HunterController(self.worker, settings, self.clock)


@dataclass(frozen=True)
class NeuralPilot:
    """The neural pilot: a policy run in the game loop, deciding every `decision_frames` frames."""
    policy: Any
    decision_frames: int
    greedy: bool = True
    rng: Optional[Any] = None

    def controller(self, settings):
        return NeuralController(self.policy, self.decision_frames, greedy=self.greedy, rng=self.rng)


class HunterFlight:
    def __init__(self, ship, pilot, surroundings, *, encounter, owns_worker=False):
        self.ship = ship
        self.encounter = encounter
        self._worker = getattr(pilot, 'worker', None) if owns_worker else None
        self._closed = self._closing = False
        self._frame_listeners = []
        self._event_listeners = []
        self.surroundings = surroundings
        # For the lab, which reads the pilot's decision steps and may override a decision; play has no need of it.
        self.controller = pilot.controller(ship.settings)
        self._neural = getattr(self.controller, 'kind', None) == 'neural'
        self._observer = Senses(ship.settings) if self._neural else HunterPerception(ship.settings)
        self._listeners = []

    @property
    def settings(self):
        return self.ship.settings

    @property
    def status(self):
        """The pilot's status: 'waiting', 'active', 'coasting' or 'unavailable'."""
        return self.controller.status

    def on_observed(self, listener):
        """Call `listener` with everything the pilot is shown (its senses, or its observation) until the flight closes."""
        self._listeners.append(listener)

    def decide(self):
        """Sense before timers advance, then give the Creature all of the pilot's held controls."""
        from creatures.traits.burst_fire import cancel_burst
        ship = self.ship
        from creatures.traits.energy import register_hit
        previous = getattr(ship, '_pilot_velocity', (ship.vx, ship.vy))
        if previous != (ship.vx, ship.vy):
            register_hit(ship, ship.vx - previous[0], ship.vy - previous[1])
        action = self.controller.tick(self._sense if self._neural else self._perceive)
        controls = ship.controls
        for field in ('turn', 'thrust', 'fire', 'track', 'course', 'burn_heading', 'burn_frames', 'burn_reference'):
            setattr(controls, field, getattr(action, field))
        controls.decision_token = action
        controls.gun_enabled = self.controller.status == 'active'
        if not controls.gun_enabled:
            cancel_burst(ship)
        solution = None
        if self._neural:
            if action.fire:
                solution = FiringSolution(0.0, True)
        elif action.track or action.fire or ship.burst_remaining:
            solution = find_firing_solution(ship, self.surroundings.enemies(), self.surroundings.maze, ship.settings)
        controls.lead_degrees = solution.lead_degrees if solution is not None else None
        controls.on_target = solution is not None and solution.on_target

    def step(self, dt):
        """Step the Creature once; its gun places shots directly in the world's sink."""
        if not self.ship.active:
            self.close()
            return
        before = self.ship.shots_fired
        self.frame_start_angle = self.ship.angle
        listeners = tuple(self._frame_listeners)
        self.encounter.step_creature(self.ship, dt)
        for listener in listeners:
            listener(self.ship, dt, self.ship.controls.decision_token, self.ship.shots_fired - before)

    def on_frame(self, listener):
        self._frame_listeners.append(listener)

    def on_event(self, listener):
        self._event_listeners.append(listener)

    def _event(self, creature, name):
        for listener in tuple(self._event_listeners):
            listener(creature, name)

    def pause(self):
        """Hold still for a frame of paused play: the pilot stops deciding, the engine cuts and any burst is dropped."""
        self.controller.tick(None, running=False)
        self.ship.pilot_thrusting = False
        from creatures.traits.burst_fire import cancel_burst
        cancel_burst(self.ship)

    def close(self):
        """End the flight: the pilot stops for good and the listeners are let go. The ship stays as it is."""
        if self._closing or self._closed:
            return
        self._closing = True
        if self.encounter is not None:
            self.encounter.close_creature(self.ship)
        self._shutdown()
        self._closing = False

    def _shutdown(self):
        if self._closed:
            return
        self._closed = True
        self.controller.close()
        self._listeners.clear()
        self._frame_listeners.clear()
        self._event_listeners.clear()
        close = getattr(self._worker, 'close', None)
        if close is not None:
            close()
        self._worker = None

    def _perceive(self, now, generation):
        return self._shown(self._observer.perceive(
            self.ship, self.surroundings, self.controller.action, now, generation))

    def _sense(self, last_controls, now):
        return self._shown(self._observer.perceive(self.ship, self.surroundings, last_controls, now))

    def _shown(self, seen):
        for listener in self._listeners:
            listener(seen)
        return seen
