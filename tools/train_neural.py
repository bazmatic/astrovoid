"""Trains the neural student from teaching data: python -m tools.train_neural."""
import argparse
import sys
from pathlib import Path
import numpy as np
from hunter.neural.policy import HEAD_SIZES, NeuralPolicy
from hunter.senses import SENSE_SIZE

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'assets' / 'neural' / 'hunter.npz'


def load_episodes(*directories):
    episodes = []
    for directory in directories:
        for path in sorted(Path(directory).glob('*.npz')):
            try:
                data = np.load(path)
                senses, labels = data['senses'].astype(np.float32), data['labels'].astype(np.int64)
            except Exception:
                continue
            if len(senses) and len(senses) == len(labels):
                episodes.append((path.stem, senses, labels))
    return episodes


def split_episodes(episodes, held_out_fraction=0.1, seed=0):
    order = list(range(len(episodes)))
    np.random.default_rng(seed).shuffle(order)
    held = set(order[:max(1, round(len(episodes) * held_out_fraction))])
    return ([e for i, e in enumerate(episodes) if i not in held],
            [e for i, e in enumerate(episodes) if i in held])


def _torch_net_class():
    import torch

    class TorchNet(torch.nn.Module):
        def __init__(self, hidden=128, embed=64):
            super().__init__()
            self.embed = torch.nn.Linear(SENSE_SIZE, embed)
            self.gru = torch.nn.GRU(embed, hidden, batch_first=True)
            self.heads = torch.nn.ModuleDict({k: torch.nn.Linear(hidden, n) for k, n in HEAD_SIZES.items()})

        def forward(self, x, state=None):
            h, state = self.gru(torch.tanh(self.embed(x)), state)
            return {k: head(h) for k, head in self.heads.items()}, state
    return TorchNet


def __getattr__(name):
    if name == 'TorchNet':
        return _torch_net_class()
    raise AttributeError(name)


def to_numpy_policy(net, mean, scale):
    params = {'embed_w': net.embed.weight, 'embed_b': net.embed.bias,
              'gru_w_ih': net.gru.weight_ih_l0, 'gru_w_hh': net.gru.weight_hh_l0,
              'gru_b_ih': net.gru.bias_ih_l0, 'gru_b_hh': net.gru.bias_hh_l0}
    for head in HEAD_SIZES:
        params[f'{head}_w'], params[f'{head}_b'] = net.heads[head].weight, net.heads[head].bias
    return NeuralPolicy({k: v.detach().numpy().copy() for k, v in params.items()}, mean, scale)


def _load_into(net, policy):
    import torch
    mapping = {'embed_w': net.embed.weight, 'embed_b': net.embed.bias,
               'gru_w_ih': net.gru.weight_ih_l0, 'gru_w_hh': net.gru.weight_hh_l0,
               'gru_b_ih': net.gru.bias_ih_l0, 'gru_b_hh': net.gru.bias_hh_l0}
    for head in HEAD_SIZES:
        mapping[f'{head}_w'], mapping[f'{head}_b'] = net.heads[head].weight, net.heads[head].bias
    with torch.no_grad():
        for key, tensor in mapping.items():
            tensor.copy_(torch.from_numpy(policy.params[key]))


def _windows(episodes, window, rng):
    """Random windows of `window` consecutive steps (shorter episodes give one short window)."""
    out = []
    for _, senses, labels in episodes:
        n = len(senses)
        starts = range(0, max(1, n - window + 1), window)
        for s in starts:
            e = min(n, s + window)
            out.append((senses[s:e], labels[s:e]))
    rng.shuffle(out)
    return out


def _pad(batch, mean, scale):
    import torch
    length = max(len(s) for s, _ in batch)
    x = torch.zeros(len(batch), length, SENSE_SIZE)
    y = torch.full((len(batch), length, 3), -100, dtype=torch.long)
    for i, (s, l) in enumerate(batch):
        x[i, :len(s)] = torch.from_numpy((s - mean) / scale)
        y[i, :len(l)] = torch.from_numpy(l)
    return x, y


def train(train_episodes, val_episodes, hidden=128, embed=64, window=64, warmup=16, epochs=30,
          lr=1e-3, batch=32, init=None, seed=0, log=print):
    import torch
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    allsenses = np.concatenate([e[1] for e in train_episodes])
    if init is not None:
        mean, scale = init.mean, init.scale
        hidden, embed = init.hidden, init.params['embed_w'].shape[0]
    else:
        mean = allsenses.mean(axis=0)
        std = allsenses.std(axis=0)
        scale = np.where(std > 1e-6, std, 1.0).astype(np.float32)
    net = _torch_net_class()(hidden, embed)
    if init is not None:
        _load_into(net, init)
    optimiser = torch.optim.Adam(net.parameters(), lr=lr)
    for epoch in range(epochs):
        net.train()
        total, count = 0.0, 0
        windows = _windows(train_episodes, window, rng)
        for i in range(0, len(windows), batch):
            x, y = _pad(windows[i:i + batch], mean, scale)
            out, _ = net(x)
            mask = torch.zeros(y.shape[:2], dtype=torch.bool)
            mask[:, warmup:] = True
            loss = 0.0
            for k, head in enumerate(('turn', 'thrust', 'fire')):
                target = y[:, :, k].clone()
                target[~mask] = -100
                loss = loss + torch.nn.functional.cross_entropy(
                    out[head].reshape(-1, HEAD_SIZES[head]), target.reshape(-1), ignore_index=-100)
            if not torch.isfinite(loss):
                continue
            optimiser.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            optimiser.step()
            total, count = total + float(loss.detach()), count + 1
        if count:
            log(f'epoch {epoch + 1}/{epochs}  loss {total / count:.4f}')
    return to_numpy_policy(net, mean, scale)


def agreement(policy, episodes):
    """Per-head and joint agreement with the teacher, replaying each episode from a clean memory."""
    hits = {'turn': 0, 'thrust': 0, 'fire': 0, 'joint': 0}
    total = 0
    for _, senses, labels in episodes:
        state = policy.initial_state()
        for t in range(len(senses)):
            (turn, thrust, fire), state = policy.act(senses[t], state)
            ok = (turn == labels[t, 0], int(thrust) == labels[t, 1], int(fire) == labels[t, 2])
            hits['turn'] += ok[0]; hits['thrust'] += ok[1]; hits['fire'] += ok[2]; hits['joint'] += all(ok)
            total += 1
    return {k: v / max(total, 1) for k, v in hits.items()} | {'steps': total}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', nargs='+', required=True)
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--init')
    parser.add_argument('--epochs', type=int, default=30)
    parser.add_argument('--hidden', type=int, default=128)
    parser.add_argument('--embed', type=int, default=64)
    args = parser.parse_args(argv)
    episodes = load_episodes(*args.data)
    train_eps, val_eps = split_episodes(episodes)
    print(f'{len(train_eps)} training episodes, {len(val_eps)} validation episodes, '
          f'{sum(len(e[1]) for e in episodes)} steps')
    init = NeuralPolicy.load(args.init) if args.init else None
    policy = train(train_eps, val_eps, hidden=args.hidden, embed=args.embed, epochs=args.epochs, init=init)
    print('validation agreement (a diagnostic, not the gate):', agreement(policy, val_eps))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    policy.save(args.out)
    print('saved', args.out)


if __name__ == '__main__':
    main(sys.argv[1:])
