"""Utility functions module.

This module provides mathematical operations, collision detection,
and other helper functions used throughout the game.
"""

# Re-export all utilities for backward compatibility
from utils.math_utils import (
    distance,
    angle_to_radians,
    radians_to_angle,
    normalize_angle,
    rotate_point,
    point_in_rect,
    circle_circle_collision,
    circle_rect_collision,
    line_line_collision,
    circle_line_collision,
    circle_line_collision_swept,
    get_angle_to_point,
    get_closest_point_on_line,
    get_wall_normal,
    reflect_velocity
)

__all__ = [
    'distance',
    'angle_to_radians',
    'radians_to_angle',
    'normalize_angle',
    'rotate_point',
    'point_in_rect',
    'circle_circle_collision',
    'circle_rect_collision',
    'line_line_collision',
    'circle_line_collision',
    'circle_line_collision_swept',
    'get_angle_to_point',
    'get_closest_point_on_line',
    'get_wall_normal',
    'reflect_velocity'
]

