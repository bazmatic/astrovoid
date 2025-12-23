"""Entity management for consolidating enemy list management.

This module provides a unified interface for managing all enemy types,
eliminating the need to maintain separate lists in the main game class.
"""

from typing import List, Iterator, Tuple, TYPE_CHECKING
if TYPE_CHECKING:
    from entities.enemy import Enemy
    from entities.replay_enemy_ship import ReplayEnemyShip
    from entities.flocker_enemy_ship import FlockerEnemyShip
    from entities.flighthouse_enemy import FlighthouseEnemy
    from entities.split_boss import SplitBoss
    from entities.mother_boss import MotherBoss
    from entities.baby import Baby
    from entities.egg import Egg


class EntityManager:
    """Manages all enemy entities in the game."""
    
    def __init__(self):
        """Initialize entity manager with empty lists."""
        self.enemies: List['Enemy'] = []
        self.replay_enemies: List['ReplayEnemyShip'] = []
        self.flockers: List['FlockerEnemyShip'] = []
        self.flighthouses: List['FlighthouseEnemy'] = []
        self.split_bosses: List['SplitBoss'] = []
        self.mother_bosses: List['MotherBoss'] = []
        self.babies: List['Baby'] = []
        self.eggs: List['Egg'] = []
    
    def clear_all(self) -> None:
        """Clear all enemy lists."""
        self.enemies.clear()
        self.replay_enemies.clear()
        self.flockers.clear()
        self.flighthouses.clear()
        self.split_bosses.clear()
        self.mother_bosses.clear()
        self.babies.clear()
        self.eggs.clear()
    
    def get_all_enemy_positions(self) -> List[Tuple[float, float]]:
        """Get positions of all enemies for spawn position calculation.
        
        Returns:
            List of all enemy positions.
        """
        positions = []
        positions.extend([e.get_pos() for e in self.enemies])
        positions.extend([re.get_pos() for re in self.replay_enemies])
        positions.extend([f.get_pos() for f in self.flockers])
        positions.extend([fh.get_pos() for fh in self.flighthouses])
        positions.extend([sb.get_pos() for sb in self.split_bosses])
        positions.extend([mb.get_pos() for mb in self.mother_bosses])
        positions.extend([baby.get_pos() for baby in self.babies])
        positions.extend([egg.get_pos() for egg in self.eggs])
        return positions
    
    def get_all_active_enemies(self) -> Iterator:
        """Get iterator over all active enemies.
        
        Yields:
            Active enemy instances from all lists.
        """
        for enemy in self.enemies:
            if enemy.active:
                yield enemy
        for replay_enemy in self.replay_enemies:
            if replay_enemy.active:
                yield replay_enemy
        for flocker in self.flockers:
            if flocker.active:
                yield flocker
        for flighthouse in self.flighthouses:
            if flighthouse.active:
                yield flighthouse
        for split_boss in self.split_bosses:
            if split_boss.active:
                yield split_boss
        for mother_boss in self.mother_bosses:
            if mother_boss.active:
                yield mother_boss
        for baby in self.babies:
            if baby.active:
                yield baby
        for egg in self.eggs:
            if egg.active:
                yield egg

