"""A walking gun: many gripping legs, an armoured barrel, and folded legs in flight."""
import math

import pygame


class WallcrawlerBody:
    LEG_PAIRS = 3
    DEATH_DURATION = 30.0
    DEATH_FRICTION = 0.94

    def __init__(self, creature):
        self.grip = None
        self.barrel_angle = None
        self.recoil = 0.

    def on_event(self, creature, name):
        if name == 'fired':
            self.recoil = 1.

    def update(self, creature, dt, target=None):
        self.recoil *= math.exp(-dt/4)
        attached=creature.wall_state=='attached'
        planted=attached or creature.wall_phase in ('launch','landing') or creature.wall_approach is not None
        goal=1. if planted else 0.
        if self.grip is None:self.grip=goal
        self.grip+= (goal-self.grip)*(1-math.exp(-dt/3))
        desired=creature.angle
        if self.barrel_angle is None:self.barrel_angle=desired
        delta=(desired-self.barrel_angle+180)%360-180
        self.barrel_angle=(self.barrel_angle+max(-12*dt,min(12*dt,delta)))%360

    def update_death(self, creature, dt):
        if not hasattr(creature,'wall_body_angle'):
            creature.wall_body_angle=creature.angle
            creature.wall_angular_velocity=0.
        from physics.angular_motion import advance
        advance(creature,0.,dt)

    def draw(self, screen, c):
        self._draw(screen, c, 1.0)

    def draw_death(self, screen, c):
        self._draw(screen, c, 1.0 - c.death_progress)

    def _draw(self, screen, c, scale):
        r = c.radius * scale
        if r < 0.5:
            return
        attached = getattr(c, 'wall_state', 'returning') == 'attached'
        body_angle=math.radians(getattr(c,'wall_body_angle',c.angle))
        nx,ny=math.cos(body_angle),math.sin(body_angle)
        tx, ty = -ny, nx
        phase = getattr(c, 'walk_phase', 0.0)
        colour = tuple(c.kind.tuning['color'])
        def point(t, n):
            return (round(c.x + tx * t + nx * n), round(c.y + ty * t + ny * n))
        # Grounded feet stay on the same rock while the body pushes away or settles in.
        phase_name=getattr(c,'wall_phase','flight')
        site=getattr(c,'wall_destination',None)
        if phase_name=='launch' and c.wall_launch_origin is not None:
            gx,gy=c.wall_launch_normal
            anchor=(c.wall_launch_origin[0]-gx*(c.radius+2),c.wall_launch_origin[1]-gy*(c.radius+2))
        elif phase_name=='landing' and site is not None:
            gx,gy=site.normal;anchor=site.foot
        elif getattr(c,'wall_approach',None) is not None and not attached:
            anchor,(gx,gy)=c.wall_approach
        else:
            gx,gy=getattr(c,'wall_normal',(0.,-1.));anchor=(c.x-gx*(c.radius+2),c.y-gy*(c.radius+2))
        grip=self.grip if self.grip is not None else float(attached)
        grip *= scale
        legs=[]
        for side in (-1,1):
            for i in range(self.LEG_PAIRS):
                along=(i/(self.LEG_PAIRS-1)-.5)*r*1.35
                wave=math.sin(phase+i*math.pi*.8)
                hip=point(along+side*r*.07,-r*.28)
                folded=point(along+side*r*.12,-r*.45)
                spread=along+side*r*.18+(wave*r*.12 if attached else 0)
                lift=max(0,wave*side)*r*.3 if attached else 0
                grounded=(anchor[0]-gy*spread+gx*lift,anchor[1]+gx*spread+gy*lift)
                foot=(folded[0]+(grounded[0]-folded[0])*grip,
                      folded[1]+(grounded[1]-folded[1])*grip)
                knee=self._knee(hip,foot,r*.70,r*.95,(side*tx,side*ty))
                legs.append((side,hip,knee,foot))
        # Far legs sit behind the shell; near legs emerge from its lower rim.
        for side,hip,knee,foot in legs:
            if side<0 or grip<.3:self._leg(screen,hip,knee,foot,r,colour,False)
        self._shell(screen,point,r,colour,attached)
        for side,hip,knee,foot in legs:
            if side>0 and grip>=.3:self._leg(screen,hip,knee,foot,r,colour,True)
        self._feeler(screen,c,r,attached)

    @staticmethod
    def _knee(hip,foot,thigh,shin,bend):
        """Two articulated segments unfold around a hock while the foot stays planted."""
        dx,dy=foot[0]-hip[0],foot[1]-hip[1]
        distance=max(1e-6,math.hypot(dx,dy))
        ux,uy=dx/distance,dy/distance
        reach=max(abs(thigh-shin)+1e-6,min(thigh+shin,distance))
        along=(thigh*thigh-shin*shin+reach*reach)/(2*reach)
        height=math.sqrt(max(0.,thigh*thigh-along*along))
        sign=1 if -uy*bend[0]+ux*bend[1]>=0 else -1
        return hip[0]+ux*along-uy*height*sign,hip[1]+uy*along+ux*height*sign

    @staticmethod
    def _leg(screen,hip,knee,foot,r,colour,near):
        edge=(42,35,24)
        chitin=colour if near else tuple(round(v*.55) for v in colour)
        thigh=max(1,round(r*.30))
        shin=max(1,round(r*.16))
        pygame.draw.lines(screen,edge,False,[hip,knee,foot],shin+2)
        pygame.draw.line(screen,chitin,hip,knee,thigh)
        pygame.draw.line(screen,chitin,knee,foot,shin)
        joint=tuple(round(v) for v in knee)
        pygame.draw.circle(screen,edge,joint,max(1,round(r*.16)))
        pygame.draw.circle(screen,chitin,joint,max(1,round(r*.10)))
        # Small dark gripping tips, rather than a luminous comb along the wall.
        pygame.draw.circle(screen,(104,117,105),tuple(round(v) for v in foot),max(1,round(r*.09)))

    @staticmethod
    def _shell(screen,point,r,colour,attached):
        def oval(t,n,width,height):
            return [point((t+width*math.sin(i*math.tau/24))*r,
                          (n+height*math.cos(i*math.tau/24))*r) for i in range(24)]
        dark=(38,34,25)
        bronze=tuple(round(v*.56) for v in colour)
        shaded=tuple(round(v*.76) for v in colour)
        # A rounded abdomen, two domed wing cases, and a low head shield.
        hull=oval(0,.04,1.0,.72)
        pygame.draw.polygon(screen,dark,hull)
        pygame.draw.polygon(screen,bronze,oval(0,.08,.9,.64))
        pygame.draw.polygon(screen,shaded,oval(.27,.10,.48,.55))
        pygame.draw.polygon(screen,colour,oval(-.28,.13,.43,.54))
        highlight=tuple(min(255,round(v*.65+255*.35)) for v in colour)
        pygame.draw.line(screen,highlight,point(-r*.55,r*.13),point(-r*.36,r*.52),max(1,round(r*.09)))
        pygame.draw.line(screen,dark,point(0,-r*.49),point(0,r*.53),max(1,round(r*.10)))
        head=oval(0,.55,.5,.33)
        pygame.draw.polygon(screen,(60,66,47),head)
        pygame.draw.polygon(screen,bronze,head,max(1,round(r*.1)))
        eye=(245,146,62) if attached else (98,136,122)
        for side in (-1,1):
            pygame.draw.circle(screen,eye,point(side*r*.28,r*.59),max(1,round(r*.11)))

    def _feeler(self,screen,c,r,attached):
        """A squat, knuckled antenna with a dark aperture in its terminal bulb."""
        angle=math.radians(c.angle if self.barrel_angle is None else self.barrel_angle)
        ax,ay=math.cos(angle),math.sin(angle)
        recoil=self.recoil*r*.13
        def tip(forward,side=0):
            return (round(c.x+ax*(r*forward-recoil)-ay*r*side),
                    round(c.y+ay*(r*forward-recoil)+ax*r*side))
        root,joint,muzzle=tip(.30),tip(.77,.06),tip(1.12,.1)
        pygame.draw.line(screen,(42,38,27),root,joint,max(2,round(r*.36)))
        pygame.draw.line(screen,(159,132,77),root,joint,max(1,round(r*.21)))
        pygame.draw.line(screen,(124,107,68),joint,muzzle,max(1,round(r*.16)))
        pygame.draw.circle(screen,(193,163,93),joint,max(1,round(r*.17)))
        bulb=(227,191,111) if attached else (126,132,101)
        pygame.draw.circle(screen,bulb,muzzle,max(1,round(r*.20)))
        aperture=(255,235,165) if self.recoil>.65 else (30,34,27)
        pygame.draw.circle(screen,aperture,muzzle,max(1,round(r*.075)))
