"""Typed Jev decision adapter. SDK imports and credentials are deliberately lazy."""
import json
import math
import os
from hunter.model import ACTIONS, PilotDecision

PILOT_INSTRUCTIONS = (
    'Pilot an allied hunter that independently explores and destroys enemies. '
    'Choose simultaneous turning, thrust and firing for the action horizon. '
    'Coordinates increase right and down; heading 0 points right, 90 down. '
    'Turn -1 means left (decrease heading), 0 holds, +1 means right. '
    'Thrust accelerates along heading; coast keeps momentum subject to friction '
    'and collision. Fire repeats forward shots only when cooldown permits. '
    'Velocity and projectile speed are pixels per normalised frame; fps is supplied. '
    'Avoid walls and hostile fire. Seek enemies or explore observed open exits. '
    'The player is friendly. Remembered sightings are stale; ages are seconds. '
    'Unknown geometry is not necessarily open. Map edges contain observed '
    '[start fraction, end fraction, blocked] portions, with gaps meaning unknown. '
    'Top/bottom edges run left to right; left/right edges run top to bottom.'
)


class PilotUnavailable(Exception):
    """A local configuration issue prevents decisions for this level."""


def create_client():
    if not os.environ.get('TYPESAFE_API_KEY', '').strip():
        raise PilotUnavailable('missing_key')
    try:
        from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy
    except ImportError:
        raise PilotUnavailable('missing_sdk') from None
    try:
        return AsyncTypeSafeClient(
            model=os.environ.get('TYPESAFE_DEFAULT_MODEL', '').strip() or 'jev-latest',
            timeout=1.0, retry=RetryPolicy(max_retries=0))
    except Exception:
        # Client construction performs validation, not an inference request.
        raise PilotUnavailable('invalid_configuration') from None


class JevPilot:
    def __init__(self, client):
        self.client = client

    async def decide(self, observation):
        result = await self.client.system_one(
            state=json.loads(observation.state_json),
            questions={'pilot': {
                'type': 'choice', 'instructions': PILOT_INSTRUCTIONS,
                'criteria': {name: {'turn':action.turn,'thrust':action.thrust,'fire':action.fire}
                             for name,action in ACTIONS.items()},
            }})
        answer = result.choices['pilot']
        action = ACTIONS[answer.choice]
        confidence = getattr(answer, 'confidence', None)
        if confidence is not None and (type(confidence) not in (int,float)
                                      or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError('invalid confidence')
        return PilotDecision(action,confidence)
