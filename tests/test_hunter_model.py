from hunter.model import ACTIONS, NEUTRAL, PilotAction


def test_controls_include_simultaneous_flight_and_fire():
    assert len(ACTIONS) == 16
    assert ACTIONS['left_thrust_fire'] == PilotAction(-1, True, True)
    assert ACTIONS['none_coast_hold'] == NEUTRAL
    assert len(set(ACTIONS.values())) == 16
