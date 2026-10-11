"""Trains the Jev student from logged decisions: python -m tools.train_student."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
from hunter.student.encoder import FEATURE_NAMES, encode
from hunter.student.network import HEADS, StudentModel

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / '.astrovoid-local' / 'decisions'
DEFAULT_OUT = ROOT / 'assets' / 'student' / 'jev_student.npz'


def load_records(directory):
    records = []
    for path in sorted(Path(directory).glob('*.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _target(head, answer):
    """Jev's probabilities over the head's choices, or one-hot on the chosen option."""
    choices = HEADS[head]
    if answer['choice'] not in choices:
        raise KeyError(answer['choice'])
    probabilities = answer.get('probabilities')
    if probabilities and all(c in probabilities for c in choices):
        row = np.array([probabilities[c] for c in choices], dtype=np.float32)
        return row / row.sum()
    row = np.zeros(len(choices), dtype=np.float32)
    row[choices.index(answer['choice'])] = 1.0
    return row


def build_dataset(records):
    rows, run_ids = [], []
    columns = {head: [] for head in HEADS}
    for record in records:
        try:
            targets = {head: _target(head, record['answers'][head]) for head in HEADS}
            features = encode(record['state'])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append(features)
        run_ids.append(str(record.get('run_id', '')))
        for head in HEADS:
            columns[head].append(targets[head])
    X = np.stack(rows) if rows else np.zeros((0, len(FEATURE_NAMES)), dtype=np.float32)
    return X, {h: np.stack(v) if v else np.zeros((0, len(HEADS[h])), dtype=np.float32)
               for h, v in columns.items()}, run_ids


def split_by_run(run_ids, held_out_fraction=.2, seed=0):
    """Hold out whole runs: consecutive decisions are near-duplicates, so rows would leak."""
    runs = sorted(set(run_ids))
    if len(runs) < 2:
        raise ValueError('need at least two runs to hold one out')
    rng = np.random.default_rng(seed)
    rng.shuffle(runs)
    held = set(runs[:max(1, round(len(runs) * held_out_fraction))])
    ids = np.array(run_ids)
    test = np.flatnonzero(np.isin(ids, list(held)))
    train = np.flatnonzero(~np.isin(ids, list(held)))
    return train, test


def train(X, targets, train_idx, epochs=60, hidden=128, lr=1e-3, seed=0):
    import torch
    torch.manual_seed(seed)
    Xt = X[train_idx]
    mean = Xt.mean(axis=0)
    std = Xt.std(axis=0)
    scale = np.where(std > 1e-6, std, 1.0).astype(np.float32)
    inputs = torch.tensor((Xt - mean) / scale, dtype=torch.float32)
    soft = {h: torch.tensor(targets[h][train_idx]) for h in HEADS}
    trunk = torch.nn.Sequential(
        torch.nn.Linear(X.shape[1], hidden), torch.nn.ReLU(),
        torch.nn.Linear(hidden, hidden), torch.nn.ReLU())
    heads = torch.nn.ModuleDict({h: torch.nn.Linear(hidden, len(HEADS[h])) for h in HEADS})
    optimiser = torch.optim.Adam(list(trunk.parameters()) + list(heads.parameters()), lr=lr)
    count = len(inputs)
    for _ in range(epochs):
        order = torch.randperm(count)
        for start in range(0, count, 256):
            batch = order[start:start + 256]
            features = trunk(inputs[batch])
            loss = sum(-(soft[h][batch] * torch.log_softmax(heads[h](features), dim=1))
                       .sum(dim=1).mean() for h in HEADS)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()

    def arrays(layer):
        return (layer.weight.detach().numpy().T.copy(), layer.bias.detach().numpy().copy())

    return StudentModel(
        mean.astype(np.float32), scale,
        (arrays(trunk[0]), arrays(trunk[2])),
        {h: arrays(heads[h]) for h in HEADS})


def majority_labels(targets, idx):
    return {h: int(np.bincount(targets[h][idx].argmax(axis=1), minlength=len(HEADS[h])).argmax())
            for h in HEADS}


def evaluate(model, X, targets, idx, majority):
    """Agreement with Jev's most likely answer on the rows in idx."""
    predicted = {h: [] for h in HEADS}
    for row in X[idx]:
        probs = model.predict(row)
        for h, choices in HEADS.items():
            predicted[h].append(max(range(len(choices)), key=lambda i: probs[h][choices[i]]))
    metrics, joint, majority_joint = {}, np.ones(len(idx), bool), np.ones(len(idx), bool)
    for h in HEADS:
        truth = targets[h][idx].argmax(axis=1)
        match = np.array(predicted[h]) == truth
        metrics[h] = float(match.mean()) if len(idx) else 0.0
        metrics[f'majority_{h}'] = float((truth == majority[h]).mean()) if len(idx) else 0.0
        joint &= match
        majority_joint &= truth == majority[h]
    metrics['joint'] = float(joint.mean()) if len(idx) else 0.0
    metrics['majority_joint'] = float(majority_joint.mean()) if len(idx) else 0.0
    metrics['rows'] = int(len(idx))
    return metrics


def tree_baseline(X, targets, train_idx, test_idx):
    """A decision tree on the same features: does the network add anything?"""
    from sklearn.tree import DecisionTreeClassifier
    out = {}
    for h in HEADS:
        labels = targets[h].argmax(axis=1)
        tree = DecisionTreeClassifier(max_depth=12, random_state=0).fit(X[train_idx], labels[train_idx])
        out[h] = float((tree.predict(X[test_idx]) == labels[test_idx]).mean())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default=str(DEFAULT_DATA))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--epochs', type=int, default=60)
    args = parser.parse_args(argv)
    records = load_records(args.data)
    X, targets, run_ids = build_dataset(records)
    print(f'{len(X)} usable decisions from {len(set(run_ids))} runs '
          f'({len(records) - len(X)} records skipped)')
    train_idx, test_idx = split_by_run(run_ids)
    model = train(X, targets, train_idx, epochs=args.epochs)
    metrics = evaluate(model, X, targets, test_idx, majority_labels(targets, train_idx))
    metrics['tree'] = tree_baseline(X, targets, train_idx, test_idx)
    print(json.dumps(metrics, indent=2))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model.save(args.out, metrics)
    print(f'saved {args.out}')


if __name__ == '__main__':
    main(sys.argv[1:])
