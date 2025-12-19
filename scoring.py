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
        """Calculate final score for completed level (0-100 scale)."""
        # Start with maximum score
        score = config.MAX_LEVEL_SCORE
        
        # Time penalty (major reduction)
        time_penalty = completion_time * config.TIME_PENALTY_RATE
        
        # Collision penalty (significant reduction per collision)
        collision_penalty = (self.wall_collisions + self.enemy_collisions) * config.COLLISION_PENALTY
        
        # Ammo penalty (minor reduction per shot)
        ammo_penalty = self.shots_fired * config.AMMO_PENALTY_RATE
        
        # Fuel penalty (minor reduction per unit used)
        fuel_used = config.INITIAL_FUEL - remaining_fuel
        fuel_penalty = fuel_used * config.FUEL_PENALTY_RATE
        
        # Calculate final score
        final_score = score - time_penalty - collision_penalty - ammo_penalty - fuel_penalty
        final_score = max(0, min(config.MAX_LEVEL_SCORE, final_score))  # Clamp between 0 and 100
        
        self.level_score = final_score
        self.total_score += final_score
        
        return {
            "time_penalty": time_penalty,
            "collision_penalty": collision_penalty,
            "ammo_penalty": ammo_penalty,
            "fuel_penalty": fuel_penalty,
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
        # Perfect run: instant completion, no collisions, no shots, no fuel used
        return config.MAX_LEVEL_SCORE
    
    def calculate_current_potential_score(
        self,
        current_time: float,
        remaining_fuel: int,
        remaining_ammo: int
    ) -> Dict[str, float]:
        """Calculate potential score based on current performance (real-time, 0-100 scale)."""
        elapsed_time = self.get_current_time(current_time)
        
        # Start with maximum score
        score = config.MAX_LEVEL_SCORE
        
        # Time penalty (major reduction)
        time_penalty = elapsed_time * config.TIME_PENALTY_RATE
        
        # Collision penalty (significant reduction per collision)
        collision_penalty = (self.wall_collisions + self.enemy_collisions) * config.COLLISION_PENALTY
        
        # Ammo penalty (minor reduction per shot)
        ammo_penalty = self.shots_fired * config.AMMO_PENALTY_RATE
        
        # Fuel penalty (minor reduction per unit used)
        fuel_used = config.INITIAL_FUEL - remaining_fuel
        fuel_penalty = fuel_used * config.FUEL_PENALTY_RATE
        
        # Calculate potential score if level completed now
        potential_score = score - time_penalty - collision_penalty - ammo_penalty - fuel_penalty
        potential_score = max(0, min(config.MAX_LEVEL_SCORE, potential_score))  # Clamp between 0 and 100
        
        # Calculate score percentage (0.0 to 1.0)
        max_score = self.calculate_max_possible_score()
        score_percentage = min(1.0, max(0.0, potential_score / max_score)) if max_score > 0 else 0.0
        
        return {
            "time_penalty": time_penalty,
            "collision_penalty": collision_penalty,
            "ammo_penalty": ammo_penalty,
            "fuel_penalty": fuel_penalty,
            "potential_score": potential_score,
            "score_percentage": score_percentage,
            "max_score": max_score
        }

