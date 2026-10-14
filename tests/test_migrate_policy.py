import numpy as np
import pytest
from hunter.neural.policy import NeuralPolicy, random_policy
from hunter.senses import FEATURE_NAMES, SENSE_SIZE
from tools import migrate_policy


def _old_policy_file(tmp_path, dropped=5):
    """A policy as it was before the last `dropped` senses existed."""
    new = random_policy(3)
    data = {k: np.asarray(v) for k, v in new.params.items()}
    data['embed_w'] = data['embed_w'][:, :SENSE_SIZE - dropped]
    path = tmp_path / 'old.npz'
    np.savez(path, mean=new.mean[:SENSE_SIZE - dropped], scale=new.scale[:SENSE_SIZE - dropped],
             feature_names=np.array(FEATURE_NAMES[:SENSE_SIZE - dropped]), **data)
    return path, new


def test_a_migrated_policy_flies_exactly_as_the_old_one_did(tmp_path):
    old_path, _ = _old_policy_file(tmp_path)
    new_path = tmp_path / 'new.npz'
    assert migrate_policy.migrate(old_path, new_path) == 5
    new = NeuralPolicy.load(new_path)
    old = np.load(old_path)
    rng = np.random.default_rng(0)
    senses = rng.normal(size=SENSE_SIZE).astype(np.float32)
    senses[SENSE_SIZE - 5:] = 7.0                         # the new inputs say anything: they carry no weight yet
    short = senses[:SENSE_SIZE - 5]
    x_old = np.tanh(old['embed_w'] @ ((short - old['mean']) / old['scale']) + old['embed_b'])
    x_new = np.tanh(new.params['embed_w'] @ ((senses - new.mean) / new.scale) + new.params['embed_b'])
    assert np.allclose(x_old, x_new, atol=1e-6)


def test_a_layout_that_is_not_a_prefix_cannot_be_migrated(tmp_path):
    old_path, _ = _old_policy_file(tmp_path)
    data = dict(np.load(old_path))
    names = list(data['feature_names'])
    names[0], names[1] = names[1], names[0]
    data['feature_names'] = np.array(names)
    np.savez(old_path, **data)
    with pytest.raises(ValueError):
        migrate_policy.migrate(old_path, tmp_path / 'new.npz')
