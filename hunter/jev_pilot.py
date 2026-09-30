"""Typed Jev decision adapter. SDK imports and credentials are deliberately lazy."""
import json
import math
import os
from hunter.model import ACTIONS, PilotDecision
from hunter.pilot_sensors import pilot_state

PILOT_QUESTIONS = {
    'turn': {
        'type': 'choice',
        'instructions': 'Pilot an allied hunter. Choose one short steering pulse. '
            'Directions are relative to your nose. Pursue visible enemies; when none '
            'are visible, explore clear space toward unvisited cells or remembered enemies. '
            'Avoid blocked space. Stop turning when facing your destination. '
            'A pulse turns about 30 degrees, then holds heading.',
        'criteria': {
            'left': 'Turn left toward an enemy or open exploration route on your left.',
            'none': 'Hold heading: an enemy or open exploration route is ahead.',
            'right': 'Turn right toward an enemy or open exploration route on your right.'}},
    'thrust': {
        'type': 'choice',
        'instructions': 'Choose whether to accelerate forward now. Thrust adds momentum '
            'and coasting does not brake. Use the space ahead and current speed.',
        'criteria': {
            'thrust': 'Space ahead is clear and speed is slow: accelerate forward.',
            'coast': 'Space ahead is close or blocked, or speed is fast: stop accelerating.'}},
    'fire': {
        'type': 'choice',
        'instructions': 'Choose whether to fire forward at a currently visible enemy. '
            'Remembered enemies are not confirmed targets. The player is friendly.',
        'criteria': {
            'fire': 'A visible enemy is ahead: shoot.',
            'hold': 'No visible enemy is ahead: hold fire.'}},
}


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
            state=pilot_state(json.loads(observation.state_json)),
            questions=PILOT_QUESTIONS)
        answers = [result.choices[name] for name in ('turn','thrust','fire')]
        action = ACTIONS['_'.join(answer.choice for answer in answers)]
        confidences = []
        for answer in answers:
            confidence = getattr(answer, 'confidence', None)
            if confidence is not None:
                if (type(confidence) not in (int,float) or
                        not math.isfinite(confidence) or not 0 <= confidence <= 1):
                    raise ValueError('invalid confidence')
                confidences.append(confidence)
        return PilotDecision(action, min(confidences) if confidences else None)
