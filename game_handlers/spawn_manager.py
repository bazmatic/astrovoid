"""Enemy spawning management.

This module handles all enemy spawning logic, eliminating duplication
in the start_level() method.
"""

from dataclasses import dataclass
from typing import List, Tuple, Callable, Optional, TYPE_CHECKING
import random
import level_rules
if TYPE_CHECKING:
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.split_boss import SplitBoss
    from entities.command_recorder import CommandRecorder
    from game_handlers.entity_manager import EntityManager
    from level_rules import EnemyCounts


@dataclass
class SpawnConfig:
    """Configuration for spawning a type of entity.
    
    Attributes:
        count: Number of entities to spawn.
        entity_list_attr: Attribute name on EntityManager (e.g., "replay_enemies").
        factory_func: Factory function that takes (pos, command_recorder) and returns entity.
        requires_command_recorder: Whether command_recorder is needed for factory.
        post_create_hook: Optional function to call after entity creation (entity) -> None.
    """
    count: int
    entity_list_attr: str
    factory_func: Callable[[Tuple[float, float], Optional['CommandRecorder']], object]
    requires_command_recorder: bool = False
    post_create_hook: Optional[Callable[[object], None]] = None


class SpawnManager:
    """Manages enemy spawning for levels."""
    
    def __init__(self, entity_manager: 'EntityManager'):
        """Initialize spawn manager.
        
        Args:
            entity_manager: Entity manager to add spawned enemies to.
        """
        self.entity_manager = entity_manager
    
    def _update_available_positions(
        self,
        used_positions: List[Tuple[float, float]],
        all_positions: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """Calculate available positions after excluding used ones.
        
        Args:
            used_positions: Positions that have been used.
            all_positions: All available spawn positions.
            
        Returns:
            List of positions that are still available.
        """
        return [pos for pos in all_positions if pos not in used_positions]
    
    def _spawn_entities(
        self,
        config: SpawnConfig,
        available_positions: List[Tuple[float, float]],
        command_recorder: Optional['CommandRecorder'] = None
    ) -> List[Tuple[float, float]]:
        """Spawn entities based on configuration.
        
        Args:
            config: Spawn configuration.
            available_positions: Available spawn positions.
            command_recorder: Command recorder (required if config.requires_command_recorder).
            
        Returns:
            List of positions used by spawned entities.
        """
        if config.count <= 0 or len(available_positions) == 0:
            return []
        
        # Get the entity list from entity manager
        entity_list = getattr(self.entity_manager, config.entity_list_attr)
        entity_list.clear()
        
        used_positions = []
        spawn_count = min(config.count, len(available_positions))
        
        for i in range(spawn_count):
            pos = available_positions[i]
            
            # Create entity using factory function
            if config.requires_command_recorder:
                if command_recorder is None:
                    raise ValueError(f"command_recorder required for {config.entity_list_attr}")
                entity = config.factory_func(pos, command_recorder)
            else:
                entity = config.factory_func(pos, None)
            
            # Apply post-create hook if provided
            if config.post_create_hook:
                config.post_create_hook(entity)
            
            entity_list.append(entity)
            used_positions.append(pos)
        
        return used_positions
    
    def spawn_all_enemies(
        self,
        level: int,
        spawn_positions: List[Tuple[float, float]],
        command_recorder: 'CommandRecorder',
        enemy_counts: 'EnemyCounts',
        split_boss_count: int,
        mother_boss_count: int
    ) -> None:
        """Spawn all enemies for a level.
        
        Args:
            level: Current level number.
            spawn_positions: Available spawn positions.
            command_recorder: Command recorder for replay enemies.
            enemy_counts: Enemy count configuration.
            split_boss_count: Number of SplitBoss enemies to spawn.
            mother_boss_count: Number of Mother Boss enemies to spawn.
        """
        from entities.enemy import create_enemies
        from entities.replay_enemy_ship import ReplayEnemyShip
        from entities.split_boss import SplitBoss
        
        # Clear existing enemies
        self.entity_manager.clear_all()
        
        # Create regular enemies based on enemy_counts
        new_enemies = self._create_enemies_from_counts(
            level, spawn_positions, enemy_counts
        )
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
        
        # Update used positions
        used_positions.extend([sb.get_pos() for sb in self.entity_manager.split_bosses])
        available_positions = [pos for pos in spawn_positions if pos not in used_positions]
        
        # Spawn Mother Boss enemies
        self._spawn_mother_bosses(
            mother_boss_count,
            available_positions,
            command_recorder
        )
        
        # Update used positions
        used_positions.extend([mb.get_pos() for mb in self.entity_manager.mother_bosses])
        available_positions = [pos for pos in spawn_positions if pos not in used_positions]
        
        # Spawn egg enemies
        self._spawn_eggs(
            enemy_counts.egg,
            available_positions
        )
    
    def _create_enemies_from_counts(
        self,
        level: int,
        spawn_positions: List[Tuple[float, float]],
        enemy_counts: 'EnemyCounts'
    ) -> List['Enemy']:
        """Create enemies based on enemy_counts configuration.
        
        Args:
            level: Current level number.
            spawn_positions: List of valid spawn positions.
            enemy_counts: Enemy count configuration.
            
        Returns:
            List of Enemy instances.
        """
        from entities.enemy import Enemy
        
        enemies = []
        used_positions = []
        
        # Shuffle positions
        available_positions = spawn_positions.copy()
        random.shuffle(available_positions)
        
        # Create static enemies
        for i in range(min(enemy_counts.static, len(available_positions))):
            pos = available_positions[i]
            enemies.append(Enemy(pos, "static", level))
            used_positions.append(pos)
        
        # Create patrol enemies
        remaining_positions = [p for p in available_positions if p not in used_positions]
        for i in range(min(enemy_counts.patrol, len(remaining_positions))):
            pos = remaining_positions[i]
            enemies.append(Enemy(pos, "patrol", level))
            used_positions.append(pos)
        
        # Create aggressive enemies
        remaining_positions = [p for p in available_positions if p not in used_positions]
        for i in range(min(enemy_counts.aggressive, len(remaining_positions))):
            pos = remaining_positions[i]
            enemies.append(Enemy(pos, "aggressive", level))
        
        return enemies
    
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
    
    def _spawn_mother_bosses(
        self,
        count: int,
        available_positions: List[Tuple[float, float]],
        command_recorder: 'CommandRecorder'
    ) -> None:
        """Spawn Mother Boss enemies.
        
        Args:
            count: Number of Mother Boss enemies to spawn.
            available_positions: Available spawn positions.
            command_recorder: Command recorder for replay enemies.
        """
        from entities.mother_boss import MotherBoss
        
        self.entity_manager.mother_bosses.clear()
        
        if count > 0 and len(available_positions) > 0:
            for i in range(min(count, len(available_positions))):
                mother_boss_spawn = available_positions[i]
                mother_boss = MotherBoss(mother_boss_spawn, command_recorder)
                mother_boss.current_replay_index = 0
                self.entity_manager.mother_bosses.append(mother_boss)
    
    def _spawn_eggs(
        self,
        count: int,
        available_positions: List[Tuple[float, float]]
    ) -> None:
        """Spawn egg enemies.
        
        Args:
            count: Number of egg enemies to spawn.
            available_positions: Available spawn positions.
        """
        from entities.egg import Egg
        
        self.entity_manager.eggs.clear()
        
        if count > 0 and len(available_positions) > 0:
            for i in range(min(count, len(available_positions))):
                egg_spawn = available_positions[i]
                egg = Egg(egg_spawn)
                self.entity_manager.eggs.append(egg)

