"""Score calculation logic.

This module provides a centralized score calculator that eliminates
duplication between real-time and final score calculations (DRY principle).
"""

from typing import Dict
import config


class ScoreCalculator:
    """Calculates scores based on game performance metrics.
    
    This class centralizes score calculation logic to avoid duplication
    between real-time and final score calculations.
    """
    
    @staticmethod
    def calculate_score(
        elapsed_time: float,
        enemy_collisions: int,
        enemies_destroyed: int,
        shots_fired: int,
        fuel_used: int
    ) -> Dict[str, float]:
        """Calculate score based on performance metrics.
        
        Args:
            elapsed_time: Time taken in seconds.
            enemy_collisions: Number of enemy collisions.
            enemies_destroyed: Number of enemies destroyed by projectiles.
            shots_fired: Number of shots fired.
            fuel_used: Amount of fuel consumed.
            
        Returns:
            Dictionary containing:
                - time_penalty: Points deducted for time
                - collision_penalty: Points deducted for collisions
                - enemy_destruction_bonus: Points awarded for destroyed enemies
                - ammo_penalty: Points deducted for shots
                - fuel_penalty: Points deducted for fuel usage
                - final_score: Calculated final score
        """
        # Start with maximum score
        score = config.MAX_LEVEL_SCORE
        
        # Time penalty (major reduction)
        time_penalty = elapsed_time * config.TIME_PENALTY_RATE
        
        # Collision penalty (significant reduction per enemy collision only, not walls)
        collision_penalty = enemy_collisions * config.COLLISION_PENALTY
        
        # Enemy destruction bonus (gain points equal to collision penalty for each enemy destroyed)
        enemy_destruction_bonus = enemies_destroyed * config.COLLISION_PENALTY
        
        # Ammo penalty (minor reduction per shot)
        ammo_penalty = shots_fired * config.AMMO_PENALTY_RATE
        
        # Fuel penalty (minor reduction per unit used)
        fuel_penalty = fuel_used * config.FUEL_PENALTY_RATE
        
        # Calculate final score (bonus adds to score, can exceed 100)
        final_score = (
            score - time_penalty - collision_penalty - ammo_penalty - fuel_penalty
            + enemy_destruction_bonus
        )
        final_score = max(0, final_score)  # Minimum 0, but can exceed 100
        
        return {
            "time_penalty": time_penalty,
            "collision_penalty": collision_penalty,
            "enemy_destruction_bonus": enemy_destruction_bonus,
            "ammo_penalty": ammo_penalty,
            "fuel_penalty": fuel_penalty,
            "final_score": final_score
        }
    
    @staticmethod
    def calculate_score_percentage(score: float, max_score: float) -> float:
        """Calculate score as a percentage of maximum.
        
        Args:
            score: Current score.
            max_score: Maximum possible score.
            
        Returns:
            Score percentage (can exceed 1.0 for bonuses).
        """
        if max_score <= 0:
            return 0.0
        return max(0.0, score / max_score)


