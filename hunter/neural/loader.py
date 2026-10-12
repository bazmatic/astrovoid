"""Loads the shipped neural policy, or reports that there is none."""
import logging
from hunter.neural.policy import InvalidPolicy, NeuralPolicy
from utils.resource_path import resource_path

DEFAULT_PATH = resource_path('assets/neural/hunter.npz')
_warned = set()


def load_neural_policy(path=None):
    path = str(path or DEFAULT_PATH)
    try:
        return NeuralPolicy.load(path)
    except InvalidPolicy as exc:
        if path not in _warned:
            _warned.add(path)
            logging.getLogger(__name__).warning('Neural pilot unavailable (%s): %s', path, exc)
        return None
