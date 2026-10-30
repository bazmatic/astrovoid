"""Momentum exchange from actual emitted projectiles, without a steering controller."""
from utils.math_utils import calculate_entity_mass
from physics.angular_motion import inertia


def apply_firing_recoil(body, shot, launch_velocity=None, launch_spin=None):
    """Exchange muzzle-relative bullet momentum; support absorbs attached recoil.

    Velocities use pixels/frame, while angular velocity uses radians/second.
    A volley may supply one pre-volley velocity/spin for all its projectiles.
    """
    if getattr(body,'wall_state',None)=='attached' or getattr(getattr(body,'kind',None),'anchored',False):
        return False
    vx,vy = (body.vx,body.vy) if launch_velocity is None else launch_velocity
    spin = getattr(body,'wall_angular_velocity',0.) if launch_spin is None else launch_spin
    rx,ry = shot.x-body.x,shot.y-body.y
    # Gun-configured speed is relative to the moving muzzle.
    px=calculate_entity_mass(shot.radius)*max(0.,shot.strength)*shot.vx
    py=calculate_entity_mass(shot.radius)*max(0.,shot.strength)*shot.vy
    shot.vx+=vx-spin*ry/60
    shot.vy+=vy+spin*rx/60
    mass=calculate_entity_mass(body.radius)
    body.vx-=px/mass
    body.vy-=py/mass
    if hasattr(body,'wall_angular_velocity'):
        body.wall_angular_velocity-=(rx*py-ry*px)*60/inertia(body.radius)
    return bool(px or py)
