"""Training target adapter for the production Jellyfish creature with allied allegiance."""
from creatures.encounter import Encounter
from game_handlers.enemy_roster import EnemyRoster

PURSUER_COUNT = 4
PURSUER_SPEED_MIN = .5
PURSUER_SPEED_MAX = 2.5
PURSUER_HEALTH = 2
PURSUER_START_DISTANCE = 300.
CONTACT_DAMAGE = 4.
CONTACT_INTERVAL = 30
CONTACT_COST = 5.


class PursuitEncounter(Encounter):
    def target_for(self, creature):
        # The production chase brain asks the encounter for a target. Allies pursue enemies.
        enemies = [c for c in self.world.roster.alive() if c.allegiance == 'enemy']
        target = min(enemies,key=lambda c:(c.x-creature.x)**2+(c.y-creature.y)**2,default=None)
        return target.get_pos() if target is not None else None


class AlliedJellyfish:
    """Expose the same target lifecycle as practice targets while reusing real creature traits."""
    shots_fired = 0

    def __init__(self, position, env, encounter, speed):
        import creatures
        self.creature = creatures.build('aggressive',position,env.level)
        self.creature.allegiance = 'ally'
        # Change only this instance's speed; campaign Jellyfish retain catalogue tuning.
        next(t for t in self.creature.traits if t.NAME == 'drift').speed = speed
        next(t for t in self.creature.traits if t.NAME == 'takesHits').hit_points = PURSUER_HEALTH
        self.encounter = encounter
        encounter.roster.add(self.creature)
        self.env = env

    def __getattr__(self,name):
        return getattr(self.creature,name)

    def get_pos(self):return self.creature.get_pos()

    def step(self,maze):
        if self.encounter.last_frame != self.env.frames:
            self.encounter.last_frame = self.env.frames
            self.encounter.step(1)

    def fire(self,crawlers,maze):return None

    def take_hit(self,shot):
        before = self.creature.hit_points
        self.encounter.apply_hit(self.creature,shot)
        return self.creature.hit_points < before

    def on_contacts(self):
        if not self.creature.active:return
        for c in self.env.world.roster.alive():
            if self.creature.check_circle_collision(c.get_pos(),c.radius,c):
                self.env.contact_hit(c)

    def draw(self,screen):
        if self.creature.active:self.creature.draw(screen)

    def close(self):self.encounter.close()


def create_pursuers(env,positions,seed):
    from learning.adapters.crawler_curriculum import setup_dodge
    # Keep the tested wall starts and useful landing routes from reposition encounters.
    sites = setup_dodge(env,positions,seed)
    encounter = PursuitEncounter(EnemyRoster(),env.world)
    encounter.last_frame = -1
    import math
    import random
    from creatures.traits.rooted import wall_between
    rng=random.Random(seed+41000)
    maze=env.world.maze;crew=env.team.members()
    cells=[maze.position_calculator.grid_center_to_screen(x,y)
           for y in range(1,maze.grid_height-1) for x in range(1,maze.grid_width-1) if not maze.grid[y][x]]
    rng.shuffle(cells)
    chosen=[]
    for i in range(PURSUER_COUNT):
        c=crew[i%len(crew)]
        choices=[p for p in [t.get_pos() for t in sites]+cells
                 if maze.is_open(p,10)
                 and all(math.dist(p,other.get_pos())>=PURSUER_START_DISTANCE for other in crew)
                 and all(math.dist(p,q)>=24 for q in chosen)]
        if not choices:raise ValueError('pursuit arena lacks separated Jellyfish starts')
        def priority(p):
            distance=math.dist(c.get_pos(),p)
            outward=((p[0]-c.x)*c.wall_normal[0]+(p[1]-c.y)*c.wall_normal[1])/max(distance,1e-9)
            # An oblique pursuer leaves a forward escape lane while this skill is taught.
            oblique=math.cos(math.pi/4)<=outward<=math.cos(math.pi/6)
            return wall_between(c.get_pos(),p,maze),not oblique,distance
        choices.sort(key=priority)
        chosen.append(choices[0])
    # Separate speed sampling from placement so geometry search cannot change the draws.
    speed_rng = random.Random(seed+43000)
    targets = [AlliedJellyfish(p,env,encounter,
               speed_rng.uniform(PURSUER_SPEED_MIN,PURSUER_SPEED_MAX)) for p in chosen]
    encounter.ready()
    for target in targets:
        target.reposition_target = any(getattr(site,'reposition_target',False) and site.get_pos()==target.get_pos() for site in sites)
    return targets
