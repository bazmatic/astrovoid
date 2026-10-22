"""Shared plume rendering and particle animation, independent of a ship class."""
import math
import random
import pygame
import config
from utils import angle_to_radians


def draw_thrust_plume(body, screen, min_length=0.0):
    # Draw enhanced thrust visualization (only when actively thrusting)
    # Check if we have active thrust particles (from previous frame's thrust)
    # or if thrusting flag is currently set (from this frame's apply_thrust call)
    has_thrust_effect = body.thrusting or len(body.thrust_particles) > 0 or min_length > 0
    if has_thrust_effect:
        angle_rad = angle_to_radians(body.angle)
        base_x = body.x - math.cos(angle_rad) * body.radius * 0.8
        base_y = body.y - math.sin(angle_rad) * body.radius * 0.8
        
        # Calculate speed for plume length
        speed = math.sqrt(body.vx * body.vx + body.vy * body.vy)
        
        # Draw particle trail
        for particle in body.thrust_particles:
            particle_x = body.x + particle['x']
            particle_y = body.y + particle['y']
            life_ratio = particle['life'] / config.THRUST_PLUME_LENGTH
            
            # Color gradient: yellow -> orange -> red
            if life_ratio > 0.6:
                color = (255, 255, 100)  # Yellow
            elif life_ratio > 0.3:
                color = (255, 180, 50)   # Orange
            else:
                color = (255, 100, 50)   # Red
            
            size = int(particle['size'] * life_ratio)
            if size > 0:
                pygame.draw.circle(screen, color, 
                                 (int(particle_x), int(particle_y)), size)
        
        # Draw cone-shaped thrust plume
        plume_length = max(min_length, min(config.THRUST_PLUME_LENGTH, speed * 2))
        for i in range(config.THRUST_PLUME_PARTICLES):
            t = i / config.THRUST_PLUME_PARTICLES
            plume_x = base_x - math.cos(angle_rad) * plume_length * t
            plume_y = base_y - math.sin(angle_rad) * plume_length * t
            
            # Size decreases along plume
            size = int(4 * (1 - t))
            if size > 0:
                # Color gradient
                if t < 0.3:
                    color = (255, 255, 150)  # Bright yellow
                elif t < 0.6:
                    color = (255, 200, 50)   # Orange
                else:
                    color = (255, 100, 0)    # Red
                
                # Add some randomness for flicker
                flicker = random.uniform(0.8, 1.0)
                flicker_color = tuple(int(c * flicker) for c in color)
                pygame.draw.circle(screen, flicker_color,
                                 (int(plume_x), int(plume_y)), size)



def advance_thrust_particles(body, dt):
    # Update thrust particles (only when thrusting from previous frame)
    speed = math.sqrt(body.vx * body.vx + body.vy * body.vy)
    if body.pilot_thrusting and speed > 0.0:
        # Add new particles based on speed
        angle_rad = angle_to_radians(body.angle)
        for _ in range(int(speed * 0.5)):
            if len(body.thrust_particles) < config.THRUST_PLUME_PARTICLES * 3:
                particle_x = -math.cos(angle_rad) * body.radius * 0.8
                particle_y = -math.sin(angle_rad) * body.radius * 0.8
                particle_vx = -math.cos(angle_rad) * speed * 0.3
                particle_vy = -math.sin(angle_rad) * speed * 0.3
                body.thrust_particles.append({
                    'x': particle_x,
                    'y': particle_y,
                    'vx': particle_vx,
                    'vy': particle_vy,
                    'life': config.THRUST_PLUME_LENGTH,
                    'size': random.uniform(2, 4)
                })
    
    # Update existing particles (use list comprehension instead of remove)
    for particle in body.thrust_particles:
        particle['x'] += particle['vx'] * dt
        particle['y'] += particle['vy'] * dt
        particle['life'] -= 1
    # Filter out dead particles
    body.thrust_particles = [p for p in body.thrust_particles if p['life'] > 0]
    
