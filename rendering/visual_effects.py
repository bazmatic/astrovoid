"""Visual effects utilities for rendering enhancements.

This module provides helper functions for common visual effects including
gradients, glow effects, and color interpolation.
"""

import pygame
import math
import random
from typing import Tuple, List, Dict, Optional
import config


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
        alpha = max(0, min(255, alpha))
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


class Starfield:
    """Animated starfield background for menus."""
    
    def __init__(self, width: int, height: int, star_count: int = None):
        """Initialize starfield.
        
        Args:
            width: Screen width.
            height: Screen height.
            star_count: Number of stars (defaults to config.STARFIELD_STAR_COUNT).
        """
        self.width = width
        self.height = height
        self.star_count = star_count if star_count is not None else config.STARFIELD_STAR_COUNT
        self.stars: List[Tuple[float, float, float, float]] = []  # (x, y, brightness, twinkle_phase)
        self._initialize_stars()
    
    def _initialize_stars(self) -> None:
        """Initialize star positions and properties."""
        self.stars = []
        for _ in range(self.star_count):
            x = random.uniform(0, self.width)
            y = random.uniform(0, self.height)
            brightness = random.uniform(0.3, 1.0)
            twinkle_phase = random.uniform(0, 2 * math.pi)
            self.stars.append((x, y, brightness, twinkle_phase))
    
    def update(self, dt: float) -> None:
        """Update starfield animation.
        
        Args:
            dt: Delta time (normalized to 60fps).
        """
        dt_seconds = dt / 60.0
        for i, (x, y, brightness, phase) in enumerate(self.stars):
            # Update twinkle phase
            new_phase = phase + config.STARFIELD_TWINKLE_SPEED * dt_seconds
            if new_phase >= 2 * math.pi:
                new_phase -= 2 * math.pi
            self.stars[i] = (x, y, brightness, new_phase)
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw starfield.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        for x, y, base_brightness, phase in self.stars:
            # Calculate twinkling brightness
            twinkle = 0.5 + 0.5 * math.sin(phase)
            brightness = base_brightness * (0.5 + 0.5 * twinkle)
            
            # Draw star (size varies with brightness)
            size = int(1 + brightness * 2)
            color_value = int(200 + 55 * brightness)
            color = (color_value, color_value, color_value)
            pygame.draw.circle(screen, color, (int(x), int(y)), size)


class MenuParticleSystem:
    """Simple particle system for menu background effects."""
    
    def __init__(self, width: int, height: int, particle_count: int = None):
        """Initialize particle system.
        
        Args:
            width: Screen width.
            height: Screen height.
            particle_count: Number of particles (defaults to config.MENU_PARTICLE_COUNT).
        """
        self.width = width
        self.height = height
        self.particle_count = particle_count if particle_count is not None else config.MENU_PARTICLE_COUNT
        self.particles: List[Tuple[float, float, float, float, Tuple[int, int, int]]] = []  # (x, y, vx, vy, color)
        self._initialize_particles()
    
    def _initialize_particles(self) -> None:
        """Initialize particle positions and velocities."""
        self.particles = []
        for _ in range(self.particle_count):
            x = random.uniform(0, self.width)
            y = random.uniform(0, self.height)
            vx = random.uniform(-0.5, 0.5)
            vy = random.uniform(-0.5, 0.5)
            # Subtle cyan/blue particles
            color = (
                random.randint(50, 150),
                random.randint(150, 255),
                random.randint(200, 255)
            )
            self.particles.append((x, y, vx, vy, color))
    
    def update(self, dt: float) -> None:
        """Update particle positions.
        
        Args:
            dt: Delta time (normalized to 60fps).
        """
        dt_seconds = dt / 60.0
        new_particles = []
        for x, y, vx, vy, color in self.particles:
            # Update position
            new_x = x + vx * dt_seconds * 10
            new_y = y + vy * dt_seconds * 10
            
            # Wrap around screen
            if new_x < 0:
                new_x = self.width
            elif new_x > self.width:
                new_x = 0
            if new_y < 0:
                new_y = self.height
            elif new_y > self.height:
                new_y = 0
            
            new_particles.append((new_x, new_y, vx, vy, color))
        self.particles = new_particles
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw particles.
        
        Args:
            screen: The pygame Surface to draw on.
        """
        for x, y, _, _, color in self.particles:
            # Draw small, semi-transparent particles
            alpha_surf = pygame.Surface((3, 3), pygame.SRCALPHA)
            alpha_color = (*color, 80)  # Low alpha for subtlety
            pygame.draw.circle(alpha_surf, alpha_color, (1, 1), 1)
            screen.blit(alpha_surf, (int(x) - 1, int(y) - 1))


def draw_neon_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    position: Tuple[int, int],
    color_start: Tuple[int, int, int],
    color_end: Tuple[int, int, int],
    glow_intensity: float = None,
    pulse_phase: float = 0.0,
    center: bool = True
) -> None:
    """Draw text with neon glow effect.
    
    Args:
        screen: The pygame Surface to draw on.
        text: Text to render.
        font: Font to use.
        position: (x, y) position or center point if center=True.
        color_start: Start color for gradient.
        color_end: End color for gradient.
        glow_intensity: Glow intensity (defaults to config.NEON_GLOW_INTENSITY).
        pulse_phase: Phase for pulsing animation (0.0 to 2*pi).
        center: If True, position is treated as center point.
    """
    if glow_intensity is None:
        glow_intensity = config.NEON_GLOW_INTENSITY
    
    # Calculate pulsing intensity
    pulse = 0.5 + 0.5 * math.sin(pulse_phase)
    current_intensity = glow_intensity * (0.7 + 0.3 * pulse)
    
    # Render text surface
    text_surface = font.render(text, True, (255, 255, 255))
    text_rect = text_surface.get_rect()
    if center:
        text_rect.center = position
    else:
        text_rect.topleft = position
    
    # Draw multiple glow layers
    glow_radius = 8
    for layer in range(int(glow_radius)):
        layer_radius = glow_radius - layer
        alpha = int(255 * current_intensity * (1.0 - layer / glow_radius))
        if alpha > 0:
            # Create glow surface
            glow_surf = pygame.Surface((text_rect.width + layer_radius * 2, text_rect.height + layer_radius * 2), pygame.SRCALPHA)
            
            # Draw text multiple times with offset for glow
            for offset_x in range(-layer_radius, layer_radius + 1, 2):
                for offset_y in range(-layer_radius, layer_radius + 1, 2):
                    if offset_x * offset_x + offset_y * offset_y <= layer_radius * layer_radius:
                        # Interpolate color based on position
                        t = (offset_x + offset_y) / (layer_radius * 2)
                        glow_color = interpolate_color(color_start, color_end, abs(t))
                        glow_color_alpha = (*glow_color, alpha // 3)
                        temp_surf = font.render(text, True, glow_color_alpha)
                        glow_surf.blit(temp_surf, (layer_radius + offset_x, layer_radius + offset_y))
            
            screen.blit(glow_surf, (text_rect.x - layer_radius, text_rect.y - layer_radius))
    
    # Draw main text with gradient effect
    # Simple approach: draw text multiple times with slight color variation
    for i in range(3):
        t = i / 2.0
        text_color = interpolate_color(color_start, color_end, t)
        text_surf = font.render(text, True, text_color)
        screen.blit(text_surf, text_rect)


def draw_button_glow(
    screen: pygame.Surface,
    rect: pygame.Rect,
    color: Tuple[int, int, int],
    intensity: float = None,
    pulse_phase: float = 0.0
) -> None:
    """Draw glow effect around a button rectangle.
    
    Args:
        screen: The pygame Surface to draw on.
        rect: Button rectangle.
        color: Glow color.
        intensity: Glow intensity (defaults to config.BUTTON_GLOW_INTENSITY).
        pulse_phase: Phase for pulsing animation (0.0 to 2*pi).
    """
    if intensity is None:
        intensity = config.BUTTON_GLOW_INTENSITY
    
    # Calculate pulsing intensity
    pulse = 0.5 + 0.5 * math.sin(pulse_phase)
    current_intensity = intensity * (0.7 + 0.3 * pulse)
    
    # Draw glow layers
    glow_size = 6
    for layer in range(glow_size):
        layer_size = glow_size - layer
        alpha = int(255 * current_intensity * (1.0 - layer / glow_size))
        if alpha > 0:
            glow_color = (*color, alpha)
            glow_rect = pygame.Rect(
                rect.x - layer_size,
                rect.y - layer_size,
                rect.width + layer_size * 2,
                rect.height + layer_size * 2
            )
            glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, glow_color, (0, 0, glow_rect.width, glow_rect.height), layer_size + 1)
            screen.blit(glow_surf, glow_rect.topleft)

