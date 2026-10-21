"""Recurrent PPO fine-tuning of the neural student: python -m tools.ppo_neural (the loop is in Task 3)."""
import argparse
import functools
import os
import sys
import time
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
            # Clamped so a policy that has moved far within one update cannot overflow the ratio's gradient.
            ratio = torch.exp(torch.clamp(joint_logp(logits, controls[index]) - old_logp[index], -20.0, 20.0))
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
            # A finite loss can still have an infinite gradient, which clipping turns into NaN weights: skip it.
            if not torch.isfinite(torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)):
                optimiser.zero_grad()
                continue
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
DEFAULT_HORIZON = 90.0        # seconds of game time per training episode unless the shaping says otherwise


RULES_LEVEL = 25          # the level with a Rules hunter on it (levels/25.json)


def make_jobs(iteration, count, weights, decision_frames, turn_rate, rules_share=0.0, levels=None):
    """One job per episode: the training levels (`levels`, default the tune set) in turn, with `rules_share` of the
    episodes (spread evenly through the batch) flown on the Rules hunter's level and the other levels never
    including it."""
    from experiments.run import TUNE_LEVELS
    from experiments.student import StudentSpec
    levels = tuple(levels or TUNE_LEVELS)
    others = tuple(level for level in levels if level != RULES_LEVEL)
    jobs = []
    for i in range(count):
        n = iteration * count + i
        spec = StudentSpec(weights=str(weights), decision_frames=decision_frames, turn_rate=turn_rate,
                           greedy=False, sample_seed=n)
        if rules_share > 0.0:
            rules_episode = int((n + 1) * rules_share + 1e-9) > int(n * rules_share + 1e-9)
            level = RULES_LEVEL if rules_episode else others[n % len(others)]
        else:
            level = levels[n % len(levels)]
        jobs.append((level, 300 + n % TRAIN_SEEDS, spec))
    return jobs


def kl_coefficient(iteration, iterations, start=0.1, end=0.02, fade=0.5):
    span = max(fade * iterations, 1.0)
    return end if iteration >= span else start + (end - start) * iteration / span


def _rollout_job(job, shaping=None):
    import time
    from experiments.rollout import fly_rollout
    level, seed, spec = job
    started = time.perf_counter()
    flown = fly_rollout(level, seed, spec, **(shaping or {}))
    flown['wall'] = time.perf_counter() - started
    return flown


def _indexed_job(fly, item):
    index, job = item
    return index, fly(job)


def longest_first(jobs, estimates):
    """Submission order for the pool: levels not yet timed first, then the slowest levels, so no long flight starts last."""
    return sorted(range(len(jobs)), key=lambda i: (jobs[i][0] in estimates, -estimates.get(jobs[i][0], 0.0), i))


class PoolRollout:
    """Flies jobs on a pool of worker processes that stays up between iterations.

    Results come back in job order whatever order the workers finish in, so the training batch does not depend on
    scheduling. Jobs go out slowest level first, judged by the previous iteration's wall times.
    """

    def __init__(self, workers, shaping=None, job=None):
        self.fly = job or functools.partial(_rollout_job, shaping=shaping)
        self.estimates = {}
        self._pool = None
        if workers > 1:
            import multiprocessing
            from experiments import run
            self._pool = multiprocessing.get_context('spawn').Pool(workers, initializer=run._use_dummy_drivers)

    def __call__(self, jobs, workers=None):
        order = longest_first(jobs, self.estimates)
        items = [(i, jobs[i]) for i in order]
        if self._pool is None:
            pairs = [_indexed_job(self.fly, item) for item in items]
        else:
            pairs = list(self._pool.imap_unordered(functools.partial(_indexed_job, self.fly), items, chunksize=1))
        results = [None] * len(jobs)
        for index, flown in pairs:
            results[index] = flown
        times = {}
        for (level, _, _), flown in zip(jobs, results):
            times.setdefault(level, []).append(flown.get('wall', 0.0))
        self.estimates = {level: sum(t) / len(t) for level, t in times.items()}
        return results

    def close(self):
        if self._pool is not None:
            self._pool.close()
            self._pool.join()
            self._pool = None


def log_line(*parts):
    print(*parts, flush=True)         # a log redirected to a file is otherwise block-buffered


def train_rl(start, out_dir, iterations, episodes=96, workers=12, lr=1e-4, seed=0, decision_frames=6,
             turn_rate=1.0, rollout=None, log=log_line, shaping=None, rules_share=0.0,
             levels=None):
    """PPO on the lab's own score, with optional reward shaping. No gate: every iteration saves a checkpoint."""
    import torch
    from experiments.score import mean_components
    policy = NeuralPolicy.load(start)                  # raises InvalidPolicy: never train from nothing
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pooled = None if rollout else PoolRollout(workers, shaping)
    rollout = rollout or (lambda jobs, count: pooled(jobs))
    net, ref = build_net(policy), build_net(policy)
    for parameter in ref.parameters():
        parameter.requires_grad_(False)
    optimiser = torch.optim.Adam(net.parameters(), lr=lr)
    current = out_dir / 'iter_start.npz'
    export(net, policy, current)
    history = []
    try:
        for iteration in range(iterations):
            jobs = make_jobs(iteration, episodes, current, decision_frames, turn_rate, rules_share,
                             levels)
            t0 = time.perf_counter()
            flown = rollout(jobs, workers)
            t1 = time.perf_counter()
            stats = improve(net, ref, optimiser, flown, policy.mean, policy.scale,
                            kl_coefficient(iteration, iterations), rng)
            summary = mean_components([e['result'] for e in flown])
            stats.update(iteration=iteration, mean_return=float(np.mean([e['rewards'].sum() for e in flown])),
                         score=summary['score'], kills_per_min=summary['kills_per_min'],
                         wall_quotient_per_min=summary['wall_quotient_per_min'],
                         hits_taken_per_min=summary['hits_taken_per_min'],
                         speed_fraction=float(np.mean([e.get('speed_fraction', 0.0) for e in flown])),
                         deaths_per_episode=float(np.mean([1.0 if e.get('died') else 0.0 for e in flown])),
                         powerups_per_episode=float(np.mean([e.get('powerups', 0) for e in flown])),
                         upgraded_fraction=float(np.mean([e.get('upgraded_fraction', 0.0) for e in flown])),
                         rollout_s=t1 - t0, update_s=time.perf_counter() - t1)
            arena = [e for e in flown if e.get('rules_arena')]
            stats.update(rules_episodes=len(arena),
                         rules_beaten=float(np.mean([1.0 if e.get('rules_beaten') else 0.0 for e in arena]))
                         if arena else 0.0)
            blind = sum(e.get('blind_steps', 0) for e in flown)
            stats.update(compass_follow=sum(e.get('following_steps', 0) for e in flown) / blind if blind else 0.0)
            unseen = sum(e.get('unseen_steps', 0) for e in flown)
            stats.update(unaimed_shots_per_episode=float(np.mean([e.get('unaimed_shots', 0) for e in flown])))
            stats.update(bored_fraction=sum(e.get('bored_steps', 0) for e in flown) / unseen if unseen else 0.0)
            current = out_dir / f'iter{iteration:04d}.npz'
            export(net, policy, current)
            history.append(stats)
            line = ' '.join(f'{k}={v:.3f}' if isinstance(v, float) else f'{k}={v}' for k, v in stats.items())
            log(line)
            with open(out_dir / 'train.log', 'a') as record:     # the dashboard reads the newest run's train.log
                record.write(line + '\n')
    finally:
        if pooled is not None:
            pooled.close()
    (out_dir / 'iter_start.npz').unlink(missing_ok=True)
    return {'last': current if history else None, 'history': history}


def reward_summary(args):
    """The reward terms a run trains on, as plain numbers for the dashboard: (name, sign, value, unit) rows."""
    from experiments.harness import IDLE_AFTER_SECONDS
    from experiments.rollout import KILL_REWARD_TOTAL
    from experiments.score import Weights
    w = Weights()
    rows = [('Kills', '+', KILL_REWARD_TOTAL, 'points shared across all the enemies in an episode'),
            ('Powerup collected', '+', args.powerup_reward, 'points each'),
            ('Gun upgraded', '+', args.upgrade_bonus, 'points per second'),
            ('Wall impact', '-', w.quotient * args.wall_scale, 'points per full-speed hit (scales with the speed lost)'),
            ('Enemy hit', '-', w.hit * args.hit_scale, 'points each'),
            ('Idle', '-', w.idle / 60.0, f'points per second beyond {IDLE_AFTER_SECONDS:.0f} s without a kill, until the field is clear'),
            ('Flying below top speed', '-', args.speed_penalty, 'points per second at a standstill, in proportion to the shortfall'),
            ('Crawling under the still speed', '-', args.still_penalty, f'points per second below {args.still_speed:.0%} of top speed'),
            ('Starting or reversing a turn', '-', args.turn_change_penalty, 'points each'),
            ('Reversing a turn directly', '-', args.reversal_penalty, 'extra points each, left to right or back'),
            ('Death', '-', args.death_penalty, f'points when the hunter is destroyed (it survives {args.health} hits)'),
            ('Rules hunter destroyed', '+', args.rules_bounty, 'points, on top of its share of the kill reward'),
            ('Following the enemy compass', '+', getattr(args, 'compass_reward', 0.0),
             'points per maze width the route to the nearest enemy shortens while none is in sight'),
            ('Shot with no enemy in sight', '-', getattr(args, 'shot_price', 0.0), 'points each'),
            ('Boredom', '-', getattr(args, 'boredom_penalty', 0.0),
             f'points per second with no enemy in sight in a cell visited in the last {getattr(args, "boredom_window", 10.0):g} s')]
    return [{'name': n, 'sign': s, 'value': round(v, 4), 'unit': u} for n, s, v, u in rows if v]


def _wall_energy():
    import config
    return config.SETTINGS.game.neuralWallEnergy


def parse_levels(text):
    """'1-20' or '4,7,13' (or a mix) as a tuple of level numbers."""
    levels = []
    for part in text.split(','):
        low, _, high = part.strip().partition('-')
        levels.extend(range(int(low), int(high or low) + 1))
    return tuple(levels)


def write_run_config(args):
    """Record what this run trains on beside its log, so the dashboard can list it."""
    import json
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'config.json').write_text(json.dumps({
        'rewards': reward_summary(args),
        'episode': {'horizon_seconds': args.horizon, 'after_clear_seconds': args.after_clear,
                    'episodes_per_iteration': args.episodes, 'learning_rate': args.lr,
                    'health': args.health, 'wall_energy': _wall_energy() if args.health else 0,
                    'rules_share': args.rules_share, 'levels': args.levels},
        'start': str(args.start)}, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default=str(DEFAULT_START))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument('--episodes', type=int, default=96)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 1)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--wall-scale', type=float, default=1.0,
                        help='multiplies the wall-collision penalty in the training reward (the score is unchanged)')
    parser.add_argument('--fixed-start', action='store_true',
                        help='start the hunter beside the player on every episode instead of at a random open cell')
    parser.add_argument('--still-speed', type=float, default=0.15,
                        help='below this share of top speed counts as near-motionless')
    parser.add_argument('--turn-change-penalty', type=float, default=0.0,
                        help='points lost each time a turn starts or reverses')
    parser.add_argument('--health', type=int, default=0,
                        help='hits the hunter survives before it is destroyed and the episode ends (0: indestructible)')
    parser.add_argument('--death-penalty', type=float, default=0.0,
                        help='points lost when the hunter is destroyed (needs --health)')
    parser.add_argument('--reversal-penalty', type=float, default=0.0,
                        help='extra points lost each time the turn flips straight from left to right or back')
    parser.add_argument('--horizon', type=float, default=DEFAULT_HORIZON,
                        help='seconds of game time per training episode')
    parser.add_argument('--still-penalty', type=float, default=0.0,
                        help='points lost per second spent near-motionless in the training reward')
    parser.add_argument('--speed-penalty', type=float, default=0.0,
                        help='points lost per second at standstill, scaling down linearly to zero at top speed')
    parser.add_argument('--powerup-reward', type=float, default=0.0,
                        help='points gained per powerup crystal the hunter collects in the training reward')
    parser.add_argument('--upgrade-bonus', type=float, default=0.0,
                        help='points gained per second the hunter\'s guns are upgraded in the training reward')
    parser.add_argument('--decoy-player', action='store_true',
                        help='leave the parked player as a target for enemies (by default they chase only the hunter)')
    parser.add_argument('--after-clear', type=float, default=0.0,
                        help='seconds an episode keeps going after the last enemy dies (less if no crystal is left)')
    parser.add_argument('--hit-scale', type=float, default=1.0,
                        help='multiplies the enemy-hit penalty in the training reward (the score is unchanged)')
    parser.add_argument('--rules-share', type=float, default=0.25,
                        help='share of episodes flown on the Rules hunter level (25); 0 keeps the old level cycle')
    parser.add_argument('--rules-bounty', type=float, default=50.0,
                        help='points gained for destroying the Rules hunter in the training reward')
    parser.add_argument('--compass-reward', type=float, default=0.0,
                        help='points per maze width the enemy compass route shortens while no enemy is in sight')
    parser.add_argument('--boredom-penalty', type=float, default=0.0,
                        help='points lost per second with no enemy in sight in a recently visited maze cell')
    parser.add_argument('--boredom-window', type=float, default=10.0,
                        help='seconds before a visited maze cell counts as new again')
    parser.add_argument('--shot-price', type=float, default=0.0,
                        help='points lost per shot fired with no enemy in sight (the neural hunter fires unaimed then)')
    parser.add_argument('--levels', type=parse_levels, default=None,
                        help='levels to train on, e.g. 1-20 or 4,7,13 (default: the tune set)')
    args = parser.parse_args(argv)
    write_run_config(args)
    from experiments import run
    run._use_dummy_drivers()
    result = train_rl(args.start, args.out, args.iterations, args.episodes, args.workers, lr=args.lr,
                      shaping={'wall_scale': args.wall_scale, 'hit_scale': args.hit_scale,
                               'still_penalty': args.still_penalty, 'horizon': args.horizon,
                               'random_start': not args.fixed_start,
                               'still_speed': args.still_speed,
                               'turn_change_penalty': args.turn_change_penalty,
                               'reversal_penalty': args.reversal_penalty,
                               'health': args.health, 'death_penalty': args.death_penalty,
                               'speed_penalty': args.speed_penalty,
                               'powerup_reward': args.powerup_reward, 'after_clear': args.after_clear,
                               'upgrade_bonus': args.upgrade_bonus, 'pursue_hunter': not args.decoy_player,
                               'rules_bounty': args.rules_bounty, 'compass_reward': args.compass_reward,
                               'boredom_penalty': args.boredom_penalty, 'boredom_window': args.boredom_window,
                               'shot_price': args.shot_price},
                      rules_share=args.rules_share, levels=args.levels)
    print('done | last checkpoint:', result['last'])


if __name__ == '__main__':
    main(sys.argv[1:])
