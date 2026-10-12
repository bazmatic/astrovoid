import numpy as np
import pytest
from hunter.neural.policy import HEAD_SIZES, InvalidPolicy, NeuralPolicy, random_policy
from hunter.senses import SENSE_SIZE


def test_a_policy_steps_and_returns_logits_for_each_head():
    policy = random_policy(0)
    logits, state = policy.step(np.zeros(SENSE_SIZE, dtype=np.float32), policy.initial_state())
    assert {k: v.shape for k, v in logits.items()} == {k: (n,) for k, n in HEAD_SIZES.items()}
    assert state.shape == policy.initial_state().shape
    assert all(np.isfinite(v).all() for v in logits.values()) and np.isfinite(state).all()


def test_the_memory_changes_the_answer():
    policy = random_policy(1)
    s = np.ones(SENSE_SIZE, dtype=np.float32)
    first, state = policy.step(s, policy.initial_state())
    second, _ = policy.step(s, state)
    assert not np.allclose(first['turn'], second['turn'])


def test_greedy_play_is_deterministic_and_returns_controls():
    policy = random_policy(2)
    s = np.full(SENSE_SIZE, 0.3, dtype=np.float32)
    a, _ = policy.act(s, policy.initial_state())
    b, _ = policy.act(s, policy.initial_state())
    assert a == b
    turn, thrust, fire = a
    assert turn in (0, 1, 2) and isinstance(thrust, bool) and isinstance(fire, bool)


def test_sampling_is_reproducible_with_a_seeded_generator_and_can_differ_from_greedy():
    policy = random_policy(3)
    s = np.full(SENSE_SIZE, 0.1, dtype=np.float32)
    picks = {policy.act(s, policy.initial_state(), greedy=False, rng=np.random.default_rng(k))[0] for k in range(40)}
    assert len(picks) > 1
    x = policy.act(s, policy.initial_state(), greedy=False, rng=np.random.default_rng(7))[0]
    y = policy.act(s, policy.initial_state(), greedy=False, rng=np.random.default_rng(7))[0]
    assert x == y


def test_save_and_load_round_trip(tmp_path):
    policy = random_policy(4)
    path = tmp_path / 'p.npz'
    policy.save(path)
    loaded = NeuralPolicy.load(path)
    s = np.arange(SENSE_SIZE, dtype=np.float32) / SENSE_SIZE
    a, sa = policy.step(s, policy.initial_state())
    b, sb = loaded.step(s, loaded.initial_state())
    for k in a:
        assert np.allclose(a[k], b[k])
    assert np.allclose(sa, sb)


def test_load_rejects_missing_truncated_foreign_and_mismatched_files(tmp_path):
    with pytest.raises(InvalidPolicy):
        NeuralPolicy.load(tmp_path / 'absent.npz')
    bad = tmp_path / 'bad.npz'
    bad.write_bytes(b'not a policy')
    with pytest.raises(InvalidPolicy):
        NeuralPolicy.load(bad)
    good = tmp_path / 'good.npz'
    random_policy(5).save(good)
    good.write_bytes(good.read_bytes()[:300])
    with pytest.raises(InvalidPolicy):
        NeuralPolicy.load(good)
    other = tmp_path / 'other.npz'
    random_policy(6).save(other)
    data = dict(np.load(other))
    data['feature_names'] = np.array(['renamed'] * SENSE_SIZE)
    np.savez(other, **data)
    with pytest.raises(InvalidPolicy, match='layout'):
        NeuralPolicy.load(other)
