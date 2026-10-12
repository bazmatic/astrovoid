"""Recurrent PPO fine-tuning of the neural student: python -m tools.ppo_neural (the loop is in Task 3)."""
import argparse
import os
import sys
from pathlib import Path
import numpy as np
from hunter.neural.policy import HEAD_SIZES, NeuralPolicy
from hunter.senses import SENSE_SIZE
from tools.train_neural import _load_into, _torch_net_class, to_numpy_policy

HEADS = ('turn', 'thrust', 'fire')
REWARD_SCALE = 0.1            # keeps returns near 1 so one learning rate suits the policy and value heads


def _net_class():
    import torch
    base = _torch_net_class()

    class PolicyValueNet(base):
        def __init__(self, hidden, embed):
            super().__init__(hidden, embed)
            self.value = torch.nn.Linear(hidden, 1)
            torch.nn.init.zeros_(self.value.weight)
            torch.nn.init.zeros_(self.value.bias)

        def forward(self, x, state=None):
            h, _ = self.gru(torch.tanh(self.embed(x)), state)
            return {k: head(h) for k, head in self.heads.items()}, self.value(h).squeeze(-1)
    return PolicyValueNet


def build_net(policy):
    """A torch net holding `policy`'s weights, plus a zeroed value head (training only)."""
    net = _net_class()(policy.hidden, policy.params['embed_w'].shape[0])
    _load_into(net, policy)
    return net


def pack(episodes, mean, scale):
    import torch
    batch, length = len(episodes), max(len(e['senses']) for e in episodes)
    x = torch.zeros(batch, length, SENSE_SIZE)
    controls = torch.zeros(batch, length, 3, dtype=torch.long)
    rewards = torch.zeros(batch, length)
    mask = torch.zeros(batch, length, dtype=torch.bool)
    for i, e in enumerate(episodes):
        n = len(e['senses'])
        x[i, :n] = torch.from_numpy((np.asarray(e['senses'], dtype=np.float32) - mean) / scale)
        controls[i, :n] = torch.from_numpy(np.asarray(e['controls'], dtype=np.int64))
        rewards[i, :n] = torch.from_numpy(np.asarray(e['rewards'], dtype=np.float32)) * REWARD_SCALE
        mask[i, :n] = True
    return {'x': x, 'controls': controls, 'rewards': rewards, 'mask': mask}


def joint_logp(logits, controls):
    import torch
    total = 0.0
    for k, head in enumerate(HEADS):
        logp = torch.log_softmax(logits[head], dim=-1)
        total = total + logp.gather(-1, controls[..., k:k + 1]).squeeze(-1)
    return total


def gae(rewards, values, mask, gamma=0.99, lam=0.95):
    """Advantages and returns; each episode ends at its last unmasked step (terminal, value 0 after)."""
    import torch
    batch, length = rewards.shape
    zero = torch.zeros(batch)
    advantages = torch.zeros_like(rewards)
    running = zero
    for t in reversed(range(length)):
        has_next = mask[:, t + 1] if t + 1 < length else torch.zeros(batch, dtype=torch.bool)
        next_value = torch.where(has_next, values[:, t + 1], zero) if t + 1 < length else zero
        delta = rewards[:, t] + gamma * next_value - values[:, t]
        running = delta + gamma * lam * torch.where(has_next, running, zero)
        advantages[:, t] = torch.where(mask[:, t], running, zero)
    return advantages, advantages + torch.where(mask, values, torch.zeros_like(values))


def _kl_and_entropy(logits, ref_logits):
    import torch
    kl, entropy = 0.0, 0.0
    for head in HEADS:
        logp = torch.log_softmax(logits[head], dim=-1)
        p = logp.exp()
        kl = kl + (p * (logp - torch.log_softmax(ref_logits[head], dim=-1))).sum(-1)
        entropy = entropy - (p * logp).sum(-1)
    return kl, entropy


def improve(net, ref, optimiser, episodes, mean, scale, kl_coef, rng, clip=0.2, epochs=4, minibatches=4,
            gamma=0.99, lam=0.95, value_coef=0.5, entropy_coef=0.003):
    """One PPO update on a batch of whole episodes. Returns the mean loss terms of the last epoch."""
    import torch
    batch = pack(episodes, mean, scale)
    x, controls, mask = batch['x'], batch['controls'], batch['mask']
    with torch.no_grad():
        logits, values = net(x)
        old_logp = joint_logp(logits, controls)
        advantages, returns = gae(batch['rewards'], values, mask, gamma, lam)
        ref_logits, _ = ref(x)
        chosen = advantages[mask]
        advantages = torch.where(mask, (advantages - chosen.mean()) / (chosen.std() + 1e-8),
                                 torch.zeros_like(advantages))
    stats = {}
    for _ in range(epochs):
        order = rng.permutation(len(episodes))
        sums, count = {'policy_loss': 0.0, 'value_loss': 0.0, 'kl': 0.0, 'entropy': 0.0,
                       'clip_fraction': 0.0}, 0
        for chunk in np.array_split(order, min(minibatches, len(episodes))):
            index = torch.as_tensor(chunk, dtype=torch.long)
            m = mask[index]
            logits, values = net(x[index])
            ratio = torch.exp(joint_logp(logits, controls[index]) - old_logp[index])
            a = advantages[index]
            surrogate = torch.minimum(ratio * a, torch.clamp(ratio, 1 - clip, 1 + clip) * a)
            policy_loss = -surrogate[m].mean()
            value_loss = ((values - returns[index]) ** 2)[m].mean()
            kl, entropy = _kl_and_entropy(logits, {k: v[index] for k, v in ref_logits.items()})
            loss = (policy_loss + value_coef * value_loss + kl_coef * kl[m].mean()
                    - entropy_coef * entropy[m].mean())
            if not torch.isfinite(loss):
                continue
            optimiser.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            optimiser.step()
            for key, value in (('policy_loss', policy_loss), ('value_loss', value_loss), ('kl', kl[m].mean()),
                               ('entropy', entropy[m].mean()),
                               ('clip_fraction', ((ratio - 1).abs() > clip)[m].float().mean())):
                sums[key] += float(value.detach())
            count += 1
        stats = {key: value / max(count, 1) for key, value in sums.items()}
    return stats


def export(net, policy, path):
    """Save the net as a game policy file (the value head is left behind)."""
    to_numpy_policy(net, policy.mean, policy.scale).save(path)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_START = ROOT / 'assets' / 'neural' / 'hunter.npz'
DEFAULT_OUT = ROOT / '.astrovoid-local' / 'neural' / 'rl'
TRAIN_SEEDS = 100             # seeds 300-399


def make_jobs(iteration, count, weights, decision_frames, turn_rate):
    from experiments.run import TUNE_LEVELS
    from experiments.student import StudentSpec
    jobs = []
    for i in range(count):
        n = iteration * count + i
        spec = StudentSpec(weights=str(weights), decision_frames=decision_frames, turn_rate=turn_rate,
                           greedy=False, sample_seed=n)
        jobs.append((TUNE_LEVELS[n % len(TUNE_LEVELS)], 300 + n % TRAIN_SEEDS, spec))
    return jobs


def kl_coefficient(iteration, iterations, start=0.1, end=0.02, fade=0.5):
    span = max(fade * iterations, 1.0)
    return end if iteration >= span else start + (end - start) * iteration / span


def _rollout_job(job):
    from experiments.rollout import fly_rollout
    level, seed, spec = job
    return fly_rollout(level, seed, spec)


def pool_rollout(jobs, workers):
    from experiments import run
    if workers <= 1:
        return [_rollout_job(job) for job in jobs]
    import multiprocessing
    with multiprocessing.get_context('spawn').Pool(workers, initializer=run._use_dummy_drivers) as pool:
        return pool.map(_rollout_job, jobs, chunksize=1)


def make_gate(workers, seeds, decision_frames, turn_rate):
    """gate(path) -> report: the checkpoint flown greedily against the rules pilot on the tune set."""
    from experiments import neural_lab, run
    from experiments.student import StudentSpec
    from hunter.rule_params import RULES
    seed_list = tuple(range(seeds))
    reference = []

    def gate(path):
        if not reference:
            reference.append(run.evaluate(RULES, 'tune', seed_list, 90.0, workers))
        spec = StudentSpec(weights=str(path), decision_frames=decision_frames, turn_rate=turn_rate)
        student = run.evaluate(RULES, 'tune', seed_list, 90.0, workers, student=spec)
        return neural_lab.gate_report(reference[0], student)
    return gate


def train_rl(start, out_dir, iterations, episodes=96, workers=12, check_every=5, check_seeds=6, lr=1e-4,
             seed=0, decision_frames=6, turn_rate=1.0, rollout=None, gate=None, log=print):
    import torch
    from experiments.score import mean_components
    policy = NeuralPolicy.load(start)                  # raises InvalidPolicy: never train from nothing
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rollout = rollout or pool_rollout
    gate = gate or make_gate(workers, check_seeds, decision_frames, turn_rate)
    net, ref = build_net(policy), build_net(policy)
    for parameter in ref.parameters():
        parameter.requires_grad_(False)
    optimiser = torch.optim.Adam(net.parameters(), lr=lr)
    current = out_dir / 'iter_start.npz'
    export(net, policy, current)
    history, best_score, best_path, passed = [], None, None, False
    for iteration in range(iterations):
        jobs = make_jobs(iteration, episodes, current, decision_frames, turn_rate)
        flown = rollout(jobs, workers)
        stats = improve(net, ref, optimiser, flown, policy.mean, policy.scale,
                        kl_coefficient(iteration, iterations), rng)
        results = [e['result'] for e in flown]
        summary = mean_components(results)
        stats.update(iteration=iteration, mean_return=float(np.mean([e['rewards'].sum() for e in flown])),
                     score=summary['score'], kills_per_min=summary['kills_per_min'],
                     wall_hits_per_min=summary['wall_hits_per_min'],
                     hits_taken_per_min=summary['hits_taken_per_min'])
        current = out_dir / f'iter{iteration:04d}.npz'
        export(net, policy, current)
        if (iteration + 1) % check_every == 0:
            report = gate(current)
            stats['gate_score'] = report['student']['score']
            stats['gate_passed'] = bool(report['passed'])
            if best_score is None or stats['gate_score'] > best_score:
                best_score, best_path = stats['gate_score'], current
                (out_dir / 'best.npz').write_bytes(current.read_bytes())
            passed = bool(report['passed'])
        history.append(stats)
        log(' '.join(f'{k}={v:.3f}' if isinstance(v, float) else f'{k}={v}' for k, v in stats.items()))
        if passed:
            break
    (out_dir / 'iter_start.npz').unlink(missing_ok=True)
    return {'best': out_dir / 'best.npz' if best_path else None, 'history': history, 'passed': passed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default=str(DEFAULT_START))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--episodes', type=int, default=96)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--check-every', type=int, default=5)
    parser.add_argument('--lr', type=float, default=1e-4)
    args = parser.parse_args(argv)
    from experiments import run
    run._use_dummy_drivers()
    result = train_rl(args.start, args.out, args.iterations, args.episodes, args.workers,
                      args.check_every, lr=args.lr)
    print('gate passed on the tune set' if result['passed'] else 'budget used without passing the tune gate',
          '| best:', result['best'])


if __name__ == '__main__':
    main(sys.argv[1:])
