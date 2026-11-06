"""Draws a team battle (Flockers vs Wallcrawlers): the arena and its gates, the creatures and their shots, how many
each contender has left in its colour, and the end banner."""
import pygame

import config
from rendering.fonts import get_font
from rendering.gates import draw_gate

def banner_text(result):
    if result.winner is not None:
        return f'{result.winner.upper()} WIN'
    return 'DRAW: TIME UP' if result.reason == 'timeout' else 'DRAW'


def draw_battle(screen, battle):
    battle.maze.draw(screen)
    for gate in battle.obstacles.gates if battle.obstacles else ():
        draw_gate(screen, gate.pin, gate.angle, gate.half_length, gate.thickness, gate.motor)
    for name in battle.sides:
        battle.rosters[name].draw(screen)
        for shot in battle.shots(name):
            shot.draw(screen)
    font = get_font(30)
    contenders = battle.contenders()
    for i, name in enumerate(contenders):
        count = font.render(f'{name.upper()}  {len(battle.alive(name))}', True, battle.sides[name].colour)
        screen.blit(count, count.get_rect(center=(config.SCREEN_WIDTH * (2 * i + 1) // (2 * len(contenders)), 24)))
    if battle.result is not None:
        font = get_font(96)
        text = font.render(banner_text(battle.result), True, (255, 255, 255))
        rect = text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2))
        pygame.draw.rect(screen, (10, 10, 30), rect.inflate(60, 40), border_radius=12)
        pygame.draw.rect(screen, (215, 225, 255), rect.inflate(60, 40), 2, border_radius=12)
        screen.blit(text, rect)
