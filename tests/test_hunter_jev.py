import asyncio
import json
from types import SimpleNamespace
import pytest
from hunter.model import ACTIONS, PilotObservation
from hunter.jev_pilot import JevPilot, create_client, PilotUnavailable


@pytest.mark.parametrize('choice', list(ACTIONS))
def test_jev_translates_typed_combined_action(choice):
    class Client:
        async def system_one(self, **kwargs):
            assert kwargs['state'] == {'visible_contacts': []}
            assert len(kwargs['questions']['pilot']['criteria']) == 12
            return SimpleNamespace(choices={'pilot':SimpleNamespace(choice=choice,confidence=.8)})
    decision = asyncio.run(JevPilot(Client()).decide(PilotObservation(1,10,json.dumps({'visible_contacts':[]}))))
    assert decision.action == ACTIONS[choice]
    assert decision.confidence == .8


@pytest.mark.parametrize('choice,confidence', [('teleport',.8), ('none_coast_hold',float('nan'))])
def test_invalid_model_outputs_rejected(choice,confidence):
    class Client:
        async def system_one(self, **kwargs):
            return SimpleNamespace(choices={'pilot':SimpleNamespace(choice=choice,confidence=confidence)})
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
        assert len(body['questions']['pilot']['criteria']) == 12
        return httpx.Response(200, json={
            'model':'jev-latest', 'usage':{}, 'answers':{'pilot':{
                'type':'choice','choice':'none_thrust_fire','confidence':.9,
                'probabilities':{'none_thrust_fire':1.}}}})
    async def exercise():
        async with sdk.AsyncTypeSafeClient(api_key='test-local',model='jev-latest',
                transport=httpx.MockTransport(respond),retry=sdk.RetryPolicy(max_retries=0)) as client:
            return await JevPilot(client).decide(PilotObservation(1,0,'{}'))
    assert asyncio.run(exercise()).action == ACTIONS['none_thrust_fire']
