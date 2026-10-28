"""Shared physical constraints and delayed local radio, independent of the choice of brain."""
from dataclasses import dataclass
import math

from utils import get_closest_point_on_line

DECISION_FRAMES = 6
RADIO_RANGE = 300.0
LANDING_RANGE = 300.0
LANDING_HALF_ANGLE = 45.0


@dataclass(frozen=True)
class Intent:
    move: int = 1
    aim: int = 0
    fire: bool = False
    detach: bool = False
    landing: int = 0
    message: int = 0


@dataclass(frozen=True)
class Landing:
    wall: object
    foot: tuple
    normal: tuple
    position: tuple


def crawlers(enc):
    return [c for c in enc.creatures() if c.active and c.type == 'wallcrawler']


def space_free(c, enc, pos):
    return all(other is c or math.dist(pos, other.get_pos()) >= c.radius+other.radius+1
               for other in crawlers(enc))


def swept_peers(c, enc):
    """Stop before another body; following and head-on traffic cannot tunnel or stack."""
    start, end = (c.prev_x, c.prev_y), c.get_pos()
    earliest = 1.0
    for other in crawlers(enc):
        if other is c:
            continue
        dx, dy = end[0]-start[0], end[1]-start[1]
        ox, oy = start[0]-other.x, start[1]-other.y
        radius = c.radius+other.radius+1
        a, b, d = dx*dx+dy*dy, 2*(ox*dx+oy*dy), ox*ox+oy*oy-radius*radius
        if d < -0.01:
            # Overlapping spawn or external shove: allow movement only out of the overlap.
            if math.dist(end, other.get_pos()) <= math.dist(start, other.get_pos()):
                earliest = 0.0
        elif a > 1e-12 and b*b-4*a*d >= 0:
            t = (-b-math.sqrt(b*b-4*a*d))/(2*a)
            if 0 <= t <= 1:
                earliest = min(earliest, max(0, t-0.001))
    if earliest < 1:
        c.x, c.y = start[0]+(end[0]-start[0])*earliest, start[1]+(end[1]-start[1])*earliest
        c.vx = c.vy = 0.0
        return True
    return False


def capsule_hits(start, end, radius, a, b):
    """Exact swept-circle clearance against a segment, without distance-dependent sampling."""
    def cross(p,q,r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    if cross(start,end,a)*cross(start,end,b) < 0 and cross(a,b,start)*cross(a,b,end) < 0:
        return True
    return min(math.dist(start,get_closest_point_on_line(start,a,b)),
               math.dist(end,get_closest_point_on_line(end,a,b)),
               math.dist(a,get_closest_point_on_line(a,start,end)),
               math.dist(b,get_closest_point_on_line(b,start,end))) <= radius


def path_clear(c, enc, target):
    maze = enc.maze
    walls = (maze.spatial_grid.get_walls_along_path(c.get_pos(), target, c.radius+1)
             if maze.spatial_grid is not None else maze.walls)
    return not any(w.active and capsule_hits(c.get_pos(),target,c.radius+0.2,w.start,w.end)
                   for w in list(walls)+list(getattr(maze, 'gate_segments', ())))


def candidates(c, enc, include_near=False, reach=LANDING_RANGE):
    from creatures.traits.wallcrawl import clear, nearby
    team = getattr(enc, 'wallcrawler_team', None)
    found = []
    for w in nearby(enc.maze, c.get_pos(), reach):
        if not w.active:
            continue
        dx, dy = w.end[0]-w.start[0], w.end[1]-w.start[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        foot = get_closest_point_on_line(c.get_pos(), w.start, w.end)
        t = ((foot[0]-w.start[0])*dx+(foot[1]-w.start[1])*dy)/(length*length)
        normal = (-dy/length, dx/length)
        if (c.x-foot[0])*normal[0]+(c.y-foot[1])*normal[1] < 0:
            normal = (-normal[0], -normal[1])
        for u in (t, max(0, t-3*c.radius/length), min(1, t+3*c.radius/length)):
            p = (w.start[0]+u*dx, w.start[1]+u*dy)
            pos = (p[0]+normal[0]*(c.radius+2), p[1]+normal[1]*(c.radius+2))
            distance = math.dist(c.get_pos(), pos)
            if distance > reach or (not include_near and distance < 3*c.radius):
                continue
            if not include_near:
                # A ballistic hop must actually approach its receiving wall.
                incidence=-((pos[0]-c.x)*normal[0]+(pos[1]-c.y)*normal[1])/max(distance,1e-8)
                if incidence<.25:
                    continue
                heading = math.radians(c.angle)
                forward = (pos[0]-c.x)*math.cos(heading)+(pos[1]-c.y)*math.sin(heading)
                if forward < distance*math.cos(math.radians(LANDING_HALF_ANGLE))-1e-8:
                    continue
            if not space_free(c, enc, pos) or (team is not None and not team.available(c, pos)):
                continue
            found.append((distance, Landing(w, p, normal, pos)))
    # At most one representative in each direction; inspect nearer candidates first.
    bins = {}
    reference = math.atan2(c.wall_normal[1],c.wall_normal[0]) if include_near else math.radians(c.angle)
    for _, site in sorted(found, key=lambda item: item[0]):
        angle = math.atan2(site.position[1]-c.y, site.position[0]-c.x)-reference
        angle = (angle+math.pi) % (2*math.pi)-math.pi
        if include_near:
            bucket = int((angle+math.pi)/(2*math.pi)*8) % 8
        else:
            half = math.radians(LANDING_HALF_ANGLE)
            bucket = max(0,min(7,int((angle+half)/(2*half)*8)))
        if bucket in bins:
            continue
        if clear(enc.maze, site.position, c.radius) and path_clear(c, enc, site.position):
            bins[bucket] = site
        if len(bins) == 8:
            break
    if include_near:
        return sorted(bins.values(), key=lambda site: math.dist(c.get_pos(), site.position))
    return [bins.get(i) for i in range(8)]


class WallcrawlerTeam:
    def __init__(self, enc):
        self.enc = enc
        self.maze = enc.maze
        self.tick = self.frames = 0
        self.messages, self.pending, self.reservations = {}, {}, {}
        self.external = False
        self.driver = None
        self._next_id = 0

    def members(self):
        members = crawlers(self.enc)
        for c in members:
            if not hasattr(c, 'agent_id'):
                c.agent_id = self._next_id
                self._next_id += 1
        return sorted(members, key=lambda c: c.agent_id)

    def available(self, c, pos):
        return all(owner == c.agent_id or math.dist(pos, site.position) >= 2*c.radius+1
                   for owner, site in self.reservations.items())

    def clean(self):
        live = {c.agent_id: c for c in self.members()}
        self.reservations = {i: site for i, site in self.reservations.items()
                             if i in live and live[i].wall_state == 'returning' and site.wall.active
                             and getattr(live[i], 'wall_destination', None) is site}
        self.messages = {i: value for i, value in self.messages.items() if i in live}

    def advance(self):
        self.tick += 1
        self.messages, self.pending = self.pending, {}
        self.clean()

    def inbox(self, c, muted=False):
        if muted:
            return {}
        return {other.agent_id: self.messages[other.agent_id][0] for other in self.members()
                if other is not c and other.agent_id in self.messages
                and math.dist(c.get_pos(), self.messages[other.agent_id][1]) <= RADIO_RANGE}

    def commit(self, actions, sites=None):
        members = self.members()
        self.clean()
        # Rotate priority each tick; the result is independent of roster iteration order.
        if members:
            k = self.tick % len(members)
            members = members[k:]+members[:k]
        for c in members:
            intent = actions.get(c.agent_id, Intent(move=0))
            c.wall_intent = intent
            c.wall_message = intent.message
            self.pending[c.agent_id] = (intent.message, c.get_pos())
            if not intent.detach or c.wall_state != 'attached' or c.wall_attach_cooldown > 0:
                continue
            options = sites[c.agent_id] if sites is not None else candidates(c, self.enc)
            site = options[intent.landing] if 0 <= intent.landing < len(options) else None
            if site is None or not self.available(c, site.position) or not space_free(c, self.enc, site.position):
                continue
            self.reservations[c.agent_id] = site
            c.wall_destination = site
            c.wall_state = 'returning'
            c.wall_phase = 'launch'
            c.wall_phase_time = 0.
            c.wall_launch_origin = c.get_pos()
            c.wall_launch_normal = c.wall_normal
            c.wall_in_flight = True
            c.vx = c.vy = 0.
            c.wall_stall = 0
            c.controls.fire, c.controls.aim = False, None

    def reserve_return(self, c):
        self.members()
        if self.frames < getattr(c,'wall_retry_after',0):
            return None
        self.reservations.pop(c.agent_id, None)
        options = candidates(c, self.enc, include_near=True)
        if not options:
            grid = self.maze.spatial_grid
            reach = math.hypot(grid.width, grid.height) if grid is not None else 10000
            options = candidates(c, self.enc, include_near=True, reach=reach)
        c.wall_destination = options[0] if options else None
        # With no route, remain safely airborne and retry twice per second.
        c.wall_retry_after = 0 if options else self.frames+30
        if c.wall_destination is not None:
            self.reservations[c.agent_id] = c.wall_destination
        return c.wall_destination

    def before_frame(self):
        self.clean()
        members = self.members()
        if members:
            k = self.tick % len(members)
            for c in members[k:]+members[:k]:
                if c.wall_state == 'returning' and c.wall_destination is None and not c.wall_in_flight:
                    self.reserve_return(c)
        if not self.external and self.frames % DECISION_FRAMES == 0:
            if self.frames:
                self.advance()
            if self.driver is None:
                policy = getattr(self.enc.world, 'wallcrawler_policy', None)
                if policy is not None:
                    from learning.adapters.wallcrawler import CrawlerDriver
                    self.driver = CrawlerDriver(policy)
            if self.driver is not None:
                self.driver.decide(self)
        self.frames += 1


def get_team(enc):
    team = getattr(enc, 'wallcrawler_team', None)
    if team is None or team.maze is not enc.maze:
        team = enc.wallcrawler_team = WallcrawlerTeam(enc)
    return team
