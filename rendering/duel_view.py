"""Draws the pilot duel: the maze, both hunters with name tags and health pips, bullets, and the end banner."""
import pygame

import config
from rendering.fonts import get_font

TAGS = {'rules': 'RULES', 'vibes': 'VIBES'}


def banner_text(result):
    if result.winner is not None:
        return f'{TAGS.get(result.winner, result.winner.upper())} WINS'
    return 'DRAW: TIME UP' if result.reason == 'timeout' else 'DRAW'


def draw_duel(screen, arena):
    arena.maze.draw(screen)
    if arena.enemies is not None:
        arena.enemies.roster.draw(screen)
        for bullet in arena.enemies.bullets:
            bullet.draw(screen)
    tag_font = get_font(22)
    for side in arena.sides:
        for shot in arena.shots[side.name]:
            shot.draw(screen)
    for side in arena.sides:
        hunter = side.hunter
        if hunter.active:
            hunter.draw(screen)
        colour = hunter.COLOR
        tag = tag_font.render(TAGS.get(side.name, side.name.upper()), True, colour)
        screen.blit(tag, tag.get_rect(center=(int(hunter.x), int(hunter.y - hunter.radius * 3.2))))
        for pip in range(max(hunter.settings.health, 0)):
            x = int(hunter.x + (pip - (hunter.settings.health - 1) / 2) * 9)
            y = int(hunter.y - hunter.radius * 2.2)
            pygame.draw.circle(screen, colour, (x, y), 3, 0 if pip < max(hunter.health, 0) else 1)
    if arena.result is not None:
        font = get_font(96)
        text = font.render(banner_text(arena.result), True, (255, 255, 255))
        rect = text.get_rect(center=(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2))
        pygame.draw.rect(screen, (10, 10, 30), rect.inflate(60, 40), border_radius=12)
        pygame.draw.rect(screen, (215, 225, 255), rect.inflate(60, 40), 2, border_radius=12)
        screen.blit(text, rect)
