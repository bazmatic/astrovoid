import pytest
from experiments import shadow
from experiments.harness import run_episode
from experiments.teach import StepRecorder
from hunter.model import PilotAction


@pytest.fixture(scope='module', autouse=True)
def undo_harness_side_effects():
    yield
    from experiments import harness
    harness.reset()


def real_game_at(frame_count=300):
    """A running level with the harness's hunter, paused after some frames; returns (game, hunter)."""
    captured = {}

    def trace(t, game, hunter):
        captured['game'], captured['hunter'] = game, hunter
        captured['frames'] = captured.get('frames', 0) + 1
        if captured['frames'] == frame_count:
            raise StopIteration
    try:
        run_episode(14, 100, horizon=20.0, trace=trace)
    except StopIteration:
        pass
    return captured['game'], captured['hunter']


def test_snapshot_and_restore_are_exact():
    game, hunter = real_game_at()
    before = shadow.snapshot(hunter)
    hunter.x += 50; hunter.vx = 3.0; hunter.angle = 123.0; hunter.burst_remaining = 2
    hunter.fire_remaining = 0.2; hunter._burn_left = 4.0; hunter.thrust_frames += 9
    shadow.restore(hunter, before)
    assert shadow.snapshot(hunter) == before


def test_a_trial_leaves_the_real_ship_exactly_as_it_was():
    game, hunter = real_game_at()
    before = shadow.snapshot(hunter)
    projectiles = len(game.projectiles)
    shadow.trial_controls(game, hunter, PilotAction(1, True, True), frames=6)
    assert shadow.snapshot(hunter) == before
    assert len(game.projectiles) == projectiles


def test_a_plain_action_trial_reports_that_action():
    game, hunter = real_game_at()
    turn, thrust, fire = shadow.trial_controls(game, hunter, PilotAction(-1, True, False), frames=6)
    assert (turn, thrust, fire) == (0, True, False)          # left, thrust on, trigger off
    turn, thrust, _ = shadow.trial_controls(game, hunter, PilotAction(1, False, False), frames=6)
    assert (turn, thrust) == (2, False)


def test_a_trial_is_not_counted_by_a_recorder_wrapping_the_ships_step():
    seen = []
    game, hunter = real_game_at()
    original = hunter.step
    hunter.step = lambda *a, **k: (seen.append(1), original(*a, **k))[1]
    shadow.trial_controls(game, hunter, PilotAction(1, True, False), frames=6)
    assert seen == []


def test_the_trial_matches_what_the_ship_really_does_when_the_teacher_flies():
    """Replaying the teacher's held action on the saved state gives the controls the real run executed."""
    mismatches, total = 0, 0

    class Checker(StepRecorder):
        def before_frame(self, game, hunter):
            super().before_frame(game, hunter)
            if self._count % self.decision_frames == 0:
                controller = game.hunter_flight.controller
                self._started_with = controller.action
                self._expected = shadow.trial_controls(game, hunter, controller.action, self.decision_frames)
                self._controller = controller

        def _close_step(self):
            nonlocal mismatches, total
            label = self.pending_label()
            # Only steps where the teacher's action was not refreshed part-way through are comparable.
            if getattr(self, '_expected', None) is not None and self._controller.action is self._started_with:
                total += 1
                mismatches += self._expected != label
            super()._close_step()
    run_episode(14, 100, horizon=25.0, recorder=Checker(decision_frames=6))
    assert total > 60
    assert mismatches / total < 0.05          # what remains is walls and enemies moving within the step


def test_the_shadow_teacher_decides_every_fifteen_frames_and_labels_with_its_held_action():
    from hunter.rule_params import RULES
    game, hunter = real_game_at()
    teacher = shadow.ShadowTeacher(RULES, hunter.settings)
    seen = []
    for frame in range(31):
        teacher.decide(game, hunter, frame / 60.0, frame)
        seen.append(teacher.action)
    assert seen[0] is seen[14] and seen[15] is seen[29] and seen[15] is not seen[0]
    controls = teacher.label(game, hunter, 6)
    assert controls[0] in (0, 1, 2)


def test_a_trial_does_not_disturb_the_global_random_stream_or_the_particles():
    import copy
    import random
    game, hunter = real_game_at()
    hunter.thrust_particles.append({'x': 1.0, 'y': 2.0, 'vx': 0.1, 'vy': 0.1, 'life': 5.0, 'size': 3.0})   # make sure there is one to mutate
    random.seed(5)
    state = random.getstate()
    particles = copy.deepcopy(hunter.thrust_particles)
    shadow.trial_controls(game, hunter, PilotAction(1, True, False), frames=6)
    assert random.getstate() == state
    assert hunter.thrust_particles == particles
