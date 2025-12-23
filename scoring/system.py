"""Scoring system for tracking and managing game scores.

This module provides the ScoringSystem class that tracks game metrics
and uses ScoreCalculator for actual score calculations.
"""

import config
from typing import Dict
from scoring.calculator import ScoreCalculator


class ScoringSystem:
    """Manages scoring with multiple performance metrics.
    
    This class tracks game events and metrics, delegating actual score
    calculations to ScoreCalculator to follow the Single Responsibility Principle.
    
    Attributes:
        level_start_time: Timestamp when current level started.
        total_score: Accumulated score across all levels.
        level_score: Score for current/completed level.
        wall_collisions: Count of wall collisions.
        enemy_collisions: Count of enemy collisions.
        shots_fired: Count of shots fired.
        enemies_destroyed: Count of enemies destroyed by projectiles.
    """
    
    def __init__(self):
        """Initialize scoring system."""
        self.level_start_time = 0.0
        self.total_score = 0
        self.level_score = 0
        self.wall_collisions = 0
        self.enemy_collisions = 0
        self.shots_fired = 0
        self.enemies_destroyed = 0
        self.powerup_crystals_collected = 0
        self.enemy_bullet_hits = 0
    
    def start_level(self, current_time: float) -> None:
        """Start tracking a new level.
        
        Args:
            current_time: Current timestamp.
        """
        self.level_start_time = current_time
        self.level_score = 0
        self.wall_collisions = 0
        self.enemy_collisions = 0
        self.shots_fired = 0
        self.enemies_destroyed = 0
        self.powerup_crystals_collected = 0
        self.enemy_bullet_hits = 0
    
    def record_wall_collision(self) -> None:
        """Record a wall collision."""
        self.wall_collisions += 1
    
    def record_enemy_collision(self) -> None:
        """Record an enemy collision."""
        self.enemy_collisions += 1
    
    def record_shot(self) -> None:
        """Record a shot fired."""
        self.shots_fired += 1
    
    def record_enemy_destroyed(self) -> None:
        """Record an enemy destroyed by projectile (awards bonus points)."""
        self.enemies_destroyed += 1
    
    def record_powerup_collected(self) -> None:
        """Record when the ship collects a powerup crystal."""
        self.powerup_crystals_collected += 1

    def record_enemy_bullet_hit(self) -> None:
        """Record when the ship is hit by an enemy projectile."""
        self.enemy_bullet_hits += 1

    def calculate_level_score(
        self,
        completion_time: float,
        remaining_fuel: int,
        remaining_ammo: int
    ) -> Dict[str, float]:
        """Calculate final score for completed level.
        
        Args:
            completion_time: Time taken to complete level in seconds.
            remaining_fuel: Fuel remaining at completion.
            remaining_ammo: Ammo remaining at completion.
            
        Returns:
            Dictionary containing score breakdown and final score.
        """
        fuel_used = config.INITIAL_FUEL - remaining_fuel
        
        result = ScoreCalculator.calculate_score(
            elapsed_time=completion_time,
            enemy_collisions=self.enemy_collisions,
            enemies_destroyed=self.enemies_destroyed,
            shots_fired=self.shots_fired,
            fuel_used=fuel_used,
            wall_collisions=self.wall_collisions,
            powerups_collected=self.powerup_crystals_collected,
            enemy_bullet_hits=self.enemy_bullet_hits
        )
        
        self.level_score = result["final_score"]
        self.total_score += self.level_score
        
        result["total_score"] = self.total_score
        return result
    
    def get_current_time(self, current_time: float) -> float:
        """Get elapsed time for current level.
        
        Args:
            current_time: Current timestamp.
            
        Returns:
            Elapsed time in seconds.
        """
        return current_time - self.level_start_time
    
    def get_total_score(self) -> int:
        """Get total accumulated score.
        
        Returns:
            Total score as integer.
        """
        return int(self.total_score)
    
    def get_level_score(self) -> int:
        """Get score for current/completed level.
        
        Returns:
            Level score as integer.
        """
        return int(self.level_score)
    
    def calculate_max_possible_score(self) -> float:
        """Calculate the maximum possible score for a perfect run.
        
        Returns:
            Maximum possible score (100).
        """
        return config.MAX_LEVEL_SCORE
    
    def calculate_current_potential_score(
        self,
        current_time: float,
        remaining_fuel: int,
        remaining_ammo: int
    ) -> Dict[str, float]:
        """Calculate potential score based on current performance (real-time).
        
        Args:
            current_time: Current timestamp.
            remaining_fuel: Current fuel remaining.
            remaining_ammo: Current ammo remaining.
            
        Returns:
            Dictionary containing potential score breakdown and percentage.
        """
        elapsed_time = self.get_current_time(current_time)
        fuel_used = config.INITIAL_FUEL - remaining_fuel
        
        result = ScoreCalculator.calculate_score(
            elapsed_time=elapsed_time,
            enemy_collisions=self.enemy_collisions,
            enemies_destroyed=self.enemies_destroyed,
            shots_fired=self.shots_fired,
            fuel_used=fuel_used,
            wall_collisions=self.wall_collisions,
            powerups_collected=self.powerup_crystals_collected,
            enemy_bullet_hits=self.enemy_bullet_hits
        )
        
        max_score = self.calculate_max_possible_score()
        potential_score = result["final_score"]
        result["score_percentage"] = ScoreCalculator.calculate_score_percentage(
            potential_score, max_score
        )
        result["max_score"] = max_score
        result["potential_score"] = potential_score
        
        return result

