"""Single-worm physical drills and a gated five-lesson recurrent PPO curriculum."""
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import numpy as np

from learning.environment import Snapshot, Transition
from learning.adapters.inchworm import (SPEC, CRITIC_SIZE, DECISION_FRAMES, observe, intention,
                                        action_for, enabled, load_policy)
from learning import inchworm_rewards

INITIAL_STAGE = 1
USES_OPPONENT = False
EVALUATION_MODES = ('trained', 'scripted')
IMITATION_HEADS = tuple(n for n,_ in SPEC.heads)
IMITATION_EPOCHS = 4
STAGES = ('crawl','turn','reach','feed','recover')
TRAIN_LEVELS = (0,1,2,3)
VALIDATION_LEVELS = (4,5,6,7)
HOLDOUT_LEVELS = (8,9,10,11)
ARENAS = {str(i):dict(angle=angle,half_length=350.) for i,angle in enumerate(
    (0.,90.,180.,270.,22.5,112.5,202.5,292.5,45.,135.,225.,315.))}


class InchwormEnvironment:
    spec = SPEC
    adapter = sys.modules[__name__]

    def __init__(self,horizon=45.,arenas=None,scripted=False,rewards=None,opponent=None,muted=False):
        if not math.isfinite(horizon) or horizon <= 0:
            raise ValueError('inchworm horizon must be finite and positive')
        self.horizon, self.arenas = horizon, arenas or ARENAS
        self.scripted = scripted
        self.rewards = inchworm_rewards.validate(rewards or {})
        self.world = None
        self.render_frames = None

    def reset(self,seed,level=0,stage=1):
        import creatures
        from creatures.encounter import Encounter
        from creatures.inchworm_control import InchwormController
        from creatures.traits.combat import TakesHits
        from game_handlers.enemy_roster import EnemyRoster
        from maze.wall_segment import WallSegment
        self.close()
        if stage not in range(1,6):
            raise ValueError('inchworm stage must be 1..5')
        self.seed, self.level, self.stage = seed,level,stage
        self.rng = rng = random.Random(seed)
        angle = math.radians(self.arenas[str(level)]['angle'])
        self.forward, self.normal = (math.cos(angle),math.sin(angle)),(math.sin(angle),-math.cos(angle))
        self.origin = (650.,430.)
        def point(along,out):
            return (self.origin[0]+self.forward[0]*along+self.normal[0]*out,
                    self.origin[1]+self.forward[1]*along+self.normal[1]*out)
        half = self.arenas[str(level)]['half_length']
        wall = WallSegment(point(-half,0),point(half,0),1,destructible=False)
        maze = SimpleNamespace(walls=[wall],gate_segments=[],spatial_grid=None)
        self.world = SimpleNamespace(ship=None,hunter=None,maze=maze,roster=EnemyRoster(),
            inchworm_policy=None,additional_targets=[],projectiles=[],worm_goal=None,
            sound_manager=SimpleNamespace(play_enemy_destroy=lambda:None),
            collision_handler=SimpleNamespace(drop_pickup=lambda *a:None),powerup_crystals=[],
            jev_beacon_allowed=lambda:False,command_recorder=None)
        self.worm = c = creatures.build('inchworm',point(rng.uniform(-70,-40),14.),angle=math.degrees(angle))
        c.agent_id = 0
        self.world.roster.add(c)
        self.enc = Encounter(self.world.roster,self.world)
        self.enc.ready()
        self.start = c.get_pos()
        self.goal_direction = -1 if stage == 2 else 1
        distance = rng.uniform(60.,90.)
        self.world.worm_goal = (c.x+self.forward[0]*distance*self.goal_direction,
                                c.y+self.forward[1]*distance*self.goal_direction)
        self.prey = None
        if stage >= 3:
            along = rng.uniform(15.,30.)
            outward = rng.uniform(28.,40.) if stage == 3 else rng.uniform(12.,26.)
            pos = (c.x+self.forward[0]*along+self.normal[0]*outward,
                   c.y+self.forward[1]*along+self.normal[1]*outward)
            self.prey = creatures.build('static',pos,angle=0.)
            self.prey.allegiance = 'friend'
            self.prey.traits = (TakesHits(6),)
            self.prey.after_frame_traits = ()
            self.world.roster.add(self.prey)
            self.enc.ready()
            self.world.worm_goal = None
            self.prey_anchor = pos
        self.teacher = InchwormController()
        if stage == 2:
            self.teacher.request_turn(c.worm_physics)
        self.frames = self.bites = self.contact_frames = self.recovered_frames = 0
        self.shove_at = rng.randrange(180,241)
        self.shoved = False
        self.bites_at_shove = 0
        self.finished = self.success = False
        self.effort_sum = self.airborne_frames = self.return_total = 0.
        self.previous = np.zeros(8,np.float32)
        self.action_trace = []
        return self.snapshot()

    def snapshot(self):
        x,masks,_ = observe(self.worm,self.enc)
        live = self.worm.active
        return Snapshot({0:x} if live else {},{0:masks} if live else {},x,{0:x})

    def distance(self):
        if self.prey is not None:
            return max(0.,math.dist(self.worm.worm_front,self.prey.get_pos())-self.prey.radius-self.worm.worm_skin)
        return math.dist(self.worm.get_pos(),self.world.worm_goal)

    def step(self,actions):
        if self.finished:
            raise RuntimeError('step after inchworm episode ended')
        if self.scripted:
            action = teacher_action(self,0,None)
        else:
            if set(actions) != {0}:
                raise ValueError('inchworm episode expects action for agent 0')
            action = tuple(actions[0])
        command = intention(action)
        self.action_trace.append({0:tuple(float(v) for v in action)})
        self.worm.worm_command = command
        start_distance = self.distance()
        old_bites = self.bites
        applied = np.asarray([*command.muscles,command.rear_grip,command.front_grip,command.bite])
        reward = -self.rewards['action_change_cost']*float(np.mean((applied-self.previous)**2))
        self.previous = applied
        count = min(DECISION_FRAMES, max(0,math.ceil(self.horizon*60)-self.frames))
        for _ in range(count):
            if self.stage == 5 and self.frames == self.shove_at:
                self.worm.apply_momentum(self.normal[0]*.15+self.forward[0]*.25,
                                         self.normal[1]*.15+self.forward[1]*.25)
                self.shoved, self.bites_at_shove = True,self.bites
            before = self.prey.hit_points if self.prey is not None else 0
            self.enc.step(1.)
            p = self.worm.worm_physics
            self.bites += int(before-(self.prey.hit_points if self.prey else 0))
            if self.prey is not None and self.prey.active:
                # The solver supplies grasp impulses. Only stage 5 adds a modest
                # physical evasive acceleration; the prey is never repositioned.
                if self.stage == 5:
                    for axis,i in (('vx',0),('vy',1)):
                        restore = (self.prey_anchor[i]-self.prey.get_pos()[i])*.001
                        setattr(self.prey,axis,getattr(self.prey,axis)+restore+self.forward[i]*.008*math.sin(self.frames/90.))
                self.prey.vx *= .98
                self.prey.vy *= .98
                self.prey.prev_x,self.prey.prev_y = self.prey.get_pos()
                self.prey.x += self.prey.vx
                self.prey.y += self.prey.vy
                from physics.thrust import sweep_walls
                sweep_walls(self.prey,self.world.maze.walls)
            touching = p.mouth_contact and self.worm.worm_rear_grip
            self.contact_frames = self.contact_frames+1 if touching else 0
            grounded = self.worm.worm_front_grip or self.worm.worm_rear_grip
            if self.shoved and grounded and self.worm.worm_stun == 0:
                self.recovered_frames += 1
            self.effort_sum += p.effort
            self.airborne_frames += not grounded
            reward -= (self.rewards['effort_cost']*p.effort+self.rewards['time_cost']
                       +self.rewards['airborne_cost']*float(not grounded and self.worm.worm_stun == 0))/60.
            self.frames += 1
            if self.stage == 1:
                self.success = self.distance() < 14. and grounded
            elif self.stage == 2:
                facing = math.cos(p.heading)*self.forward[0]+math.sin(p.heading)*self.forward[1]
                self.success = (facing < -.9 and math.dist(p.head,p.tail) > p.length*5
                                and self.worm.worm_front_grip and self.distance() < 25.)
            elif self.stage == 3:
                self.success = self.contact_frames >= 12
            elif self.stage == 4:
                self.success = self.bites >= 2
            else:
                self.success = self.shoved and self.recovered_frames >= 30 and self.bites-self.bites_at_shove >= 2
            if self.render_frames is not None:
                self.render_frames(self)
            if self.success or not self.worm.active:
                break
        # Telescoping potential: moving away is negative, so rocking back and
        # forth or releasing/regrabbing cannot harvest repeated progress rewards.
        reward += self.rewards['progress_reward']*(start_distance-self.distance())
        reward += self.rewards['bite_reward']*(self.bites-old_bites)
        if self.success:
            reward += self.rewards['success_reward']
        if not self.worm.active:
            reward -= self.rewards['death_penalty']
        self.return_total += reward
        terminated = self.success or not self.worm.active
        truncated = not terminated and self.frames >= math.ceil(self.horizon*60)
        self.finished = terminated or truncated
        return Transition(self.snapshot(),reward,terminated,truncated,self.events(),{0:reward})

    def events(self):
        return dict(seconds=self.frames/60.,success=float(self.success),bites=self.bites,
                    distance=self.distance(),effort=self.effort_sum/max(1,self.frames),
                    airborne_fraction=self.airborne_frames/max(1,self.frames),
                    survived=float(self.worm.active),recovered=float(self.recovered_frames>=30),
                    return_total=self.return_total,stage=self.stage)

    def close(self):
        if self.world is not None:
            self.enc.close()
            self.world = None


def teacher_action(env, agent, action):
    target = env.prey if env.prey is not None and env.prey.active else None
    return action_for(env.teacher.command(env.worm.worm_physics,DECISION_FRAMES,target))


def environment(**options):
    return InchwormEnvironment(**options)


def environment_options(manifest):
    return dict(rewards=inchworm_rewards.validate(manifest.get('rewards',{})))


def metadata(args):
    import enemy_kinds
    import pymunk
    root = Path(__file__).resolve().parents[2]
    files = ('physics/inchworm.py','creatures/inchworm_control.py','creatures/traits/inchworm.py',
             'learning/adapters/inchworm.py','learning/adapters/inchworm_scenario.py')
    return dict(task=SPEC.task,scenario_version=1,spec=SPEC.metadata(),horizon=args.horizon,
                decision_frames=DECISION_FRAMES,opponent_sha256=None,arenas=ARENAS,
                creature=asdict(enemy_kinds.kind('inchworm')),rewards=inchworm_rewards.from_args(args),
                pymunk=pymunk.version,physics_fps=60,twist='automatic_bounded_reflex',
                implementation_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files})


def training_cases(iteration,count,stage,bootstrap=False,curriculum=None):
    current = curriculum['stage'] if curriculum else stage
    return [dict(level=TRAIN_LEVELS[j%4],seed=10000+iteration*count+j+(500000000 if bootstrap else 0),
                 stage=1+j%5 if bootstrap else (1+(j//4)%(current-1) if current>1 and j%4==0 else current)) for j in range(count)]


def validation_cases():
    return [dict(level=level,seed=2000000000+stage*100+j*4+k,stage=stage)
            for stage in range(1,6) for j,level in enumerate(VALIDATION_LEVELS) for k in range(3)]


def evaluation_cases():
    return [dict(level=level,seed=3000000000+stage*100+j*4+k,stage=stage)
            for stage in range(1,6) for j,level in enumerate(HOLDOUT_LEVELS) for k in range(3)]


def metrics(rows):
    return {key:float(np.mean([r.get(key,0.) for r in rows])) if rows else 0.
            for key in ('success','bites','distance','effort','airborne_fraction','survived','recovered','return_total')}


def selection_score(summary):
    return summary['success']*10+summary['bites']-summary['distance']*.01-summary['effort']*.1


def compare(a,b):
    if len(a['episodes']) != len(b['episodes']):
        raise ValueError('inchworm comparison requires paired cases')
    values = []
    for x,y in zip(a['episodes'],b['episodes']):
        if any(x[k] != y[k] for k in ('level','seed','stage')):
            raise ValueError('inchworm comparison cases do not match')
        values.append(x['success']-y['success'])
    if not values:
        return dict(mean=0.,lower_95=-1.,upper_95=1.)
    samples = np.random.default_rng(0).choice(values,(2000,len(values))).mean(axis=1)
    return dict(mean=float(np.mean(values)),lower_95=float(np.quantile(samples,.025)),upper_95=float(np.quantile(samples,.975)))


def promote(stage,summary):
    return stage


def initial_curriculum(args):
    return dict(stage=1,passing_blocks=0)


def validation_evidence(summary,state,args,deadline=math.inf):
    threshold = (.8,.8,.8,.75,.65)[state['stage']-1]
    passed = summary['success'] >= threshold and summary['survived'] == 1.
    return dict(inchworm_validation_passed=passed)


def advance_curriculum(state,summary):
    state = dict(state)
    if 'inchworm_validation_passed' not in summary:
        return state
    state['passing_blocks'] = state['passing_blocks']+1 if summary['inchworm_validation_passed'] else 0
    if state['passing_blocks'] >= 2 and state['stage'] < 5:
        state.update(stage=state['stage']+1,passing_blocks=0)
    return state


def curriculum_key(state):
    return STAGES[state['stage']-1]


def curriculum_validation_cases(state):
    return [c for c in validation_cases() if c['stage']==state['stage']]


def curriculum_evaluation_cases(state):
    return evaluation_cases()


def curriculum_selection_score(summary,state):
    return selection_score(summary)


def deployment_report(reports,args,deadline=math.inf):
    rows = reports['trained']['episodes']
    coverage = {r['stage'] for r in rows} == set(range(1,6))
    passed = coverage and all(metrics([r for r in rows if r['stage']==s])['success'] >= (.8,.8,.8,.75,.65)[s-1]
                              for s in range(1,6))
    paired = compare(reports['trained'],reports['scripted'])
    return dict(passed=bool(passed and paired['lower_95']>=-.05),versus_reflex=paired,
                automatic_install=False)
