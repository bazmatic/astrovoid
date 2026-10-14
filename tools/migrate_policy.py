"""Carry a trained policy over to a longer senses layout: python -m tools.migrate_policy OLD.npz NEW.npz

The old layout must be a prefix of the current one (new senses are only ever added at the end). The new inputs
get zero weights, so the migrated pilot flies exactly as the old one did until training teaches it to use them.
"""
import sys
import numpy as np
from hunter.senses import FEATURE_NAMES, SENSE_SIZE
from hunter.neural.policy import NeuralPolicy


def migrate(old_path, new_path):
    data = dict(np.load(old_path, allow_pickle=False))
    old_names = tuple(str(n) for n in data['feature_names'])
    if old_names != FEATURE_NAMES[:len(old_names)]:
        raise ValueError('the old senses are not a prefix of the current layout; it cannot be migrated')
    added = SENSE_SIZE - len(old_names)
    if added:
        embed = data['embed_w']
        data['embed_w'] = np.concatenate([embed, np.zeros((embed.shape[0], added), embed.dtype)], axis=1)
        data['mean'] = np.concatenate([data['mean'], np.zeros(added, data['mean'].dtype)])
        data['scale'] = np.concatenate([data['scale'], np.ones(added, data['scale'].dtype)])
    data['feature_names'] = np.array(FEATURE_NAMES)
    np.savez(new_path, **data)
    NeuralPolicy.load(new_path)               # raises InvalidPolicy if the result does not fit
    return added


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(f'migrated: {migrate(sys.argv[1], sys.argv[2])} new inputs, zero-weighted')
