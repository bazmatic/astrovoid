"""Local, legal pre-contact escape demonstrations; never used by deployed brains."""
import math
from creatures.traits.rooted import wall_between
from creatures.wallcrawler_team import DECISION_FRAMES

CONTACT_LEAD_FRAMES = 120
PREDICTION_FRAMES = 240
CLEARANCE_MARGIN = 3.
PREPARATION_HEADINGS = (-60, 0, 60)
POST_LANDING_FRAMES = 60


def motion_path(env, c, action, site=None, frames=PREDICTION_FRAMES):
    """Predict our own movement using the actual wall mechanics, without side effects.

    The maze is shared read-only. Bodies, controls and reservations are isolated;
    no hypothetical launch may reserve space or alter the live encounter.
    """
    from copy import copy
    from types import SimpleNamespace
    from creatures.wallcrawler_team import WallcrawlerTeam, Intent
    body = copy(c)
    body.controls = copy(c.controls)
    peers = [copy(other) for other in env.team.members() if other is not c]
    enc = SimpleNamespace(maze=env.world.maze, creatures=lambda: [body]+peers)
    body.encounter = enc
    team = WallcrawlerTeam(enc)
    enc.wallcrawler_team = team
    team.reservations = dict(env.team.reservations)
    body.wall_intent = Intent(move=action[0]-1)
    trait = next(t for t in body.traits if t.NAME == 'wallCrawls')
    if site is not None:
        body.wall_destination = site
        body.wall_state, body.wall_phase = 'returning', 'launch'
        body.wall_phase_time = 0.
        body.wall_launch_origin = body.get_pos()
        body.wall_launch_normal = body.wall_normal
        body.wall_in_flight = True
        body.vx = body.vy = 0.
        team.reservations[body.agent_id] = site
    points = [body.get_pos()]
    landed = None
    for frame in range(1, frames+1):
        if frame>1 and (frame-1)%DECISION_FRAMES==0:
            # Future scripted decisions stop walking in flight. A mid-tick
            # landing keeps that stop intention until the next decision tick.
            body.wall_intent=Intent(move=int(body.walk_direction) if body.wall_state=='attached' else 0)
        trait._move(body, enc.maze, 1)
        points.append(body.get_pos())
        if site is not None and landed is None and body.wall_state == 'attached':
            landed = frame
    return points, landed


def contact_time(relative_position, relative_velocity, radius):
    x,y=relative_position;vx,vy=relative_velocity
    distance=x*x+y*y-radius*radius
    if distance<=0:return 0.
    speed=vx*vx+vy*vy
    if speed<1e-9:return math.inf
    approach=x*vx+y*vy
    discriminant=approach*approach-speed*distance
    if approach>=0 or discriminant<0:return math.inf
    return (-approach-math.sqrt(discriminant))/speed


def defensive_jump(env,c,action):
    if c.wall_state!='attached' or not env.jumping_enabled:
        return action
    threats=[t for t in env.world.additional_targets if t.active and getattr(t,'allegiance',None)=='ally'
             and math.dist(c.get_pos(),t.get_pos())<=c.gun_range
             and not wall_between(c.get_pos(),t.get_pos(),env.world.maze)]
    def clearance(points,frames=PREDICTION_FRAMES):
        # Jellies pursue rather than coasting in a straight line. Predict from local
        # observed speeds, steering conservatively toward the proposed crawler path.
        positions=[t.get_pos() for t in threats]
        # A bouncing Jelly may be briefly slow, then regain its pursuit speed.
        # Use the fastest currently observed pursuer rather than treating each
        # transient slowdown as its permanent top speed. No private trait reads.
        speed=max(math.hypot(t.vx,t.vy) for t in threats)
        speeds=[speed]*len(threats)
        least=math.inf
        for frame in range(1,frames+1):
            point=points[frame]
            for i,t in enumerate(threats):
                px,py=positions[i]
                # Targets move first in the real encounter, toward our previous position.
                dx,dy=points[frame-1][0]-px,points[frame-1][1]-py
                distance=math.hypot(dx,dy)
                step=min(distance,speeds[i])
                positions[i]=(px+dx/max(distance,1e-9)*step,py+dy/max(distance,1e-9)*step)
                least=min(least,math.dist(point,positions[i])-c.radius-t.radius)
        return least
    if not threats:return action
    walking,_=motion_path(env,c,action)
    if clearance(walking,CONTACT_LEAD_FRAMES)>0:return action
    standing=clearance(walking)
    best=None
    current_sites=env._sites.get(c.agent_id,()) if c.wall_attach_cooldown<=0 else ()
    for index,site in enumerate(current_sites):
        if site is None:continue
        path,landed=motion_path(env,c,action,site)
        # Require a completed landing and a full attachment cooldown of clearance.
        if landed is None or landed+POST_LANDING_FRAMES>PREDICTION_FRAMES:continue
        score=clearance(path,landed+POST_LANDING_FRAMES)
        if score>CLEARANCE_MARGIN and score>standing+CLEARANCE_MARGIN and (best is None or score>best[0]):
            best=score,index
    if best is not None:return action[:3]+(1,best[1],action[5])
    # Gun direction gates the forward landing cone. Turning toward a route is
    # a legal preparatory action; it must not be confused with launching at a
    # destination that is outside the current action mask.
    from copy import copy
    from creatures.wallcrawler_team import candidates
    normal=math.degrees(math.atan2(c.wall_normal[1],c.wall_normal[0]))
    seen=set()
    preparation=None
    for heading in PREPARATION_HEADINGS:
        probe=copy(c);probe.angle=normal+heading
        for site in candidates(probe,env.enc):
            if site is None or site.position in seen:continue
            seen.add(site.position)
            bearing=math.degrees(math.atan2(site.position[1]-c.y,site.position[0]-c.x))
            delta=(bearing-c.angle+180)%360-180
            # Turn only enough to bring the destination well inside the cone.
            turn=max(0.,abs(delta)-30.)
            delay=max(DECISION_FRAMES,math.ceil(turn/(3*DECISION_FRAMES))*DECISION_FRAMES,
                      math.ceil(c.wall_attach_cooldown/DECISION_FRAMES)*DECISION_FRAMES)
            if delay+POST_LANDING_FRAMES>=PREDICTION_FRAMES:continue
            if clearance([c.get_pos()]*(delay+1),delay)<=CLEARANCE_MARGIN:continue
            path,landed=motion_path(env,c,action,site,frames=PREDICTION_FRAMES-delay)
            if landed is None or delay+landed+POST_LANDING_FRAMES>PREDICTION_FRAMES:continue
            path=[c.get_pos()]*delay+path
            score=clearance(path,delay+landed+POST_LANDING_FRAMES)
            if score<=CLEARANCE_MARGIN:continue
            if preparation is None or score>preparation[0]:
                preparation=score,delta
    if preparation is None:return action
    delta=preparation[1]
    return (1,math.copysign(20.,delta),0,0,action[4],action[5])
