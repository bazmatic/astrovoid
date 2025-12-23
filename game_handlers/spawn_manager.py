"""Enemy spawning management.

This module handles all enemy spawning logic, eliminating duplication
in the start_level() method.
"""

from dataclasses import dataclass
from typing import List, Tuple, Callable, Optional, TYPE_CHECKING
import random
import math
import level_rules
import config as game_config
if TYPE_CHECKING:
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.flocker_enemy_ship import FlockerEnemyShip
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

        entity_list = getattr(self.entity_manager, config.entity_list_attr)
        entity_list.clear()

        positions_to_use = self._select_positions(config, available_positions)
        used_positions: List[Tuple[float, float]] = []
        
        for pos in positions_to_use:
            entity = self._create_entity(config, pos, command_recorder)
            if config.post_create_hook:
                config.post_create_hook(entity)
            entity_list.append(entity)
            used_positions.append(pos)
        
        return used_positions

    def _create_entity(
        self,
        config: SpawnConfig,
        pos: Tuple[float, float],
        command_recorder: Optional['CommandRecorder']
    ):
        """Create an entity using the provided factory and recorder requirement."""
        if config.requires_command_recorder:
            if command_recorder is None:
                raise ValueError(f"command_recorder required for {config.entity_list_attr}")
            return config.factory_func(pos, command_recorder)
        return config.factory_func(pos, None)

    def _select_positions(
        self,
        config: SpawnConfig,
        available_positions: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """Select spawn positions with special handling for flockers."""
        spawn_count = min(config.count, len(available_positions))
        if spawn_count <= 0:
            return []

        if config.entity_list_attr == "flockers":
            return self._select_flocker_positions(available_positions, spawn_count)

        return available_positions[:spawn_count]

    def _select_flocker_positions(
        self,
        available_positions: List[Tuple[float, float]],
        spawn_count: int
    ) -> List[Tuple[float, float]]:
        """Select clustered positions for flockers using configurable radius."""
        anchor = available_positions[0]
        radius_sq = game_config.FLOCKER_ENEMY_CLUSTER_RADIUS * game_config.FLOCKER_ENEMY_CLUSTER_RADIUS

        within_radius = [
            p for p in available_positions
            if (p[0] - anchor[0]) ** 2 + (p[1] - anchor[1]) ** 2 <= radius_sq
        ]

        positions_sorted = sorted(
            within_radius if within_radius else available_positions,
            key=lambda p: (p[0] - anchor[0]) ** 2 + (p[1] - anchor[1]) ** 2
        )

        if len(positions_sorted) >= spawn_count:
            return positions_sorted[:spawn_count]

        # Allow overlap if not enough slots; repeat anchor to fill
        return positions_sorted + [anchor] * (spawn_count - len(positions_sorted))
    
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
        # Clear existing enemies
        self.entity_manager.clear_all()
        
        # Create regular enemies based on enemy_counts
        new_enemies = self._create_enemies_from_counts(
            level, spawn_positions, enemy_counts
        )
        self.entity_manager.enemies.extend(new_enemies)
        
        # Track used positions
        used_positions = [e.get_pos() for e in self.entity_manager.enemies]
        available_positions = self._update_available_positions(used_positions, spawn_positions)
        
        # Define spawn configurations for all enemy types
        spawn_configs = self._create_spawn_configs(
            enemy_counts, split_boss_count, mother_boss_count
        )
        
        # Spawn all entities using configuration
        for config in spawn_configs:
            newly_used = self._spawn_entities(config, available_positions, command_recorder)
            used_positions.extend(newly_used)
            available_positions = self._update_available_positions(used_positions, spawn_positions)
    
    def _create_spawn_configs(
        self,
        enemy_counts: 'EnemyCounts',
        split_boss_count: int,
        mother_boss_count: int
    ) -> List[SpawnConfig]:
        """Create spawn configurations for all enemy types.
        
        Args:
            enemy_counts: Enemy count configuration.
            split_boss_count: Number of SplitBoss enemies.
            mother_boss_count: Number of Mother Boss enemies.
            
        Returns:
            List of SpawnConfig objects.
        """
        from entities.replay_enemy_ship import ReplayEnemyShip
        from entities.flocker_enemy_ship import FlockerEnemyShip
        from entities.split_boss import SplitBoss
        from entities.mother_boss import MotherBoss
        from entities.egg import Egg
        
        def set_replay_index(entity):
            """Post-create hook to set replay index."""
            entity.current_replay_index = 0
        
        configs = []
        
        # Replay enemies
        if enemy_counts.replay > 0:
            configs.append(SpawnConfig(
                count=enemy_counts.replay,
                entity_list_attr="replay_enemies",
                factory_func=lambda pos, cr: ReplayEnemyShip(pos, cr),
                requires_command_recorder=True,
                post_create_hook=set_replay_index
            ))
        
        # Flocker enemies
        if enemy_counts.flocker > 0:
            configs.append(SpawnConfig(
                count=enemy_counts.flocker,
                entity_list_attr="flockers",
                factory_func=lambda pos, cr: FlockerEnemyShip(pos),
                requires_command_recorder=False,
                post_create_hook=None
            ))
        
        # SplitBoss enemies
        if split_boss_count > 0:
            configs.append(SpawnConfig(
                count=split_boss_count,
                entity_list_attr="split_bosses",
                factory_func=lambda pos, cr: SplitBoss(pos, cr),
                requires_command_recorder=True,
                post_create_hook=set_replay_index
            ))
        
        # Mother Boss enemies
        if mother_boss_count > 0:
            configs.append(SpawnConfig(
                count=mother_boss_count,
                entity_list_attr="mother_bosses",
                factory_func=lambda pos, cr: MotherBoss(pos, cr),
                requires_command_recorder=True,
                post_create_hook=set_replay_index
            ))
        
        # Egg enemies
        if enemy_counts.egg > 0:
            configs.append(SpawnConfig(
                count=enemy_counts.egg,
                entity_list_attr="eggs",
                factory_func=lambda pos, cr: Egg(pos),
                requires_command_recorder=False,
                post_create_hook=None
            ))
        
        return configs
    
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
        
        # Define enemy type configurations
        enemy_types = [
            ("static", enemy_counts.static),
            ("patrol", enemy_counts.patrol),
            ("aggressive", enemy_counts.aggressive)
        ]
        
        # Create enemies for each type
        for enemy_type, count in enemy_types:
            if count <= 0:
                continue
            
            remaining_positions = self._update_available_positions(used_positions, available_positions)
            spawn_count = min(count, len(remaining_positions))
            
            for i in range(spawn_count):
                pos = remaining_positions[i]
                enemies.append(Enemy(pos, enemy_type, level))
                used_positions.append(pos)
        
        return enemies
    

