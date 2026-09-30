import pytest
from hunter.visibility import visible_point, visible_wall_portions, visible_cell_edges


def test_wall_hides_contact_and_range_limits_visibility():
    walls = [((5.,-2.),(5.,2.))]
    assert visible_point((0,0),(4,0),walls,10)
    assert visible_point((0,0),(5,0),walls,10)
    assert not visible_point((0,0),(8,0),walls,10)
    assert not visible_point((0,0),(0,11),walls,10)
    assert not visible_point((0,0),(8,0), [((3,0),(5,0))],10)


def test_wall_portions_clip_range_and_hidden_ends():
    front = ((5.,-2.),(5.,2.))
    back = ((8.,-20.),(8.,20.))
    pieces = visible_wall_portions((0,0), [front, front, back], 10)
    assert len([p for p in pieces if p[0][0] == 5]) == 1
    for a,b in pieces:
        assert a[0]**2+a[1]**2 <= 100.00001
        assert b[0]**2+b[1]**2 <= 100.00001
        if a[0] == 8:
            assert not (-3.19 < (a[1]+b[1])/2 < 3.19)


def test_cell_edges_do_not_reveal_hidden_side():
    walls = [((5.,-20.),(5.,20.))]
    edges = visible_cell_edges((0,0), (4,-1,6,1), walls, 10)
    assert not edges['right']
    assert edges['left']
