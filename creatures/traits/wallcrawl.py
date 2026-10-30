"""Wall walking, leg-driven ballistic launches and soft magnetic landings."""
import math

from creatures.trait import Trait
from creatures.traits.rooted import wall_between
from physics.thrust import sweep_walls
from utils import get_closest_point_on_line

LAUNCH_FRAMES = 12.0


def nearby(maze, pos, reach):
    grid = maze.spatial_grid
    return grid.get_nearby_walls(pos, reach) if grid is not None else maze.walls


def contact(maze, pos, walls=None):
    """Closest active surface, its foot, outward normal and distance from this open-space point.

    Gates are moving obstacles, not surfaces the creature can cling to.
    """
    if walls is None and maze.spatial_grid is not None:
        reach = 24.0
        grid = maze.spatial_grid
        while reach < math.hypot(grid.width, grid.height) * 2:
            found = contact(maze, pos, grid.get_nearby_walls(pos, reach))
            if found is not None and found[3] <= reach:
                return found
            reach *= 2
    best, least = None, math.inf
    for wall in maze.walls if walls is None else walls:
        if not wall.active or wall.start == wall.end:
            continue
        foot = get_closest_point_on_line(pos, wall.start, wall.end)
        dx, dy = pos[0] - foot[0], pos[1] - foot[1]
        distance = math.hypot(dx, dy)
        if distance < least and distance > 1e-6:
            best = (wall, foot, (dx / distance, dy / distance), distance)
            least = distance
    return best


def clear(maze, pos, radius):
    cave = getattr(maze, 'cave', None)
    if cave is not None and cave.field.is_rock(*pos):
        return False
    walls = list(nearby(maze, pos, radius + 3)) + list(getattr(maze, 'gate_segments', ()))
    return all(not w.active or math.dist(pos, get_closest_point_on_line(pos, w.start, w.end)) >= radius + 0.1
               for w in walls)


class WallCrawls(Trait):
    NAME = 'wallCrawls'
    REQUIRES = ('gun',)

    def __init__(self, walkSpeed=0.65, returnSpeed=2.4, stunFrames=36.0, knockSpeed=2.8, bulletReleaseSpeed=0.9):
        if min(walkSpeed, returnSpeed, stunFrames, knockSpeed, bulletReleaseSpeed) <= 0:
            raise ValueError('wallCrawls: speeds and stunFrames must be positive')
        self.walk_speed, self.return_speed = walkSpeed, returnSpeed
        self.stun_frames, self.knock_speed = stunFrames, knockSpeed
        self.bullet_release_speed = bulletReleaseSpeed

    def on_spawn(self, c, enc):
        c.wall_state = 'returning'
        c.wall_normal = (0.0, -1.0)
        c.wall_stun = c.walk_phase = 0.0
        c.wall_attach_cooldown = c.wall_stall = 0.0
        c.wall_destination = None
        c.wall_retry_after = 0
        c.wall_body_angle = c.angle
        c.wall_angular_velocity = 0.
        c.wall_phase = 'flight'
        c.wall_phase_time = 0.
        c.wall_in_flight = False
        c.wall_launch_origin = None
        c.wall_approach = None
        c.wall_launch_normal = c.wall_normal
        c.walk_direction = 1.0
        self._silence(c)
        surface = contact(enc.maze, c.get_pos())
        if surface is not None and surface[3] <= c.radius + 5:
            self._attach(c, enc.maze, surface)

    @staticmethod
    def _silence(c):
        c.controls.fire, c.controls.aim = False, None
        c.just_fired = False

    def _dislodge(self, c, release_speed=None):
        attached = c.wall_state == 'attached'
        c.wall_state, c.wall_stun = 'stunned', self.stun_frames
        c.wall_destination = None
        c.wall_retry_after = 0
        c.wall_phase = 'flight'
        c.wall_approach = None
        c.wall_in_flight = True
        if attached:
            # Even a shot travelling into the rock knocks it into open space.
            nx, ny = c.wall_normal
            outward = c.vx * nx + c.vy * ny
            c.vx += nx * max(0.0, (self.knock_speed if release_speed is None else release_speed) - outward)
            c.vy += ny * max(0.0, (self.knock_speed if release_speed is None else release_speed) - outward)
        self._silence(c)

    def on_shot(self, c, shot, enc):
        from physics.angular_motion import inertia
        # Transfer projectile momentum using the same area-based mass as other bodies.
        # Training bullets carry a fraction of normal strength, including their impulse.
        from utils.math_utils import calculate_entity_mass
        strength = max(0., getattr(shot, 'creature_damage', 1.))
        rx,ry = shot.x-c.x,shot.y-c.y
        impulse_mass = calculate_entity_mass(shot.radius)*strength
        c.wall_angular_velocity += (rx*shot.vy-ry*shot.vx)*60*impulse_mass/inertia(c.radius)
        ratio = impulse_mass/calculate_entity_mass(c.radius)
        c.vx += shot.vx * ratio
        c.vy += shot.vy * ratio
        # Breaking the planted grip supplies a release kick independent of bullet damage.
        # _dislodge applies it only while attached; airborne hits retain small impulses.
        self._dislodge(c, release_speed=self.bullet_release_speed)

    def on_event(self, c, name, enc):
        if name == 'shoved':
            self._dislodge(c)
        elif name == 'recoil' and c.wall_state!='attached':
            # A genuine firing impulse establishes flight even when initial
            # placement had no wall to return to. Never erase it on the next tick.
            c.wall_in_flight=True
            site=c.wall_destination
            if c.wall_phase=='landing' and site is not None and c.vx*site.normal[0]+c.vy*site.normal[1]>0:
                c.wall_destination=None
                c.wall_phase='flight'
                c.wall_approach=None
                from creatures.wallcrawler_team import get_team
                get_team(enc).reservations.pop(c.agent_id,None)

    def _attach(self, c, maze, surface):
        _, foot, normal, _ = surface
        gap = c.radius + 2.0
        pos = (foot[0] + normal[0] * gap, foot[1] + normal[1] * gap)
        from creatures.wallcrawler_team import space_free
        if not clear(maze, pos, c.radius) or not space_free(c, c.encounter, pos):
            return False
        c.x, c.y = pos
        landing = c.wall_state != 'attached'
        c.wall_normal, c.wall_state = normal, 'attached'
        c.wall_destination = None
        c.wall_phase = 'attached'
        c.wall_in_flight = False
        c.wall_angular_velocity = 0.
        c.wall_body_angle = math.degrees(math.atan2(normal[1],normal[0]))
        if landing:
            c.wall_attach_cooldown = 60.0
        c.vx = c.vy = 0.0
        if landing:
            c.angle = math.degrees(math.atan2(normal[1], normal[0]))
        return True

    def on_frame(self, c, enc, dt):
        self._silence(c)
        gun_angle=c.angle
        c.wall_attach_cooldown = max(0, c.wall_attach_cooldown-dt)
        # Small steps keep projected walking continuous at short curved contour segments.
        remaining = max(0.0, dt)
        while remaining > 1e-6:
            step = min(1.0, remaining)
            self._move(c, enc.maze, step)
            remaining -= step
        if c.wall_state == 'stunned':
            return
        attached=c.wall_state=='attached'
        # Stabilise the gun in world space while the chassis spins ballistically.
        # Aiming alone cannot steer flight; the gun applies recoil only on actual shots.
        if not attached:c.angle=gun_angle
        intent = getattr(c, 'wall_intent', None)
        if intent is not None:
            if attached:
                normal = math.degrees(math.atan2(c.wall_normal[1], c.wall_normal[0]))
                off = (c.angle-normal+180) % 360-180
                c.angle = normal+max(-89,min(89,off+intent.aim*3*dt))
            else:
                c.angle=(c.angle+intent.aim*3*dt)%360
            rad = math.radians(c.angle)
            c.controls.aim = (c.x+math.cos(rad)*c.gun_range, c.y+math.sin(rad)*c.gun_range)
            c.controls.fire = intent.fire
            return
        target = enc.target_for(c)
        if target is not None:
            dx, dy = target[0] - c.x, target[1] - c.y
            outward = dx * c.wall_normal[0] + dy * c.wall_normal[1]
            if (not attached or outward > 0) and math.hypot(dx, dy) <= c.gun_range and not wall_between(c.get_pos(), target, enc.maze):
                desired = math.degrees(math.atan2(dy, dx))
                delta = (desired-c.angle+180) % 360-180
                turn=max(-3*dt,min(3*dt,delta))
                if attached:
                    normal = math.degrees(math.atan2(c.wall_normal[1], c.wall_normal[0]))
                    offset = (c.angle-normal+180) % 360-180
                    c.angle = normal+max(-89,min(89,offset+turn))
                else:c.angle=(c.angle+turn)%360
                rad = math.radians(c.angle)
                c.controls.aim = (c.x+math.cos(rad)*c.gun_range,c.y+math.sin(rad)*c.gun_range)
                c.controls.fire = abs((desired-c.angle+180) % 360-180) <= 12

    def _move(self, c, maze, dt):
        if c.wall_state == 'stunned':
            c.wall_stun = max(0.0, c.wall_stun - dt)
            from physics.angular_motion import advance
            advance(c,0.,dt)
            c.prev_x, c.prev_y = c.x, c.y
            c.x += c.vx * dt
            c.y += c.vy * dt
            self._sweep(c, maze, dt)
            if c.wall_stun <= 0:
                c.wall_state = 'returning'
            return
        if c.wall_state == 'returning':
            self._return(c,c.encounter,dt)
            return
        surface = contact(maze, c.get_pos(), nearby(maze, c.get_pos(), c.radius + 8))
        if surface is None or surface[3] > c.radius + 5:
            c.wall_state = 'returning'  # the wall was destroyed or reshaped
            c.wall_phase='flight'
            c.wall_in_flight=True
            return
        nx, ny = surface[2]
        intent = getattr(c, 'wall_intent', None)
        direction = intent.move if intent is not None else c.walk_direction
        stride = self.walk_speed * dt * direction
        ahead = (c.x - ny * stride, c.y + nx * stride)
        next_surface = contact(maze, ahead, nearby(maze, ahead, c.radius + 8))
        old = c.get_pos()
        if next_surface is None or not self._attach(c, maze, next_surface):
            c.walk_direction *= -1  # a tight corner or a gate: walk the other way
            return
        c.prev_x, c.prev_y = old
        from creatures.wallcrawler_team import swept_peers
        swept_peers(c, c.encounter, dt)
        c.walk_phase += math.dist(old, c.get_pos()) / max(1.0, c.radius) * 3

    def _launch_plan(self,c,site,ramp=True):
        """Choose an impulse and coasted spin that meet the wall facing outward.

        Account for the twelve-frame push and the legs contacting before the body centre
        reaches its final resting point. Short hops use less impulse to keep spin gentle.
        """
        dx,dy=site.position[0]-c.x,site.position[1]-c.y
        distance=math.hypot(dx,dy)
        incidence=-(dx*site.normal[0]+dy*site.normal[1])/max(distance,1e-8)
        travel=max(.01,distance-c.radius*.6/max(.01,incidence))
        desired=math.degrees(math.atan2(site.normal[1],site.normal[0]))
        rotation=math.radians((desired-c.wall_body_angle+180)%360-180)
        minimum_spin_frames=abs(rotation)*60/math.pi
        speed=min(self.return_speed,travel/max(.01,minimum_spin_frames))
        arrival=math.ceil(travel/max(speed,1e-8)+(LAUNCH_FRAMES/2 if ramp else 0)-1e-8)
        spin=rotation*60/max(1,arrival-(LAUNCH_FRAMES/2 if ramp else 0))
        return speed,spin

    def _return(self,c,enc,dt):
        from creatures.wallcrawler_team import get_team,space_free,Landing
        from physics.angular_motion import turn,advance,inertia
        team=get_team(enc)
        site=c.wall_destination
        if site is not None and (not site.wall.active or not clear(enc.maze,site.position,c.radius)
                                 or not space_free(c,enc,site.position)):
            c.wall_destination=site=None
            c.wall_phase='flight'
            team.reservations.pop(c.agent_id,None)
        if c.wall_phase=='landing' and site is not None:
            desired=math.degrees(math.atan2(site.normal[1],site.normal[0]))
            turn(c,desired,dt,magnetic=True)
            c.prev_x,c.prev_y=c.x,c.y
            # Feet contact the rock: their damped spring absorbs the incoming momentum.
            omega=max(.18,math.hypot(c.vx,c.vy)/(c.radius*.6)+.03)
            remaining=dt
            while remaining>1e-8:
                step=min(.25,remaining)
                c.vx+=(omega*omega*(site.position[0]-c.x)-2*omega*c.vx)*step
                c.vy+=(omega*omega*(site.position[1]-c.y)-2*omega*c.vy)*step
                c.x+=c.vx*step;c.y+=c.vy*step
                remaining-=step
            self._sweep(c,enc.maze,dt)
            error=abs((desired-c.wall_body_angle+180)%360-180)
            if (math.dist(c.get_pos(),site.position)<.4 and math.hypot(c.vx,c.vy)<.15
                    and error<3 and abs(c.wall_angular_velocity)<.4):
                self._attach(c,enc.maze,(site.wall,site.foot,site.normal,0))
            return
        if not c.wall_in_flight:
            if site is None:site=team.reserve_return(c)
            if site is None:
                c.vx=c.vy=0.
                return
            dx,dy=site.position[0]-c.x,site.position[1]-c.y
            distance=math.hypot(dx,dy)
            if distance<1e-6:
                c.wall_phase='landing'
                return
            speed,spin=self._launch_plan(c,site,ramp=False)
            c.vx,c.vy=dx/distance*speed,dy/distance*speed
            c.wall_angular_velocity=spin
            c.wall_in_flight=True
            c.wall_phase='flight'
        c.prev_x,c.prev_y=c.x,c.y
        if c.wall_phase=='launch' and site is not None:
            dx,dy=site.position[0]-c.wall_launch_origin[0],site.position[1]-c.wall_launch_origin[1]
            distance=math.hypot(dx,dy)
            # Planned linear and angular impulses are supplied only by the planted feet.
            if c.wall_phase_time==0:
                c.wall_launch_speed,c.wall_launch_spin=self._launch_plan(c,site)
                c.wall_angular_velocity=0.
            boost=min(dt,LAUNCH_FRAMES-c.wall_phase_time)
            ax=dx/max(distance,1e-6)*c.wall_launch_speed/LAUNCH_FRAMES
            ay=dy/max(distance,1e-6)*c.wall_launch_speed/LAUNCH_FRAMES
            c.x+=c.vx*boost+.5*ax*boost*boost
            c.y+=c.vy*boost+.5*ay*boost*boost
            c.vx+=ax*boost;c.vy+=ay*boost
            advance(c,inertia(c.radius)*c.wall_launch_spin/(LAUNCH_FRAMES/60),boost)
            c.wall_phase_time+=boost
            if c.wall_phase_time>=LAUNCH_FRAMES-1e-8:c.wall_phase='flight'
            coast=dt-boost
            c.x+=c.vx*coast;c.y+=c.vy*coast
            advance(c,0.,coast)
        else:
            advance(c,0.,dt)
            c.x+=c.vx*dt;c.y+=c.vy*dt
        c.wall_approach=None
        if c.wall_phase!='launch':
            surface=contact(enc.maze,c.get_pos(),nearby(enc.maze,c.get_pos(),c.radius*3+4))
            if surface is not None:
                wall,foot,normal,distance=surface
                approaching=c.vx*normal[0]+c.vy*normal[1]<0
                pos=(foot[0]+normal[0]*(c.radius+2),foot[1]+normal[1]*(c.radius+2))
                if (approaching and distance<=c.radius*3+4 and clear(enc.maze,pos,c.radius)
                        and space_free(c,enc,pos) and team.available(c,pos)):
                    c.wall_approach=(foot,normal)
                    if distance<=c.radius*1.6+2+1e-6:
                        site=Landing(wall,foot,normal,pos)
                        c.wall_destination=site;c.wall_phase='landing'
                        team.reservations[c.agent_id]=site
        self._sweep(c,enc.maze,dt)

    @staticmethod
    def _sweep(c, maze, dt=1.):
        sweep_walls(c, maze.walls, maze.spatial_grid)
        gates = getattr(maze, 'gate_segments', ())
        if gates:
            sweep_walls(c, gates)
        from creatures.wallcrawler_team import swept_peers
        swept_peers(c, c.encounter, dt)
