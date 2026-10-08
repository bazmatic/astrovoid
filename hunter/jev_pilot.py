"""Typed Jev decision adapter. SDK imports and credentials are deliberately lazy."""
import json
import math
import os
from dataclasses import replace
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
    '`motion.brake` is a worked braking solution. It finds the wall your hull will actually '
    'reach on your present motion vector and compares the distance a stop needs with the '
    'room you have. Moving fast alongside a wall is not moving towards it: only a wall on '
    'your course counts, however near others are. With no wall on your course the room is '
    'your sensor range. There are no brakes: stopping means swinging the nose against the '
    'motion vector and thrusting. brake.stopping_distance_metres is the room a stop needs '
    'now, including the swing of the nose, and brake.safe_speed_metres_per_second is the '
    'fastest speed from which you could still stop in the room you have. brake.speed_state '
    'compares your speed with that: slow (under half), cruising (over half), or too_fast '
    '(the stop no longer fits: brake now). It is never too_fast at a crawl, when touching '
    'a wall would not matter. brake.thrust_effect says what the engine would do to your '
    'speed with the nose where it is: speeds_up, sideways, or slows. '
    'brake.burn_heading_degrees and brake.burn_seconds are the braking burn itself. When '
    'brake.speed_state is too_fast, the ship\'s navigator flies that burn for you: choose '
    'the steering `course` and hold the engine on, and it swings the nose to the braking '
    'attitude, fires only once lined up and cuts the engine when the ship has stopped. '
)

POWERUP_INSTRUCTIONS = (
    '`collect_powerup` is your job whenever no enemy is visible and a powerup crystal is in '
    'sight: fly onto it. Touching a powerup collects it and upgrades your guns: first a '
    'faster rate of fire, then a three-way spread, then bigger and faster shots. It is null '
    'when no powerup is in sight. It points at the nearest powerup you can see: '
    'degrees_off_nose_at_next_decision is where it will be relative to the nose when your '
    'choice takes over (negative left, positive right), distance_metres is how far it is, '
    'and collect_powerup.course is the navigation course that flies you onto it. There is '
    'no need to stop at a powerup: flying through it collects it. Collecting a powerup '
    'outranks following the player and following a wall, and you go back to those once it '
    'is collected. '
)

FOLLOW_INSTRUCTIONS = (
    '`follow_player` is your job whenever no enemy is visible and there is no powerup to '
    'collect: follow the friendly player ship. It is null when there is no player or no open route to it. It points at the next waypoint on the '
    'route through the maze to the player (the player itself when player_visible is true): '
    'degrees_off_nose_at_next_decision is where that waypoint will be relative to the nose '
    'when your choice takes over (negative left, positive right), waypoint_distance_metres '
    'is how far it is, route_distance_metres is the length of the whole route, and alongside '
    'is true when you are already next to the player. '
)

COURSE_INSTRUCTIONS = (
    'A navigation course is a worked course correction: the turn and burn that leave your '
    'motion vector pointing straight at where you need to go without going too fast. '
    'Pointing the nose at a place and thrusting does not do that, because thrust adds to '
    'the motion you already have; the nose must point where the change in motion has to '
    'go. course.burn_degrees_off_nose is where the nose must point for the burn, relative '
    'to where it points now (negative left, positive right), and course.burn_seconds is '
    'how long the engine must then fire. course.burn_needed is false when the motion '
    'vector is already where it should be at a good speed. '
    'course.speed_after_metres_per_second is your speed once the burn is done and '
    'course.speed_limit_metres_per_second is the too-fast speed it stays under, set by '
    'the room to stop beyond the destination. '
    'The ship has a navigator that flies a course for you. Choosing the steering `course` '
    'hands the nose to it: it swings the nose onto the burn heading and holds it there. '
    'While you also hold the engine on, the navigator fires it only once the nose is lined '
    'up and cuts it when the burn is complete, so holding thrust on a course never '
    'overshoots. Held left or right steering cannot do this: it moves the nose about '
    '`turning.degrees_per_decision` degrees per decision. '
)

WALL_FOLLOW_INSTRUCTIONS = (
    '`wall_follow` is your job when there is nobody to follow: no enemy is visible, there '
    'is no powerup to collect and follow_player is null because there is no player or no '
    'open route to it. You are cut '
    'off, so explore by keeping a wall on your left and moving along it; in a maze that '
    'leads past every opening. wall_follow.degrees_off_nose is the direction to travel, '
    'parallel to the nearest wall with that wall on your left, wall_follow.wall_distance_metres '
    'is the gap between your hull and that wall (null when no wall is in sight, and the '
    'direction is then straight ahead to find one), and wall_follow.course is the '
    'navigation course that takes you that way. wall_follow is null whenever follow_player '
    'is not. The navigation course is collect_powerup.course when collect_powerup is not '
    'null; otherwise it is follow_player.course when follow_player is not null, and '
    'wall_follow.course otherwise. '
)

ENGINE_INSTRUCTIONS = (
    'The engine has four settings, and your choice lasts until your next decision. '
    'coast: engine off. '
    'pulse: one short burn of a tenth of a second, a nudge of about 13 metres per second '
    'along the nose. Choosing pulse again at the next decision pulses again, so repeated '
    'pulses work like a low throttle. '
    'burn: the worked burn. The ship fires the engine for exactly the worked length and '
    'only while the nose is on the burn\'s heading, then cuts it, so it never overshoots. '
    'With a worked burn of zero it does not fire at all. '
    'thrust: engine on, wherever the nose points, until your next decision. That adds '
    'about 60 metres per second each decision; it is the coarsest setting. '
)

ENGAGE_INSTRUCTIONS = (
    '`engage` is the worked approach to the enemy that fire control is engaging: the '
    'nearest visible enemy with a non-null aim. It is null when there is none. While you '
    'track, the nose stays on that enemy, so the engine can only push you towards it. '
    'engage.distance_metres is how far it is and engage.standoff_metres is the distance '
    'to fight from. engage.range_state is far (outside the standoff), in_range, or '
    'too_close. engage.closing_speed_metres_per_second is how fast you are closing on it '
    '(negative when it is getting further away) and '
    'engage.target_closing_speed_metres_per_second is the fastest closing speed from '
    'which you could still turn round and stop at the standoff. engage.burn_seconds is '
    'the worked burn along the nose that brings your closing speed up to that; '
    'engage.burn_needed is false when you are already closing fast enough or are inside '
    'the standoff. engage.holding_still is true when you are barely moving. '
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
            'as a visible enemy has a non-null `aim`. ' + POWERUP_INSTRUCTIONS + FOLLOW_INSTRUCTIONS +
            COURSE_INSTRUCTIONS + WALL_FOLLOW_INSTRUCTIONS +
            'When no enemy is visible and the navigation course is not null, the steering '
            'is course, whichever way the burn heading lies; do not steer a course with left '
            'or right. `turning.direction` is course while the navigator already has the '
            'nose: keep choosing course for as long as there is a navigation course and no '
            'visible enemy. When no enemy is visible and there is no navigation course '
            'because follow_player.alongside is true, the target is the follow_player '
            'waypoint and the value is follow_player.degrees_off_nose_at_next_decision. With '
            'no visible enemy, no follow_player and no wall_follow, hold the heading. '
            + BRAKE_INSTRUCTIONS +
            'Avoiding walls outranks everything else: when brake.speed_state is too_fast the '
            'steering is course, whatever enemies are visible, so the navigator can fly the '
            'braking burn.',
        'criteria': {
            'course': 'Hand the nose to the navigator: brake.speed_state is too_fast; or no '
                      'visible enemy has an aim and the navigation course '
                      '(collect_powerup.course when collect_powerup is not null, '
                      'otherwise follow_player.course, or wall_follow.course when '
                      'follow_player is null) is not null.',
            'track': 'Hand the nose to fire control: brake.speed_state is not too_fast and a '
                     'visible enemy has a non-null aim.',
            'left': 'Hold left: brake.speed_state is not too_fast, no visible enemy has an '
                    'aim, there is no navigation course, and '
                    'follow_player.degrees_off_nose_at_next_decision is below -20.',
            'none': 'Hold no steering: brake.speed_state is not too_fast, no visible enemy '
                    'has an aim, there is no navigation course, and '
                    'follow_player.degrees_off_nose_at_next_decision is between -20 and 20 '
                    'or there is no follow_player.',
            'right': 'Hold right: brake.speed_state is not too_fast, no visible enemy has an '
                     'aim, there is no navigation course, and '
                     'follow_player.degrees_off_nose_at_next_decision is above 20.'}},
    'thrust': {
        'type': 'choice',
        'instructions': SHARED_INSTRUCTIONS + BRAKE_INSTRUCTIONS + ENGINE_INSTRUCTIONS +
            'Choose the engine setting. This is independent of steering and shooting: the '
            'ship can thrust while it turns and while it fires. In every situation a worked '
            'burn tells you whether the engine is wanted, so the usual choice is between '
            'burn and coast. '
            'When brake.speed_state is too_fast the worked burn is the braking burn: choose '
            'burn, wherever the nose points. '
            + ENGAGE_INSTRUCTIONS +
            'When brake.speed_state is not too_fast and engage is not null you are fighting: '
            'choose burn while engage.burn_needed is true. When it is false, a hunter '
            'sitting still is an easy target, so choose pulse if engage.holding_still is '
            'true and engage.range_state is in_range, and coast otherwise. '
            + POWERUP_INSTRUCTIONS + FOLLOW_INSTRUCTIONS + COURSE_INSTRUCTIONS
            + WALL_FOLLOW_INSTRUCTIONS +
            'When brake.speed_state is not too_fast, engage is null and the navigation '
            'course is not null you are flying that course: choose burn while the course\'s '
            'burn_needed is true and coast when it is false. '
            'When brake.speed_state is not too_fast, engage is null and there is no '
            'navigation course, you are alongside the player or have nowhere to go: hold '
            'station, so coast, unless brake.thrust_effect is slows, when thrust takes off '
            'the speed you still have.',
        'criteria': {
            'burn': 'brake.speed_state is too_fast; or it is not too_fast and engage is not '
                    'null and engage.burn_needed is true; or it is not too_fast, engage is '
                    'null, and the navigation course (collect_powerup.course when '
                    'collect_powerup is not null, otherwise follow_player.course, or '
                    'wall_follow.course when follow_player is null) is not null and its '
                    'burn_needed is true.',
            'pulse': 'brake.speed_state is not too_fast, engage is not null, '
                     'engage.burn_needed is false, engage.holding_still is true and '
                     'engage.range_state is in_range.',
            'thrust': 'brake.speed_state is not too_fast, engage is null, there is no '
                      'navigation course, and brake.thrust_effect is slows.',
            'coast': 'brake.speed_state is not too_fast and: engage is not null, '
                     'engage.burn_needed is false, and engage.holding_still is false or '
                     'engage.range_state is not in_range; or engage is null and the '
                     'navigation course is not null with burn_needed false; or engage is '
                     'null, there is no navigation course, and brake.thrust_effect is not '
                     'slows.'}},
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


def navigation_course(state):
    """The burn the navigator flies on a course decision.

    Braking for a wall comes first. Otherwise it is the course with no enemy to
    engage: onto a powerup in sight, else to the player, or else along a wall.
    """
    brake = state.get('motion', {}).get('brake', {})
    if brake.get('speed_state') == 'too_fast':
        return {'burn_needed': True, 'burn_heading_degrees': brake['burn_heading_degrees'],
                'burn_seconds': brake['burn_seconds']}
    navigation = (state.get('collect_powerup') or state.get('follow_player')
                  or state.get('wall_follow'))
    return navigation.get('course') if navigation else None


def worked_burn(state):
    """The burn the engine setting `burn` flies: braking first, then the fight, then the course."""
    brake = state.get('motion', {}).get('brake', {})
    if brake.get('speed_state') != 'too_fast' and state.get('engage'):
        return state['engage']
    return navigation_course(state)


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
        # A fresh copy each time: the ship tells one decision from the next by identity,
        # so that a repeated pulse pulses again.
        action = replace(ACTIONS['_'.join(answer.choice for answer in answers)])
        # The navigator and the worked burn fly what the pilot was looking at when it chose.
        fps = observation_state.get('physics', {}).get('fps', 60)
        course = navigation_course(state) if action.course else None
        if course is not None:
            action = replace(action, burn_heading=course['burn_heading_degrees'])
        if action.worked_burn:
            burn = course if action.course else worked_burn(state)
            if burn is not None:
                action = replace(
                    action, burn_heading=burn['burn_heading_degrees'],
                    burn_frames=burn['burn_seconds'] * fps if burn['burn_needed'] else 0.0,
                    burn_reference=observation_state.get('self', {}).get('thrust_frames', 0))
        confidences = []
        for answer in answers:
            confidence = getattr(answer, 'confidence', None)
            if confidence is not None:
                if (type(confidence) not in (int,float) or
                        not math.isfinite(confidence) or not 0 <= confidence <= 1):
                    raise ValueError('invalid confidence')
                confidences.append(confidence)
        return PilotDecision(action, min(confidences) if confidences else None)
