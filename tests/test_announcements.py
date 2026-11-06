"""Important announcements, shown in the centre of the playfield until dismissed, then faded out."""
import pygame

import config
from rendering.announcements import Announcer

SIZE = (1352, 878)


def drawn(announcer):
    screen = pygame.Surface(SIZE)
    screen.fill((0, 0, 0))
    announcer.draw(screen)
    return screen


def brightness(screen, rect):
    """Total brightness of the pixels in an area."""
    area = screen.subsurface(rect)
    return sum(sum(area.get_at((x, y))[:3]) for x in range(0, area.get_width(), 2) for y in range(0, area.get_height(), 2))


def playfield_centre():
    return pygame.Rect(config.UI_ZONE_WIDTH, SIZE[1] // 2 - 60, SIZE[0] - config.UI_ZONE_WIDTH, 120)


def side_panel():
    return pygame.Rect(0, 0, config.UI_ZONE_WIDTH, SIZE[1])


def shown(heading='MISSION', text='Destroy every Egg to open the exit'):
    announcer = Announcer()
    announcer.show(heading, text)
    announcer.update(60.0)   # fully faded in
    return announcer


def test_an_announcement_shows_in_the_middle_of_the_playfield():
    screen = drawn(shown())
    assert brightness(screen, playfield_centre()) > 0
    assert brightness(screen, side_panel()) == 0


def test_nothing_shows_without_an_announcement():
    assert brightness(drawn(Announcer()), playfield_centre()) == 0


def test_it_stays_until_dismissed():
    announcer = shown()
    announcer.update(600.0)
    assert brightness(drawn(announcer), playfield_centre()) > 0


def test_once_dismissed_it_fades_away():
    announcer = shown()
    full = brightness(drawn(announcer), playfield_centre())
    announcer.dismiss()
    announcer.update(30.0)
    assert 0 < brightness(drawn(announcer), playfield_centre()) < full
    announcer.update(40.0)
    assert brightness(drawn(announcer), playfield_centre()) == 0


def test_a_new_announcement_replaces_the_old():
    announcer = shown(text='Destroy every enemy to open the exit')
    announcer.show('MISSION', 'Go')
    announcer.update(60.0)
    replaced = brightness(drawn(announcer), playfield_centre())
    assert 0 < replaced < brightness(drawn(shown(text='Destroy every enemy to open the exit')), playfield_centre())


def test_clearing_removes_it_at_once():
    announcer = shown()
    announcer.clear()
    assert brightness(drawn(announcer), playfield_centre()) == 0
