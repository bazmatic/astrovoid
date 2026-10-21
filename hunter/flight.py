"""A hunter flight: one hunter in play with its pilot, from its summons until it dies, is replaced, or the level ends.

The flight is built once from the hunter's ship, a pilot and its surroundings (see hunter.surroundings),
then flown a frame at a time:

    flight = HunterFlight(HunterShip(pos, settings), WorkerPilot(worker), surroundings)
    shots = flight.fly(dt)        # each frame of play; the caller places the shots
    flight.pause()                # each frame play is paused
    flight.close()                # when it is done with

The ship's settings are the flight's settings, fixed for its life: a flight with different settings is a new
flight. Inside, the flight picks the observer its pilot reads (perception for Jev and the rules pilot, senses
for the neural one), consults fire control while the pilot engages, drops a burst the pilot is no longer
behind, and settles the ship against the walls.
"""
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from hunter.controller import HunterController
from hunter.fire_control import find_firing_solution, nose_on_block
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
    def __init__(self, ship, pilot, surroundings):
        self.ship = ship
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

    def fly(self, dt):
        """Fly one frame (dt in frame units, 1.0 = 1/60 s) and return the shots fired, for the caller to place.

        The pilot may look and decide, fire control aims while it engages, and the ship moves and meets the walls.
        A destroyed hunter does not fly: its pilot is closed.
        """
        ship = self.ship
        if not ship.active:
            self.controller.close()
            return []
        action = self.controller.tick(self._sense if self._neural else self._perceive)
        if self.controller.status != 'active':
            ship.cancel_burst()
        maze = self.surroundings.maze
        # Fire control is only consulted while the pilot is engaging something.
        solution = None
        if action.track or action.fire or ship.burst_remaining:
            solution = find_firing_solution(ship, self.surroundings.enemies(), maze, ship.settings)
            # With no enemy to aim at, the neural pilot may shoot its way out: through the wall block its enemy
            # compass routes through, and no other.
            breach = getattr(self._observer, 'breach', None) if self._neural else None
            if (solution is None and breach is not None
                    and nose_on_block(ship, maze, breach, ship.settings.sensor_range(maze))):
                solution = FiringSolution(0.0, True)
        shots = ship.step(dt, action, solution) or []
        ship.check_wall_collision(maze.walls, maze.spatial_grid)
        return shots

    def pause(self):
        """Hold still for a frame of paused play: the pilot stops deciding, the engine cuts and any burst is dropped."""
        self.controller.tick(None, running=False)
        self.ship.pilot_thrusting = False
        self.ship.cancel_burst()

    def close(self):
        """End the flight: the pilot stops for good and the listeners are let go. The ship stays as it is."""
        self.controller.close()
        self._listeners.clear()

    def _perceive(self, now, generation):
        return self._shown(self._observer.perceive(
            self.ship, self.surroundings, self.controller.action, now, generation))

    def _sense(self, last_controls, now):
        return self._shown(self._observer.perceive(self.ship, self.surroundings, last_controls, now))

    def _shown(self, seen):
        for listener in self._listeners:
            listener(seen)
        return seen
