"""Unit tests for scoring system."""

import pytest
from scoring.calculator import ScoreCalculator
import config


class TestScoreCalculator:
    """Tests for score calculation logic."""
    
    def test_perfect_score(self):
        """Perfect run should give maximum score."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=0.0,
            enemy_collisions=0,
            enemies_destroyed=0,
            shots_fired=0,
            fuel_used=0
        )
        assert result["final_score"] == config.MAX_LEVEL_SCORE
        assert result["time_penalty"] == 0.0
        assert result["collision_penalty"] == 0.0
        assert result["enemy_destruction_bonus"] == 0.0
        assert result["ammo_penalty"] == 0.0
        assert result["fuel_penalty"] == 0.0
    
    def test_time_penalty(self):
        """Time should reduce score."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=10.0,
            enemy_collisions=0,
            enemies_destroyed=0,
            shots_fired=0,
            fuel_used=0
        )
        expected_penalty = 10.0 * config.TIME_PENALTY_RATE
        assert abs(result["time_penalty"] - expected_penalty) < 0.0001
        assert result["final_score"] == config.MAX_LEVEL_SCORE - expected_penalty
    
    def test_collision_penalty(self):
        """Enemy collisions should reduce score."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=0.0,
            enemy_collisions=3,
            enemies_destroyed=0,
            shots_fired=0,
            fuel_used=0
        )
        expected_penalty = 3 * config.COLLISION_PENALTY
        assert result["collision_penalty"] == expected_penalty
        assert result["final_score"] == config.MAX_LEVEL_SCORE - expected_penalty
    
    def test_enemy_destruction_bonus(self):
        """Destroying enemies should add bonus points."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=0.0,
            enemy_collisions=0,
            enemies_destroyed=2,
            shots_fired=0,
            fuel_used=0
        )
        expected_bonus = 2 * config.COLLISION_PENALTY
        assert result["enemy_destruction_bonus"] == expected_bonus
        assert result["final_score"] == config.MAX_LEVEL_SCORE + expected_bonus
    
    def test_ammo_penalty(self):
        """Firing shots should reduce score slightly."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=0.0,
            enemy_collisions=0,
            enemies_destroyed=0,
            shots_fired=10,
            fuel_used=0
        )
        expected_penalty = 10 * config.AMMO_PENALTY_RATE
        assert abs(result["ammo_penalty"] - expected_penalty) < 0.0001
        assert result["final_score"] == config.MAX_LEVEL_SCORE - expected_penalty
    
    def test_fuel_penalty(self):
        """Using fuel should reduce score slightly."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=0.0,
            enemy_collisions=0,
            enemies_destroyed=0,
            shots_fired=0,
            fuel_used=100
        )
        expected_penalty = 100 * config.FUEL_PENALTY_RATE
        assert abs(result["fuel_penalty"] - expected_penalty) < 0.0001
        assert result["final_score"] == config.MAX_LEVEL_SCORE - expected_penalty
    
    def test_combined_penalties(self):
        """Multiple penalties should combine correctly."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=5.0,
            enemy_collisions=2,
            enemies_destroyed=1,
            shots_fired=5,
            fuel_used=50
        )
        time_penalty = 5.0 * config.TIME_PENALTY_RATE
        collision_penalty = 2 * config.COLLISION_PENALTY
        enemy_bonus = 1 * config.COLLISION_PENALTY
        ammo_penalty = 5 * config.AMMO_PENALTY_RATE
        fuel_penalty = 50 * config.FUEL_PENALTY_RATE
        
        expected_score = (
            config.MAX_LEVEL_SCORE
            - time_penalty
            - collision_penalty
            - ammo_penalty
            - fuel_penalty
            + enemy_bonus
        )
        assert abs(result["final_score"] - expected_score) < 0.0001
    
    def test_score_cannot_go_below_zero(self):
        """Score should never go below zero."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=1000.0,  # Very long time
            enemy_collisions=100,  # Many collisions
            enemies_destroyed=0,
            shots_fired=1000,
            fuel_used=10000
        )
        assert result["final_score"] >= 0.0
    
    def test_score_can_exceed_maximum(self):
        """Score can exceed maximum with bonuses."""
        result = ScoreCalculator.calculate_score(
            elapsed_time=0.0,
            enemy_collisions=0,
            enemies_destroyed=10,  # Many enemies destroyed
            shots_fired=0,
            fuel_used=0
        )
        assert result["final_score"] > config.MAX_LEVEL_SCORE
    
    def test_calculate_score_percentage(self):
        """Score percentage should be calculated correctly."""
        percentage = ScoreCalculator.calculate_score_percentage(50.0, 100.0)
        assert abs(percentage - 0.5) < 0.0001
        
        percentage = ScoreCalculator.calculate_score_percentage(100.0, 100.0)
        assert abs(percentage - 1.0) < 0.0001
        
        percentage = ScoreCalculator.calculate_score_percentage(150.0, 100.0)
        assert abs(percentage - 1.5) < 0.0001  # Can exceed 100%
    
    def test_calculate_score_percentage_zero_max(self):
        """Score percentage with zero max should return zero."""
        percentage = ScoreCalculator.calculate_score_percentage(50.0, 0.0)
        assert percentage == 0.0
    
    def test_calculate_score_percentage_negative(self):
        """Negative score should return zero percentage."""
        percentage = ScoreCalculator.calculate_score_percentage(-10.0, 100.0)
        assert percentage == 0.0


