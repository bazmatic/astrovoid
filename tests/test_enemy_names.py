import enemy_names
from level_layout import ENEMY_TYPES


def test_every_enemy_kind_has_a_name_and_a_plural():
    assert set(enemy_names.ENEMY_NAMES) == set(ENEMY_TYPES) | {'baby'}
    assert enemy_names.KINDS == ENEMY_TYPES + ('baby',)


def test_the_names_chosen_for_the_game():
    expected = {'static': ('Urchin', 'Urchins'), 'patrol': ('Crab', 'Crabs'), 'aggressive': ('Jelly', 'Jellies'),
                'replay': ('Squiddler', 'Squiddlers'), 'flocker': ('Flocker', 'Flockers'),
                'flighthouse': ('Flighthouse', 'Flighthouses'), 'egg': ('Egg', 'Eggs'),
                'baby': ('Squidlet', 'Squidlets'), 'anemone': ('Anemone', 'Anemones'),
                'split_boss': ('Squiddler Boss', 'Squiddler Bosses'), 'mother_boss': ('Mother', 'Mothers'),
                'rules_hunter': ('Terminator', 'Terminators'), 'neural_hunter': ('Viber', 'Vibers'),
                'boss_viber': ('Boss Viber', 'Boss Vibers'), 'vibelet': ('Vibelet', 'Vibelets')}
    assert enemy_names.ENEMY_NAMES == expected
    assert enemy_names.name('static') == 'Urchin' and enemy_names.plural('aggressive') == 'Jellies'
