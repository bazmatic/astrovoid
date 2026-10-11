"""Logs Jev's pilot decisions as JSONL so a student can be trained on them."""
import json
import logging
import queue
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

DECISIONS_DIR = Path(__file__).resolve().parents[2] / '.astrovoid-local' / 'decisions'
_STOP = object()


class DecisionSink:
    """Appends JSON lines from a background thread; never blocks or raises into its caller."""

    def __init__(self, path, max_queue=256):
        self.path = Path(path)
        self._queue = queue.Queue(max_queue)
        self._file = None
        self._thread = threading.Thread(target=self._drain, name='decision-sink', daemon=True)
        self._thread.start()

    def write(self, record):
        try:
            line = json.dumps(record)
        except (TypeError, ValueError):
            log.warning('Decision record is not serialisable; dropped')
            return
        try:
            self._queue.put_nowait(line)
        except queue.Full:
            log.warning('Decision sink is full; dropped a record')

    def flush(self):
        self._queue.join()

    def close(self):
        self._queue.put(_STOP)
        self._thread.join(2)

    def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return open(self.path, 'a', encoding='utf-8')

    def _drain(self):
        while True:
            line = self._queue.get()
            try:
                if line is _STOP:
                    if self._file:
                        self._file.close()
                    return
                if self._file is None:
                    self._file = self._open()
                self._file.write(line + '\n')
                self._file.flush()
            except Exception:
                # Disk trouble must never reach the decision loop, nor kill this thread.
                log.warning('Decision sink cannot write %s; dropped a record', self.path)
                self._file = None
            finally:
                self._queue.task_done()


class RecordingJevClient:
    """Wraps the real Jev client and logs each successful decision."""

    def __init__(self, inner, sink, run_id=None, model='jev-latest'):
        self.inner, self.sink, self.model = inner, sink, model
        self.run_id = run_id or uuid.uuid4().hex

    async def system_one(self, **kwargs):
        started = time.monotonic()
        result = await self.inner.system_one(**kwargs)
        latency = time.monotonic() - started
        try:
            answers = {}
            for name, reply in result.choices.items():
                probabilities = getattr(reply, 'probabilities', None)
                answers[name] = {
                    'choice': reply.choice,
                    'confidence': getattr(reply, 'confidence', None),
                    'probabilities': None if probabilities is None else dict(probabilities)}
            self.sink.write({'t': time.time(), 'run_id': self.run_id, 'model': self.model,
                             'latency': latency, 'state': kwargs.get('state'),
                             'answers': answers})
        except Exception:
            # Recording is best effort: it must never cost the hunter a decision.
            log.warning('Could not record a decision', exc_info=True)
        return result

    async def aclose(self):
        try:
            close = getattr(self.inner, 'aclose', None)
            if close is not None:
                await close()
        finally:
            self.sink.close()


def record_to_disk(inner, model='jev-latest'):
    run_id = uuid.uuid4().hex
    return RecordingJevClient(inner, DecisionSink(DECISIONS_DIR / f'{run_id}.jsonl'),
                              run_id=run_id, model=model)
