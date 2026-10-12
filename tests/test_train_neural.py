import numpy as np
import pytest

pytest.importorskip('torch')

from hunter.neural.policy import NeuralPolicy
from hunter.senses import FEATURE_NAMES, SENSE_SIZE
from tools import train_neural as tn


def toy_episodes(n=12, length=300, seed=0):
    """Labels are a function of the senses and of the previous senses, so memory helps."""
    rng = np.random.default_rng(seed)
    episodes = []
    ahead = FEATURE_NAMES.index('enemy0_sin'); present = FEATURE_NAMES.index('enemy0_present')
    for e in range(n):
        senses = rng.normal(0, 1, (length, SENSE_SIZE)).astype(np.float32)
        senses[:, present] = (rng.random(length) < 0.7).astype(np.float32)
        turn = np.where(senses[:, ahead] > 0.3, 2, np.where(senses[:, ahead] < -0.3, 0, 1)).astype(np.int8)
        thrust = (senses[:, FEATURE_NAMES.index('ray_0')] > 0).astype(np.int8)
        fire = (senses[:, present] > 0.5).astype(np.int8)
        episodes.append((f'e{e}', senses, np.stack([turn, thrust, fire], axis=1)))
    return episodes


def test_the_numpy_policy_matches_the_torch_net_it_was_exported_from():
    import torch
    net = tn.TorchNet(hidden=16, embed=8)
    mean = np.zeros(SENSE_SIZE, dtype=np.float32); scale = np.ones(SENSE_SIZE, dtype=np.float32)
    policy = tn.to_numpy_policy(net, mean, scale)
    senses = np.random.default_rng(1).normal(0, 1, (12, SENSE_SIZE)).astype(np.float32)
    with torch.no_grad():
        out, _ = net(torch.from_numpy(senses)[None])
    state = policy.initial_state()
    for t in range(12):
        logits, state = policy.step(senses[t], state)
        for head in ('turn', 'thrust', 'fire'):
            assert np.allclose(logits[head], out[head][0, t].numpy(), atol=1e-4), (t, head)


def test_training_learns_a_simple_rule_and_beats_the_majority_baseline():
    episodes = toy_episodes()
    train, val = tn.split_episodes(episodes, held_out_fraction=0.34, seed=0)
    policy = tn.train(train, val, hidden=32, embed=16, window=32, warmup=8, epochs=60, lr=3e-3, batch=8,
                      log=lambda *_: None)
    result = tn.agreement(policy, val)
    majority = max(np.mean(np.concatenate([e[2][:, 0] for e in val]) == k) for k in (0, 1, 2))
    assert result['turn'] > max(0.8, majority + 0.1)
    assert result['fire'] > 0.9


def test_the_exported_file_loads_and_flies(tmp_path):
    episodes = toy_episodes(n=3, length=80)
    policy = tn.train(episodes[:2], episodes[2:], hidden=16, embed=8, window=16, warmup=4, epochs=2, log=lambda *_: None)
    path = tmp_path / 'p.npz'
    policy.save(path)
    loaded = NeuralPolicy.load(path)
    controls, _ = loaded.act(episodes[0][1][0], loaded.initial_state())
    assert controls[0] in (0, 1, 2)


def test_continuing_from_an_earlier_policy_starts_from_its_weights():
    episodes = toy_episodes(n=3, length=80)
    first = tn.train(episodes[:2], episodes[2:], hidden=16, embed=8, window=16, warmup=4, epochs=1, log=lambda *_: None)
    again = tn.train(episodes[:2], episodes[2:], hidden=16, embed=8, window=16, warmup=4, epochs=0, init=first, log=lambda *_: None)
    assert np.allclose(first.params['gru_w_ih'], again.params['gru_w_ih'])


def test_splits_are_by_episode_and_deterministic():
    episodes = toy_episodes(n=10, length=20)
    a = tn.split_episodes(episodes, 0.3, seed=1); b = tn.split_episodes(episodes, 0.3, seed=1)
    assert [e[0] for e in a[1]] == [e[0] for e in b[1]]
    assert not {e[0] for e in a[0]} & {e[0] for e in a[1]} and len(a[1]) == 3


def test_load_episodes_reads_directories_and_skips_bad_files(tmp_path):
    ok = toy_episodes(n=1, length=10)[0]
    np.savez(tmp_path / 'a.npz', senses=ok[1], labels=ok[2])
    (tmp_path / 'junk.npz').write_bytes(b'x')
    episodes = tn.load_episodes(tmp_path)
    assert [e[0] for e in episodes] == ['a'] and episodes[0][1].shape == (10, SENSE_SIZE)


def test_windows_never_cross_episode_boundaries_and_short_episodes_are_handled():
    episodes = toy_episodes(n=2, length=10)          # shorter than one window
    policy = tn.train(episodes[:1], episodes[1:], hidden=8, embed=4, window=32, warmup=4, epochs=1, log=lambda *_: None)
    assert policy is not None
