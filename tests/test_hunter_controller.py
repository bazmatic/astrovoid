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
    now[0] = 10.75
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
