import numpy as np
import pytest

torch = pytest.importorskip('torch')

from hunter.neural.policy import NeuralPolicy, random_policy
from hunter.senses import SENSE_SIZE
from tools import ppo_neural as ppo


def toy_episodes(net, policy, rng, count=16, length=40):
    """Episodes sampled from the net on random senses; reward 1 for every right turn (turn == 2)."""
    episodes = []
    for _ in range(count):
        senses = rng.normal(0, 1, (length, SENSE_SIZE)).astype(np.float32)
        x = torch.from_numpy((senses - policy.mean) / policy.scale)[None]
        with torch.no_grad():
            logits, _ = net(x)
        controls = np.zeros((length, 3), dtype=np.int8)
        for k, head in enumerate(ppo.HEADS):
            probs = torch.softmax(logits[head][0], dim=-1).numpy().astype(np.float64)
            probs /= probs.sum(axis=1, keepdims=True)
            controls[:, k] = [rng.choice(len(p), p=p) for p in probs]
        rewards = (controls[:, 0] == 2).astype(np.float32) * 10.0
        episodes.append({'senses': senses, 'controls': controls, 'rewards': rewards})
    return episodes


def right_turn_probability(net, policy, rng, count=64, length=40):
    senses = rng.normal(0, 1, (count, length, SENSE_SIZE)).astype(np.float32)
    with torch.no_grad():
        logits, _ = net(torch.from_numpy((senses - policy.mean) / policy.scale))
    return float(torch.softmax(logits['turn'], dim=-1)[..., 2].mean())


def learn(kl_coef, iterations=25, seed=0):
    policy = random_policy(seed, hidden=16, embed=8)
    net, ref = ppo.build_net(policy), ppo.build_net(policy)
    for p in ref.parameters():
        p.requires_grad_(False)
    optimiser = torch.optim.Adam(net.parameters(), lr=3e-3)
    rng = np.random.default_rng(seed)
    start = right_turn_probability(net, policy, np.random.default_rng(99))
    for _ in range(iterations):
        ppo.improve(net, ref, optimiser, toy_episodes(net, policy, rng), policy.mean, policy.scale, kl_coef, rng)
    return start, right_turn_probability(net, policy, np.random.default_rng(99)), net, policy


def test_the_built_net_matches_the_policy_it_was_built_from():
    policy = random_policy(1, hidden=16, embed=8)
    net = ppo.build_net(policy)
    senses = np.random.default_rng(1).normal(0, 1, (10, SENSE_SIZE)).astype(np.float32)
    with torch.no_grad():
        logits, values = net(torch.from_numpy((senses - policy.mean) / policy.scale)[None])
    state = policy.initial_state()
    for t in range(10):
        expected, state = policy.step(senses[t], state)
        for head in ppo.HEADS:
            assert np.allclose(expected[head], logits[head][0, t].numpy(), atol=1e-4), (t, head)
    assert torch.allclose(values, torch.zeros_like(values))        # a fresh value head predicts nothing


def test_gae_matches_a_hand_worked_two_step_episode():
    rewards = torch.tensor([[1.0, 2.0, 0.0]])
    values = torch.tensor([[0.5, 0.25, 9.9]])                         # the padded third step must not matter
    mask = torch.tensor([[True, True, False]])
    adv, ret = ppo.gae(rewards, values, mask, gamma=0.5, lam=1.0)
    # step 1 is the last: delta = 2 - 0.25 = 1.75; step 0: delta = 1 + 0.5*0.25 - 0.5 = 0.625, plus 0.5*1.75
    assert adv[0, 1].item() == pytest.approx(1.75) and adv[0, 0].item() == pytest.approx(0.625 + 0.875)
    assert adv[0, 2].item() == 0.0
    assert ret[0, 0].item() == pytest.approx(adv[0, 0].item() + 0.5)


def test_pack_pads_episodes_and_masks_the_padding():
    policy = random_policy(2, hidden=8, embed=4)
    short = {'senses': np.zeros((3, SENSE_SIZE), np.float32), 'controls': np.ones((3, 3), np.int8),
             'rewards': np.ones(3, np.float32)}
    long = {'senses': np.zeros((5, SENSE_SIZE), np.float32), 'controls': np.ones((5, 3), np.int8),
            'rewards': np.ones(5, np.float32)}
    batch = ppo.pack([short, long], policy.mean, policy.scale)
    assert batch['x'].shape == (2, 5, SENSE_SIZE) and batch['mask'].sum(dim=1).tolist() == [3, 5]
    assert batch['rewards'][0, 0].item() == pytest.approx(ppo.REWARD_SCALE)


def test_ppo_raises_the_probability_of_a_rewarded_action():
    start, end, _, _ = learn(kl_coef=0.0)
    assert end > max(0.7, start + 0.25)


def test_the_kl_anchor_holds_the_policy_near_where_it_started():
    start, free, _, _ = learn(kl_coef=0.0)
    _, anchored, _, _ = learn(kl_coef=50.0)
    assert anchored < free - 0.2 and abs(anchored - start) < 0.15


def test_a_nan_loss_skips_the_update_instead_of_poisoning_the_weights():
    policy = random_policy(3, hidden=8, embed=4)
    net, ref = ppo.build_net(policy), ppo.build_net(policy)
    optimiser = torch.optim.Adam(net.parameters(), lr=1e-3)
    episode = {'senses': np.zeros((6, SENSE_SIZE), np.float32), 'controls': np.zeros((6, 3), np.int8),
               'rewards': np.array([0, 0, np.nan, 0, 0, 0], dtype=np.float32)}
    before = [p.detach().clone() for p in net.parameters()]
    ppo.improve(net, ref, optimiser, [episode], policy.mean, policy.scale, 0.0, np.random.default_rng(0))
    assert all(torch.equal(a, b) for a, b in zip(before, net.parameters()))


def test_an_exported_checkpoint_loads_in_the_game_and_has_no_value_head(tmp_path):
    _, _, net, policy = learn(kl_coef=0.0, iterations=2)
    path = tmp_path / 'ckpt.npz'
    ppo.export(net, policy, path)
    loaded = NeuralPolicy.load(path)
    assert not any('value' in key for key in np.load(path).files)
    senses = np.random.default_rng(5).normal(0, 1, (6, SENSE_SIZE)).astype(np.float32)
    with torch.no_grad():
        logits, _ = net(torch.from_numpy((senses - policy.mean) / policy.scale)[None])
    state = loaded.initial_state()
    for t in range(6):
        out, state = loaded.step(senses[t], state)
        for head in ppo.HEADS:
            assert np.allclose(out[head], logits[head][0, t].numpy(), atol=1e-4)
