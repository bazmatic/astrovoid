from hunter.controller import HunterController
from hunter.model import PilotObservation, PilotResult, PilotDecision, ACTIONS, NEUTRAL


class Worker:
    def __init__(self):
        self.busy = False
        self.sent = []
        self.result = None
    def submit(self, observation):
        assert not self.busy
        self.busy = True
        self.sent.append(observation)
        return True
    def poll(self):
        result,self.result = self.result,None
        if result:
            self.busy = False
        return result
    def cancel(self):
        self.busy = False
    def close(self):
        self.cancel()


def setup():
    now = [10.]
    worker = Worker()
    controller = HunterController(worker, clock=lambda:now[0])
    observe = lambda t,g:PilotObservation(g,t,'{}')
    return now,worker,controller,observe


def test_expiry_is_snapshot_based_and_no_backlog():
    now,w,c,observe = setup()
    assert c.tick(observe) == NEUTRAL
    for _ in range(20):
        c.tick(observe)
    assert len(w.sent) == 1
    now[0] = 10.6
    w.result = PilotResult(c.generation,10,10.6,PilotDecision(ACTIONS['left_thrust_fire']))
    assert c.tick(observe) == ACTIONS['left_thrust_fire']
    now[0] = 10+c.settings.action_ttl
    assert c.tick(observe) == NEUTRAL
    assert c.status == 'coasting'


def test_pause_rejects_previous_generation_and_permanent_errors_stop_requests():
    now,w,c,observe = setup()
    c.tick(observe)
    c.tick(observe, running=False)
    old = w.sent[0]
    w.result = PilotResult(old.generation,10,10.1,PilotDecision(ACTIONS['left_thrust_fire']))
    now[0] = 10.1
    assert c.tick(observe) == NEUTRAL
    new = w.sent[-1]
    w.result = PilotResult(new.generation,10.1,10.2,error='auth',permanent=True)
    c.tick(observe)
    assert c.status == 'unavailable'
    count = len(w.sent)
    now[0] = 100
    c.tick(observe)
    assert len(w.sent) == count


def test_transient_backoff_does_not_extend_inputs():
    now,w,c,observe = setup()
    c.tick(observe)
    w.result = PilotResult(c.generation,10,10,error='timeout')
    c.tick(observe)
    now[0] = 10.99
    c.tick(observe)
    assert len(w.sent) == 1
    now[0] = 11
    c.tick(observe)
    assert len(w.sent) == 2
    assert c.action == NEUTRAL


def test_turn_is_held_until_replaced_or_expired():
    from entities.hunter_ship import HunterShip
    now,w,c,observe = setup()
    ship = HunterShip((100,100))
    c.tick(observe)
    now[0] = 10.1
    w.result = PilotResult(c.generation,10,10.1,PilotDecision(ACTIONS['left_thrust_fire']))
    for frame in range(12):
        now[0] = 10.1 + frame/60
        ship.step(1,c.tick(observe))
    # Steering stays held for every frame, like a key held down.
    assert (360-ship.angle)%360 == 12*ship.current_rotation_speed
    assert c.action == ACTIONS['left_thrust_fire']
    # The next observation reports the steering still being held.
    assert w.sent[-1].snapshot_at > 10.1
    w.result = PilotResult(c.generation,w.sent[-1].snapshot_at,now[0],
                           PilotDecision(ACTIONS['none_thrust_fire']))
    angle = ship.angle
    ship.step(1,c.tick(observe))
    assert ship.angle == angle
    w.result = PilotResult(c.generation,now[0],now[0],PilotDecision(ACTIONS['right_coast_hold']))
    c.tick(observe)
    now[0] += c.settings.action_ttl
    assert c.tick(observe) == NEUTRAL


import pytest


@pytest.mark.parametrize('latency', [0.35, 0.5, 0.7])
def test_held_controls_do_not_lapse_between_decisions_at_measured_latency(latency):
    """Real round trips take 0.35-0.7 s. Back-to-back decisions must hand over without
    the controls dropping to neutral in between, and none may be thrown away as stale."""
    now,w,c,observe = setup()
    held = ACTIONS['track_thrust_fire']
    c.tick(observe)
    lapses = 0
    for frame in range(1, 60*5):
        now[0] = 10 + frame/60
        if w.busy and now[0]-w.sent[-1].snapshot_at >= latency:
            w.result = PilotResult(c.generation,w.sent[-1].snapshot_at,now[0],PilotDecision(held))
        action = c.tick(observe)
        if c.ever_accepted and action != held:
            lapses += 1
    assert c.accepted >= 5
    assert c.discarded == 0
    assert lapses == 0


def test_predictions_look_as_far_ahead_as_a_decision_takes_to_land():
    from hunter.model import HunterSettings
    settings = HunterSettings()
    # Measured median round trip is 0.4-0.5 s.
    assert 0.4 <= settings.decision_delay <= 0.5
    assert settings.action_ttl >= 2*0.7
    assert settings.request_timeout <= settings.action_ttl
