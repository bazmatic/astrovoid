"""Flying-fish flockers: ribbed gliding fins, metallic scales, and a forked tail.

Hit recoil and fin folding are visual only, including the first moments of a lethal hit.
"""
import math
import pygame
import config


class FlockerBody:
    DEATH_DURATION = 48.0
    DEATH_FRICTION = 0.94
    WING_SPEED = 0.18
    FLINCH_FRAMES = 12.0
    VISUAL_SCALE = 0.7

    def __init__(self, creature):
        self._creature = creature
        self.wing_phase = (creature.x*.013+creature.y*.017)%math.tau
        self.flinch_remaining = 0.0

    x = property(lambda self: self._creature.x)
    y = property(lambda self: self._creature.y)
    radius = property(lambda self: self._creature.radius)
    angle = property(lambda self: self._creature.angle)

    def on_event(self, creature, name):
        if name in ('hit','flinch'):
            self.flinch_remaining = self.FLINCH_FRAMES

    def update(self, creature, dt, target=None):
        self.wing_phase = (self.wing_phase+dt*self.WING_SPEED)%math.tau
        self._advance_flinch(dt)

    def update_death(self, creature, dt):
        self._advance_flinch(dt)

    def _advance_flinch(self, dt):
        self.flinch_remaining = max(0.0,self.flinch_remaining-dt)

    def draw(self, screen, creature):
        self._draw_fish(screen)

    def draw_death(self, screen, creature):
        self._draw_fish(screen,creature.death_progress)

    def _draw_fish(self, screen, progress=0.0):
        radius = self.radius*self.VISUAL_SCALE*(1-progress*progress)
        if radius < 1:
            return
        flinch = self.flinch_remaining/self.FLINCH_FRAMES
        fold = min(1.0,progress/.45)
        fold = fold*fold*(3-2*fold)
        angle = math.radians(self.angle+240*progress**1.5
                             +12*flinch*math.sin((1-flinch)*math.tau))
        cs,sn = math.cos(angle),math.sin(angle)
        recoil = -.35*radius*flinch
        center = (self.x+cs*recoil,self.y+sn*recoil)

        def point(x,y):
            return (center[0]+radius*(x*cs-y*sn),center[1]+radius*(x*sn+y*cs))

        def color(rgb):
            flash = flinch*.85
            return tuple(round(channel+(255-channel)*flash) for channel in rgb)

        def polygon(rgb, points, outline=None):
            vertices = [point(x,y) for x,y in points]
            pygame.draw.polygon(screen,color(rgb),vertices)
            if outline:
                pygame.draw.aalines(screen,color(outline),True,vertices)

        def line(rgb, points, width=1):
            pygame.draw.lines(screen,color(rgb),False,[point(x,y) for x,y in points],width)

        base = config.FLOCKER_ENEMY_COLOR
        dark = (75,65,58)
        fin = (36,139,150)
        fin_light = (113,224,207)
        gold = (255,220,120)
        from rendering.visual_effects import draw_glow_circle
        draw_glow_circle(screen,center,radius*.45,base,glow_radius=radius*.35,intensity=.2)

        # A flying fish's long lower tail lobe and two smaller pelvic gliding fins.
        tail_sway = math.sin(self.wing_phase*1.6)*.1*(1-fold)
        polygon((218,130,54),[(-.72,0),(-1.67,-.43+tail_sway),(-1.25,tail_sway),
                              (-1.85,.56+tail_sway),(-1.03,.14)],gold)
        line(dark,[(-.9,0),(-1.55,-.32+tail_sway)])
        line(dark,[(-.9,0),(-1.69,.43+tail_sway)])
        for side in (-1,1):
            polygon((70,168,161),[(-.42,side*.2),(-1.06,side*.65*(1-.65*fold)),
                                   (-.87,side*.17)],fin_light)

        # Broad pectoral membranes breathe gently, with scalloped edges and visible fin rays.
        span = (1+.1*math.sin(self.wing_phase))*(1-.76*fold)*(1-.38*flinch)
        for side in (-1,1):
            root=(.32,side*.18)
            edge=[(.05,side*.95*span),(-.35,side*1.62*span),(-.64,side*1.54*span),
                  (-.78,side*1.25*span),(-1.04,side*1.14*span),(-.9,side*.72*span),
                  (-1.05,side*.46*span),(-.52,side*.25)]
            polygon(fin,[root,*edge],fin_light)
            polygon((55,174,173),[root,edge[0],edge[1],(-.33,side*.46*span)])
            for tip in edge[1:-1]:
                line((109,215,190),[root,tip])
            line(gold,[root,edge[0],edge[1]])
            line((24,100,120),[(-.45,side*.28),edge[-3]])

        # Streamlined, faceted body: dark metallic back and a warm reflective belly.
        hull=[(1.2,0),(.88,-.24),(.35,-.38),(-.35,-.3),(-.96,-.1),
              (-1.04,.08),(-.38,.29),(.32,.38),(.94,.22)]
        polygon(base,hull,dark)
        polygon((133,105,57),[(1.15,0),(.72,-.2),(.3,-.3),(-.4,-.23),(-.91,-.06),(.3,-.04)])
        polygon(gold,[(1.05,.06),(.6,.14),(.2,.29),(-.45,.18),(-.85,.07),(.16,.04)])
        # Individual scale facets retain detail when inflated by the comedy weapon.
        for x in (-.48,-.19,.1,.39):
            for side in (-1,1):
                y=side*.12
                polygon((228,173,76),[(x-.1,y),(x,y-.075),(x+.1,y),(x,y+.075)])
        line((255,240,173),[(-.78,.03),(-.12,.02),(.5,.06),(.84,.03)])
        line(dark,[(.54,-.27),(.46,-.05),(.57,.26)])  # gill cover
        line((247,225,151),[(.64,-.25),(.58,-.05),(.66,.23)])
        polygon((57,134,145),[(.2,-.06),(-.36,-.12),(-.1,-.01)],fin_light)  # dorsal ridge

        # Raised eyes, dark pupils, tiny specular glints, and a pointed mouth.
        for side in (-1,1):
            eye=point(.85,side*.16)
            er=max(1,round(radius*.115))
            pygame.draw.circle(screen,color((249,242,194)),(round(eye[0]),round(eye[1])),er+1)
            pygame.draw.circle(screen,(20,38,46),(round(eye[0]),round(eye[1])),er)
            glint=point(.89,side*.16-.04)
            screen.set_at((round(glint[0]),round(glint[1])),(255,255,245))
        line(dark,[(1.2,0),(1.04,.035)])

        if flinch > 0:
            # A short, deterministic spray makes even a one-hit death read as an impact.
            for i in range(6):
                a=i*math.tau/6+.2
                reach=radius*(1.1+.75*(1-flinch))
                head=(center[0]+math.cos(a)*reach,center[1]+math.sin(a)*reach)
                tail=(head[0]+math.cos(a)*radius*.35*flinch,
                      head[1]+math.sin(a)*radius*.35*flinch)
                pygame.draw.line(screen,(255,235,175),head,tail,1)
