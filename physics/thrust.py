"""The physics of a body that flies like a ship: thrust along its heading, coast with friction, bounce off the screen
edges, sweep into walls without tunnelling, and turn toward a heading.

Each function acts on any object with `x`, `y`, `vx`, `vy`, `angle`, `radius`, `prev_x` and `prev_y`: the thruster
ships (`RotatingThrusterShip` and its subclasses) and Creatures with the `thrusters` trait alike.
"""
import math

import config
from utils import (
    angle_to_radians,
    circle_line_collision,
    circle_line_collision_swept,
    distance_squared,
    get_closest_point_on_line,
    get_wall_normal,
    normalize_angle,
)
from utils.math_utils import apply_wall_collision_physics


def apply_thrust(body, force: float, max_speed: float) -> None:
    """Add `force` along the body's heading, then cap its speed at `max_speed`."""
    angle_rad = angle_to_radians(body.angle)
    body.vx += math.cos(angle_rad) * force
    body.vy += math.sin(angle_rad) * force
    cap_speed(body, max_speed)


def cap_speed(body, max_speed: float) -> None:
    """Scale the body's velocity down to `max_speed` if it is faster."""
    speed = math.sqrt(body.vx * body.vx + body.vy * body.vy)
    if speed > max_speed:
        scale = max_speed / speed
        body.vx *= scale
        body.vy *= scale


def coast(body, dt: float, friction: float) -> int:
    """Remember where the body was, apply friction and move it, then bounce it off the screen edges. Returns how many
    edges it bounced off."""
    body.prev_x = body.x
    body.prev_y = body.y
    body.vx *= friction
    body.vy *= friction
    body.x += body.vx * dt
    body.y += body.vy * dt
    edges = 0
    if body.x < body.radius:
        body.x = body.radius
        apply_wall_collision_physics(body, (1.0, 0.0), config.COLLISION_RESTITUTION)
        edges += 1
    elif body.x > config.SCREEN_WIDTH - body.radius:
        body.x = config.SCREEN_WIDTH - body.radius
        apply_wall_collision_physics(body, (-1.0, 0.0), config.COLLISION_RESTITUTION)
        edges += 1
    if body.y < body.radius:
        body.y = body.radius
        apply_wall_collision_physics(body, (0.0, 1.0), config.COLLISION_RESTITUTION)
        edges += 1
    elif body.y > config.SCREEN_HEIGHT - body.radius:
        body.y = config.SCREEN_HEIGHT - body.radius
        apply_wall_collision_physics(body, (0.0, -1.0), config.COLLISION_RESTITUTION)
        edges += 1
    return edges


def turn_toward(body, heading: float, rate: float) -> None:
    """Snap to `heading` when it is within `rate` degrees, else turn `rate` degrees the shorter way toward it."""
    diff = (heading - body.angle + 180.0) % 360.0 - 180.0
    if abs(diff) < rate:
        body.angle = heading
    else:
        body.angle = normalize_angle(body.angle + (rate if diff > 0 else -rate))


def sweep_walls(body, walls, spatial_grid=None) -> bool:
    """Check the body's path from (prev_x, prev_y) to (x, y) against the walls, so a fast body cannot tunnel through
    one. On a hit it is stopped at the wall, pushed clear and bounced; a body already inside a wall is pushed out.
    True on a hit."""

    # Use swept collision detection to find earliest collision
    earliest_collision = None
    earliest_time = 1.0  # Start with end of path
    collision_wall = None
    
    start_pos = (body.prev_x, body.prev_y)
    end_pos = (body.x, body.y)
    
    # Use spatial grid if available, otherwise check all walls
    walls_to_check = walls
    if spatial_grid is not None:
        # Get walls along the entire movement path to prevent tunneling
        # This ensures walls near both start and end positions are checked
        walls_to_check = spatial_grid.get_walls_along_path(
            start_pos, end_pos, body.radius * 2.0  # Check slightly larger area
        )
    
    # Check walls for collisions along movement path
    for wall in walls_to_check:
        # Handle both WallSegment and tuple formats
        if hasattr(wall, 'get_segment'):
            # WallSegment instance
            if not wall.active:
                continue
            segment = wall.get_segment()
        else:
            # Tuple format (backward compatibility)
            segment = wall
        
        collision_detected, collision_time, collision_point = circle_line_collision_swept(
            start_pos, end_pos, body.radius,
            segment[0], segment[1]
        )
        
        if collision_detected and collision_time is not None:
            # Found a collision - check if it's earlier than previous
            if collision_time < earliest_time:
                earliest_time = collision_time
                earliest_collision = collision_point
                collision_wall = segment
    
    # If no collision found, also check if ship is already inside a wall
    # (can happen if ship spawns in wall or previous frame had issues)
    if earliest_collision is None:
        for wall in walls_to_check:
            # Handle both WallSegment and tuple formats
            if hasattr(wall, 'get_segment'):
                if not wall.active:
                    continue
                segment = wall.get_segment()
            else:
                segment = wall
            
            if circle_line_collision(
                (body.x, body.y), body.radius,
                segment[0], segment[1]
            ):
                # Ship is already inside wall - push out immediately
                normal = get_wall_normal((body.x, body.y), segment[0], segment[1])
                
                # Calculate penetration depth
                closest_point = get_closest_point_on_line((body.x, body.y), segment[0], segment[1])
                dist_to_wall_sq = distance_squared((body.x, body.y), closest_point)
                dist_to_wall = math.sqrt(dist_to_wall_sq)
                penetration_depth = body.radius - dist_to_wall
                
                # Push back by penetration depth + safety margin
                push_distance = penetration_depth + body.radius * 0.5
                body.x += normal[0] * push_distance
                body.y += normal[1] * push_distance
                
                # Reflect velocity using physics
                apply_wall_collision_physics(body, normal, config.COLLISION_RESTITUTION)
                
                return True
    
    # Handle swept collision
    if earliest_collision is not None and collision_wall is not None:
        # Move ship to collision point (or slightly before to be safe)
        # Use a small epsilon before collision point to ensure we're not inside wall
        safe_time = max(0.0, earliest_time - 0.01)
        body.x = body.prev_x + (body.x - body.prev_x) * safe_time
        body.y = body.prev_y + (body.y - body.prev_y) * safe_time
        
        # Get wall normal at collision point
        normal = get_wall_normal((body.x, body.y), collision_wall[0], collision_wall[1])
        
        # Calculate penetration depth (how far inside wall we are)
        closest_point = get_closest_point_on_line((body.x, body.y), collision_wall[0], collision_wall[1])
        dist_to_wall_sq = distance_squared((body.x, body.y), closest_point)
        dist_to_wall = math.sqrt(dist_to_wall_sq)
        penetration_depth = max(0.0, body.radius - dist_to_wall)
        
        # Push ship away from wall
        # Use penetration depth + safety margin to ensure complete clearance
        push_distance = penetration_depth + body.radius * 0.5
        body.x += normal[0] * push_distance
        body.y += normal[1] * push_distance
        
        # Reflect velocity off the wall using physics
        apply_wall_collision_physics(body, normal, config.COLLISION_RESTITUTION)
        
        return True
    
    return False

