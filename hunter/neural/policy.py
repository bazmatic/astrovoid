"""The student's brain: a small GRU with one softmax head per control, run in plain numpy."""
import numpy as np
from hunter.senses import FEATURE_NAMES, SENSE_SIZE, OBSERVATION_VERSION

HEAD_SIZES = {'turn': 3, 'thrust': 2, 'fire': 2}
_PARAMS = ('embed_w', 'embed_b', 'gru_w_ih', 'gru_w_hh', 'gru_b_ih', 'gru_b_hh',
           'turn_w', 'turn_b', 'thrust_w', 'thrust_b', 'fire_w', 'fire_b')


class InvalidPolicy(Exception):
    """The policy file is missing, damaged, or built for a different senses layout."""


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class NeuralPolicy:
    def __init__(self, params, mean, scale):
        self.params = {k: np.asarray(params[k], dtype=np.float32) for k in _PARAMS}
        self.mean = np.asarray(mean, dtype=np.float32)
        self.scale = np.asarray(scale, dtype=np.float32)
        self.hidden = self.params['gru_w_hh'].shape[1]

    def initial_state(self):
        return np.zeros(self.hidden, dtype=np.float32)

    def step(self, senses, state):
        p = self.params
        x = np.tanh(p['embed_w'] @ ((np.asarray(senses, dtype=np.float32) - self.mean) / self.scale) + p['embed_b'])
        gi = p['gru_w_ih'] @ x + p['gru_b_ih']
        gh = p['gru_w_hh'] @ state + p['gru_b_hh']
        H = self.hidden
        r = _sigmoid(gi[:H] + gh[:H])
        z = _sigmoid(gi[H:2 * H] + gh[H:2 * H])
        n = np.tanh(gi[2 * H:] + r * gh[2 * H:])
        new_state = ((1.0 - z) * n + z * state).astype(np.float32)
        logits = {k: p[f'{k}_w'] @ new_state + p[f'{k}_b'] for k in HEAD_SIZES}
        return logits, new_state

    def act(self, senses, state, greedy=True, rng=None, temperature=1.0):
        """Choose the controls. Sampled choices are drawn at `temperature`: above 1 the odds flatten (training's
        panic); the greedy choice is the same at any temperature."""
        logits, new_state = self.step(senses, state)
        picks = []
        for head in ('turn', 'thrust', 'fire'):
            z = (logits[head] - logits[head].max()) / temperature
            probs = np.exp(z) / np.exp(z).sum()
            if greedy:
                picks.append(int(np.argmax(probs)))
            else:
                picks.append(int((rng or np.random.default_rng()).choice(len(probs), p=probs)))
        return (picks[0], bool(picks[1]), bool(picks[2])), new_state

    def save(self, path):
        np.savez(path, mean=self.mean, scale=self.scale, feature_names=np.array(FEATURE_NAMES),
                 observation_version=OBSERVATION_VERSION,
                 **self.params)

    @classmethod
    def load(cls, path):
        try:
            data = np.load(path, allow_pickle=False)
            names = tuple(str(n) for n in data['feature_names'])
            legacy_size = FEATURE_NAMES.index('power_boost')
            version = int(data['observation_version']) if 'observation_version' in data else (1 if len(names) == legacy_size else OBSERVATION_VERSION)
            if version not in (1, OBSERVATION_VERSION):
                raise InvalidPolicy('unsupported observation version')
            if names != FEATURE_NAMES and names != FEATURE_NAMES[:legacy_size]:
                raise InvalidPolicy('senses layout differs from this build')
            params = {k: data[k] for k in _PARAMS}
            mean, scale = data['mean'], data['scale']
            if len(names) == legacy_size:
                # Explicit legacy-prefix adapter: new weapon features have zero influence.
                # It preserves old behaviour but does not teach old pilots weapon choice.
                if params['embed_w'].shape[1] != legacy_size or mean.shape != (legacy_size,) or scale.shape != (legacy_size,):
                    raise InvalidPolicy('invalid legacy observation dimensions')
                extra = SENSE_SIZE-legacy_size
                params['embed_w'] = np.pad(params['embed_w'], ((0,0),(0,extra)))
                mean = np.pad(mean, (0,extra))
                scale = np.pad(scale, (0,extra), constant_values=1)
            policy = cls(params, mean, scale)
            policy.legacy_observations = len(names) == legacy_size
            if policy.params['embed_w'].shape[1] != SENSE_SIZE:
                raise InvalidPolicy('senses layout differs from this build')
            if policy.mean.shape != (SENSE_SIZE,) or policy.scale.shape != (SENSE_SIZE,):
                raise InvalidPolicy('standardisation does not fit the senses layout')
            logits, _ = policy.step(np.zeros(SENSE_SIZE, dtype=np.float32), policy.initial_state())
            if not all(np.isfinite(v).all() and v.shape == (n,) for v, n in
                       ((logits[k], HEAD_SIZES[k]) for k in HEAD_SIZES)):
                raise InvalidPolicy('weights do not run')
            return policy
        except InvalidPolicy:
            raise
        except Exception as exc:
            raise InvalidPolicy(type(exc).__name__) from None


def random_policy(seed, hidden=32, embed=16):
    """A small random policy, for tests."""
    rng = np.random.default_rng(seed)
    g = lambda *shape: (rng.normal(0, 0.3, shape)).astype(np.float32)
    params = {'embed_w': g(embed, SENSE_SIZE), 'embed_b': g(embed),
              'gru_w_ih': g(3 * hidden, embed), 'gru_w_hh': g(3 * hidden, hidden),
              'gru_b_ih': g(3 * hidden), 'gru_b_hh': g(3 * hidden)}
    for head, n in HEAD_SIZES.items():
        params[f'{head}_w'], params[f'{head}_b'] = g(n, hidden), g(n)
    return NeuralPolicy(params, np.zeros(SENSE_SIZE), np.ones(SENSE_SIZE))
