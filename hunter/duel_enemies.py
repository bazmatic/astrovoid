"""The enemies that make the pilot duel messier: a random handful of the game's ordinary enemy types.

They run on the game's own enemy code (movement, shooting, death), so they behave as they do in a level. They go after
whichever hunter is nearest. Replay squids, bosses, eggs, anemones and flighthouses are left out: the squids replay the
player's earlier run (a duel has none) and the rest have mechanics that need a player.
"""
import math
import random

import config
from game_handlers.collision_handler import CollisionHandler
from game_handlers.enemy_updater import EnemyUpdater
from game_handlers.enemy_roster import EnemyRoster
from game_handlers.spawn_manager import SpawnManager
from entities.command_recorder import CommandRecorder
from level_rules import EnemyCounts
from scoring.system import ScoringSystem

DUEL_ENEMY_LEVEL = 13               # the level whose enemy strength the duel's enemies use
BASIC_RANGE = (2, 4)                # roaming enemies per duel
FLOCKER_RANGE = (1, 3)              # flocking enemies per duel
KEEP_CLEAR_OF_HUNTERS = 300.0       # pixels: nothing starts on top of a hunter


class _Target:
    """A hunter standing in for the player where enemy code expects a ship.

    Enemies read its position and whether it is alive. Contact damage to hunters is handled separately, so it reports
    its shield up and never collides here.
    """

    def __init__(self, hunter):
        self._hunter = hunter

    def __getattr__(self, name):
        return getattr(self._hunter, name)

    def is_shield_active(self):
        return True

    def check_circle_collision(self, *args, **kwargs):
        return False


class DuelEnemies:
    def __init__(self, maze, sound_manager):
        self.maze, self.sound_manager = maze, sound_manager
        self.roster = EnemyRoster()
        self.spawner = SpawnManager(self.roster)
        self.updater = EnemyUpdater()
        self.scoring = ScoringSystem()              # the enemy code reports to one; it is thrown away with the duel
        self.recorder = CommandRecorder()
        self.collisions = CollisionHandler(sound_manager, self.scoring, self.recorder)
        self.bullets = []                           # shots the enemies have fired

    def spawn(self, hunter_positions, rng=None):
        """A random handful of enemies on open ground, well clear of both hunters."""
        rng = rng or random.Random()
        basic, flockers = rng.randint(*BASIC_RANGE), rng.randint(*FLOCKER_RANGE)
        patrol = basic // 2
        counts = EnemyCounts(total=basic, static=0, patrol=patrol, aggressive=basic - patrol, replay=0,
                             flocker=flockers, flighthouse=0, egg=0, anemone=0)
        wanted = (basic + flockers) * 3 + 5
        positions = [p for p in self.maze.get_valid_spawn_positions(wanted, start_clearance=0)
                     if all(math.dist(p, h) >= KEEP_CLEAR_OF_HUNTERS for h in hunter_positions)]
        rng.shuffle(positions)
        self.spawner.spawn_all_enemies(DUEL_ENEMY_LEVEL, positions, self.recorder, counts, 0, 0)

    def active(self):
        return self.roster.alive()

    def update(self, dt, hunters):
        """Move and fire every enemy, then let any that touch a hunter hurt it."""
        first, second = hunters
        roster = self.roster
        target = _Target(first)
        self.updater.update_enemies(roster.of_kind('static', 'patrol', 'aggressive'), dt, None, self.maze, target, self.scoring, self.bullets,
                                    hunter=second)
        self.updater.update_flockers(roster.of_kind('flocker'), dt, None, self.maze, target, self.scoring, self.bullets,
                                     self.sound_manager, hunter=second)
        roster.update_dying(dt)
        for hunter in hunters:
            self.collisions.handle_hunter_contacts(hunter, None, self.active())

    def shot_hits(self, shot):
        """Whether a hunter's shot struck an enemy (it is then spent). The enemy code only lets friendly shots hit."""
        was_enemy, shot.is_enemy = shot.is_enemy, False
        try:
            return self.collisions.shoot_into(shot, self.roster, [], maze=self.maze)
        finally:
            shot.is_enemy = was_enemy

    def move_bullets(self, dt, hunters):
        """Fly the enemies' shots; one that reaches a hunter hurts it."""
        alive = []
        for bullet in self.bullets:
            bullet.update(dt)
            if bullet.active:
                bullet.check_wall_collision(self.maze.walls, self.maze.spatial_grid)
            for hunter in hunters:
                if bullet.active and self.collisions.handle_projectile_hunter_collision(bullet, hunter):
                    break
            if bullet.active:
                alive.append(bullet)
        self.bullets = alive
