"""Asks the rules pilot what it would do at a state the student reached, for teacher-corrected rounds."""
import asyncio
import copy
import random
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
    state['thrust_particles'] = copy.deepcopy(hunter.thrust_particles)      # the step appends to and edits these
    return state


def restore(hunter, state):
    for name, value in state.items():
        setattr(hunter, name, copy.deepcopy(value) if name == 'thrust_particles' else value)


def trial_controls(game, hunter, action, frames):
    """The (turn, thrust, fire) the ship would execute over `frames` frames of `action`, state restored."""
    from types import SimpleNamespace
    from creatures.encounter import Encounter
    from game_handlers.enemy_roster import EnemyRoster
    # Portrait copying deliberately drops pilot/controller/listeners. Trials use only the same traits and state.
    trial = copy.deepcopy(hunter)
    trial._decision = hunter._decision  # immutable held action: preserve its identity and remaining burn budget
    roster = EnemyRoster()
    roster.add(trial)
    enc = Encounter(roster, SimpleNamespace(ship=None, hunter=None, maze=None, projectiles=[]))
    random_state = random.getstate()
    record = []
    try:
        for _ in range(frames):
            solution = None
            if action.track or action.fire or trial.burst_remaining:
                solution = find_firing_solution(trial, game.roster.alive(), game.maze, trial.settings)
            for field in ('turn', 'thrust', 'fire', 'track', 'course', 'burn_heading', 'burn_frames', 'burn_reference'):
                setattr(trial.controls, field, getattr(action, field))
            trial.controls.decision_token = action
            trial.controls.gun_enabled = True
            trial.controls.on_target = solution is not None and solution.on_target
            trial.controls.lead_degrees = solution.lead_degrees if solution is not None else None
            before, volleys = trial.angle, trial.shots_fired
            enc.step_creature(trial, 1)
            record.append((((trial.angle - before + 180) % 360) - 180,
                           bool(trial.pilot_thrusting), bool(action.fire or trial.shots_fired > volleys)))
    finally:
        random.setstate(random_state)
    return step_labels(record, hunter.current_rotation_speed)


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
        observation = self.perception.perceive(hunter, game.hunter_surroundings, self.action, now, self.generation)
        self.action = asyncio.run(self.pilot.decide(observation)).action
        return self.action

    def label(self, game, hunter, frames):
        return trial_controls(game, hunter, self.action, frames)
