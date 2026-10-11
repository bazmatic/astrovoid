"""The trained student: a small MLP with one softmax head per Jev question."""
import ast
from dataclasses import dataclass
import numpy as np
from hunter.jev_pilot import PILOT_QUESTIONS
from hunter.student.encoder import FEATURE_NAMES

# Head and choice order come from the rubric, so a model file records exactly which
# questions and answers its outputs mean.
HEADS = {name: tuple(question['criteria']) for name, question in PILOT_QUESTIONS.items()}


def _heads_text():
    return repr({name: list(choices) for name, choices in HEADS.items()})


class InvalidModel(Exception):
    """The model file cannot drive the current encoder or questions."""


@dataclass(frozen=True)
class StudentModel:
    mean: np.ndarray
    scale: np.ndarray
    layers: tuple  # ((weights, bias), ...): the shared trunk, ReLU after each
    heads: dict  # head name -> (weights, bias)

    def predict(self, features):
        """Per-head probabilities as {head: {choice: probability}}."""
        x = (np.asarray(features, dtype=np.float32) - self.mean) / self.scale
        for weights, bias in self.layers:
            x = np.maximum(0.0, x @ weights + bias)
        out = {}
        for name, choices in HEADS.items():
            weights, bias = self.heads[name]
            logits = x @ weights + bias
            probs = np.exp(logits - logits.max())
            probs /= probs.sum()
            out[name] = dict(zip(choices, (float(p) for p in probs)))
        return out

    def save(self, path, metrics=None):
        arrays = {'mean': self.mean, 'scale': self.scale,
                  'feature_names': np.array(FEATURE_NAMES),
                  'heads_json': np.array(_heads_text()),
                  'trunk_count': np.array(len(self.layers)),
                  'metrics_json': np.array(repr(metrics or {}))}
        for i, (weights, bias) in enumerate(self.layers):
            arrays[f'trunk{i}_w'], arrays[f'trunk{i}_b'] = weights, bias
        for name, (weights, bias) in self.heads.items():
            arrays[f'head_{name}_w'], arrays[f'head_{name}_b'] = weights, bias
        np.savez(path, **arrays)

    @classmethod
    def load(cls, path):
        try:
            data = np.load(path, allow_pickle=False)
            if tuple(str(n) for n in data['feature_names']) != FEATURE_NAMES:
                raise InvalidModel('feature list differs from the encoder')
            if str(data['heads_json']) != _heads_text():
                raise InvalidModel('heads differ from the pilot questions')
            layers = tuple((data[f'trunk{i}_w'], data[f'trunk{i}_b'])
                           for i in range(int(data['trunk_count'])))
            heads = {name: (data[f'head_{name}_w'], data[f'head_{name}_b']) for name in HEADS}
            return cls(data['mean'], data['scale'], layers, heads)
        except InvalidModel:
            raise
        except Exception as exc:
            # Truncated or foreign files fail in many ways (zipfile, pickle, key, value).
            raise InvalidModel(type(exc).__name__) from None

    @staticmethod
    def metrics(path):
        """The metrics recorded at training time, for display."""
        return ast.literal_eval(str(np.load(path, allow_pickle=False)['metrics_json']))
