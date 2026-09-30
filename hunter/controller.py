"""Main-thread decision scheduling and snapshot-based input expiry."""
import itertools
import logging
import time
from hunter.model import HunterSettings, NEUTRAL, PilotAction

log = logging.getLogger(__name__)
_generations = itertools.count()


class HunterController:
    def __init__(self, worker, settings=HunterSettings(), clock=time.monotonic):
        self.worker, self.settings, self.clock = worker, settings, clock
        self.generation = next(_generations)
        self.action = NEUTRAL
        self.action_expires_at = 0.0
        self.turn_expires_at = 0.0
        self.next_request_at = 0.0
        self.failures = 0
        self.unavailable = False
        self.running = False
        self.closed = False
        self.ever_accepted = False
        self.status = 'waiting'
        self.accepted = self.discarded = 0

    def invalidate(self):
        self.generation = next(_generations)
        self.action = NEUTRAL
        self.action_expires_at = 0.0
        self.turn_expires_at = 0.0
        self.next_request_at = 0.0
        self.worker.cancel()

    def close(self):
        if not self.closed:
            self.invalidate()
            self.closed = True
            self.status = 'coasting'

    def tick(self, observation_factory, running=True):
        if self.closed:
            return NEUTRAL
        if not running:
            if self.running:
                self.invalidate()
            self.running = False
            self.status = 'unavailable' if self.unavailable else 'coasting'
            return NEUTRAL
        self.running = True
        now = self.clock()
        result = self.worker.poll()
        if result is not None:
            if result.generation != self.generation:
                self.discarded += 1
            elif result.error:
                self.unavailable = result.permanent
                self.next_request_at = now + min(8., 2. ** min(self.failures,3))
                self.failures += 1
                log.warning('Hunter pilot error=%s permanent=%s',result.error,result.permanent)
            else:
                self.failures = 0
                age = now-result.snapshot_at
                accepted = result.decision is not None and 0 <= age < self.settings.action_ttl
                if accepted:
                    self.action = result.decision.action
                    self.action_expires_at = result.snapshot_at+self.settings.action_ttl
                    # Release steering independently of network latency. Wait for
                    # the pulse to finish before observing the next heading.
                    self.turn_expires_at = min(self.action_expires_at, now+self.settings.turn_pulse)
                    if self.action.turn:
                        self.next_request_at = max(self.next_request_at, self.turn_expires_at)
                    self.ever_accepted = True
                    self.accepted += 1
                else:
                    self.discarded += 1
                log.debug('Hunter decision latency=%.3f age=%.3f accepted=%s confidence=%s',
                          result.finished_at-result.snapshot_at,age,accepted,
                          result.decision.confidence if result.decision else None)
        if now >= self.turn_expires_at:
            self.action = PilotAction(0, self.action.thrust, self.action.fire)
        if now >= self.action_expires_at:
            self.action = NEUTRAL
        if not self.unavailable and not self.worker.busy and now >= self.next_request_at:
            observation = observation_factory(now,self.generation)
            if self.worker.submit(observation):
                self.next_request_at = now+self.settings.request_interval
        if self.unavailable:
            self.status = 'unavailable'
        elif now < self.action_expires_at:
            self.status = 'active'
        elif not self.ever_accepted and self.worker.busy and not self.discarded and not self.failures:
            self.status = 'waiting'
        else:
            self.status = 'coasting'
        return self.action
