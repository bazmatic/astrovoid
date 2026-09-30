import asyncio
import threading
import time
from types import SimpleNamespace
from dataclasses import replace
from hunter.worker import PilotWorker
from hunter.model import PilotObservation, HunterSettings


def wait_until(predicate):
    deadline = time.monotonic()+2
    while not predicate():
        assert time.monotonic()<deadline
        time.sleep(.002)


class Client:
    def __init__(self, blocked=False):
        self.blocked = blocked
        self.entered = threading.Event()
        self.closed = threading.Event()
    async def system_one(self, **kwargs):
        self.entered.set()
        if self.blocked:
            await asyncio.sleep(5)
        return SimpleNamespace(choices={'pilot':SimpleNamespace(choice='left_thrust_fire',confidence=.9)})
    async def aclose(self):
        self.closed.set()


def test_worker_returns_result_without_blocking_and_closes():
    client = Client()
    worker = PilotWorker(lambda:client)
    try:
        assert worker.submit(PilotObservation(2,time.monotonic(),'{}'))
        wait_until(lambda:not worker.busy)
        result = worker.poll()
        assert result.generation == 2
        assert result.decision.action.fire
    finally:
        worker.close()
        worker.join(2)
    assert client.closed.is_set()


def test_timeout_and_cancel_allow_no_overlapping_request():
    client = Client(True)
    worker = PilotWorker(lambda:client,settings=replace(HunterSettings(),request_timeout=.03))
    try:
        assert worker.submit(PilotObservation(1,time.monotonic(),'{}'))
        assert not worker.submit(PilotObservation(1,time.monotonic(),'{}'))
        wait_until(lambda:not worker.busy)
        assert worker.poll().error == 'timeout'
        assert worker.submit(PilotObservation(1,time.monotonic(),'{}'))
        worker.cancel()
        wait_until(lambda:not worker.busy)
        assert client.closed.is_set()
    finally:
        worker.close()
        worker.join(2)
