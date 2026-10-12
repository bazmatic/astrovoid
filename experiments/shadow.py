"""Asks the rules pilot what it would do at a state the student reached, for teacher-corrected rounds."""
import asyncio
from hunter.fire_control import find_firing_solution
from hunter.jev_pilot import JevPilot
from hunter.model import NEUTRAL
from hunter.neural.controls import step_labels
from hunter.perception import HunterPerception
from hunter.rules_pilot import RulesClient

_FIELDS = ('x', 'y', 'prev_x', 'prev_y', 'vx', 'vy', 'angle', 'fire_remaining', 'burst_remaining',
           'immunity_remaining', 'upgrade_remaining', 'gun_upgrade_level', 'pilot_thrusting',
           'thrusting', 'thrust_frames', '_decision', '_burn_left', 'health', 'active', 'death_timer')
TEACHER_INTERVAL_FRAMES = 15


def snapshot(hunter):
    state = {name: getattr(hunter, name) for name in _FIELDS}
    state['thrust_particles'] = list(hunter.thrust_particles)      # a list the step appends to
    return state


def restore(hunter, state):
    for name, value in state.items():
        setattr(hunter, name, list(value) if name == 'thrust_particles' else value)


def trial_controls(game, hunter, action, frames):
    """The (turn, thrust, fire) the ship would execute over `frames` frames of `action`, state restored."""
    saved = snapshot(hunter)
    rate = hunter.current_rotation_speed
    record = []
    try:
        for _ in range(frames):
            solution = None
            if action.track or action.fire or hunter.burst_remaining:
                solution = find_firing_solution(
                    hunter, list(game.entity_manager.get_all_active_enemies()), game.maze, hunter.settings)
            before = hunter.angle
            # The class method, not hunter.step: the lab wraps the instance's step to count frames, and a
            # trial must not be counted.
            shots = type(hunter).step(hunter, 1, action, solution)
            record.append((((hunter.angle - before + 180.0) % 360.0) - 180.0,
                           bool(hunter.pilot_thrusting), bool(action.fire or shots)))
    finally:
        restore(hunter, saved)
    return step_labels(record, rate)


class ShadowTeacher:
    """A rules pilot that watches the same game (own perception and timing) and holds its own action."""

    def __init__(self, params, settings):
        self.params = params
        self.perception = HunterPerception(settings)
        self.pilot = JevPilot(RulesClient(params), params)
        self.action = NEUTRAL
        self.generation = 1

    def decide(self, game, hunter, now, frame):
        if frame % TEACHER_INTERVAL_FRAMES:
            return self.action
        observation = self.perception.observe(
            hunter, game.maze, game.ship if game._hunter_sees_player() else None,
            game._hunter_entities(), game.projectiles, self.action, now, self.generation,
            powerups=[c for c in game.powerup_crystals if type(c).__name__ != 'JevBeacon'])
        self.action = asyncio.run(self.pilot.decide(observation)).action
        return self.action

    def label(self, game, hunter, frames):
        return trial_controls(game, hunter, self.action, frames)
