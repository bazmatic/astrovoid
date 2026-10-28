"""Torque-driven rotation of a circular body, integrated in seconds."""
import math
from utils.math_utils import calculate_entity_mass


def inertia(radius):
    return .5*calculate_entity_mass(radius)*radius*radius


def advance(body,torque,dt_frames):
    """Integrate constant torque exactly; zero torque preserves angular momentum."""
    dt=dt_frames/60
    acceleration=torque/inertia(body.radius)
    rotation=body.wall_angular_velocity*dt+.5*acceleration*dt*dt
    body.wall_body_angle=(body.wall_body_angle+math.degrees(rotation))%360
    body.wall_angular_velocity+=acceleration*dt
    body.angle=body.wall_body_angle


def turn(body, target_degrees, dt_frames, magnetic=False):
    """A damped angular spring; magnetic capture has a stronger actuator than flight steering."""
    moment=inertia(body.radius)
    remaining=max(0.,dt_frames/60)
    while remaining>1e-9:
        dt=min(1/240,remaining)
        omega=body.wall_angular_velocity
        if target_degrees is None:
            torque=-moment*.2*omega
            limit=float('inf')
        else:
            error=math.radians((target_degrees-body.wall_body_angle+180)%360-180)
            stiffness,damping,maximum,limit=((2_000_000,200_000,750_000,4*math.pi) if magnetic
                                             else (180_000,60_000,90_000,math.pi))
            torque=max(-maximum,min(maximum,stiffness*error-damping*omega))
        omega=max(-limit,min(limit,omega+torque/moment*dt))
        body.wall_body_angle=(body.wall_body_angle+math.degrees(omega*dt))%360
        body.wall_angular_velocity=omega
        remaining-=dt
    body.angle=body.wall_body_angle
