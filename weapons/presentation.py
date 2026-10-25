"""Weapon symbols shared by ground pickups and HUD."""
import pygame

def draw_symbol(screen, center, size, definition):
    x, y = center
    r = max(3, size)
    color = definition.color
    if definition.symbol in ('single', 'twin'):
        for offset in ((-0.45, 0.45) if definition.symbol == 'twin' else (0,)):
            pygame.draw.line(screen, color, (x + r*offset, y-r), (x+r*offset, y+r), 3)
    elif definition.symbol == 'fan':
        for offset in (-1, 0, 1):
            pygame.draw.line(screen, color, (x, y+r), (x+offset*r, y-r), 2)
    elif definition.symbol == 'needle':
        pygame.draw.polygon(screen, color, [(x,y-r*1.4),(x+r*.45,y+r),(x,y+r*.5),(x-r*.45,y+r)])
    elif definition.symbol == 'fork':
        pygame.draw.lines(screen, color, False, [(x-r,y),(x,y-r),(x+r,y)], 2)
        pygame.draw.line(screen, color, (x,y-r),(x,y+r), 3)
    elif definition.symbol == 'shell':
        pygame.draw.circle(screen, color, (round(x),round(y+r*.2)), round(r*.75), 2)
        pygame.draw.lines(screen, color, False, [(x,y-r*.5),(x+r*.3,y-r),(x+r*.7,y-r)], 2)
    elif definition.symbol == 'balloon':
        rect = pygame.Rect(0,0,round(r*1.5),round(r*1.8))
        rect.center = (round(x),round(y-r*.3))
        pygame.draw.ellipse(screen,color,rect,2)
        pygame.draw.lines(screen,color,False,[(x,y+r*.6),(x-r*.3,y+r),(x+r*.2,y+r*1.4)],1)
