"""Versioned recurrent categorical policies; deployment depends on NumPy alone."""
from dataclasses import dataclass
import json
import numpy as np


@dataclass(frozen=True)
class PolicySpec:
    task: str
    features: tuple
    heads: tuple  # ordered (name, categorical size)
    version: int = 1

    def metadata(self):
        return {'task': self.task, 'features': list(self.features), 'heads': [list(h) for h in self.heads],
                'version': self.version}


class RecurrentPolicy:
    def __init__(self, params, mean, scale, spec):
        self.params = {k: np.asarray(v, dtype=np.float32) for k, v in params.items()}
        self.mean, self.scale, self.spec = np.asarray(mean, np.float32), np.asarray(scale, np.float32), spec
        self.hidden = self.params['gru_w_hh'].shape[1]
        if self.mean.shape != (len(spec.features),) or self.scale.shape != self.mean.shape or np.any(self.scale <= 0):
            raise ValueError('incompatible observation normalization')
        shapes = {'embed_w': (self.params['embed_w'].shape[0], len(spec.features)),
                  'embed_b': (self.params['embed_w'].shape[0],),
                  'gru_w_ih': (3*self.hidden, self.params['embed_w'].shape[0]),
                  'gru_w_hh': (3*self.hidden, self.hidden),
                  'gru_b_ih': (3*self.hidden,), 'gru_b_hh': (3*self.hidden,)}
        for name, size in spec.heads:
            shapes.update({name+'_w': (size, self.hidden), name+'_b': (size,)})
        for key, shape in shapes.items():
            if self.params[key].shape != shape or not np.isfinite(self.params[key]).all():
                raise ValueError(f'invalid policy parameter {key}')

    def initial_state(self):
        return np.zeros(self.hidden, np.float32)

    def step(self, senses, state):
        p = self.params
        x = np.tanh(p['embed_w'] @ ((np.asarray(senses, np.float32)-self.mean)/self.scale)+p['embed_b'])
        gi, gh = p['gru_w_ih'] @ x+p['gru_b_ih'], p['gru_w_hh'] @ state+p['gru_b_hh']
        h = self.hidden
        sigmoid = lambda a: 1/(1+np.exp(-np.clip(a, -80, 80)))
        r, z = sigmoid(gi[:h]+gh[:h]), sigmoid(gi[h:2*h]+gh[h:2*h])
        n = np.tanh(gi[2*h:]+r*gh[2*h:])
        state = ((1-z)*n+z*state).astype(np.float32)
        return {k: p[k+'_w'] @ state+p[k+'_b'] for k, _ in self.spec.heads}, state

    def choose(self, senses, state, masks=None, greedy=True, rng=None, temperature=1.0):
        logits, state = self.step(senses, state)
        actions = []
        for name, size in self.spec.heads:
            legal = np.asarray((masks or {}).get(name, np.ones(size, bool)), bool)
            if not legal.any():
                raise ValueError(f'no legal action for {name}')
            z = np.where(legal, logits[name]/temperature, -1e9)
            probs = np.exp(z-z.max()); probs /= probs.sum()
            actions.append(int(np.argmax(z) if greedy else rng.choice(size, p=probs)))
        return tuple(actions), state

    def save(self, path):
        np.savez(path, mean=self.mean, scale=self.scale, policy_spec=json.dumps(self.spec.metadata()), **self.params)

    @classmethod
    def load(cls, path, expected=None):
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data['policy_spec']))
            spec = PolicySpec(meta['task'], tuple(meta['features']), tuple(tuple(h) for h in meta['heads']), meta['version'])
            if expected is not None and spec != expected:
                raise ValueError('checkpoint task or observation/action schema does not match')
            params = {k: data[k].copy() for k in data.files if k not in ('mean', 'scale', 'policy_spec')}
            return cls(params, data['mean'], data['scale'], spec)


def random_policy(spec, seed=0, hidden=64, embed=32):
    rng = np.random.default_rng(seed)
    def normal(*shape):
        return rng.normal(0, 0.08, shape).astype(np.float32)
    params = dict(embed_w=normal(embed, len(spec.features)), embed_b=np.zeros(embed, np.float32),
                  gru_w_ih=normal(3*hidden, embed), gru_w_hh=normal(3*hidden, hidden),
                  gru_b_ih=np.zeros(3*hidden, np.float32), gru_b_hh=np.zeros(3*hidden, np.float32))
    for name, size in spec.heads:
        params[name+'_w'], params[name+'_b'] = normal(size, hidden), np.zeros(size, np.float32)
    return RecurrentPolicy(params, np.zeros(len(spec.features), np.float32), np.ones(len(spec.features), np.float32), spec)
