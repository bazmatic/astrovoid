import asyncio
import json
import threading
from types import SimpleNamespace
import pytest
from hunter.student.recorder import DecisionSink, RecordingJevClient


def answer(choice, confidence=.9, probabilities=None):
    reply = SimpleNamespace(choice=choice, confidence=confidence)
    if probabilities is not None:
        reply.probabilities = probabilities
    return reply


class Inner:
    def __init__(self, probabilities=True, fail=False):
        self.probabilities, self.fail, self.closed = probabilities, fail, False

    async def system_one(self, **kwargs):
        if self.fail:
            raise RuntimeError('boom')
        p = (lambda c: {c: .9, 'other': .1}) if self.probabilities else (lambda c: None)
        return SimpleNamespace(choices={
            'turn': answer('left', probabilities=p('left')),
            'thrust': answer('burn', probabilities=p('burn')),
            'fire': answer('fire', probabilities=p('fire'))})

    async def aclose(self):
        self.closed = True


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def recorder(tmp_path, inner=None, **kwargs):
    sink = DecisionSink(tmp_path / 'run.jsonl', **kwargs)
    return RecordingJevClient(inner or Inner(), sink, run_id='r1', model='m'), sink


def test_success_returns_inner_result_and_writes_one_record(tmp_path):
    client, sink = recorder(tmp_path)
    result = asyncio.run(client.system_one(state={'speed': 3}, questions={}))
    sink.flush()
    assert result.choices['turn'].choice == 'left'
    [record] = lines(tmp_path / 'run.jsonl')
    assert record['run_id'] == 'r1' and record['model'] == 'm'
    assert record['state'] == {'speed': 3}
    assert record['latency'] >= 0 and record['t'] > 0
    assert record['answers']['turn'] == {
        'choice': 'left', 'confidence': .9, 'probabilities': {'left': .9, 'other': .1}}
    assert set(record['answers']) == {'turn', 'thrust', 'fire'}


def test_missing_probabilities_are_recorded_as_null(tmp_path):
    client, sink = recorder(tmp_path, Inner(probabilities=False))
    asyncio.run(client.system_one(state={}, questions={}))
    sink.flush()
    [record] = lines(tmp_path / 'run.jsonl')
    assert record['answers']['fire']['probabilities'] is None


def test_failed_calls_are_not_recorded_and_still_raise(tmp_path):
    client, sink = recorder(tmp_path, Inner(fail=True))
    with pytest.raises(RuntimeError):
        asyncio.run(client.system_one(state={}, questions={}))
    sink.flush()
    assert not (tmp_path / 'run.jsonl').exists() or lines(tmp_path / 'run.jsonl') == []


def test_unserialisable_state_does_not_break_the_decision(tmp_path):
    client, sink = recorder(tmp_path)
    result = asyncio.run(client.system_one(state={'bad': object()}, questions={}))
    sink.flush()
    assert result.choices['fire'].choice == 'fire'
    assert not (tmp_path / 'run.jsonl').exists() or lines(tmp_path / 'run.jsonl') == []


def test_unwritable_directory_does_not_break_the_decision(tmp_path):
    blocker = tmp_path / 'file'
    blocker.write_text('x')
    sink = DecisionSink(blocker / 'sub' / 'run.jsonl')
    client = RecordingJevClient(Inner(), sink, run_id='r1')
    result = asyncio.run(client.system_one(state={}, questions={}))
    sink.flush()
    assert result.choices['turn'].choice == 'left'


def test_full_queue_drops_records_without_blocking(tmp_path):
    gate = threading.Event()
    sink = DecisionSink(tmp_path / 'run.jsonl', max_queue=2)
    sink._open = lambda: gate.wait(2) and None  # hold the writer thread
    for _ in range(50):
        sink.write({'x': 1})  # must return immediately, never raise
    gate.set()


def test_aclose_closes_inner_and_sink(tmp_path):
    inner = Inner()
    client, sink = recorder(tmp_path, inner)
    asyncio.run(client.system_one(state={}, questions={}))
    asyncio.run(client.aclose())
    assert inner.closed
    assert len(lines(tmp_path / 'run.jsonl')) == 1
