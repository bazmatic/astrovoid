"""Utility functions for collision detection and math operations."""

import math
from typing import Tuple


def distance(pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
    """Calculate distance between two points."""
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    return math.sqrt(dx * dx + dy * dy)


def angle_to_radians(angle: float) -> float:
    """Convert angle in degrees to radians."""
    return math.radians(angle)


def radians_to_angle(radians: float) -> float:
    """Convert radians to angle in degrees."""
    return math.degrees(radians)


def normalize_angle(angle: float) -> float:
    """Normalize angle to 0-360 range."""
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle


def rotate_point(point: Tuple[float, float], center: Tuple[float, float], angle: float) -> Tuple[float, float]:
    """Rotate a point around a center by an angle in degrees."""
    angle_rad = angle_to_radians(angle)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    
    new_x = center[0] + dx * cos_a - dy * sin_a
    new_y = center[1] + dx * sin_a + dy * cos_a
    
    return (new_x, new_y)


def point_in_rect(point: Tuple[float, float], rect: Tuple[float, float, float, float]) -> bool:
    """Check if point is inside rectangle (x, y, width, height)."""
    x, y = point
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def circle_circle_collision(
    pos1: Tuple[float, float], radius1: float,
    pos2: Tuple[float, float], radius2: float
) -> bool:
    """Check collision between two circles."""
    dist = distance(pos1, pos2)
    return dist < (radius1 + radius2)


def circle_rect_collision(
    circle_pos: Tuple[float, float], circle_radius: float,
    rect: Tuple[float, float, float, float]
) -> bool:
    """Check collision between circle and rectangle."""
    cx, cy = circle_pos
    rx, ry, rw, rh = rect
    
    # Find closest point on rectangle to circle center
    closest_x = max(rx, min(cx, rx + rw))
    closest_y = max(ry, min(cy, ry + rh))
    
    # Check if closest point is inside circle
    dist = distance((cx, cy), (closest_x, closest_y))
    return dist < circle_radius


def line_line_collision(
    line1_start: Tuple[float, float], line1_end: Tuple[float, float],
    line2_start: Tuple[float, float], line2_end: Tuple[float, float]
) -> bool:
    """Check if two line segments intersect."""
    x1, y1 = line1_start
    x2, y2 = line1_end
    x3, y3 = line2_start
    x4, y4 = line2_end
    
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-10:
        return False  # Lines are parallel
    
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    
    return 0 <= t <= 1 and 0 <= u <= 1


def circle_line_collision(
    circle_pos: Tuple[float, float], circle_radius: float,
    line_start: Tuple[float, float], line_end: Tuple[float, float]
) -> bool:
    """Check collision between circle and line segment."""
    cx, cy = circle_pos
    x1, y1 = line_start
    x2, y2 = line_end
    
    # Vector from line start to end
    dx = x2 - x1
    dy = y2 - y1
    line_len_sq = dx * dx + dy * dy
    
    if line_len_sq < 1e-10:
        # Line is a point
        return distance(circle_pos, line_start) < circle_radius
    
    # Vector from line start to circle center
    cx_rel = cx - x1
    cy_rel = cy - y1
    
    # Project circle center onto line
    t = max(0, min(1, (cx_rel * dx + cy_rel * dy) / line_len_sq))
    
    # Closest point on line to circle center
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    # Check distance
    dist = distance(circle_pos, (closest_x, closest_y))
    return dist < circle_radius


def get_angle_to_point(from_pos: Tuple[float, float], to_pos: Tuple[float, float]) -> float:
    """Get angle in degrees from one point to another."""
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]
    angle = math.degrees(math.atan2(dy, dx))
    return normalize_angle(angle)


def get_closest_point_on_line(
    point: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float]
) -> Tuple[float, float]:
    """Get the closest point on a line segment to a given point."""
    x, y = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    line_len_sq = dx * dx + dy * dy
    
    if line_len_sq < 1e-10:
        return line_start
    
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / line_len_sq))
    return (x1 + t * dx, y1 + t * dy)


def get_wall_normal(
    circle_pos: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float]
) -> Tuple[float, float]:
    """Get the normal vector from a wall pointing toward the circle."""
    closest = get_closest_point_on_line(circle_pos, line_start, line_end)
    
    # Vector from closest point to circle (this is the normal direction)
    dx = circle_pos[0] - closest[0]
    dy = circle_pos[1] - closest[1]
    
    # Normalize
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-10:
        # If circle is exactly on the line, use perpendicular to line
        line_dx = line_end[0] - line_start[0]
        line_dy = line_end[1] - line_start[1]
        line_len = math.sqrt(line_dx * line_dx + line_dy * line_dy)
        if line_len > 1e-10:
            # Perpendicular vector (rotated 90 degrees)
            dx = -line_dy / line_len
            dy = line_dx / line_len
        else:
            dx, dy = 1.0, 0.0
    else:
        dx /= length
        dy /= length
    
    return (dx, dy)


def reflect_velocity(
    velocity: Tuple[float, float],
    normal: Tuple[float, float],
    restitution: float = 0.85
) -> Tuple[float, float]:
    """Reflect a velocity vector off a surface with given normal.
    
    Uses coefficient of restitution for realistic energy loss on bounce.
    This function delegates to the implementation in utils.math_utils for consistency.
    
    Args:
        velocity: (vx, vy) velocity vector
        normal: (nx, ny) normalized normal vector pointing away from surface
        restitution: Coefficient of restitution (0.0 = perfectly inelastic, 1.0 = perfectly elastic).
                     Default 0.85 provides realistic bounce behavior.
    
    Returns:
        Reflected velocity vector (vx, vy)
    """
    # Delegate to math_utils implementation for consistency
    from utils.math_utils import reflect_velocity as _reflect_velocity
    return _reflect_velocity(velocity, normal, restitution)

