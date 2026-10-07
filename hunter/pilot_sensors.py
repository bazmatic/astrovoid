"""Translate sensed geometry into body-relative readings, without choosing controls."""
import math
from hunter.braking import braking_solution, hull_travel
from hunter.course import course_correction
from hunter.visibility import visible_point
from hunter.wall_follow import wall_follow_target


# Below this a brush with a wall is harmless, so the hunter is never told to brake.
HARMLESS_SPEED_METRES_PER_SECOND = 15
# The distance the hunter fights from, in maze cells.
ENGAGE_STANDOFF_CELLS = 1.5


def direction(bearing, heading):
    error = (bearing-heading+180) % 360-180
    if abs(error) <= 20:
        return 'ahead'
    if abs(error) >= 160:
        return 'behind'
    return 'left' if error < 0 else 'right'


def off_nose(bearing, heading, digits=1):
    error = (bearing-heading+180) % 360-180
    return error if digits is None else round(error,digits)


def nose_miss_distance(relative, velocity, heading, shot_speed, shot_lifetime):
    """How close a shot along the nose passes to a steady target's centre, or None if it never arrives."""
    nose = math.radians(heading)
    ux,uy = math.cos(nose)*shot_speed-velocity[0],math.sin(nose)*shot_speed-velocity[1]
    closest = (relative[0]*ux+relative[1]*uy)/(ux*ux+uy*uy)
    if not 0 < closest <= shot_lifetime:
        return None
    return math.hypot(relative[0]-ux*closest,relative[1]-uy*closest)


def firing_solution(relative, velocity, shot_speed):
    """Frames until, and bearing of, the point where a shot fired now meets a steady target."""
    rx,ry = relative
    vx,vy = velocity
    a = vx*vx+vy*vy-shot_speed*shot_speed
    b = 2*(rx*vx+ry*vy)
    c = rx*rx+ry*ry
    if abs(a) < 1e-9:
        times = [-c/b] if b < 0 else []
    else:
        root = b*b-4*a*c
        if root < 0:
            return None
        times = [(-b-math.sqrt(root))/(2*a),(-b+math.sqrt(root))/(2*a)]
    times = [t for t in times if t > 0]
    if not times:
        return None
    frames = min(times)
    return frames,math.degrees(math.atan2(ry+vy*frames,rx+vx*frames))


def pilot_state(state):
    ship = state.get('self', {})
    origin = ship.get('position', [0,0])
    heading = ship.get('heading', 0)
    radius = ship.get('radius', 10)
    cell_size = state.get('cell_size', 100)
    sensor_range = state.get('sensor_range', cell_size*4)
    walls = state.get('visible_walls', [])
    fps = state.get('physics',{}).get('fps',60)
    rotation_speed = state.get('physics',{}).get('rotation_per_frame',5)*fps
    # The held steering input keeps rotating the nose until a later decision replaces it,
    # so bearings are also given relative to where the nose will be by then.
    turn = state.get('previous_action',{}).get('turn',0)
    tracking = state.get('previous_action',{}).get('track',False)
    on_course = state.get('previous_action',{}).get('course',False)
    turn_step = rotation_speed*state.get('action_horizon_seconds',.25)
    turning = {'direction':('track' if tracking else 'course' if on_course else
                            'left' if turn < 0 else 'right' if turn > 0 else 'none'),
               'degrees_per_decision':turn_step}
    next_heading = heading+turn*turn_step

    physics = state.get('physics',{})
    shot_speed = physics.get('projectile_speed',8)
    shot_lifetime = physics.get('projectile_lifetime',120)
    own_velocity = ship.get('velocity',[0,0])
    horizon_frames = state.get('action_horizon_seconds',.25)*fps

    def aim(c):
        """Where the nose must point for a shot to meet this contact on its present course."""
        relative,velocity = c['relative_position'],c['velocity']
        now = firing_solution(relative,velocity,shot_speed)
        if now is None or now[0] > shot_lifetime:
            return None
        # By the next decision both ships have moved; shots do not inherit our velocity.
        later = firing_solution(
            [relative[i]+(velocity[i]-own_velocity[i])*horizon_frames for i in (0,1)],
            velocity,shot_speed)
        # A shot along the present nose: how close does it pass to the contact?
        miss = nose_miss_distance(relative,velocity,heading,shot_speed,shot_lifetime)
        reach = c.get('radius',10)+physics.get('projectile_radius',3)
        return {'lead_degrees_off_nose':off_nose(now[1],heading),
                'lead_degrees_off_nose_at_next_decision':
                    off_nose(later[1],next_heading) if later else None,
                'seconds_to_hit':round(now[0]/fps,2),
                'on_target':miss is not None and miss <= reach,
                'miss_distance_metres':None if miss is None else round(max(0,miss-reach),1)}

    def bearings(bearing):
        return {'direction':direction(bearing,heading),
                'degrees_off_nose':off_nose(bearing,heading),
                'degrees_off_nose_at_next_decision':off_nose(bearing,next_heading)}

    def contact(c, target=False):
        reading = {'id':c['id'], 'allegiance':c['allegiance'], **bearings(c['bearing']),
                   'heading_degrees':c['bearing'] % 360,
                   'distance_metres':c['distance'],
                   'age_seconds':round(c.get('age',0),1)}
        if target and c['allegiance'] == 'enemy':
            reading['aim'] = aim(c)
        return reading

    # Three rays per bearing measure a small corridor, accounting for ship size.
    # Only locally observed walls are available here; no hidden world queries.
    def ray(start, bearing):
        angle = math.radians(bearing)
        dx,dy = math.cos(angle),math.sin(angle)
        nearest = None
        for a,b in walls:
            ex,ey = b[0]-a[0],b[1]-a[1]
            denom = dx*ey-dy*ex
            if abs(denom) < 1e-9:
                continue
            ax,ay = a[0]-start[0],a[1]-start[1]
            t,u = (ax*ey-ay*ex)/denom,(ax*dy-ay*dx)/denom
            if t >= 0 and 0 <= u <= 1 and (nearest is None or t < nearest):
                nearest = t
        return nearest

    def clearance(bearing):
        hits = [ray(origin,bearing+spread) for spread in (-10,0,10)]
        return max(0,min([sensor_range]+[t for t in hits if t is not None])-radius)

    space = {}
    for name,offset in [('ahead',0),('ahead_left',-45),('left',-90),
                        ('behind_left',-135),('behind',180),('behind_right',135),
                        ('right',90),('ahead_right',45)]:
        space[name] = {'heading_degrees':(heading+offset) % 360,
                       'clearance_metres':clearance(heading+offset)}

    speed = math.hypot(*ship.get('velocity',[0,0]))
    speed_limit = state.get('physics',{}).get('speed_limit',8)
    visible = state.get('visible_contacts',[])
    visible_ids = {c['id'] for c in visible}
    velocity = ship.get('velocity',[0,0])
    velocity_heading = math.degrees(math.atan2(velocity[1],velocity[0])) if speed else None
    nose = math.radians(heading)
    # Right of the nose is heading+90 because y grows downward.
    motion = {'velocity_metres_per_second':{'x':velocity[0]*fps,'y':velocity[1]*fps},
              'direction':direction(velocity_heading,heading) if speed else None,
              'forward_speed_metres_per_second':
                  (velocity[0]*math.cos(nose)+velocity[1]*math.sin(nose))*fps,
              'rightward_speed_metres_per_second':
                  (velocity[1]*math.cos(nose)-velocity[0]*math.sin(nose))*fps,
              'wall_clearance_metres':None, 'seconds_to_wall_impact':None}
    # Whether the ship must brake is worked out, not judged: the wall the hull will
    # really reach on its present motion, against the distance a stop takes. Sliding
    # along a wall is not closing on it.
    thrust_per_frame = physics.get('thrust_per_frame',.0375)
    solution = braking_solution(
        origin,velocity,heading,walls,radius,
        thrust=thrust_per_frame,rotation_per_frame=physics.get('rotation_per_frame',5),
        sensor_range=sensor_range,friction=physics.get('friction_per_frame',1),
        # The need is noticed up to a decision late and acted on a decision after that.
        reaction_frames=2*horizon_frames,
        # Slow enough that touching a wall does not matter.
        harmless_speed=HARMLESS_SPEED_METRES_PER_SECOND/fps)
    brake = {'speed_state':'slow', 'safe_speed_metres_per_second':None,
             'stopping_distance_metres':0, 'thrust_effect':None,
             'retrograde_degrees_off_nose':None,
             'retrograde_degrees_off_nose_at_next_decision':None,
             'burn_heading_degrees':None, 'burn_seconds':0}
    if speed:
        # Null impact time: no sensed wall on this course, or drag stops the ship first.
        motion['wall_clearance_metres'] = solution.wall_distance
        if solution.frames_to_impact is not None:
            motion['seconds_to_wall_impact'] = round(solution.frames_to_impact/fps,2)
        retrograde = round(solution.degrees_off_nose,1)
        brake = {'speed_state':('too_fast' if solution.must_brake else
                                'cruising' if speed > solution.safe_speed*.5 else 'slow'),
                 'safe_speed_metres_per_second':round(solution.safe_speed*fps,1),
                 'stopping_distance_metres':round(solution.stopping_distance,1),
                 'thrust_effect':('slows' if abs(retrograde) <= 60 else
                                  'speeds_up' if abs(retrograde) >= 120 else 'sideways'),
                 'retrograde_degrees_off_nose':retrograde,
                 'retrograde_degrees_off_nose_at_next_decision':
                     off_nose(velocity_heading+180,next_heading),
                 # The burn that brings the ship to rest, for the navigator to fly.
                 'burn_heading_degrees':round(solution.heading_degrees,1),
                 'burn_seconds':round(solution.burn_frames/fps,2)}
    motion['brake'] = brake
    def engage_reading():
        """The worked approach to the enemy fire control is engaging, or None.

        Fire control holds the nose on that enemy, so thrust pushes towards it
        and nothing can push away. The burn therefore only ever builds closing
        speed, up to the fastest from which the ship could still turn round and
        stop at the standoff distance; inside the standoff it calls for none.
        """
        for c in visible:
            if c['allegiance'] != 'enemy':
                continue
            solution = aim(c)
            if solution is None:
                continue
            distance = c['distance']
            standoff = ENGAGE_STANDOFF_CELLS*cell_size
            toward = [c['relative_position'][i]/distance if distance else 0 for i in (0,1)]
            closing = sum((velocity[i]-c['velocity'][i])*toward[i] for i in (0,1))
            deceleration = thrust_per_frame*fps*fps
            reaction = 2*state.get('action_horizon_seconds',.25)+180/rotation_speed
            room = max(0,distance-standoff)
            target = min(speed_limit*fps,
                         deceleration*(math.sqrt(reaction*reaction+2*room/deceleration)-reaction))
            burn_frames = max(0,(target/fps-closing)/thrust_per_frame)
            return {'id':c['id'],
                    'distance_metres':distance,
                    'standoff_metres':standoff,
                    'range_state':('too_close' if distance < standoff*.6 else
                                   'far' if distance > standoff*1.15 else 'in_range'),
                    'closing_speed_metres_per_second':round(closing*fps,1),
                    'target_closing_speed_metres_per_second':round(target,1),
                    'holding_still':speed*fps < HARMLESS_SPEED_METRES_PER_SECOND,
                    'burn_needed':burn_frames >= 2,
                    'burn_heading_degrees':round(
                        (heading+solution['lead_degrees_off_nose']) % 360,1),
                    'burn_seconds':round(burn_frames/fps,2) if burn_frames >= 2 else 0}
        return None

    def course_to(point, bearing, cruise=None):
        """The turn and burn that aim the ship's motion at a point.

        The speed it may arrive at is what it could still shed before the wall
        beyond the point, allowing for the lag in deciding to brake and a full
        swing of the nose. `cruise` (pixels per second) caps that speed, and the
        ship then holds most of it, where the default is to settle for half.
        """
        thrust = physics.get('thrust_per_frame',.0375)
        deceleration = thrust*fps*fps
        # The need to brake is noticed one decision late and acted on a decision
        # after that, and then the nose has to swing right round.
        reaction = 2*state.get('action_horizon_seconds',.25)+180/rotation_speed
        # Room is what the hull can travel that way before touching a wall; a wall
        # running alongside the course takes none of it. Stop a hull's width short.
        angle = math.radians(bearing)
        travel = hull_travel(origin,(math.cos(angle),math.sin(angle)),radius,walls,sensor_range)
        room = max(0,(sensor_range if travel is None else travel)-radius)
        limit = min(speed_limit*fps,
                    deceleration*(math.sqrt(reaction*reaction+2*room/deceleration)-reaction))
        if cruise is not None:
            limit = min(limit,cruise)
        correction = course_correction(
            origin,velocity,heading,point,thrust=thrust,speed_limit=limit/fps,
            # Holding right at the limit leaves no slack for lag; a little under it does.
            approach_speed=None if cruise is None else limit/fps*.7,
            rotation_per_frame=physics.get('rotation_per_frame',5),
            friction=physics.get('friction_per_frame',1))
        if correction is None:
            return None
        return {# The navigator times the burn itself, so even a short one can be flown.
                'burn_needed':correction.burn_frames >= 2,
                'burn_heading_degrees':round(correction.heading_degrees,1),
                'burn_degrees_off_nose':round(correction.degrees_off_nose,1),
                'burn_degrees_off_nose_at_next_decision':
                    off_nose(correction.heading_degrees,next_heading),
                'burn_seconds':round(correction.burn_frames/fps,2),
                'speed_after_metres_per_second':round(correction.final_speed*fps,1),
                'speed_limit_metres_per_second':round(limit,1)}

    raw_follow = state.get('follow_player')
    # Cut off: no player, or no open route to it. Then there is nobody to follow,
    # and the hunter explores along a wall instead.
    cut_off = raw_follow is None or raw_follow['route_distance'] is None
    follow = wall_follow = None
    if not cut_off:
        follow = {**bearings(raw_follow['bearing']),
                  'heading_degrees':raw_follow['bearing'],
                  'waypoint_distance_metres':raw_follow['waypoint_distance'],
                  'route_distance_metres':raw_follow['route_distance'],
                  'player_visible':raw_follow['player_visible'],
                  # Close enough to keep station without running the player down.
                  'alongside':(raw_follow['player_visible']
                               and raw_follow['player_distance'] < cell_size),
                  'course':None}
        if not follow['alongside']:
            follow['course'] = course_to(raw_follow['waypoint'],raw_follow['bearing'])
    else:
        goal = wall_follow_target(origin,heading,radius,walls,cell_size)
        bearing = math.degrees(math.atan2(goal.point[1]-origin[1],goal.point[0]-origin[0]))
        wall_follow = {**bearings(bearing),
                       'heading_degrees':bearing % 360,
                       'wall_distance_metres':goal.wall_distance,
                       # Slow enough to swing round the free end of a wall and stay
                       # with it: the engine can only bend the path so tightly.
                       'course':course_to(
                           goal.point,bearing,
                           cruise=.6*math.sqrt(physics.get('thrust_per_frame',.0375)*goal.standoff)*fps)}
    return {'snapshot_at_seconds':state.get('snapshot_at',0),
            'speed_metres_per_second':speed*fps,
            'heading_degrees':heading % 360,
            'velocity_heading_degrees':velocity_heading % 360 if speed else None,
            'motion':motion,
            'speed_limit_metres_per_second':speed_limit*fps,
            'rotation_speed_degrees_per_second':rotation_speed,
            'turning':turning,
            'radius_metres':radius,
            'sensor_range_metres':sensor_range,
            'health':ship.get('health',3), 'space':space,
            'visible_contacts':[contact(c,True) for c in visible],
            'remembered_contacts':[contact(c) for c in state.get('remembered_contacts',[])
                                   if c['id'] not in visible_ids],
            'hostile_projectiles':[contact(c) for c in state.get('visible_projectiles',[])
                                   if c['allegiance']=='enemy'],
            'engage':engage_reading(),
            'follow_player':follow,
            'wall_follow':wall_follow}
