"""Practice targets with slow, weak return fire."""
import math
import random
import pygame
from creatures.traits.rooted import wall_between

TARGET_COUNT = 12
TARGET_RADIUS = 10.
TARGET_SPEED_MIN = .5
TARGET_SPEED_MAX = 1.5
TARGET_BULLET_SPEED = 2.
TARGET_FIRE_INTERVAL = 180
TARGET_BULLET_LIFETIME = 240
TARGET_BULLET_DAMAGE = .1
TARGET_FIRE_RANGE = 550.


class PracticeTarget:
    def __init__(self, position, heading, speed, fire_delay=TARGET_FIRE_INTERVAL, *, burst_size=1, burst_spacing=12, fire_interval=TARGET_FIRE_INTERVAL, firing_enabled=True):
        self.x,self.y=position
        self.radius=TARGET_RADIUS
        self.vx=math.cos(heading)*speed
        self.vy=math.sin(heading)*speed
        self.active=True
        self.fire_cooldown=fire_delay
        self.shots_fired=0
        self.burst_size, self.burst_spacing, self.fire_interval = burst_size, burst_spacing, fire_interval
        self.burst_remaining = 0
        self.burst_angle = None
        self.firing_enabled = firing_enabled

    def get_pos(self):return self.x,self.y

    def step(self,maze):
        if not self.active:return
        position=(self.x+self.vx,self.y+self.vy)
        if maze.is_open(position,self.radius) and not wall_between(self.get_pos(),position,maze):
            self.x,self.y=position
        else:
            self.vx,self.vy=-self.vx,-self.vy

    def fire(self,crawlers,maze):
        if not self.active or not self.firing_enabled:return None
        self.fire_cooldown=max(0,self.fire_cooldown-1)
        if self.fire_cooldown>0:return None
        candidates=[c for c in crawlers if c.active
                    and math.dist(self.get_pos(),c.get_pos())<=TARGET_FIRE_RANGE
                    and not wall_between(self.get_pos(),c.get_pos(),maze)]
        target=min(candidates,key=lambda c:math.dist(self.get_pos(),c.get_pos()),default=None)
        if self.burst_remaining == 0:
            if target is None:return None
            self.burst_angle=math.degrees(math.atan2(target.y-self.y,target.x-self.x))
            self.burst_remaining=self.burst_size
        from entities.projectile import Projectile
        angle=self.burst_angle
        bullet=Projectile(self.get_pos(),angle,source='player',dynamic_color=(255,155,90))
        speed=math.hypot(bullet.vx,bullet.vy)
        bullet.vx*=TARGET_BULLET_SPEED/speed;bullet.vy*=TARGET_BULLET_SPEED/speed
        bullet.lifetime=TARGET_BULLET_LIFETIME
        bullet.creature_damage=TARGET_BULLET_DAMAGE
        bullet.practice_target_bullet=True
        self.burst_remaining-=1
        self.fire_cooldown=self.burst_spacing if self.burst_remaining else self.fire_interval
        self.shots_fired+=1
        return bullet

    def take_hit(self,shot):
        if not self.active:return False
        self.active=False
        return True

    def draw(self,screen):
        if not self.active:return
        centre=round(self.x),round(self.y)
        pygame.draw.circle(screen,(65,150,175),centre,round(self.radius))
        pygame.draw.circle(screen,(170,235,235),centre,round(self.radius),2)
        pygame.draw.circle(screen,(240,205,110),centre,6,2)


def spacious_start(maze, position, normal):
    """Require a broad, visible approach area rather than a small target-sized gap."""
    nx, ny = normal
    for depth in (50, 90, 130, 180):
        for side in (-60, -30, 0, 30, 60):
            point = (position[0]+nx*depth-ny*side, position[1]+ny*depth+nx*side)
            if not maze.is_open(point, 11) or wall_between(position, point, maze):
                return False
    return True


def practice_starts(maze,positions):
    """Wall starts with enough open space ahead for a large target."""
    from creatures.traits.wallcrawl import contact
    starts=[]
    for position in positions:
        surface=contact(maze,position)
        if surface is None:continue
        _,foot,(nx,ny),_=surface
        start=(foot[0]+nx*12,foot[1]+ny*12)
        if not maze.is_open(start,11) or not spacious_start(maze,start,(nx,ny)):continue
        for distance in (50,75,110,160):
            if any(maze.is_open((start[0]+nx*distance-ny*side,start[1]+ny*distance+nx*side),TARGET_RADIUS+2)
                   and not wall_between(start,(start[0]+nx*distance-ny*side,start[1]+ny*distance+nx*side),maze)
                   for side in (0,-50,50,-90,90)):
                starts.append(start);break
    return starts



def plant_drill_crawlers(env, positions):
    """Resolve rare concave-corner starts before an aiming drill begins."""
    from creatures.traits.wallcrawl import contact, nearby
    maze = env.world.maze
    reach = max(maze.cell_size_x,maze.cell_size_y)*2
    for crawler in env.team.members():
        if crawler.wall_state=='attached':continue
        origin = crawler.get_pos()
        trait = next(t for t in crawler.traits if t.NAME=='wallCrawls')
        surfaces = [contact(maze,origin,[wall]) for wall in nearby(maze,origin,reach)]
        for surface in sorted((s for s in surfaces if s is not None),key=lambda s:s[3]):
            _,foot,normal,distance = surface
            gap = crawler.radius+2
            candidate = (foot[0]+normal[0]*gap,foot[1]+normal[1]*gap)
            if (distance<=reach and spacious_start(maze,candidate,normal)
                    and not wall_between(origin,candidate,maze) and trait._attach(crawler,maze,surface)):
                break
        else:
            # A concave pocket can have no body-sized planted site. During reset,
            # choose another clear wall start rather than beginning the drill in flight.
            for position in sorted(positions,key=lambda p:math.dist(p,origin)):
                surface = contact(maze,position)
                if surface is None:continue
                _,foot,normal,_ = surface
                gap = crawler.radius+2
                candidate = (foot[0]+normal[0]*gap,foot[1]+normal[1]*gap)
                if spacious_start(maze,candidate,normal) and trait._attach(crawler,maze,surface):
                    break
            else:
                raise ValueError('aim drill lacks a clear planted crawler start')
        crawler.prev_x,crawler.prev_y = crawler.x,crawler.y

def create_targets(env,seed,count=TARGET_COUNT, *, distance_range=(45.,180.)):
    from creatures.traits.wallcrawl import contact
    rng=random.Random(seed+17000)
    targets=[]
    crew=env.team.members()
    for c in crew:
        trait=next(t for t in c.traits if t.NAME=='wallCrawls')
        surface=contact(env.world.maze,c.get_pos())
        if surface is not None:trait._attach(c,env.world.maze,surface)
    # Round-robin placement gives every crawler nearby visible targets before filling the arena.
    for _ in range(12):
        for c in crew:
            if len(targets)>=count:break
            nx,ny=c.wall_normal;tx,ty=-ny,nx
            for attempt in range(80):
                distance=rng.uniform(*distance_range);side=rng.uniform(-100,100)
                pos=(c.x+nx*distance+tx*side,c.y+ny*distance+ty*side)
                if (env.world.maze.is_open(pos,TARGET_RADIUS+2)
                        and not wall_between(c.get_pos(),pos,env.world.maze)
                        and all(math.dist(pos,t.get_pos())>TARGET_RADIUS*2+4 for t in targets)
                        and all(math.dist(pos,other.get_pos())>TARGET_RADIUS+other.radius+6 for other in crew)):
                    targets.append(PracticeTarget(pos,rng.uniform(0,2*math.pi),rng.uniform(TARGET_SPEED_MIN,TARGET_SPEED_MAX),rng.randint(TARGET_FIRE_INTERVAL//2,TARGET_FIRE_INTERVAL)));break
    maze=env.world.maze
    cells=[maze.position_calculator.grid_center_to_screen(x,y)
           for y in range(1,maze.grid_height-1) for x in range(1,maze.grid_width-1) if not maze.grid[y][x]]
    rng.shuffle(cells)
    for pos in cells:
        if len(targets)>=count:break
        if (maze.is_open(pos,TARGET_RADIUS+2)
                and any(math.dist(pos,c.get_pos())<=550
                        and (pos[0]-c.x)*c.wall_normal[0]+(pos[1]-c.y)*c.wall_normal[1]>0
                        and not wall_between(c.get_pos(),pos,maze) for c in crew)
                and all(math.dist(pos,t.get_pos())>TARGET_RADIUS*2+4 for t in targets)
                and all(math.dist(pos,c.get_pos())>TARGET_RADIUS+c.radius+6 for c in crew)):
            targets.append(PracticeTarget(pos,rng.uniform(0,2*math.pi),rng.uniform(TARGET_SPEED_MIN,TARGET_SPEED_MAX),rng.randint(TARGET_FIRE_INTERVAL//2,TARGET_FIRE_INTERVAL)))
    if len(targets)<len(crew):
        raise ValueError('practice arena has insufficient clear target positions')
    return targets
