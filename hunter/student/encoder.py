"""Turns a pilot_state dict into the student's fixed-length feature vector."""
import math
import numpy as np

SPACE_NAMES = ('ahead', 'ahead_left', 'left', 'behind_left', 'behind', 'behind_right',
               'right', 'ahead_right')
TURN_DIRECTIONS = ('left', 'none', 'right', 'track', 'course')
SPEED_STATES = ('slow', 'cruising', 'too_fast')
THRUST_EFFECTS = ('slows', 'sideways', 'speeds_up')
RANGE_STATES = ('too_close', 'in_range', 'far')
ENEMY_SLOTS = 3
PROJECTILE_SLOTS = 3


class _Features:
    """Collects (name, value) pairs; names and values come from the same code path."""

    def __init__(self):
        self.items = []

    def number(self, name, value):
        self.items.append((name, 0.0 if value is None else float(value)))

    def flag(self, name, value):
        self.items.append((name, 1.0 if value else 0.0))

    def angle(self, name, degrees):
        # Linear for the +-20 degree thresholds, sin/cos so +-180 are neighbours.
        if degrees is None:
            linear = sin = cos = 0.0
        else:
            linear = max(-1.0, min(1.0, degrees / 180.0))
            sin, cos = math.sin(math.radians(degrees)), math.cos(math.radians(degrees))
        self.items.append((f'{name}.linear', linear))
        self.items.append((f'{name}.sin', sin))
        self.items.append((f'{name}.cos', cos))

    def onehot(self, name, value, options):
        for option in options:
            self.flag(f'{name}.{option}', value == option)


def _course(f, prefix, course):
    f.flag(f'{prefix}.present', course is not None)
    course = course or {}
    f.flag(f'{prefix}.burn_needed', course.get('burn_needed'))
    f.angle(f'{prefix}.burn_off_nose', course.get('burn_degrees_off_nose'))
    f.angle(f'{prefix}.burn_off_nose_next', course.get('burn_degrees_off_nose_at_next_decision'))
    f.number(f'{prefix}.burn_seconds', course.get('burn_seconds'))
    f.number(f'{prefix}.speed_after', course.get('speed_after_metres_per_second'))
    f.number(f'{prefix}.speed_limit', course.get('speed_limit_metres_per_second'))


def _features(state):
    f = _Features()
    motion = state.get('motion') or {}
    turning = state.get('turning') or {}
    f.number('speed', state.get('speed_metres_per_second'))
    f.number('speed_limit', state.get('speed_limit_metres_per_second'))
    f.number('rotation_speed', state.get('rotation_speed_degrees_per_second'))
    f.number('radius', state.get('radius_metres'))
    f.number('sensor_range', state.get('sensor_range_metres'))
    f.number('health', state.get('health'))
    f.number('turn_step', turning.get('degrees_per_decision'))
    f.onehot('turning', turning.get('direction'), TURN_DIRECTIONS)
    f.number('forward_speed', motion.get('forward_speed_metres_per_second'))
    f.number('rightward_speed', motion.get('rightward_speed_metres_per_second'))
    f.flag('wall_on_course', motion.get('wall_clearance_metres') is not None)
    f.number('wall_clearance', motion.get('wall_clearance_metres'))
    f.number('seconds_to_wall_impact', motion.get('seconds_to_wall_impact'))
    space = state.get('space') or {}
    for name in SPACE_NAMES:
        f.number(f'space.{name}', (space.get(name) or {}).get('clearance_metres'))

    brake = motion.get('brake') or {}
    f.onehot('brake.speed_state', brake.get('speed_state'), SPEED_STATES)
    f.onehot('brake.thrust_effect', brake.get('thrust_effect'), THRUST_EFFECTS)
    f.number('brake.safe_speed', brake.get('safe_speed_metres_per_second'))
    f.number('brake.stopping_distance', brake.get('stopping_distance_metres'))
    f.angle('brake.retrograde', brake.get('retrograde_degrees_off_nose'))
    f.angle('brake.retrograde_next', brake.get('retrograde_degrees_off_nose_at_next_decision'))
    f.number('brake.burn_seconds', brake.get('burn_seconds'))

    engage = state.get('engage')
    f.flag('engage.present', engage is not None)
    engage = engage or {}
    f.onehot('engage.range_state', engage.get('range_state'), RANGE_STATES)
    f.number('engage.distance', engage.get('distance_metres'))
    f.number('engage.standoff', engage.get('standoff_metres'))
    f.number('engage.closing_speed', engage.get('closing_speed_metres_per_second'))
    f.number('engage.target_closing_speed', engage.get('target_closing_speed_metres_per_second'))
    f.flag('engage.holding_still', engage.get('holding_still'))
    f.flag('engage.burn_needed', engage.get('burn_needed'))
    f.number('engage.burn_seconds', engage.get('burn_seconds'))

    powerup = state.get('collect_powerup')
    f.flag('powerup.present', powerup is not None)
    powerup = powerup or {}
    f.angle('powerup.off_nose_next', powerup.get('degrees_off_nose_at_next_decision'))
    f.number('powerup.distance', powerup.get('distance_metres'))
    _course(f, 'powerup.course', powerup.get('course'))

    follow = state.get('follow_player')
    f.flag('follow.present', follow is not None)
    follow = follow or {}
    f.angle('follow.off_nose_next', follow.get('degrees_off_nose_at_next_decision'))
    f.number('follow.waypoint_distance', follow.get('waypoint_distance_metres'))
    f.number('follow.route_distance', follow.get('route_distance_metres'))
    f.flag('follow.player_visible', follow.get('player_visible'))
    f.flag('follow.alongside', follow.get('alongside'))
    _course(f, 'follow.course', follow.get('course'))

    wall = state.get('wall_follow')
    f.flag('wall_follow.present', wall is not None)
    wall = wall or {}
    f.angle('wall_follow.off_nose_next', wall.get('degrees_off_nose_at_next_decision'))
    f.flag('wall_follow.wall_in_sight', wall.get('wall_distance_metres') is not None)
    f.number('wall_follow.wall_distance', wall.get('wall_distance_metres'))
    _course(f, 'wall_follow.course', wall.get('course'))

    # Enemies keep the order they arrive in: the engage reading takes the first one with an aim.
    enemies = [c for c in state.get('visible_contacts') or [] if c.get('allegiance') == 'enemy']
    f.number('enemies.visible', len(enemies))
    f.flag('enemies.any_aim', any(c.get('aim') for c in enemies))
    f.number('enemies.remembered', len(state.get('remembered_contacts') or []))
    for slot in range(ENEMY_SLOTS):
        enemy = enemies[slot] if slot < len(enemies) else None
        aim = (enemy or {}).get('aim')
        p = f'enemy{slot}'
        f.flag(f'{p}.present', enemy is not None)
        f.flag(f'{p}.has_aim', aim is not None)
        f.angle(f'{p}.off_nose_next', (enemy or {}).get('degrees_off_nose_at_next_decision'))
        f.number(f'{p}.distance', (enemy or {}).get('distance_metres'))
        aim = aim or {}
        f.angle(f'{p}.lead', aim.get('lead_degrees_off_nose'))
        f.angle(f'{p}.lead_next', aim.get('lead_degrees_off_nose_at_next_decision'))
        f.number(f'{p}.seconds_to_hit', aim.get('seconds_to_hit'))
        f.flag(f'{p}.on_target', aim.get('on_target'))
        f.number(f'{p}.miss_distance', aim.get('miss_distance_metres'))

    projectiles = sorted(state.get('hostile_projectiles') or [],
                         key=lambda c: c.get('distance_metres', 0))
    f.number('projectiles.visible', len(projectiles))
    for slot in range(PROJECTILE_SLOTS):
        shot = projectiles[slot] if slot < len(projectiles) else None
        p = f'projectile{slot}'
        f.flag(f'{p}.present', shot is not None)
        f.angle(f'{p}.off_nose', (shot or {}).get('degrees_off_nose'))
        f.number(f'{p}.distance', (shot or {}).get('distance_metres'))
    return f.items


FEATURE_NAMES = tuple(name for name, _ in _features({}))


def encode(state):
    """The feature vector for one pilot state, in FEATURE_NAMES order."""
    return np.array([value for _, value in _features(state)], dtype=np.float32)
