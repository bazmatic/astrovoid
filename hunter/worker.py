"""One cancellable request on a dedicated asyncio thread, never the Pygame loop."""
import asyncio
import queue
import threading
import time
from hunter.jev_pilot import JevPilot, PilotUnavailable, create_client
from hunter.model import HunterSettings, PilotResult


class PilotWorker:
    def __init__(self, client_factory=create_client, clock=time.monotonic, settings=HunterSettings()):
        self.client_factory, self.clock, self.settings = client_factory, clock, settings
        self._lock = threading.Lock()
        self._busy = False
        self._closed = False
        self._epoch = 0
        self._handled_epoch = 0
        self._loop = None
        self._thread = None
        self._task = None
        self._client = None
        self._cleaning = False
        self._results = queue.SimpleQueue()

    @property
    def busy(self):
        with self._lock:
            return self._busy

    def submit(self, observation):
        with self._lock:
            if self._busy or self._closed:
                return False
            self._busy = True
            epoch = self._epoch
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(target=self._run, name='jev-pilot', daemon=True)
                self._thread.start()
            self._loop.call_soon_threadsafe(self._launch, observation, epoch)
        return True

    def _run(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def _launch(self, observation, epoch):
        self._task = self._loop.create_task(self._request(observation, epoch))
        self._task.add_done_callback(self._done)

    async def _close_client(self):
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                # Cleanup errors cannot resurrect a cancelled decision.
                pass

    async def _request(self, observation, epoch):
        try:
            if epoch != self._epoch or self._closed:
                return
            if self._client is None:
                self._client = self.client_factory()
            decision = await asyncio.wait_for(
                JevPilot(self._client).decide(observation), self.settings.request_timeout)
            result = PilotResult(observation.generation, observation.snapshot_at, self.clock(), decision)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status = getattr(exc, 'status_code', getattr(exc,'status',None))
            permanent = isinstance(exc,PilotUnavailable) or status in (401,403)
            if isinstance(exc,PilotUnavailable):
                category = str(exc)  # Only our fixed local categories, never SDK error text.
            elif isinstance(exc,asyncio.TimeoutError) or type(exc).__name__ == 'TypeSafeAPITimeoutError':
                category = 'timeout'
            elif status in (401,403):
                category = 'authentication'
            elif isinstance(exc,(ValueError,KeyError,AttributeError,TypeError)):
                category = 'invalid_response'
            else:
                category = 'request_failed'
            result = PilotResult(observation.generation,observation.snapshot_at,self.clock(),
                                 error=category,permanent=permanent)
        if epoch == self._epoch and not self._closed:
            self._results.put(result)

    def _done(self, task):
        # A task can be cancelled before its coroutine starts: cleanup belongs here.
        if not task.cancelled():
            task.exception()  # Retrieve unexpected task errors without logging payloads.
        if task.cancelled() or self._closed or getattr(self,'_reset_client',False):
            self._cleaning = True
            self._task = self._loop.create_task(self._close_client())
            self._task.add_done_callback(self._cleaned)
        else:
            self._cleaned(task)

    def _cleaned(self, task):
        self._task = None
        self._cleaning = False
        self._reset_client = False
        with self._lock:
            self._busy = self._epoch != self._handled_epoch
            closed = self._closed and not self._busy
        if closed:
            self._loop.stop()

    def poll(self):
        try:
            return self._results.get_nowait()
        except queue.Empty:
            return None

    def cancel(self):
        with self._lock:
            if self._closed:
                return
            self._epoch += 1
            if self._loop is None:
                self._handled_epoch = self._epoch
                return
            self._busy = True
            self._loop.call_soon_threadsafe(self._cancel_on_loop, self._epoch)
        while self.poll() is not None:
            pass

    def _cancel_on_loop(self, epoch):
        with self._lock:
            self._handled_epoch = max(self._handled_epoch, epoch)
        self._reset_client = True
        if self._cleaning:
            return
        if self._task is not None:
            self._task.cancel()
        else:
            self._cleaning = True
            self._task = self._loop.create_task(self._close_client())
            self._task.add_done_callback(self._cleaned)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._epoch += 1
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._cancel_on_loop, self._epoch)

    def join(self, timeout=2.0):
        if self._thread:
            self._thread.join(timeout)
