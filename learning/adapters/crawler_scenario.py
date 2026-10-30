"""Actual ship and creature physics in seeded team encounters, with a frozen neural opponent."""
from collections import Counter
from dataclasses import replace
import hashlib
import math
import random
from pathlib import Path
from types import SimpleNamespace
import numpy as np

from learning.environment import Snapshot, Transition
from learning.adapters.shot_accuracy import shot_quality, ACCURACY_WEIGHT, SHOT_COST
from learning.adapters.wallcrawler import SPEC, CRITIC_SIZE, observe, critic, intention, DECISION_FRAMES, load_transfer_policy

TRAIN_LEVELS = (11, 13, 14, 16, 17, 19, 21, 27)
HOLDOUT_LEVELS = (15, 20, 23)
PRACTICE_FIRE_INTERVAL = 15
PRACTICE_WALKING = True
PRACTICE_JUMPING = True
AIMING_PRACTICE = True
WALK_REVERSAL_COST = .02
BULLET_HIT_COST = 1.
JUMP_COST = .1
JUMP_PROXIMITY_RANGE = 150.
JUMP_PROXIMITY_REWARD = 1.
LANDING_REWARD = 1.
TRIAL_COMPLETION_REWARD = 10.
BATTLE_ALIVE_RATE = .1
BATTLE_SURVIVAL_BONUS = 20.
BATTLE_DEATH_COST = 40.
BATTLE_KILL_REWARD = 5.
SHIPS_FIRE = False
SHIP_BULLET_DAMAGE = .1
DEFAULT_OPPONENT = Path(__file__).resolve().parents[2] / 'assets/neural/hunter.npz'


class SilentSound:
    def __getattr__(self, name):
        return lambda *a, **kw: None


def opponent_settings():
    from hunter.settings_for import hunter_settings_for
    return replace(hunter_settings_for('neural'), indestructible=False, wall_energy=0.)


class FrozenHunter:
    """Use the production allied hunter flight, senses, propulsion and gun unchanged."""
    def __init__(self, path, world, position, angle, firing_enabled=SHIPS_FIRE):
        from hunter.neural.policy import NeuralPolicy
        from hunter.flight import NeuralPilot
        from hunter.build import PilotSetup, make_hunter
        from hunter.surroundings import GameSurroundings
        from learning.adapters.player_pilot import MovementOnlyPolicy
        policy = NeuralPolicy.load(path)
        if not firing_enabled:
            policy = MovementOnlyPolicy(policy)
        self.settings = opponent_settings()
        self.flight = make_hunter(position, world=world, angle=angle,
            setup=PilotSetup(self.settings, NeuralPilot(policy, DECISION_FRAMES),
                             GameSurroundings(world)))
        self.ship = self.flight.ship

    def frame(self, world):
        self.flight.step(1)

    def close(self):
        self.flight.close()


class CrawlerEnvironment:
    spec = SPEC
    from learning.adapters import wallcrawler as adapter

    def __init__(self, opponent=DEFAULT_OPPONENT, horizon=60.0, muted=False, arenas=None, scripted=False):
        self.opponent_path, self.horizon, self.muted = str(opponent), horizon, muted
        self.arenas = arenas
        self.scripted = scripted
        self.world = None
        self.render_frames = None

    def reset(self, seed, level=11, team_size=2, opponents='hunter', practice_stage='shooting', jumping=None, neural_hunter=False, jelly_count=None):
        import pygame
        import config
        import creatures
        import level_config
        from creatures.encounter import Encounter
        from creatures.wallcrawler_team import get_team
        from entities.command_recorder import CommandRecorder
        from game_handlers.enemy_roster import EnemyRoster
        from game_handlers.collision_handler import CollisionHandler
        from scoring.system import ScoringSystem
        from maze.generator import Maze
        from physics.obstacle_world import ObstacleWorld
        if practice_stage not in ('shooting','dodge','pursuit','precision','tracking'):
            raise ValueError('unknown practice stage')
        if neural_hunter and opponents != 'practice':
            raise ValueError('neural_hunter is only supported with practice opponents')
        from learning.adapters.allied_jellyfish import PURSUER_COUNT
        if jelly_count is not None and (practice_stage != 'pursuit' or type(jelly_count) is not int or not 1 <= jelly_count <= PURSUER_COUNT):
            raise ValueError('jelly_count requires a pursuit drill and a valid pursuer count')
        self.jelly_count = PURSUER_COUNT if jelly_count is None else jelly_count
        self.neural_hunter = neural_hunter
        self.aim_drill = practice_stage in ('precision','tracking')
        if self.aim_drill and (opponents != 'practice' or neural_hunter):
            raise ValueError('aim drills require harmless practice targets without a hunter')
        self.landing_reward = 0. if self.aim_drill or practice_stage == 'pursuit' else LANDING_REWARD
        self.practice_stage = practice_stage
        from learning.adapters.crawler_curriculum import DODGE_JUMP_COST
        self.jump_cost = 0. if practice_stage=='pursuit' else DODGE_JUMP_COST if practice_stage=='dodge' else JUMP_COST
        if opponents not in ('hunter', 'mixed', 'practice'):
            raise ValueError('opponents must be hunter, mixed or practice')
        if not 2 <= team_size <= 6:
            raise ValueError('team size must be 2..6')
        self.close()
        random.seed(seed)
        rng = random.Random(seed)
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1352, 878))
        self._screen_settings = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT = 1352, 878
        arena = self.arenas.get(str(level)) if self.arenas else level_config.load_level_config(level)
        from level_layout import parse_layout
        from maze.config import MazeComplexity
        grid_size = arena['maze']['grid_size']
        complexity = MazeComplexity[arena['maze']['complexity'].upper()]
        layout = parse_layout(arena['layout'], grid_size) if 'layout' in arena else None
        if layout is not None:
            layout = replace(layout, enemies=(), beacon=None)
        maze = Maze(level, complexity, grid_size,
                    layout=layout, seed=seed, curved=True)
        obstacles = ObstacleWorld(maze, layout.gates) if layout is not None and layout.gates else None
        maze.gate_segments = obstacles.segments() if obstacles else []
        positions = [maze.position_calculator.grid_center_to_screen(c, r)
                     for r in range(1, maze.grid_height-1) for c in range(1, maze.grid_width-1)
                     if not maze.grid[r][c]]
        rng.shuffle(positions)
        positions = [p for p in positions if maze.is_open(p, 11)]
        if opponents == 'practice':
            from learning.adapters.practice_targets import practice_starts
            positions = practice_starts(maze,positions)
        if len(positions) < team_size+1:
            raise ValueError('arena has insufficient clear starts')
        start, angle = positions.pop(), rng.uniform(0, 360)
        scoring = ScoringSystem()
        scoring.power_drain_enabled = False
        handler = CollisionHandler(SilentSound(), scoring, CommandRecorder())
        # Training never generates pickups or changes a real profile.
        handler.drop_pickup = lambda *a, **k: None
        self.world = SimpleNamespace(ship=None, hunter=None, maze=maze, projectiles=[],
                                     roster=EnemyRoster(), scoring=scoring, sound_manager=SilentSound(),
                                     command_recorder=handler.command_recorder, collision_handler=handler,
                                     powerup_crystals=[], jev_beacon_allowed=lambda: False, combat_ruleset='legacy',
                                     _hunter_sees_player=lambda: self.world.ship is not None)
        self.hunter = None
        self.opponent = None
        self.world.additional_targets = []
        if opponents != 'practice' or neural_hunter:
            self.hunter = FrozenHunter(self.opponent_path, self.world, start, angle,
                                       firing_enabled=neural_hunter or SHIPS_FIRE)
            self.opponent = self.world.hunter = self.hunter.ship
        self.player = None
        if opponents == 'mixed':
            from policies.ammo import UnlimitedAmmo
            from learning.adapters.player_pilot import FrozenNeuralPlayer, HunterControlledShip
            valid = [p for p in positions if math.dist(p, start) >= 90]
            if not valid:
                raise ValueError('arena has insufficient separated opponent starts')
            position = valid[0]; positions.remove(position)
            ship = self.world.ship = HunterControlledShip(position, opponent_settings())
            ship.sound_manager = SilentSound(); ship.ammo_policy = UnlimitedAmmo()
            ship.game_started = True; ship.shield_initial_timer = 0
            ship.angle = rng.uniform(0, 360)
            self.player = FrozenNeuralPlayer(ship, self.opponent_path, opponent_settings(), DECISION_FRAMES, firing_enabled=SHIPS_FIRE)
        self.opponents = opponents
        self.aiming_practice = opponents=='practice' and AIMING_PRACTICE
        self.walking_enabled = PRACTICE_WALKING
        self.jumping_enabled = PRACTICE_JUMPING if jumping is None else jumping
        chosen = []
        for i in range(team_size):
            valid = [p for p in positions if all(math.dist(p, target.get_pos()) >= 180
                     for target in (self.world.ship, self.opponent) if target is not None)
                     and all(math.dist(p, q) >= 45 for q in chosen)]
            if not valid:
                raise ValueError('arena has insufficient separated crawler starts')
            # Prefer starts near a surface, while preserving seeded variation.
            from creatures.traits.wallcrawl import contact
            pool = valid[:min(80, len(valid))]
            pool.sort(key=lambda p: contact(maze, p)[3])
            pos = rng.choice(pool[:min(12, len(pool))])
            positions.remove(pos); chosen.append(pos)
            c = creatures.build('wallcrawler', pos, level)
            if self.aiming_practice:
                gun=next(t for t in c.traits if t.NAME=='gun')
                gun.interval_min=gun.interval_max=PRACTICE_FIRE_INTERVAL
            c.agent_id = i
            self.world.roster.add(c)
        self.enc = Encounter(self.world.roster, self.world)
        self.enc.ready()
        self.team = get_team(self.enc)
        self.team.external = True
        self.team._next_id = team_size
        self.level = level
        if opponents == 'practice':
            from learning.adapters.practice_targets import create_targets
            if self.aim_drill:
                from learning.adapters.crawler_curriculum import AIM_TARGET_DISTANCE
                from learning.adapters.practice_targets import plant_drill_crawlers
                plant_drill_crawlers(self,positions)
                self.world.additional_targets = create_targets(self,seed,distance_range=AIM_TARGET_DISTANCE)
                for target in self.world.additional_targets:
                    target.firing_enabled = False
                    if practice_stage == 'precision':
                        target.vx = target.vy = 0.
            elif practice_stage == 'pursuit':
                from learning.adapters.allied_jellyfish import create_pursuers
                self.world.additional_targets = create_pursuers(self,positions,seed,count=self.jelly_count)
                # These are established wall occupants, not newly landed crawlers.
                # Subsequent landings still enforce the normal one-second cooldown.
                for c in self.team.members():c.wall_attach_cooldown=0
            elif practice_stage == 'dodge':
                from learning.adapters.crawler_curriculum import setup_dodge
                self.world.additional_targets = setup_dodge(self,positions,seed)
            else:
                self.world.additional_targets = create_targets(self,seed)
            if self.aiming_practice and not self.walking_enabled:
                for c in self.team.members():c.walk_direction=0
        self.frames = self.hits = self.shots = 0
        self.contributions = Counter()
        self._accepted = set()
        self._accuracy_scored = set()
        self.aim_quality_sum = 0.
        self.voluntary_jumps = 0
        self.walk_reversals = 0
        self.airborne_frames = 0
        self._walk_directions = {}
        self.agent_quality = Counter()
        self.agent_jumps = Counter()
        self.agent_jump_rewards = Counter()
        self.agent_landings = Counter()
        self.completion_reward = 0.
        self.agent_completion_rewards = Counter()
        self.agent_battle_alive = Counter()
        self.agent_battle_survival = Counter()
        self.agent_jelly_kills = Counter()
        self._battle_reward_frame = 0
        self._battle_horizon_awarded = False
        self._pending_landings = set()
        self.agent_reversals = Counter()
        self.agent_hits_taken = Counter()
        self.agent_contact_hits = Counter()
        self._contact_after = {}
        self._received_bullets = set()
        self.enc.on_projectile_damage = self._bullet_damage
        self.world.collision_handler.on_player_projectile_hit = self._hit
        self.obstacles = obstacles
        self.agent_ids = tuple(range(team_size))
        self.level, self.seed, self.team_size = level, seed, team_size
        self.action_trace = []
        return self.snapshot()

    def contact_hit(self, crawler):
        from learning.adapters.allied_jellyfish import CONTACT_DAMAGE,CONTACT_INTERVAL
        if not crawler.active or self.frames < self._contact_after.get(crawler.agent_id,0):return
        self._contact_after[crawler.agent_id] = self.frames+CONTACT_INTERVAL
        self.agent_contact_hits[crawler.agent_id] += 1
        crawler.hit_points -= CONTACT_DAMAGE
        crawler.emit('hit',self.enc)
        if crawler.hit_points <= 0:
            self.enc.kill(crawler)
        else:
            crawler.emit('shoved',self.enc)

    def _bullet_damage(self, creature, shot):
        recipient = getattr(creature, "agent_id", None)
        if recipient in self.agent_ids and shot not in self._received_bullets:
            self._received_bullets.add(shot)
            self.agent_hits_taken[recipient] += 1

    def _hit(self, shot):
        owner = getattr(shot, 'actor_id', None)
        if owner in self.agent_ids and shot not in self._accepted:
            self._accepted.add(shot)
            self.hits += 1
            self.contributions[owner] += 1

    def weaken_ship_shots(self):
        """Only this scenario opts into fractional creature damage from friendly bullets."""
        for shot in self.world.projectiles:
            if not shot.is_enemy:
                shot.creature_damage = SHIP_BULLET_DAMAGE

    def score_shots(self):
        for shot in self.world.projectiles:
            if (shot.active and shot.is_enemy and getattr(shot, 'actor_id', None) in self.agent_ids
                    and shot not in self._accuracy_scored):
                self._accuracy_scored.add(shot)
                quality=shot_quality(shot, [self.world.ship,self.opponent]+self.world.additional_targets, self.world.maze)
                self.aim_quality_sum += quality
                self.agent_quality[shot.actor_id] += quality

    def opponent_hit(self, shot):
        """Consume normal hunter impacts; reward only damage accepted outside immunity.

        Restore health after each collision rather than marking the hunter indestructible,
        so its ordinary damage acceptance and immunity remain meaningful.
        """
        for target in self.world.additional_targets:
            if (target.active and shot.active and shot.is_enemy and getattr(shot,'actor_id',None) in self.agent_ids
                    and shot.check_circle_collision(target.get_pos(),target.radius)):
                shot.active = False
                if target.take_hit(shot):
                    self._hit(shot)
                    if self.practice_stage == 'pursuit' and not target.active:
                        self.agent_jelly_kills[shot.actor_id] += 1
                return True
        hunter = self.opponent
        if hunter is None:
            return False
        accepted = hunter.immunity_remaining <= 0
        hit = self.world.collision_handler.handle_projectile_hunter_collision(shot, hunter)
        if hit:
            hunter.health = hunter.settings.health
            if accepted:
                self._hit(shot)
        return hit

    def commit_actions(self, actions):
        attached = [c for c in self.team.members() if c.wall_state == 'attached']
        bonuses = {c.agent_id:self.jump_bonus(c) for c in attached}
        intentions={i:intention(a) for i,a in actions.items()}
        if getattr(self,'aiming_practice',False):
            intentions={i:replace(intent,move=intent.move if self.walking_enabled else 0,detach=intent.detach if self.jumping_enabled else False) for i,intent in intentions.items()}
        self.team.commit(intentions, self._sites)
        for c in attached:
            if c.wall_state == 'returning' and c.wall_phase == 'launch':
                self.voluntary_jumps += 1
                self.agent_jumps[c.agent_id] += 1
                self._pending_landings.add(c.agent_id)
                if bonuses[c.agent_id]:
                    self.agent_jump_rewards[c.agent_id] += bonuses[c.agent_id]

    def record_landings(self):
        """Credit one completed voluntary hop; damage recovery alone earns nothing."""
        living={c.agent_id:c for c in self.team.members()}
        for agent in tuple(self._pending_landings):
            crawler=living.get(agent)
            if crawler is None or crawler.wall_state=='stunned':
                self._pending_landings.remove(agent)
            elif crawler.wall_state=='attached':
                self.agent_landings[agent]+=1
                self._pending_landings.remove(agent)

    def record_completion(self):
        """One team bonus for clearing an aiming drill with living crawlers."""
        if not self.aim_drill or self.completion_reward or not self.world.additional_targets:
            return
        living=self.team.members()
        if living and not any(target.active for target in self.world.additional_targets):
            self.completion_reward=TRIAL_COMPLETION_REWARD
            self.agent_completion_rewards.update({c.agent_id:TRIAL_COMPLETION_REWARD/len(living) for c in living})

    def record_battle_outcomes(self):
        if self.practice_stage != 'pursuit':
            return
        living = self.team.members()
        elapsed = self.frames - self._battle_reward_frame
        for c in living:
            self.agent_battle_alive[c.agent_id] += BATTLE_ALIVE_RATE * elapsed / 60
        self._battle_reward_frame = self.frames
        if self.battle_success() and not self._battle_horizon_awarded:
            self.agent_battle_survival.update({c.agent_id:BATTLE_SURVIVAL_BONUS for c in living})
            self._battle_horizon_awarded = True

    def battle_events(self):
        battle = self.practice_stage == 'pursuit'
        dead = len(self.agent_ids) - len(self.team.members()) if battle else 0
        return dict(battle_alive_reward=sum(self.agent_battle_alive.values()),
                    battle_survival_bonus=sum(self.agent_battle_survival.values()),
                    battle_kill_reward=BATTLE_KILL_REWARD*sum(self.agent_jelly_kills.values()),
                    battle_death_penalty=-BATTLE_DEATH_COST*dead,
                    battle_success=self.battle_success(),
                    battle_deaths=dead, battle_jelly_kills=sum(self.agent_jelly_kills.values()))

    def jump_bonus(self, crawler):
        """One personal bonus at takeoff, proportional to visible threat proximity."""
        if getattr(self,'practice_stage',None)!='pursuit':return 0.
        from creatures.traits.rooted import wall_between
        gaps=[max(0.,math.dist(crawler.get_pos(),target.get_pos())-crawler.radius-target.radius)
              for target in self.world.additional_targets
              if target.active and getattr(target,'allegiance',None)=='ally'
              and not wall_between(crawler.get_pos(),target.get_pos(),self.world.maze)]
        return JUMP_PROXIMITY_REWARD*max(0.,1-min(gaps,default=JUMP_PROXIMITY_RANGE)/JUMP_PROXIMITY_RANGE)

    def record_walking(self, previous):
        for c in self.team.members():
            old = previous.get(c.agent_id)
            if c.wall_state != 'attached' or old is None:
                self._walk_directions.pop(c.agent_id,None)
                continue
            intent = getattr(c,'wall_intent',None)
            direction = intent.move if intent is not None else c.walk_direction
            if not direction or math.dist(old,c.get_pos()) < 1e-4:
                continue
            direction = 1 if direction>0 else -1
            last = self._walk_directions.get(c.agent_id)
            if last is not None and last != direction:
                self.walk_reversals += 1
                self.agent_reversals[c.agent_id] += 1
            self._walk_directions[c.agent_id] = direction

    def agent_returns(self):
        from learning.adapters.allied_jellyfish import CONTACT_COST
        shots={c.agent_id:c.shots_fired for c in self.world.roster.all()}
        alive = {c.agent_id for c in self.team.members()}
        battle = self.practice_stage == 'pursuit'
        return {i:(self.contributions[i]-SHOT_COST*shots.get(i,0)
                   +ACCURACY_WEIGHT*self.agent_quality[i]-self.jump_cost*self.agent_jumps[i]
                   +self.agent_jump_rewards[i]
                   +getattr(self,'landing_reward',LANDING_REWARD)*self.agent_landings[i]
                   +getattr(self,'agent_completion_rewards',{}).get(i,0.)
                   +(self.agent_battle_alive[i]+self.agent_battle_survival[i]
                     +BATTLE_KILL_REWARD*self.agent_jelly_kills[i]
                     -BATTLE_DEATH_COST*(i not in alive) if battle else 0.)
                   -WALK_REVERSAL_COST*self.agent_reversals[i]
                   -BULLET_HIT_COST*self.agent_hits_taken[i]
                   -CONTACT_COST*self.agent_contact_hits[i]) for i in self.agent_ids}

    def snapshot(self):
        batch = {c.agent_id: observe(self.team, c, self.muted) for c in self.team.members()}
        if self.aiming_practice:
            for _,masks,_ in batch.values():
                if not self.walking_enabled:
                    masks['move']=np.array([False,True,False])
                if not self.jumping_enabled:
                    masks['detach']=np.array([True,False])
        self._sites = {i: v[2] for i, v in batch.items()}
        return Snapshot({i: v[0] for i, v in batch.items()}, {i: v[1] for i, v in batch.items()}, critic(self.team),
                        {i:critic(self.team,i) for i in batch} if self.aiming_practice else None)

    def battle_success(self):
        return (self.practice_stage == 'pursuit' and bool(self.team.members())
                and (self.frames >= self.horizon*60
                     or (self.opponent is None and bool(self.world.additional_targets)
                         and not any(t.active for t in self.world.additional_targets))))

    def trial_complete(self):
        return (self.battle_success() or not bool(self.world.roster.alive()) or
                (self.opponents=='practice' and self.opponent is None
                 and not any(t.active for t in self.world.additional_targets)))

    def step(self, actions):
        if self.frames >= self.horizon*60 or self.trial_complete():
            raise RuntimeError('step after episode ended')
        before_returns = self.agent_returns() if self.aiming_practice else None
        before_hits, before_shots = self.hits, self.shots
        before_quality = self.aim_quality_sum
        before_jumps = self.voluntary_jumps
        before_jump_rewards = sum(self.agent_jump_rewards.values())
        before_landings = sum(self.agent_landings.values())
        before_completion = self.completion_reward
        before_reversals = self.walk_reversals
        before_received = sum(self.agent_hits_taken.values())
        before_contacts = sum(self.agent_contact_hits.values())
        from learning.adapters.allied_jellyfish import CONTACT_COST
        if not self.scripted:
            self.commit_actions(actions)
        self.action_trace.append({str(i): list(a) for i, a in actions.items()})
        for _ in range(DECISION_FRAMES):
            if self.hunter is not None:
                self.hunter.frame(self.world)
            for target in self.world.additional_targets:
                target.step(self.world.maze)
                bullet=target.fire(self.world.roster.alive(),self.world.maze)
                if bullet is not None:self.world.projectiles.append(bullet)
            if self.player is not None:
                self.player.frame(self.world)
            self.weaken_ship_shots()
            walking = {c.agent_id:c.get_pos() for c in self.team.members() if c.wall_state=='attached'}
            self.airborne_frames += sum(c.wall_state != "attached" for c in self.team.members())
            self.enc.step(1)
            for target in self.world.additional_targets:
                on_contacts = getattr(target,"on_contacts",None)
                if on_contacts is not None:on_contacts()
            self.record_walking(walking)
            self.score_shots()
            self.world.collision_handler.handle_hunter_contacts(self.opponent, self.world.ship, self.world.roster.alive())
            if self.opponent is not None:
                self.opponent.health = self.opponent.settings.health
            self.world.roster.update_dying(1)
            if self.obstacles:
                self.obstacles.step(1/60, [target for target in (self.world.ship,self.opponent) if target is not None]+self.world.roster.alive())
                self.world.maze.gate_segments = self.obstacles.segments()
            live = []
            for shot in self.world.projectiles:
                shot.update(1)
                if not shot.active:
                    continue
                if shot.check_wall_collision(self.world.maze.walls, self.world.maze.spatial_grid):
                    shot.active = False
                elif self.obstacles and self.obstacles.bullet_hit(shot):
                    shot.active = False
                elif shot.is_enemy:
                    if (self.world.ship is not None and self.world.collision_handler.handle_projectile_ship_collision(
                            shot, self.world.ship, self.world.scoring)) or self.opponent_hit(shot):
                        shot.active = False
                else:
                    if self.enc.shoot(shot):
                        shot.active = False
                if shot.active:
                    live.append(shot)
            self.world.projectiles = live
            self.record_landings()
            self.record_completion()
            self.frames += 1
            self.record_battle_outcomes()
            if self.render_frames is not None:
                self.render_frames(self)
            if self.trial_complete() or self.frames >= self.horizon*60:
                break
        self.shots = sum(c.shots_fired for c in self.world.roster.all())
        self.team.advance()
        reward = (self.hits-before_hits-SHOT_COST*(self.shots-before_shots)
                  + ACCURACY_WEIGHT*(self.aim_quality_sum-before_quality)
                  - self.jump_cost*(self.voluntary_jumps-before_jumps)
                  + sum(self.agent_jump_rewards.values())-before_jump_rewards
                  + self.landing_reward*(sum(self.agent_landings.values())-before_landings)
                  + self.completion_reward-before_completion
                  - WALK_REVERSAL_COST*(self.walk_reversals-before_reversals)
                  - BULLET_HIT_COST*(sum(self.agent_hits_taken.values())-before_received)
                  - CONTACT_COST*(sum(self.agent_contact_hits.values())-before_contacts))
        individual = ({i:value-before_returns[i] for i,value in self.agent_returns().items()}
                      if before_returns is not None else None)
        if individual is not None:
            reward = sum(individual.values())
        return Transition(self.snapshot(), reward, self.trial_complete(),
                          self.frames >= self.horizon*60 and not self.trial_complete(),
                          {**self.battle_events(), 'hits': self.hits, 'shots': self.shots, 'aim_quality_sum':self.aim_quality_sum, 'voluntary_jumps':self.voluntary_jumps, 'walk_reversals':self.walk_reversals, 'seconds': self.frames/60,
                           'bullet_hits_taken':sum(self.agent_hits_taken.values()),
                           'agent_hits_taken':dict(self.agent_hits_taken),
                           'contact_hits_taken':sum(self.agent_contact_hits.values()), 'agent_contact_hits':dict(self.agent_contact_hits),
                           'airborne_frames':self.airborne_frames, 'jump_cost':self.jump_cost,
                           'jump_proximity_reward':sum(self.agent_jump_rewards.values()),
                           'agent_jump_rewards':dict(self.agent_jump_rewards),
                           'successful_landings':sum(self.agent_landings.values()),
                           'landing_reward':self.landing_reward,'trial_completion_reward':self.completion_reward,
                           'agent_completion_rewards':dict(self.agent_completion_rewards),
                           'agent_landings':dict(self.agent_landings),
                           'reposition_targets':sum(getattr(t,'reposition_target',False) for t in self.world.additional_targets),
                           'target_shots':sum(t.shots_fired for t in self.world.additional_targets),
                           'targets_remaining':sum(t.active for t in self.world.additional_targets),
                           'targets_cleared':self.opponents=='practice' and self.opponent is None and not any(t.active for t in self.world.additional_targets),
                           'alive': len(self.world.roster.alive()), 'contributions': dict(self.contributions), 'agent_returns':self.agent_returns()}, agent_rewards=individual)

    def close(self):
        if hasattr(self,'_screen_settings'):
            import config
            config.SCREEN_WIDTH,config.SCREEN_HEIGHT = self._screen_settings
            del self._screen_settings
        if self.world is not None:
            if self.hunter is not None:
                self.hunter.close()
            if self.player is not None:
                self.player.close()
            for target in self.world.additional_targets:
                close = getattr(target,"close",None)
                if close is not None:close()
            self.enc.close()
            self.world = None


def environment(**kwargs):
    return CrawlerEnvironment(**kwargs)

# Scenario policy belongs to this adapter, not to the optimiser or run manager.
INITIAL_STAGE = 4
from learning.adapters import battle_curriculum
INITIAL_CURRICULUM = battle_curriculum.INITIAL_STATE
advance_curriculum = battle_curriculum.advance
IMITATION_BALANCED = True
IMITATION_EPOCHS = 64
IMITATION_REHEARSAL_WEIGHT = .1
IMITATION_REHEARSAL_HEADS = ('move','aim','detach','landing')
IMITATION_FOCUS_HEAD = 'landing'
IMITATION_HEADS = ('move','aim','fire','detach','landing')


def metadata(args):
    import dataclasses
    import config
    import enemy_kinds
    import level_config
    from creatures.traits.wallcrawl import LAUNCH_FRAMES
    from learning.adapters.practice_targets import (TARGET_COUNT,TARGET_RADIUS,TARGET_SPEED_MIN,TARGET_SPEED_MAX,
        TARGET_BULLET_SPEED,TARGET_FIRE_INTERVAL,TARGET_BULLET_LIFETIME,TARGET_BULLET_DAMAGE,TARGET_FIRE_RANGE)
    from learning.adapters.crawler_curriculum import DODGE_TARGET_COUNT,DODGE_BURST_SIZE,DODGE_BURST_SPACING,DODGE_FIRE_INTERVAL,DODGE_JUMP_COST,SHOOTING_SHARE,AIM_WARMUP_ITERATIONS,AIM_TARGET_DISTANCE,AIM_TEAM_SIZE
    from learning.adapters.allied_jellyfish import PURSUER_COUNT,PURSUER_SPEED_MIN,PURSUER_SPEED_MAX,PURSUER_HEALTH,PURSUER_START_DISTANCE,CONTACT_DAMAGE,CONTACT_INTERVAL,CONTACT_COST
    from learning.adapters.crawler_jump_teacher import CONTACT_LEAD_FRAMES,PREDICTION_FRAMES,CLEARANCE_MARGIN,PREPARATION_HEADINGS,POST_LANDING_FRAMES
    return dict(jump_teacher={'version':4,'lead_frames':CONTACT_LEAD_FRAMES,'prediction_frames':PREDICTION_FRAMES,
                              'motion_model':'production_wall_mechanics','post_landing_clearance_frames':POST_LANDING_FRAMES,
                              'future_decisions':'scripted_walk_or_airborne_stop_every_six_frames',
                              'pursuer_speed_model':'fastest_visible_velocity',
                              'preparation_headings_degrees':list(PREPARATION_HEADINGS),
                              'preparation':'stop_and_aim_before_launch_including_during_cooldown',
                              'clearance_margin':CLEARANCE_MARGIN,'heads':list(IMITATION_HEADS),'local_information_only':True,
                              'balanced_dataset_loss':IMITATION_BALANCED,'epochs':IMITATION_EPOCHS,
                              'rehearsal_weight':IMITATION_REHEARSAL_WEIGHT,'rehearsal_heads':list(IMITATION_REHEARSAL_HEADS),
                              'focus_head':IMITATION_FOCUS_HEAD},
                pursuers={'kind':'aggressive','allegiance':'ally','count':PURSUER_COUNT,'speed_range':[PURSUER_SPEED_MIN,PURSUER_SPEED_MAX],
                          'speed_distribution':'uniform_per_creature_fixed_per_trial','speed_seed_offset':43000,'health':PURSUER_HEALTH,'minimum_start_distance':PURSUER_START_DISTANCE,'start_approach':'prefer_30_to_45_degrees_off_normal','initial_attachment':'settled_cooldown_zero',
                          'contact_damage':CONTACT_DAMAGE,'contact_interval_frames':CONTACT_INTERVAL,
                          'creature':dataclasses.asdict(enemy_kinds.kind('aggressive'))},
                battle_curriculum=battle_curriculum.metadata(),
                curriculum={'name':'continuous_aim_focus','shooting_share':SHOOTING_SHARE,'team_size':INITIAL_STAGE,
                           'warmup_iterations':AIM_WARMUP_ITERATIONS,
                           'warmup_mix':{'precision':.5,'tracking':.25,'pursuit':.25},
                           'later_mix':{'precision':.25,'tracking':.5,'pursuit':.25},
                           'aim_drills':{'team_size':AIM_TEAM_SIZE,'crawler_motion':True,'voluntary_jumps':True,'target_fire':False,'hunter':False,
                                         'target_outward_depth_range':list(AIM_TARGET_DISTANCE)},
                           'selection':'aim_validation_accuracy_times_hits_per_minute',
                           'dodge_targets':DODGE_TARGET_COUNT,'burst_size':DODGE_BURST_SIZE,'burst_spacing_frames':DODGE_BURST_SPACING,
                           'burst_interval_frames':DODGE_FIRE_INTERVAL,'dodge_jump_cost':DODGE_JUMP_COST,
                           'initial_fire_delay_frames':[60,120],'promotion':'manual_after_paired_jump_evaluation'},
                task=SPEC.task, scenario_version=56, policy_spec=SPEC.metadata(),
                aim_actuator={'distribution':'tanh_gaussian','recorded_action':'pre_squash_activation',
                              'max_degrees_per_second':180,'log_std_bounds':[-5.,1.]},
                communication={'enabled':True,'symbols':8,'silence_symbol':0,
                               'delivery_delay_decisions':1,'range_pixels':300,'through_rock':True},
                practice_hunter={'enabled':True,'training_stages':['pursuit'],'controller':'frozen_neural',
                                 'firing_enabled':True,'bullet_damage':SHIP_BULLET_DAMAGE,
                                 'health_restored_after_accepted_hits':True},
                crawler_starts={'clear_depth_pixels':180,'clear_width_pixels':120,
                                'clearance_radius_pixels':11,'enforced_after_reposition':True},
                trial_completion={'stages':['precision','tracking'],'team_bonus':TRIAL_COMPLETION_REWARD,
                                  'distribution':'split_equally_among_living_crawlers','requires':'all_targets_cleared',
                                  'once_per_trial':True},
                firing_recoil={'enabled':True,'mass':'radius_squared_times_bullet_strength',
                               'bullet_velocity':'inherits_launch_velocity_and_mount_spin',
                               'supported':'absorbed','angular_impulse':'off_centre_firing_line'},
                airborne_firing={'enabled':True,'stunned':False,'aim_reference':'world_stabilised'},
                battle_rewards={'alive_per_second':BATTLE_ALIVE_RATE,'survival_bonus':BATTLE_SURVIVAL_BONUS,
                                'death_cost':BATTLE_DEATH_COST,'jelly_kill':BATTLE_KILL_REWARD,
                                'success':'alive_at_horizon_or_hunter_free_clear','terminal_success':True,'hunter_invulnerable':True},
                landing_reward={'battle':0.,'aim_drills':0.,'scope':'individual','award':'once_per_completed_voluntary_hop',
                                'damage_interruption_cancels':True},
                jump_proximity={'range_pixels':JUMP_PROXIMITY_RANGE,'distance':'body_clearance','pursuit_jump_cost':0.,
                                'visible_only':True,'stage':'pursuit','formula':'max(0, 1 - clearance / range)',
                                'scope':'individual','award':'once_per_actual_voluntary_launch'},
                opponent_sha256=hashlib.sha256(Path(args.opponent).read_bytes()).hexdigest(),
                creatures={'wallcrawler': dataclasses.asdict(enemy_kinds.kind('wallcrawler'))},
                practice_targets={'count':TARGET_COUNT,'radius':TARGET_RADIUS,'speed_range':[TARGET_SPEED_MIN,TARGET_SPEED_MAX],'dies_on_hit':True,
                                  'return_fire':{'speed':TARGET_BULLET_SPEED,'interval_frames':TARGET_FIRE_INTERVAL,
                                                 'lifetime_frames':TARGET_BULLET_LIFETIME,'damage':TARGET_BULLET_DAMAGE,
                                                 'range':TARGET_FIRE_RANGE,'initial_delay_frames':[TARGET_FIRE_INTERVAL//2,TARGET_FIRE_INTERVAL]}},
                opponent_body='practice_targets', aiming_practice=AIMING_PRACTICE, practice_walking=PRACTICE_WALKING, practice_jumping=PRACTICE_JUMPING, practice_fire_interval_frames=PRACTICE_FIRE_INTERVAL, reward_scope='individual' if AIMING_PRACTICE else 'team',
                critic_context='focal_agent_first_v1' if AIMING_PRACTICE else 'team', ship_bullet_damage=SHIP_BULLET_DAMAGE, ships_fire=SHIPS_FIRE, player_controller='frozen_neural_hunter_controls_v1',
                player_physics=dataclasses.asdict(config.SETTINGS.ship),
                opponent_settings=dataclasses.asdict(opponent_settings()),
                hunter_physics=dataclasses.asdict(config.SETTINGS.hunterShip),
                physics={name:dataclasses.asdict(getattr(config.SETTINGS,name))
                         for name in ('projectile','momentum','maze','obstacles')},
                arenas={str(n):level_config.load_level_config(n) for n in TRAIN_LEVELS+HOLDOUT_LEVELS},
                decision_frames=DECISION_FRAMES, radio_range=300, landing_range=300,
                landing_half_angle_degrees=45, flight_turn_degrees_per_second=180, ballistic_flight=True, peer_collision="swept_mass_based_impulse_v1",
                bullet_impulse="mass_ratio_times_damage_with_attached_release_v2", magnetic_alignment=True, planned_launch_spin=True, launch_frames=LAUNCH_FRAMES,
                rewards={'successful_landing':LANDING_REWARD,'aim_drill_landing':0.,'trial_completion':TRIAL_COMPLETION_REWARD,'jump_proximity':JUMP_PROXIMITY_REWARD,'contact_hit':-CONTACT_COST,'bullet_hit':-BULLET_HIT_COST,'team_hit':1.,'shot':-SHOT_COST,'predicted_shot_accuracy':ACCURACY_WEIGHT,'voluntary_jump':-JUMP_COST,'walk_reversal':-WALK_REVERSAL_COST},
                shot_accuracy_version=1, horizon=args.horizon,
                train_levels=list(TRAIN_LEVELS),holdout_levels=list(HOLDOUT_LEVELS),observation_version=SPEC.version)


def training_cases(iteration, count, stage, bootstrap=False, curriculum=None):
    from learning.adapters.crawler_curriculum import AIM_WARMUP_ITERATIONS, AIM_TEAM_SIZE
    battle = battle_curriculum.STAGES[(curriculum or INITIAL_CURRICULUM)['stage']]
    stationary_slots = 6 if iteration < AIM_WARMUP_ITERATIONS else 3
    cases = []
    for i in range(count):
        index = iteration*count+i
        slot = index % 12
        practice_stage = 'pursuit' if slot >= 9 else 'precision' if slot < stationary_slots else 'tracking'
        cases.append(dict(level=TRAIN_LEVELS[index%len(TRAIN_LEVELS)],
                          seed=100+i if bootstrap else 300+index%100,
                          team_size=stage if practice_stage=='pursuit' else AIM_TEAM_SIZE, opponents='practice',
                          neural_hunter=practice_stage=='pursuit' and battle['neural_hunter'],
                          **({'jelly_count':battle['jelly_count']} if practice_stage=='pursuit' else {}),
                          practice_stage=practice_stage))
    return cases


def validation_cases():
    from learning.adapters.crawler_curriculum import AIM_TEAM_SIZE
    return [dict(level=n,seed=s,team_size=AIM_TEAM_SIZE,opponents='practice',
                 practice_stage=practice_stage,neural_hunter=False)
            for n,s in ((13,800),(17,801)) for practice_stage in ('precision','tracking')]


def evaluation_cases():
    return [dict(level=n,seed=s,team_size=k,opponents='practice',
                 practice_stage=practice_stage,neural_hunter=practice_stage=='pursuit')
            for n in HOLDOUT_LEVELS for s in (1000,1001) for k in (2,4,6)
            for practice_stage in ('precision','tracking','pursuit')]


def promote(stage, summary):
    # Hold the requested team size until another explicit curriculum change.
    return stage


def selection_score(summary):
    if summary.get('battle_episodes',0)>0 and summary['battle_episodes']==summary['episodes']:
        return summary['pursuit_mean_return']
    if summary.get('aim_drill_episodes',0)>0 and summary['aim_drill_episodes']==summary['episodes']:
        return summary['accuracy']*summary['hits_per_minute']
    from learning.adapters.allied_jellyfish import CONTACT_COST
    return summary['hits_per_minute']+summary.get('jump_reward_per_minute',0.)+LANDING_REWARD*summary.get('landings_per_minute',0.)-BULLET_HIT_COST*summary.get('bullet_hits_received_per_minute',0.)-CONTACT_COST*summary.get('contact_hits_received_per_minute',0.)


def metrics(rows):
    seconds=sum(r['seconds'] for r in rows)
    hits,shots=sum(r['hits'] for r in rows),sum(r['shots'] for r in rows)
    summary = dict(hits_per_minute=hits*60/max(seconds,1e-9),
                hit_probability=sum(r['hits']>0 for r in rows)/max(1,len(rows)),accuracy=hits/max(1,shots),
                survival=float(np.mean([r['alive']/r['team_size'] for r in rows])),
                hits_per_crawler=float(np.mean([r['hits']/r['team_size'] for r in rows])),
                hits=hits,shots=shots,episodes=len(rows),
                battle_trials=sum(r.get('practice_stage')=='pursuit' for r in rows),
                battle_survivors=sum(r['alive'] for r in rows if r.get('practice_stage')=='pursuit'),
                battle_crawlers=sum(r['team_size'] for r in rows if r.get('practice_stage')=='pursuit'),
                battle_successes=sum(bool(r.get('battle_success')) for r in rows if r.get('practice_stage')=='pursuit'),
                battle_episodes=sum(r.get('practice_stage')=='pursuit' for r in rows),
                aim_drill_episodes=sum(r.get('practice_stage') in ('precision','tracking') for r in rows),
                mean_aim_quality=sum(r.get('aim_quality_sum',0.) for r in rows)/max(1,shots),
                jumps_per_episode=sum(r.get('voluntary_jumps',0) for r in rows)/max(1,len(rows)),
                jump_reward_per_minute=sum(r.get('jump_proximity_reward',0.) for r in rows)*60/max(seconds,1e-9),
                landings_per_minute=sum(r.get('successful_landings',0) for r in rows)*60/max(seconds,1e-9),
                contact_hits_received_per_minute=sum(r.get('contact_hits_taken',0) for r in rows)*60/max(seconds,1e-9),
                contact_hits_taken_per_episode=sum(r.get('contact_hits_taken',0) for r in rows)/max(1,len(rows)),
                airborne_fraction=sum(r.get('airborne_frames',0) for r in rows)/max(1,sum(r['seconds']*60*r['team_size'] for r in rows)),
                bullet_hits_received_per_minute=sum(r.get('bullet_hits_taken',0) for r in rows)*60/max(seconds,1e-9),
                reposition_targets_per_episode=sum(r.get('reposition_targets',0) for r in rows)/max(1,len(rows)),
                bullet_hits_taken_per_episode=sum(r.get('bullet_hits_taken',0) for r in rows)/max(1,len(rows)),
                reversals_per_episode=sum(r.get('walk_reversals',0) for r in rows)/max(1,len(rows)),
                target_clear_rate=sum(bool(r.get('targets_cleared',False)) for r in rows)/max(1,len(rows)))

    for stage in ('precision','tracking','pursuit'):
        subset = [row for row in rows if row.get('practice_stage')==stage]
        stage_hits = sum(row['hits'] for row in subset)
        stage_shots = sum(row['shots'] for row in subset)
        stage_seconds = sum(row['seconds'] for row in subset)
        if subset:
            summary[stage+'_survival'] = float(np.mean([r['alive']/r['team_size'] for r in subset]))
            summary[stage+'_mean_return'] = float(np.mean([r.get('return',sum(r.get('agent_returns',{}).values())) for r in subset]))
            summary[stage+'_accuracy'] = stage_hits/max(1,stage_shots)
            summary[stage+'_hits_per_minute'] = stage_hits*60/max(stage_seconds,1e-9)
    return summary


def compare(a,b):
    values=np.array([x['hits']-y['hits'] for x,y in zip(a['episodes'],b['episodes'])],float)
    samples=np.random.default_rng(0).choice(values,(2000,len(values)),replace=True).mean(axis=1)
    return dict(mean_extra_hits=float(values.mean()),lower_95=float(np.quantile(samples,.025)),
                upper_95=float(np.quantile(samples,.975)))


def compare_jumping(enabled, disabled):
    """Matched seeded encounters; a useful jump reduces hits received without ruining shooting."""
    a,b=enabled['episodes'],disabled['episodes']
    avoided=np.asarray([(y.get('bullet_hits_taken',0)+y.get('contact_hits_taken',0))-(x.get('bullet_hits_taken',0)+x.get('contact_hits_taken',0)) for x,y in zip(a,b)],float)
    if not len(avoided):raise ValueError('no paired jump evaluation episodes')
    samples=np.random.default_rng(0).choice(avoided,(2000,len(avoided)),replace=True).mean(axis=1)
    lower=float(np.quantile(samples,.025))
    shots_retained=sum(x['hits'] for x in a)/max(1,sum(y['hits'] for y in b))
    supports_progression=bool(lower>0 and shots_retained>=.9 and enabled['summary']['survival']>=disabled['summary']['survival'])
    return dict(supports_progression=supports_progression, shooting_hit_retention=shots_retained,
                mean_hits_avoided=float(avoided.mean()),lower_95=lower,
                upper_95=float(np.quantile(samples,.975)),shooting_effect=compare(enabled,disabled),
                enabled=enabled['summary'],disabled=disabled['summary'])
