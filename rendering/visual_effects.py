"""Visual effects utilities for rendering enhancements.

This module provides helper functions for common visual effects including
gradients, glow effects, and color interpolation.
"""

import pygame
import math
from typing import Tuple, List, Dict, Optional


# Cache for glow surfaces to avoid recreating them every frame
_glow_surface_cache: Dict[Tuple[float, float, Tuple[int, int, int], float], pygame.Surface] = {}


def _get_cache_key(radius: float, glow_radius: float, color: Tuple[int, int, int], intensity: float) -> Tuple[float, float, Tuple[int, int, int], float]:
    """Generate cache key for glow surface.
    
    Args:
        radius: Base radius.
        glow_radius: Glow radius.
        color: Glow color.
        intensity: Glow intensity.
        
    Returns:
        Cache key tuple.
    """
    # Round values to reduce cache size (allow small variations)
    return (round(radius, 1), round(glow_radius, 1), color, round(intensity, 2))


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
    """Draw a polygon with gradient fill (optimized approximation).
    
    Uses a simplified approach: draws multiple triangles with interpolated colors
    instead of pixel-by-pixel rendering for much better performance.
    
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
    
    # For triangles (ship), use simple gradient between vertices
    if len(vertices) == 3:
        # Draw filled polygon with gradient approximation using multiple triangles
        # Split polygon into triangles from start vertex
        v0 = vertices[start_vertex]
        v1 = vertices[(start_vertex + 1) % len(vertices)]
        v2 = vertices[(start_vertex + 2) % len(vertices)]
        
        # Draw two triangles with interpolated colors
        # Triangle 1: v0 (start color) to v1 (mid color)
        mid_color = interpolate_color(color_start, color_end, 0.5)
        pygame.draw.polygon(screen, color_start, [v0, v1, v2])
        # Draw a smaller triangle with end color for gradient effect
        center = ((v0[0] + v1[0] + v2[0]) / 3, (v0[1] + v1[1] + v2[1]) / 3)
        pygame.draw.polygon(screen, color_end, [
            center,
            ((v0[0] + v1[0]) / 2, (v0[1] + v1[1]) / 2),
            ((v0[0] + v2[0]) / 2, (v0[1] + v2[1]) / 2)
        ])
    else:
        # For other polygons, use simpler approach: draw with average color
        avg_color = interpolate_color(color_start, color_end, 0.5)
        pygame.draw.polygon(screen, avg_color, vertices)


def create_glow_surface(
    radius: float,
    glow_radius: float,
    color: Tuple[int, int, int],
    intensity: float = 0.3
) -> pygame.Surface:
    """Create a glow surface for alpha blending (cached for performance).
    
    Args:
        radius: Base radius of the object.
        glow_radius: Additional radius for glow effect.
        color: Glow color (R, G, B).
        intensity: Glow intensity (0.0 to 1.0).
        
    Returns:
        Surface with glow effect.
    """
    # Check cache first
    cache_key = _get_cache_key(radius, glow_radius, color, intensity)
    if cache_key in _glow_surface_cache:
        return _glow_surface_cache[cache_key]
    
    # Create new surface
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
    
    # Cache the surface (limit cache size to prevent memory issues)
    if len(_glow_surface_cache) < 50:  # Limit to 50 cached surfaces
        _glow_surface_cache[cache_key] = surf
    
    return surf


def draw_glow_circle(
    screen: pygame.Surface,
    center: Tuple[float, float],
    radius: float,
    color: Tuple[int, int, int],
    glow_radius: float = None,
    intensity: float = 0.3
) -> None:
    """Draw a circle with glow effect (uses cached glow surfaces).
    
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
    
    # Get cached glow surface
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

