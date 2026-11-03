"""Visible-target ballistic geometry used only for training reward credit."""
import math
import config
from creatures.flocker_team import muzzle,offset
from creatures.traits.rooted import wall_between


def intercept_point(bird,target,maze):
    origin,_=muzzle(bird)
    dx,dy=target.x-origin[0],target.y-origin[1]
    if math.hypot(dx,dy)>bird.gun_range:
        return None
    gun=next(t for t in bird.traits if t.NAME=='gun')
    speed=config.PROJECTILE_SPEED*gun.shot_speed
    lifetime=config.PROJECTILE_LIFETIME*gun.shot_lifetime
    vx,vy=getattr(target,'vx',0.),getattr(target,'vy',0.)
    a=vx*vx+vy*vy-speed*speed
    b=2*(dx*vx+dy*vy)
    c=dx*dx+dy*dy
    if abs(a)<1e-9:
        roots=[-c/b] if abs(b)>1e-9 else []
    else:
        discriminant=b*b-4*a*c
        roots=[] if discriminant<0 else [(-b-math.sqrt(discriminant))/(2*a),(-b+math.sqrt(discriminant))/(2*a)]
    times=[t for t in roots if 0<t<=lifetime]
    if not times:
        return None
    time=min(times)
    point=target.x+vx*time,target.y+vy*time
    return None if maze is not None and wall_between(origin,point,maze) else point


def normalized_error(bird,point):
    origin,heading=muzzle(bird)
    bearing=math.degrees(math.atan2(point[1]-origin[1],point[0]-origin[0]))
    return abs(offset(bearing-heading))/180.
