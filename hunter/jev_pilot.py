"""Typed Jev decision adapter. SDK imports and credentials are deliberately lazy."""
import json
import math
import os
from hunter.model import ACTIONS, PilotDecision
from hunter.pilot_sensors import pilot_state

UNITS_INSTRUCTIONS = (
    'All distances and wall clearances are in metres (one game world unit is one metre). '
    'Speeds are metres per second; rotation_speed_degrees_per_second is degrees per second. '
    'Headings are absolute degrees: 0 east/right, 90 south/down, 180 west/left, 270 north/up. '
    'Your heading_degrees is nose orientation; velocity_heading_degrees is travel direction '
    '(null when stationary). Contact heading_degrees is the bearing from you to that contact, '
    'and distance_metres is its distance from your centre, not its own orientation. '
    'Wall clearance is measured from your hull; sensor-range clearance is a sensing limit, '
    'not proof of an actual wall there. Direction labels are relative to your nose. '
    'previous_states contains up to three earlier observations, oldest first; '
    'snapshot_at_seconds is a monotonic timestamp in seconds. Use changes across states '
    'to judge motion, but use the current observation for immediate controls. '
)

PHYSICS_INSTRUCTIONS = (
    'You pilot an allied hunter that steers like the ship in the old Atari "Asteroids" game. '
    'You can pivot and thrust, and the rules of momentum and motion vectors apply. '
    'Turning only pivots the nose; it does not change where the ship is travelling. '
    'Thrust accelerates along the nose and adds to the existing velocity, so the ship '
    'keeps drifting along its motion vector until thrust in another direction changes it. '
    'There are no brakes and almost no drag: the only way to slow down is to point the nose '
    'against the motion vector and thrust. '
    '`motion` is your current motion vector: velocity_metres_per_second is its absolute x/y '
    '(x east/right, y south/down), direction is where you are travelling relative to your nose '
    '(null when stationary), forward_speed_metres_per_second is the part along your nose '
    '(negative when drifting backwards) and rightward_speed_metres_per_second is the sideways '
    'drift (negative when drifting left). wall_clearance_metres is the distance the hull can '
    'travel along the motion vector before touching a wall, and seconds_to_wall_impact is '
    'how long until that impact if the ship coasts with the engine off from now (null when '
    'stationary, when no wall is sensed on that course, or when drag stops the ship first). Judge wall collisions by seconds_to_wall_impact, not only the clearance ahead '
    'of your nose. '
)

AIM_INSTRUCTIONS = (
    'Each visible enemy has an `aim` firing solution worked out from its motion, your motion '
    'and shot speed (null when a shot cannot reach it). Shots travel straight along the nose '
    'and do not inherit your velocity, so a moving enemy must be led: '
    'aim.lead_degrees_off_nose is where the nose must point, relative to where it points now, '
    'for a shot fired now to meet the enemy, and aim.lead_degrees_off_nose_at_next_decision is '
    'the same for a shot fired when your choice takes over (negative left, positive right). '
    'aim.on_target is true when a shot fired along the present nose would hit, '
    'aim.miss_distance_metres is how far such a shot would pass from the enemy\'s hull, and '
    'aim.seconds_to_hit is the shot\'s flight time. '
)

FIRE_CONTROL_INSTRUCTIONS = (
    'The ship has fire control that does the fine aiming for you. Choosing the steering '
    '`track` hands the nose to it: it swings the nose at the normal turn rate, the shortest '
    'way round, onto the firing solution of the nearest visible enemy that has one (a '
    'non-null `aim`), settles exactly on it and keeps following it as either ship moves. '
    'Held left or right steering is too coarse to line up a shot: it moves the nose about '
    '`turning.degrees_per_decision` degrees per decision, many times the width of an enemy. '
    'Fire control also holds the trigger for you: while you hold the trigger, a shot is '
    'released only on a frame when the nose is on target, so holding it never wastes shots. '
)

BRAKE_INSTRUCTIONS = (
    '`motion.brake` is a braking solution for the wall on your present course. There are no '
    'brakes: slowing means swinging the nose against the motion vector and thrusting. '
    'brake.safe_speed_metres_per_second is the fastest you can travel and still stop before '
    'that wall from your present attitude, and brake.stopping_distance_metres is the room a '
    'stop needs now. brake.speed_state compares your speed with the safe speed: slow (under '
    'half), cruising (over half), or too_fast (over it: you will hit the wall unless you '
    'start braking now). brake.thrust_effect says what the engine would do to your speed '
    'with the nose where it is: speeds_up, sideways, or slows. '
    'brake.retrograde_degrees_off_nose_at_next_decision is where the braking attitude will '
    'be relative to the nose when your choice takes over (negative left, positive right). '
)

FOLLOW_INSTRUCTIONS = (
    '`follow_player` is your job whenever no enemy is visible: follow the friendly player '
    'ship. It is null only when there is no player to follow. It points at the next waypoint on the '
    'route through the maze to the player (the player itself when player_visible is true): '
    'degrees_off_nose_at_next_decision is where that waypoint will be relative to the nose '
    'when your choice takes over (negative left, positive right), waypoint_distance_metres '
    'is how far it is, route_distance_metres is the length of the whole route, and alongside '
    'is true when you are already next to the player. '
)

COURSE_INSTRUCTIONS = (
    '`follow_player.course` is a worked course correction: the turn and burn that leave '
    'your motion vector pointing straight at the follow_player waypoint without going too '
    'fast. Pointing the nose at the waypoint and thrusting does not do that, because '
    'thrust adds to the motion you already have; the nose must point where the change in '
    'motion has to go. course.burn_degrees_off_nose is where the nose must point for the '
    'burn, relative to where it points now, and '
    'course.burn_degrees_off_nose_at_next_decision is the same when your choice takes over '
    '(negative left, positive right). course.burn_seconds is how long the engine must '
    'then fire. course.burn_needed is false when the motion vector is already on the '
    'waypoint at a good speed, or so nearly that no burn is worth flying. '
    'course.speed_after_metres_per_second is your speed once the burn is done and '
    'course.speed_limit_metres_per_second is the too-fast speed it stays under, set by '
    'the room to stop beyond the waypoint. The course is null when there is nothing to '
    'follow or you are already alongside the player. '
)

SHARED_INSTRUCTIONS = UNITS_INSTRUCTIONS + PHYSICS_INSTRUCTIONS

PILOT_QUESTIONS = {
    'turn': {
        'type': 'choice',
        'instructions': SHARED_INSTRUCTIONS + 'Choose the steering to hold. Steering works like '
            'a held key: left or right keeps the nose rotating at '
            'rotation_speed_degrees_per_second until a later decision chooses otherwise, and '
            'none stops the rotation and holds the heading. `turning.direction` is the steering '
            'held right now. Your choice only replaces it at the next decision, by which time a '
            'held turn has rotated the nose about `turning.degrees_per_decision` degrees further. '
            'Each contact and the follow_player waypoint therefore has degrees_off_nose_at_next_decision: '
            'where it will be relative to the nose when your choice takes over. Negative is to '
            'the left, positive to the right, and within 20 either way counts as ahead. '
            'Steer by that value, not by where things are now. ' + AIM_INSTRUCTIONS +
            FIRE_CONTROL_INSTRUCTIONS +
            'Pick a target: engage visible enemies. Whenever a visible enemy has a non-null '
            '`aim`, the steering is track, however far off the nose it is and whichever side '
            'it is on; do not steer at an enemy with left or right. `turning.direction` is '
            'track while fire control already has the nose: keep choosing track for as long '
            'as a visible enemy has a non-null `aim`. ' + FOLLOW_INSTRUCTIONS +
            COURSE_INSTRUCTIONS +
            'When no enemy is visible, the target is the course burn: while '
            'follow_player.course.burn_needed is true the value is '
            'follow_player.course.burn_degrees_off_nose_at_next_decision, so the nose is ready '
            'for the burn. When follow_player.course.burn_needed is false or the course is '
            'null, the target is the follow_player waypoint itself and the value is '
            'follow_player.degrees_off_nose_at_next_decision. With no visible enemy and no '
            'follow_player, hold the heading. '
            + BRAKE_INSTRUCTIONS +
            'Avoiding walls outranks everything else: when brake.speed_state is too_fast, the '
            'target is the braking attitude and its value is '
            'brake.retrograde_degrees_off_nose_at_next_decision, whatever enemies are visible, '
            'and the steering is left, none or right, never track.',
        'criteria': {
            'track': 'Hand the nose to fire control: brake.speed_state is not too_fast and a '
                     'visible enemy has a non-null aim.',
            'left': 'Hold left: the target\'s value at the next decision (the braking attitude '
                    'when too_fast; else, with no visible enemy that has an aim, the '
                    'course burn while follow_player.course.burn_needed is true, otherwise '
                    'the follow_player waypoint) is below -20.',
            'none': 'Hold no steering: the target\'s value at the next decision (the braking '
                    'attitude when too_fast; else, with no visible enemy that has an aim, the '
                    'course burn while follow_player.course.burn_needed is true, otherwise '
                    'the follow_player waypoint) is between -20 and 20; or there is no target.',
            'right': 'Hold right: the target\'s value at the next decision (the braking attitude '
                     'when too_fast; else, with no visible enemy that has an aim, the '
                     'course burn while follow_player.course.burn_needed is true, otherwise '
                     'the follow_player waypoint) is above 20, or the target is '
                     'directly behind.'}},
    'thrust': {
        'type': 'choice',
        'instructions': SHARED_INSTRUCTIONS + BRAKE_INSTRUCTIONS + 'Choose whether to fire the '
            'engine now. This is independent of steering and shooting: the ship can thrust '
            'while it turns and while it fires. Keep the hunter moving without hitting walls. '
            'A slow or stationary hunter is an easy target and cannot chase, dodge, or keep up, '
            'so when brake.speed_state is slow, thrust. When it is cruising, the ship is as '
            'fast as it can safely go: thrust only if brake.thrust_effect is sideways or slows, '
            'and coast if it is speeds_up. When it is too_fast, the ship must shed speed: thrust '
            'if brake.thrust_effect is slows or sideways, and coast if it is speeds_up, '
            'because more speed makes the collision certain. ' + FOLLOW_INSTRUCTIONS +
            'When no enemy is visible and follow_player.alongside is true you have caught up '
            'with the player: hold station and do not add speed, so coast unless '
            'brake.thrust_effect is slows. ' + COURSE_INSTRUCTIONS +
            'When no enemy is visible and follow_player.course is not null you are flying '
            'that course, and it replaces the slow and cruising guidance above: unless '
            'brake.speed_state is too_fast, thrust only while follow_player.course.burn_needed '
            'is true and follow_player.course.burn_degrees_off_nose is between -20 and 20, '
            'and coast the rest of the time, including while the nose is still swinging '
            'round to the burn.',
        'criteria': {
            'thrust': 'brake.speed_state is too_fast and brake.thrust_effect is slows or '
                      'sideways; or you are flying a course (no enemy visible and '
                      'follow_player.course not null), brake.speed_state is not too_fast, '
                      'follow_player.course.burn_needed is true and '
                      'follow_player.course.burn_degrees_off_nose is between -20 and 20; or '
                      'you are not flying a course and brake.thrust_effect is slows; or you '
                      'are not flying a course, are not alongside the player with no enemy '
                      'visible, and brake.speed_state is slow or brake.thrust_effect is '
                      'sideways.',
            'coast': 'brake.speed_state is too_fast and brake.thrust_effect is speeds_up; or '
                     'you are flying a course, brake.speed_state is not too_fast, and '
                     'follow_player.course.burn_needed is false or '
                     'follow_player.course.burn_degrees_off_nose is outside -20 to 20; or you '
                     'are not flying a course and brake.thrust_effect is speeds_up while '
                     'brake.speed_state is cruising; or no enemy is visible, '
                     'follow_player.alongside is true and brake.thrust_effect is not slows.'}},
    'fire': {
        'type': 'choice',
        'instructions': SHARED_INSTRUCTIONS + AIM_INSTRUCTIONS + FIRE_CONTROL_INSTRUCTIONS +
            'Choose whether to hold the trigger. Because fire control releases shots only '
            'when they will hit, hold the trigger for as long as any visible enemy has a '
            'firing solution, wherever the nose points; the shots come as soon as the nose '
            'arrives. Remembered enemies are not confirmed targets. The player is friendly.',
        'criteria': {
            'fire': 'A visible enemy has a non-null aim: hold the trigger.',
            'hold': 'No visible enemy has a non-null aim: release the trigger.'}},
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
        observation_state = json.loads(observation.state_json)
        state = pilot_state(observation_state)
        state['previous_states'] = observation_state.get('previous_states', [])
        result = await self.client.system_one(
            state=state,
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
