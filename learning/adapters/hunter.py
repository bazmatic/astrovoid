"""Hunter adapter retaining the original recorder, value model and checkpoint contract."""
import numpy as np
from hunter.neural.policy import HEAD_SIZES
from hunter.senses import FEATURE_NAMES, OBSERVATION_VERSION
from learning.policy import PolicySpec
from learning.environment import Snapshot, Transition

SPEC = PolicySpec('hunter', FEATURE_NAMES, tuple(HEAD_SIZES.items()), OBSERVATION_VERSION)


def environment(**kwargs):
    return HunterEnvironment(**kwargs)


def enabled(x, action, masks):
    return [True]*len(SPEC.heads)


class ExternalPolicy:
    controls = (1,0,0)
    def initial_state(self):
        return None
    def act(self, senses, state, *args, **kwargs):
        return self.controls, state


class HunterEnvironment:
    """Single-agent numeric stepping over the same real frames used by legacy hunter training.

    Legacy full-episode runs preserve the original recorder and rewards without translation.
    The stepping interface uses that recorder too, allowing the common collector to exercise
    this adapter with arbitrary policies. Hunter PPO retains its original actor value head.
    """
    spec = SPEC
    def __init__(self, horizon=90., decision_frames=6, **settings):
        from learning.adapters import hunter
        self.adapter = hunter
        self.horizon, self.decision_frames, self.settings = horizon, decision_frames, settings
        self.frames = None

    def run(self, level, seed, student, **settings):
        from experiments.rollout import fly_rollout
        return fly_rollout(level, seed, student, **settings)

    def reset(self, seed, level=14, **scenario):
        from experiments.harness import episode_frames
        from experiments.rollout import RolloutRecorder
        from experiments.student import StudentSpec
        self.close()
        self.policy = ExternalPolicy()
        self.recorder = RolloutRecorder(self.decision_frames)
        self.frames = episode_frames(level,seed,horizon=self.horizon,
            student=StudentSpec('',decision_frames=self.decision_frames), external_policy=self.policy,
            recorder=self.recorder,pursue_hunter=True,**self.settings,**scenario)
        self.current = next(self.frames)
        self.action_trace = []
        self.result = None
        return self.snapshot()

    def snapshot(self):
        game, ship, flight, _, _ = self.current
        # Preview with a separate sensor: do not update the recorder or the pilot's memory twice.
        from hunter.senses import Senses
        if not hasattr(self,'sensor'):
            self.sensor = Senses(flight.settings)
        x = self.sensor.perceive(ship,flight.surroundings,self.policy.controls,flight.controller.frames/60)
        masks = {k:np.ones(n,bool) for k,n in SPEC.heads}
        return Snapshot({0:x} if ship.active else {},{0:masks} if ship.active else {},x)

    def step(self, actions):
        if self.result is not None:
            raise RuntimeError('step after episode ended')
        before = float(self.recorder.arrays()[2].sum())
        self.policy.controls = tuple(actions[0])
        self.action_trace.append({'0':list(actions[0])})
        for _ in range(self.decision_frames):
            try:
                self.current = next(self.frames)
            except StopIteration as done:
                self.result = done.value
                break
        reward = float(self.recorder.arrays()[2].sum())-before
        terminal = self.result is not None and self.result.end != 'horizon'
        truncated = self.result is not None and self.result.end == 'horizon'
        events = {} if self.result is None else vars(self.result)
        return Transition(self.snapshot(),reward,terminal,truncated,events)

    def close(self):
        from experiments.harness import reset, _clear_overrides
        if self.frames is not None:
            self.frames.close()
            game = self.current[0]
            game._close_hunter();game._close_enemy_hunters();_clear_overrides(game)
            self.frames = None
        self.__dict__.pop('sensor',None)
        reset()
