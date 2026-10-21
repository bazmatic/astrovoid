"""The Encounter: what happens to the creatures on a level in one frame.

It runs every live creature's traits in roster order, then each kind's crowd traits, and offers each friendly shot to
the creatures in roster order. It also gives traits what they act on, read live from its world (a Game, or the duel's
stand-in): the ship, the hunter, the maze, the scoring, the shots, the pickups and the collision handler.

The enemy hunters are not Creatures: a shot no creature takes goes on to them.
"""
from typing import Dict, List, Optional, Tuple

from creatures.creature import Creature
from game_handlers.combat_targets import nearest_friendly_pos


class Encounter:

    def __init__(self, roster, world):
        self.roster = roster
        self.world = world

    @property
    def ship(self):
        return self.world.ship

    @property
    def hunter(self):
        return self.world.hunter

    @property
    def maze(self):
        return self.world.maze

    @property
    def scoring(self):
        return self.world.scoring

    @property
    def command_recorder(self):
        return self.world.command_recorder

    def creatures(self) -> List[Creature]:
        """Every creature on the roster, alive or not, in roster order."""
        return [enemy for enemy in self.roster.all() if isinstance(enemy, Creature)]

    def step(self, dt: float) -> None:
        """One frame: spawn hooks for newcomers, every live creature's traits and Body, then the crowd traits (once
        for each crowd: by default a kind, or the crowd a trait names)."""
        creatures = self.creatures()
        for creature in creatures:
            self._spawn(creature)
        crowds: Dict[Tuple[str, str], Tuple[object, List[Creature]]] = {}
        for creature in creatures:
            if not creature.active:
                continue
            for trait in creature.traits:
                trait.on_frame(creature, self, dt)
                if not creature.active:
                    break
            else:
                creature.body.update(creature, dt, self.target_for(creature))
                for trait in creature.traits:
                    if trait.CROWD:
                        crowds.setdefault((trait.NAME, trait.crowd(creature)), (trait, []))[1].append(creature)
        for trait, members in crowds.values():
            live = [creature for creature in members if creature.active]
            if live:
                trait.on_crowd(live, self, dt)

    def ready(self) -> None:
        """Set up every creature on the roster that is not yet (its spawn hooks), without a frame passing."""
        for creature in self.creatures():
            self._spawn(creature)

    def _spawn(self, creature) -> None:
        """Run a newcomer's spawn hooks, once."""
        if not creature.has_spawned and creature.active:
            creature.has_spawned = True
            for trait in creature.traits:
                trait.on_spawn(creature, self)

    def shoot(self, projectile) -> bool:
        """Offer a friendly shot to each live enemy creature in roster order; the first it reaches takes it, and the
        shot is spent (True). A shot no creature takes goes on to the enemy hunters."""
        if not projectile.is_enemy and projectile.active:
            for creature in self.creatures():
                if (creature.active and creature.allegiance == 'enemy'
                        and projectile.check_circle_collision(creature.get_pos(), creature.radius)):
                    self._spawn(creature)   # shot before its first frame
                    for trait in creature.traits:
                        trait.on_shot(creature, projectile, self)
                        if not creature.active:
                            break
                    return True
        return self.world.collision_handler.shoot_into(projectile, self.roster)

    def target_for(self, creature) -> Optional[Tuple[float, float]]:
        """Where the creature's target is: the nearest friend, or None."""
        return nearest_friendly_pos(creature, self.world.ship, self.world.hunter)

    def kill(self, creature, shot=None) -> None:
        """The creature dies; a shot that killed it counts as a kill for whoever fired it."""
        if not creature.active:
            return
        creature.killed_by = shot.source if shot is not None else 'enemy'
        creature.die()
        self.world.sound_manager.play_enemy_destroy()
        if shot is not None:
            self.world.collision_handler.record_kill(shot, creature)
        for trait in creature.traits:
            trait.on_death(creature, self)

    def drop_pickup(self, pos) -> None:
        """Roll for what a dead creature leaves behind."""
        self.world.collision_handler.drop_pickup(pos, self.world.powerup_crystals, self.world.jev_beacon_allowed())

    def spawn(self, kind: str, pos, level: int):
        """Put a new enemy of this kind on the roster, and return it. A Creature spawned during a frame first acts on
        the next one (or when a shot reaches it)."""
        from game_handlers.spawn_manager import make_enemy
        enemy = make_enemy(kind, pos, level, self.world.command_recorder)
        self.roster.add(enemy)
        return enemy

    def explode(self, blast) -> None:
        """Light a blast; the game sets it off when its fuse has burnt."""
        self.world.collision_handler.explosions.trigger(blast)

    def add_shot(self, projectile) -> None:
        self.world.projectiles.append(projectile)
