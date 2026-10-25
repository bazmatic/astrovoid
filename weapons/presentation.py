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
    elif definition.symbol == 'shield':
        pygame.draw.polygon(screen,color,[(x-r,y-r*.8),(x,y-r),(x+r,y-r*.8),
                                         (x+r*.8,y+r*.4),(x,y+r),(x-r*.8,y+r*.4)],2)
    elif definition.symbol == 'balloon':
        rect = pygame.Rect(0,0,round(r*1.5),round(r*1.8))
        rect.center = (round(x),round(y-r*.3))
        pygame.draw.ellipse(screen,color,rect,2)
        pygame.draw.lines(screen,color,False,[(x,y+r*.6),(x-r*.3,y+r),(x+r*.2,y+r*1.4)],1)


def draw_inventory(screen, inventory, rect):
    """Pickup-order slots: selected outline, remaining ammo, and dim empty weapons."""
    import config
    from rendering.fonts import get_font
    views = inventory.inventory
    columns = min(4,len(views))
    rows = (len(views)+columns-1)//columns
    slot_width = rect.width/columns
    slot_height = min(46,max(32,(rect.height-24)/rows))
    font = get_font(max(10,round(14*min(1,rect.height/112))))
    for index,view in enumerate(views):
        definition = inventory.catalog[view.id]
        slot = pygame.Rect(rect.x+(index%columns)*slot_width,
                           rect.y+(index//columns)*slot_height,slot_width-4,slot_height-4)
        selected = view.id == inventory.weapon_id
        empty = view.ammo == 0
        color = (65,70,85) if empty else definition.color
        pygame.draw.rect(screen,(24,30,44),slot,border_radius=5)
        pygame.draw.rect(screen,color if selected else (48,55,70),slot,2 if selected else 1,border_radius=5)
        icon_size = min(24,max(12,slot.height-font.get_height()-5))
        icon = pygame.Surface((icon_size,icon_size),pygame.SRCALPHA)
        draw_symbol(icon,(icon_size/2,icon_size/2),icon_size*.28,definition)
        if empty:
            icon.set_alpha(65)
        screen.blit(icon,icon.get_rect(midtop=(slot.centerx,slot.top+2)))
        text = ('EMPTY' if empty else '∞' if view.ammo is None
                else f'{view.ammo/config.FPS:.1f}s' if definition.behaviour == 'shield'
                else str(view.ammo))
        label = font.render(text,True,color)
        screen.blit(label,label.get_rect(midbottom=(slot.centerx,slot.bottom-1)))
    hint = 'DOWN: NEXT'
    if inventory.definition.behaviour == 'shield':
        hint += '  FIRE: ' + ('OFF' if inventory.shield_active else 'ON')
    label = font.render(hint,True,(175,190,210))
    if label.get_width() > rect.width:
        label = pygame.transform.smoothscale(label,(rect.width,label.get_height()))
    screen.blit(label,(rect.x,rect.y+rows*slot_height+3))
