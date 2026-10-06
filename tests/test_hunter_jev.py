import asyncio
import json
from types import SimpleNamespace
import pytest
from hunter.model import ACTIONS, PilotObservation
from hunter.jev_pilot import JevPilot, create_client, PilotUnavailable


@pytest.mark.parametrize('choice', list(ACTIONS))
def test_jev_translates_typed_control_choices(choice):
    class Client:
        async def system_one(self, **kwargs):
            assert kwargs['state']['visible_contacts'] == []
            assert set(kwargs['questions']) == {'turn','thrust','fire'}
            return SimpleNamespace(choices={k:SimpleNamespace(choice=v,confidence=.8)
                for k,v in zip(('turn','thrust','fire'),choice.split('_'))})
    decision = asyncio.run(JevPilot(Client()).decide(PilotObservation(1,10,json.dumps({'visible_contacts':[]}))))
    assert decision.action == ACTIONS[choice]
    assert decision.confidence == .8


@pytest.mark.parametrize('choice,confidence', [('teleport',.8), ('none_coast_hold',float('nan'))])
def test_invalid_model_outputs_rejected(choice,confidence):
    class Client:
        async def system_one(self, **kwargs):
            return SimpleNamespace(choices={k:SimpleNamespace(choice=v,confidence=confidence)
                for k,v in zip(('turn','thrust','fire'),choice.split('_'))})
    with pytest.raises((ValueError,KeyError)):
        asyncio.run(JevPilot(Client()).decide(PilotObservation(1,0,'{}')))


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY',raising=False)
    with pytest.raises(PilotUnavailable):
        create_client()


def test_real_sdk_serializes_request_and_parses_wire_response():
    sdk = pytest.importorskip('typesafe_sdk')
    httpx = pytest.importorskip('httpx2')
    def respond(request):
        body = json.loads(request.content)
        assert body['model'] == 'jev-latest'
        assert set(body['questions']) == {'turn','thrust','fire'}
        return httpx.Response(200, json={
            'model':'jev-latest', 'usage':{}, 'answers':{k:{
                'type':'choice','choice':v,'confidence':.9,
                'probabilities':{v:1.}} for k,v in
                zip(('turn','thrust','fire'),('none','thrust','fire'))}})
    async def exercise():
        async with sdk.AsyncTypeSafeClient(api_key='test-local',model='jev-latest',
                transport=httpx.MockTransport(respond),retry=sdk.RetryPolicy(max_retries=0)) as client:
            return await JevPilot(client).decide(PilotObservation(1,0,'{}'))
    assert asyncio.run(exercise()).action == ACTIONS['none_thrust_fire']


def test_game_import_does_not_require_sdk_or_key():
    import subprocess
    import sys
    code = '''
import builtins
original = builtins.__import__
def without_sdk(name, *args, **kwargs):
    if name.startswith('typesafe_sdk'):
        raise ImportError('SDK intentionally absent')
    return original(name, *args, **kwargs)
builtins.__import__ = without_sdk
from game import Game
from hunter.worker import PilotWorker
assert Game is not None
'''
    subprocess.run([sys.executable,'-c',code],check=True,capture_output=True,text=True)


def test_request_includes_observation_history_and_units_for_every_question():
    from entities.hunter_ship import HunterShip
    from hunter.perception import HunterPerception
    from hunter.model import NEUTRAL
    from tests.test_hunter_perception import maze
    ship,perception = HunterShip((150,150)),HunterPerception()
    for now in range(4):
        observation = perception.observe(ship,maze(),None,[],[],NEUTRAL,now,1)
    class Client:
        async def system_one(self, **kwargs):
            state = kwargs['state']
            assert state['snapshot_at_seconds'] == 3
            assert [s['snapshot_at_seconds'] for s in state['previous_states']] == [0,1,2]
            assert state['speed_metres_per_second'] == 0
            assert state['velocity_heading_degrees'] is None
            assert state['motion']['direction'] is None
            assert state['motion']['velocity_metres_per_second'] == {'x':0,'y':0}
            for question in kwargs['questions'].values():
                assert 'metres per second' in question['instructions']
                assert 'degrees per second' in question['instructions']
                assert 'oldest first' in question['instructions']
                assert 'motion vector' in question['instructions']
            return SimpleNamespace(choices={k:SimpleNamespace(choice=v,confidence=.8)
                for k,v in zip(('turn','thrust','fire'),('none','coast','hold'))})
    asyncio.run(JevPilot(Client()).decide(observation))
