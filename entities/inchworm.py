"""The articulated silhouette is the simulated anatomy, including planted feet."""
import math

import pygame

import config


class InchwormBody:
    DEATH_DURATION = 60.
    DEATH_FRICTION = 1.

    def __init__(self, creature):
        self.chew = 0.

    def on_event(self, creature, name):
        pass

    def update(self, creature, dt, target=None):
        self.chew = (self.chew+dt*.3) % math.tau

    def update_death(self, c, dt):
        p = getattr(c, 'worm_physics', None)
        if p is not None:
            from creatures.traits.inchworm import snapshot
            from creatures.traits.wallcrawl import nearby
            from physics.inchworm import InchwormCommand
            walls = nearby(c.encounter.maze, p.centre, p.length*7+p.reach+math.hypot(*p.velocity)*dt)
            p.step(InchwormCommand(), dt, walls, getattr(c.encounter.maze, 'gate_segments', ()), powered=False)
            snapshot(c)

    def collision_segments(self, c):
        pose = getattr(c, 'worm_pose', None)
        if not pose:
            length = c.kind.tuning['size']*.7
            pose = tuple((((i-3)*length+c.x, c.y), ((i-2)*length+c.x, c.y)) for i in range(6))
        centre = getattr(c, 'worm_pose_centre', c.get_pos())
        scale = c.inflation.scale
        def point(p):
            return (c.x+(p[0]-centre[0])*scale, c.y+(p[1]-centre[1])*scale)
        skin = getattr(c, 'worm_skin', c.kind.tuning['size']*.24)*scale
        return tuple((point(a), point(b), skin) for a, b in pose)

    def draw(self, screen, c):
        self._draw(screen, c, 1.)

    def draw_death(self, screen, c):
        self._draw(screen, c, max(0., 1.-c.death_progress))

    def _draw(self, screen, c, fade):
        scale = c.radius/c.kind.tuning['size']
        centre = getattr(c, 'worm_pose_centre', c.get_pos())
        pose = getattr(c, 'worm_pose', None)
        if not pose:
            # Catalogue/editor portraits exist before encounter spawn hooks.
            length = c.kind.tuning['size']*.7
            pose = tuple((((i-3)*length+c.x, c.y), ((i-2)*length+c.x, c.y)) for i in range(6))
        skin = getattr(c, 'worm_skin', c.kind.tuning['size']*.24)*scale

        def point(p):
            return (c.x+(p[0]-centre[0])*scale, c.y+(p[1]-centre[1])*scale)

        def color(rgb):
            return tuple(int(bg+(v-bg)*fade) for v, bg in zip(rgb, config.COLOR_BACKGROUND))

        feet = getattr(c, 'worm_feet', (None, None))
        for end, index in enumerate((0, 5)):
            a, b = pose[index]
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = max(1e-6, math.hypot(dx, dy))
            roll = math.cos(getattr(c, 'worm_roll', (0.,)*6)[index])
            nx, ny = -dy/length*roll, dx/length*roll
            planted = feet[end]
            for leg in (-1, 0, 1):
                root = ((a[0]+b[0])/2+dx*leg*.23, (a[1]+b[1])/2+dy*leg*.23)
                if planted:
                    foot, normal = planted
                    tip = (foot[0]-normal[1]*leg*skin*.9/scale,
                           foot[1]+normal[0]*leg*skin*.9/scale)
                else:
                    tip = (root[0]+nx*skin*1.9/scale+dx*leg*.15,
                           root[1]+ny*skin*1.9/scale+dy*leg*.15)
                knee = ((root[0]+tip[0])/2-dx*leg*.18, (root[1]+tip[1])/2-dy*leg*.18)
                pygame.draw.lines(screen, color((98, 145, 59)), False,
                                  [point(root), point(knee), point(tip)], max(1, round(skin*.45)))
                pygame.draw.circle(screen, color((228, 211, 116) if planted else (154, 178, 81)),
                                   point(tip), max(1, skin*.3))
        for i, (start, end) in enumerate(pose):
            a, b = point(start), point(end)
            pygame.draw.line(screen, color((35, 64, 45)), a, b, max(1, round(skin*2.4)))
            for p in (a, b):
                pygame.draw.circle(screen, color((35, 64, 45)), p, max(1, skin*1.2))
            pygame.draw.line(screen, color((116+i*7, 174+i*5, 63)), a, b, max(1, round(skin*2)))
            for p in (a, b):
                pygame.draw.circle(screen, color((116+i*7, 174+i*5, 63)), p, max(1, skin))
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = max(1e-6, math.hypot(dx, dy))
            roll = math.cos(getattr(c, 'worm_roll', (0.,)*6)[i])
            nx, ny = dy/length*roll, -dx/length*roll
            for t in (.3, .65):
                x, y = a[0]+dx*t, a[1]+dy*t
                pygame.draw.line(screen, color((78, 128, 54)), (x-nx*skin*.75, y-ny*skin*.75),
                                 (x+nx*skin*.75, y+ny*skin*.75), max(1, round(scale)))
            pygame.draw.line(screen, color((198, 232, 117)),
                             (a[0]+nx*skin*.5, a[1]+ny*skin*.5),
                             (b[0]+nx*skin*.5, b[1]+ny*skin*.5), max(1, round(scale)))
        a, head = (point(p) for p in pose[-1])
        angle = math.atan2(head[1]-a[1], head[0]-a[0])
        dx, dy, nx, ny = math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle)
        pygame.draw.circle(screen, color((185, 215, 92)), head, max(1, skin*1.2))
        eating = getattr(c, 'worm_state', '') == 'eating'
        opening = .5+.35*math.sin(self.chew) if eating else .65
        for side in (-1, 1):
            # Both eyes sit on the dorsal crown, rotating with the head.
            roll = math.cos(getattr(c, 'worm_roll', (0.,)*6)[-1])
            eye = (head[0]-nx*skin*roll+dx*skin*.45*side,
                   head[1]-ny*skin*roll+dy*skin*.45*side)
            pygame.draw.circle(screen, color((222, 235, 157)), eye, max(1, skin*.4))
            pygame.draw.circle(screen, color((24, 40, 29)), eye, max(1, skin*.23))
            root = (head[0]+nx*skin*.8*side+dx*skin*.5,
                    head[1]+ny*skin*.8*side+dy*skin*.5)
            jaw = (head[0]+dx*skin*2+nx*skin*opening*side,
                   head[1]+dy*skin*2+ny*skin*opening*side)
            pygame.draw.lines(screen, color((242, 166, 80) if eating else (215, 205, 125)), False,
                              [root, jaw, (jaw[0]-nx*side*skin*.5, jaw[1]-ny*side*skin*.5)], max(1, round(scale)))
