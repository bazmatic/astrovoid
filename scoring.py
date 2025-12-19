"""Scoring system with multi-factor metrics."""

import config
from typing import Dict


class ScoringSystem:
    """Manages scoring with multiple performance metrics."""
    
    def __init__(self):
        """Initialize scoring system."""
        self.start_time = 0.0
        self.level_start_time = 0.0
        self.total_score = 0
        self.level_score = 0
        self.wall_collisions = 0
        self.enemy_collisions = 0
        self.shots_fired = 0
    
    def start_level(self, current_time: float) -> None:
        """Start tracking a new level."""
        self.level_start_time = current_time
        self.level_score = 0
        self.wall_collisions = 0
        self.enemy_collisions = 0
        self.shots_fired = 0
    
    def record_wall_collision(self) -> None:
        """Record a wall collision."""
        self.wall_collisions += 1
    
    def record_enemy_collision(self) -> None:
        """Record an enemy collision."""
        self.enemy_collisions += 1
    
    def record_shot(self) -> None:
        """Record a shot fired."""
        self.shots_fired += 1
    
    def calculate_level_score(
        self,
        completion_time: float,
        remaining_fuel: int,
        remaining_ammo: int
    ) -> Dict[str, float]:
        """Calculate final score for completed level."""
        # Base time score (faster = higher)
        time_score = max(0, config.SCORE_TIME_WEIGHT - completion_time * 10)
        
        # Fuel efficiency bonus
        fuel_bonus = remaining_fuel * config.SCORE_FUEL_WEIGHT
        
        # Ammo efficiency bonus
        ammo_bonus = remaining_ammo * config.SCORE_AMMO_WEIGHT
        
        # Collision penalties
        collision_penalty = (self.wall_collisions + self.enemy_collisions) * config.SCORE_COLLISION_PENALTY
        
        # Shot penalty (firing costs points)
        shot_penalty = self.shots_fired * 5
        
        # Final score
        final_score = time_score + fuel_bonus + ammo_bonus - collision_penalty - shot_penalty
        final_score = max(0, final_score)  # No negative scores
        
        self.level_score = final_score
        self.total_score += final_score
        
        return {
            "time_score": time_score,
            "fuel_bonus": fuel_bonus,
            "ammo_bonus": ammo_bonus,
            "collision_penalty": collision_penalty,
            "shot_penalty": shot_penalty,
            "final_score": final_score,
            "total_score": self.total_score
        }
    
    def get_current_time(self, current_time: float) -> float:
        """Get elapsed time for current level."""
        return current_time - self.level_start_time
    
    def get_total_score(self) -> int:
        """Get total accumulated score."""
        return int(self.total_score)
    
    def get_level_score(self) -> int:
        """Get score for current/completed level."""
        return int(self.level_score)
    
    def calculate_max_possible_score(self) -> float:
        """Calculate the maximum possible score for a perfect run."""
        # Perfect run: instant completion, full fuel, full ammo, no collisions, no shots
        max_time_score = config.SCORE_TIME_WEIGHT
        max_fuel_bonus = config.INITIAL_FUEL * config.SCORE_FUEL_WEIGHT
        max_ammo_bonus = config.INITIAL_AMMO * config.SCORE_AMMO_WEIGHT
        # No penalties
        return max_time_score + max_fuel_bonus + max_ammo_bonus
    
    def calculate_current_potential_score(
        self,
        current_time: float,
        remaining_fuel: int,
        remaining_ammo: int
    ) -> Dict[str, float]:
        """Calculate potential score based on current performance (real-time)."""
        elapsed_time = self.get_current_time(current_time)
        
        # Base time score (faster = higher)
        time_score = max(0, config.SCORE_TIME_WEIGHT - elapsed_time * 10)
        
        # Fuel efficiency bonus
        fuel_bonus = remaining_fuel * config.SCORE_FUEL_WEIGHT
        
        # Ammo efficiency bonus
        ammo_bonus = remaining_ammo * config.SCORE_AMMO_WEIGHT
        
        # Collision penalties
        collision_penalty = (self.wall_collisions + self.enemy_collisions) * config.SCORE_COLLISION_PENALTY
        
        # Shot penalty (firing costs points)
        shot_penalty = self.shots_fired * 5
        
        # Potential score if level completed now
        potential_score = time_score + fuel_bonus + ammo_bonus - collision_penalty - shot_penalty
        potential_score = max(0, potential_score)  # No negative scores
        
        # Calculate score percentage (0.0 to 1.0)
        max_score = self.calculate_max_possible_score()
        score_percentage = min(1.0, max(0.0, potential_score / max_score)) if max_score > 0 else 0.0
        
        return {
            "time_score": time_score,
            "fuel_bonus": fuel_bonus,
            "ammo_bonus": ammo_bonus,
            "collision_penalty": collision_penalty,
            "shot_penalty": shot_penalty,
            "potential_score": potential_score,
            "score_percentage": score_percentage,
            "max_score": max_score
        }

