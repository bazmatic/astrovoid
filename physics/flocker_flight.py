"""Top-down aerodynamic flight: speed, coordinated arcs and bounded slip recovery.

Turn commands bend velocity along with the nose. Lateral acceleration limits high-speed
turns; at low airspeed steering authority fades instead of permitting a stationary pivot.
Collision impulses remain real velocities and recover towards the nose over time.
"""
import math


def _wrap(angle):
    return (angle+math.pi)%math.tau-math.pi


def advance(body, limits, dt):
    """Integrate at most one frame of flight; the propulsion trait handles contacts.

    Exponential longitudinal drag and an arc integral keep half-frame and full-frame
    movement consistent. Turning conserves speed; throttle alone supplies acceleration.
    """
    if dt<=0:
        return
    controls=body.controls
    old_speed=math.hypot(body.vx,body.vy)
    speed=min(old_speed,limits.max_speed)
    throttle=max(0.,min(1.,float(controls.thrust)))
    old_heading=math.radians(body.angle)
    course=math.atan2(body.vy,body.vx) if old_speed>1e-9 else old_heading
    # During an impact-induced slip, forward drive must not accelerate backwards.
    acceleration=limits.force*throttle*math.cos(_wrap(old_heading-course))
    drag=-math.log(limits.friction)
    if drag>1e-12:
        decay=math.exp(-drag*dt)
        next_speed=speed*decay+acceleration*(-math.expm1(-drag*dt))/drag
    else:
        next_speed=speed+acceleration*dt
    next_speed=min(limits.max_speed,max(0.,next_speed))
    average_speed=(speed+next_speed)*.5
    control_speed=limits.max_speed*limits.control_speed_share
    authority=min(1.,average_speed/control_speed)
    rate=min(math.radians(limits.turn_rate),limits.lateral_accel/max(average_speed,1e-9))*authority
    if controls.heading is not None:
        desired=_wrap(math.radians(controls.heading)-old_heading)
        yaw=max(-rate*dt,min(rate*dt,desired))
    else:
        yaw=max(-1.,min(1.,float(controls.turn)))*rate*dt
    body.angle=math.degrees(old_heading+yaw)%360
    slip=_wrap(old_heading-course)
    recovery=math.radians(limits.slip_recovery)*authority*dt
    course_change=yaw+max(-recovery,min(recovery,slip))
    middle=course+course_change*.5
    half=course_change*.5
    arc_scale=math.sin(half)/half if abs(half)>1e-9 else 1.
    distance=average_speed*dt*arc_scale
    body.prev_x,body.prev_y=body.x,body.y
    body.x+=math.cos(middle)*distance
    body.y+=math.sin(middle)*distance
    course+=course_change
    body.vx=math.cos(course)*next_speed
    body.vy=math.sin(course)*next_speed
