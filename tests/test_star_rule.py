from scoring.stars import StarTally, describe, earned, star_count

def tally(kills=0, alive=0, collected=0, left=0, seconds=10.0, par=60.0, hits=0):
    return StarTally(kills, alive, collected, left, seconds, par, hits)

def test_finishing_without_a_hit_is_one_star():
    assert earned(tally(kills=0, alive=4, collected=0, left=1, seconds=90)) == (True, False, False, False, False)

def test_finishing_alone_after_a_hit_is_no_stars():
    assert earned(tally(kills=0, alive=4, collected=0, left=1, seconds=90, hits=1)) == (False,) * 5

def test_half_the_enemies_is_a_star_and_all_of_them_another():
    assert earned(tally(kills=2, alive=2))[1:3] == (True, False)       # exactly half
    assert earned(tally(kills=1, alive=2))[1:3] == (False, False)
    assert earned(tally(kills=4, alive=0))[1:3] == (True, True)

def test_a_level_with_no_enemies_or_crystals_gives_those_stars():
    assert earned(tally()) == (True, True, True, True, True)

def test_every_crystal_means_none_left():
    assert earned(tally(collected=3, left=0))[3] and not earned(tally(collected=3, left=1))[3]

def test_par_is_met_on_the_second_and_missed_after_it():
    assert earned(tally(seconds=60.0, par=60.0))[4] and not earned(tally(seconds=60.01, par=60.0))[4]

def test_the_count_is_the_number_of_stars_lit():
    assert star_count((True, False, True, True, False)) == 3

def test_the_lines_under_the_stars():
    assert describe(tally(kills=9, alive=5, collected=2, left=1, seconds=102.4, par=103.0)) == \
        ('NO HITS', '9/14 KILLED', '5 LEFT', '2/3 CRYSTALS', '1:42 / PAR 1:43')
    assert describe(tally(kills=14, alive=0))[1:4] == ('14/14 KILLED', 'NONE LEFT', 'NO CRYSTALS')
    assert describe(tally(hits=1))[0] == '1 HIT' and describe(tally(hits=3))[0] == '3 HITS'
