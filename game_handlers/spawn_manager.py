"""Enemy spawning management.

This module handles all enemy spawning logic, eliminating duplication
in the start_level() method.
"""

from typing import List, Tuple, TYPE_CHECKING
import level_rules
if TYPE_CHECKING:
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.split_boss import SplitBoss
    from entities.command_recorder import CommandRecorder
    from game_handlers.entity_manager import EntityManager


class SpawnManager:
    """Manages enemy spawning for levels."""
    
    def __init__(self, entity_manager: 'EntityManager'):
        """Initialize spawn manager.
        
        Args:
            entity_manager: Entity manager to add spawned enemies to.
        """
        self.entity_manager = entity_manager
    
    def spawn_all_enemies(
        self,
        level: int,
        spawn_positions: List[Tuple[float, float]],
        command_recorder: 'CommandRecorder'
    ) -> None:
        """Spawn all enemies for a level.
        
        Args:
            level: Current level number.
            spawn_positions: Available spawn positions.
            command_recorder: Command recorder for replay enemies.
        """
        from entities.enemy import create_enemies
        from entities.replay_enemy_ship import ReplayEnemyShip
        from entities.split_boss import SplitBoss
        
        # Get enemy counts
        enemy_counts = level_rules.get_enemy_counts(level)
        split_boss_count = level_rules.get_split_boss_count(level)
        
        # Clear existing enemies
        self.entity_manager.clear_all()
        
        # Create regular enemies
        new_enemies = create_enemies(level, spawn_positions)
        self.entity_manager.enemies.extend(new_enemies)
        
        # Calculate used positions
        used_positions = [e.get_pos() for e in self.entity_manager.enemies]
        available_positions = [pos for pos in spawn_positions if pos not in used_positions]
        
        # Spawn replay enemies
        self._spawn_replay_enemies(
            enemy_counts.replay,
            available_positions,
            command_recorder
        )
        
        # Update used positions
        used_positions.extend([re.get_pos() for re in self.entity_manager.replay_enemies])
        available_positions = [pos for pos in spawn_positions if pos not in used_positions]
        
        # Spawn SplitBoss enemies
        self._spawn_split_bosses(
            split_boss_count,
            available_positions,
            command_recorder
        )
    
    def _spawn_replay_enemies(
        self,
        count: int,
        available_positions: List[Tuple[float, float]],
        command_recorder: 'CommandRecorder'
    ) -> None:
        """Spawn replay enemy ships.
        
        Args:
            count: Number of replay enemies to spawn.
            available_positions: Available spawn positions.
            command_recorder: Command recorder for replay enemies.
        """
        from entities.replay_enemy_ship import ReplayEnemyShip
        
        self.entity_manager.replay_enemies.clear()
        
        if len(available_positions) > 0 and count > 0:
            for i in range(min(count, len(available_positions))):
                replay_spawn = available_positions[i]
                replay_enemy = ReplayEnemyShip(replay_spawn, command_recorder)
                replay_enemy.current_replay_index = 0
                self.entity_manager.replay_enemies.append(replay_enemy)
    
    def _spawn_split_bosses(
        self,
        count: int,
        available_positions: List[Tuple[float, float]],
        command_recorder: 'CommandRecorder'
    ) -> None:
        """Spawn SplitBoss enemies.
        
        Args:
            count: Number of SplitBoss enemies to spawn.
            available_positions: Available spawn positions.
            command_recorder: Command recorder for replay enemies.
        """
        from entities.split_boss import SplitBoss
        
        self.entity_manager.split_bosses.clear()
        
        if count > 0 and len(available_positions) > 0:
            for i in range(min(count, len(available_positions))):
                split_boss_spawn = available_positions[i]
                split_boss = SplitBoss(split_boss_spawn, command_recorder)
                split_boss.current_replay_index = 0
                self.entity_manager.split_bosses.append(split_boss)

