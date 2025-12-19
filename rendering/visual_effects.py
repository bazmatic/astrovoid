"""Visual effects utilities for rendering enhancements.

This module provides helper functions for common visual effects including
gradients, glow effects, and color interpolation.
"""

import pygame
import math
from typing import Tuple, List


def interpolate_color(
    color1: Tuple[int, int, int],
    color2: Tuple[int, int, int],
    t: float
) -> Tuple[int, int, int]:
    """Interpolate between two colors.
    
    Args:
        color1: First color (R, G, B).
        color2: Second color (R, G, B).
        t: Interpolation factor (0.0 = color1, 1.0 = color2).
        
    Returns:
        Interpolated color (R, G, B).
    """
    t = max(0.0, min(1.0, t))
    r = int(color1[0] * (1 - t) + color2[0] * t)
    g = int(color1[1] * (1 - t) + color2[1] * t)
    b = int(color1[2] * (1 - t) + color2[2] * t)
    return (r, g, b)


def draw_gradient_polygon(
    screen: pygame.Surface,
    vertices: List[Tuple[float, float]],
    color_start: Tuple[int, int, int],
    color_end: Tuple[int, int, int],
    start_vertex: int = 0,
    end_vertex: int = -1
) -> None:
    """Draw a polygon with gradient fill.
    
    Uses a simplified approach: draws the polygon with interpolated colors
    along the gradient direction from start_vertex to end_vertex.
    
    Args:
        screen: The pygame Surface to draw on.
        vertices: List of (x, y) vertex coordinates.
        color_start: Color at start vertex.
        color_end: Color at end vertex.
        start_vertex: Index of start vertex for gradient.
        end_vertex: Index of end vertex for gradient (-1 for last).
    """
    if len(vertices) < 3:
        return
    
    if end_vertex == -1:
        end_vertex = len(vertices) - 1
    
    start_pos = vertices[start_vertex]
    end_pos = vertices[end_vertex]
    
    # Calculate gradient direction vector
    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    dist_total = math.sqrt(dx * dx + dy * dy) if (dx != 0 or dy != 0) else 1
    
    # Find bounding box
    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)
    
    width = int(max_x - min_x) + 2
    height = int(max_y - min_y) + 2
    
    if width <= 0 or height <= 0:
        return
    
    # Create surface with alpha for gradient
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    offset_vertices = [(v[0] - min_x, v[1] - min_y) for v in vertices]
    offset_start = (start_pos[0] - min_x, start_pos[1] - min_y)
    
    # Fill polygon with gradient using point-in-polygon and gradient calculation
    # For each pixel in bounding box, check if in polygon and calculate gradient
    for y in range(height):
        for x in range(width):
            # Simple point-in-polygon test
            inside = False
            j = len(offset_vertices) - 1
            for i in range(len(offset_vertices)):
                vi = offset_vertices[i]
                vj = offset_vertices[j]
                if ((vi[1] > y) != (vj[1] > y)) and (x < (vj[0] - vi[0]) * (y - vi[1]) / (vj[1] - vi[1]) + vi[0]):
                    inside = not inside
                j = i
            
            if inside:
                # Calculate gradient factor
                px = x - offset_start[0]
                py = y - offset_start[1]
                if dist_total > 0:
                    proj = (px * dx + py * dy) / (dist_total * dist_total)
                    t = max(0.0, min(1.0, proj))
                else:
                    t = 0.0
                
                color = interpolate_color(color_start, color_end, t)
                surf.set_at((x, y), color)
    
    # Draw the gradient surface
    screen.blit(surf, (min_x, min_y))


def create_glow_surface(
    radius: float,
    glow_radius: float,
    color: Tuple[int, int, int],
    intensity: float = 0.3
) -> pygame.Surface:
    """Create a glow surface for alpha blending.
    
    Args:
        radius: Base radius of the object.
        glow_radius: Additional radius for glow effect.
        color: Glow color (R, G, B).
        intensity: Glow intensity (0.0 to 1.0).
        
    Returns:
        Surface with glow effect.
    """
    size = int((radius + glow_radius) * 2) + 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    
    center = size // 2
    max_radius = radius + glow_radius
    
    # Draw multiple layers for smooth glow
    for layer in range(int(glow_radius)):
        layer_radius = radius + glow_radius - layer
        alpha = int(255 * intensity * (1.0 - layer / glow_radius))
        if alpha > 0 and layer_radius > 0:
            glow_color = (*color, alpha)
            pygame.draw.circle(surf, glow_color, (center, center), int(layer_radius))
    
    return surf


def draw_glow_circle(
    screen: pygame.Surface,
    center: Tuple[float, float],
    radius: float,
    color: Tuple[int, int, int],
    glow_radius: float = None,
    intensity: float = 0.3
) -> None:
    """Draw a circle with glow effect.
    
    Args:
        screen: The pygame Surface to draw on.
        center: Center position (x, y).
        radius: Circle radius.
        color: Circle color (R, G, B).
        glow_radius: Additional radius for glow (defaults to radius * 0.5).
        intensity: Glow intensity (0.0 to 1.0).
    """
    if glow_radius is None:
        glow_radius = radius * 0.5
    
    # Create glow surface
    glow_surf = create_glow_surface(radius, glow_radius, color, intensity)
    
    # Blit glow
    glow_pos = (center[0] - glow_surf.get_width() // 2, center[1] - glow_surf.get_height() // 2)
    screen.blit(glow_surf, glow_pos)
    
    # Draw main circle
    pygame.draw.circle(screen, color, (int(center[0]), int(center[1])), int(radius))
    pygame.draw.circle(screen, (255, 255, 255), (int(center[0]), int(center[1])), int(radius), 2)


def draw_glow_polygon(
    screen: pygame.Surface,
    vertices: List[Tuple[float, float]],
    color: Tuple[int, int, int],
    glow_radius: float = 3.0,
    intensity: float = 0.3
) -> None:
    """Draw a polygon with glow effect.
    
    Args:
        screen: The pygame Surface to draw on.
        vertices: List of (x, y) vertex coordinates.
        color: Polygon color (R, G, B).
        glow_radius: Additional radius for glow.
        intensity: Glow intensity (0.0 to 1.0).
    """
    if len(vertices) < 3:
        return
    
    # Find bounding box
    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)
    
    width = int(max_x - min_x) + int(glow_radius * 2) + 4
    height = int(max_y - min_y) + int(glow_radius * 2) + 4
    
    if width <= 0 or height <= 0:
        return
    
    # Create surface for glow
    glow_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    
    # Offset vertices
    offset_x = int(glow_radius) + 2
    offset_y = int(glow_radius) + 2
    offset_vertices = [(v[0] - min_x + offset_x, v[1] - min_y + offset_y) for v in vertices]
    
    # Draw glow layers
    for layer in range(int(glow_radius * 2)):
        layer_alpha = int(255 * intensity * (1.0 - layer / (glow_radius * 2)))
        if layer_alpha > 0:
            # Expand polygon slightly for each layer
            expanded = []
            center_x = sum(v[0] for v in offset_vertices) / len(offset_vertices)
            center_y = sum(v[1] for v in offset_vertices) / len(offset_vertices)
            
            for v in offset_vertices:
                dx = v[0] - center_x
                dy = v[1] - center_y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    expand = layer / 2.0
                    expanded.append((v[0] + dx / dist * expand, v[1] + dy / dist * expand))
                else:
                    expanded.append(v)
            
            glow_color = (*color, layer_alpha)
            if len(expanded) >= 3:
                pygame.draw.polygon(glow_surf, glow_color, expanded)
    
    # Blit glow
    screen.blit(glow_surf, (min_x - offset_x, min_y - offset_y))
    
    # Draw main polygon
    pygame.draw.polygon(screen, color, vertices)

