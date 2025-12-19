"""Enemy system with static and dynamic enemies."""

import pygame
import random
import math
from typing import Tuple, List, Optional
import config
import utils


class Enemy:
    """Base enemy class."""
    
    def __init__(self, pos: Tuple[float, float], enemy_type: str = "static"):
        """Initialize enemy at position."""
        self.x, self.y = pos
        self.type = enemy_type
        self.radius = config.STATIC_ENEMY_SIZE if enemy_type == "static" else config.DYNAMIC_ENEMY_SIZE
        self.active = True
        
        # Dynamic enemy properties
        if enemy_type == "patrol":
            self.speed = config.ENEMY_PATROL_SPEED
            self.angle = random.uniform(0, 360)
            self.patrol_distance = 0
            self.max_patrol_distance = random.uniform(50, 150)
            self.patrol_direction = 1
        elif enemy_type == "aggressive":
            self.speed = config.ENEMY_AGGRESSIVE_SPEED
            self.angle = 0
            self.target_pos = None
    
    def update(self, dt: float, player_pos: Optional[Tuple[float, float]] = None, walls: List = None) -> None:
        """Update enemy position and behavior."""
        if not self.active:
            return
        
        if self.type == "static":
            # Static enemies don't move
            return
        
        elif self.type == "patrol":
            # Move in a straight line, reverse when hitting limit
            angle_rad = utils.angle_to_radians(self.angle)
            dx = math.cos(angle_rad) * self.speed * dt
            dy = math.sin(angle_rad) * self.speed * dt
            
            new_x = self.x + dx
            new_y = self.y + dy
            
            # Check wall collision
            hit_wall = False
            if walls:
                for wall in walls:
                    if utils.circle_line_collision((new_x, new_y), self.radius, wall[0], wall[1]):
                        hit_wall = True
                        break
            
            if hit_wall or self.patrol_distance >= self.max_patrol_distance:
                # Reverse direction
                self.angle = (self.angle + 180) % 360
                self.patrol_distance = 0
            else:
                self.x = new_x
                self.y = new_y
                self.patrol_distance += self.speed * dt
        
        elif self.type == "aggressive":
            # Chase player
            if player_pos:
                target_angle = utils.get_angle_to_point((self.x, self.y), player_pos)
                self.angle = target_angle
                
                angle_rad = utils.angle_to_radians(self.angle)
                dx = math.cos(angle_rad) * self.speed * dt
                dy = math.sin(angle_rad) * self.speed * dt
                
                new_x = self.x + dx
                new_y = self.y + dy
                
                # Check wall collision
                can_move = True
                if walls:
                    for wall in walls:
                        if utils.circle_line_collision((new_x, new_y), self.radius, wall[0], wall[1]):
                            can_move = False
                            break
                
                if can_move:
                    self.x = new_x
                    self.y = new_y
    
    def get_pos(self) -> Tuple[float, float]:
        """Get enemy position."""
        return (self.x, self.y)
    
    def destroy(self) -> None:
        """Destroy the enemy."""
        self.active = False
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the enemy."""
        if not self.active:
            return
        
        color = config.COLOR_ENEMY_STATIC if self.type == "static" else config.COLOR_ENEMY_DYNAMIC
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 2)
        
        # Draw direction indicator for dynamic enemies
        if self.type != "static":
            angle_rad = utils.angle_to_radians(self.angle)
            indicator_x = self.x + math.cos(angle_rad) * self.radius
            indicator_y = self.y + math.sin(angle_rad) * self.radius
            pygame.draw.line(screen, (255, 255, 255), 
                           (int(self.x), int(self.y)),
                           (int(indicator_x), int(indicator_y)), 2)


def create_enemies(level: int, spawn_positions: List[Tuple[float, float]]) -> List[Enemy]:
    """Create enemies for a level."""
    enemy_count = config.BASE_ENEMY_COUNT + (level - 1) * config.ENEMY_COUNT_INCREMENT
    enemy_count = min(enemy_count, len(spawn_positions))
    
    enemies = []
    used_positions = []
    
    # Determine enemy type distribution
    static_count = max(1, enemy_count // 2)
    dynamic_count = enemy_count - static_count
    
    # Shuffle positions
    available_positions = spawn_positions.copy()
    random.shuffle(available_positions)
    
    # Create static enemies
    for i in range(min(static_count, len(available_positions))):
        pos = available_positions[i]
        enemies.append(Enemy(pos, "static"))
        used_positions.append(pos)
    
    # Create dynamic enemies (patrol and aggressive)
    remaining_positions = [p for p in available_positions if p not in used_positions]
    patrol_count = dynamic_count // 2
    aggressive_count = dynamic_count - patrol_count
    
    for i in range(min(patrol_count, len(remaining_positions))):
        pos = remaining_positions[i]
        enemies.append(Enemy(pos, "patrol"))
    
    remaining_positions = [p for p in remaining_positions if p not in [e.get_pos() for e in enemies]]
    for i in range(min(aggressive_count, len(remaining_positions))):
        pos = remaining_positions[i]
        enemies.append(Enemy(pos, "aggressive"))
    
    return enemies

