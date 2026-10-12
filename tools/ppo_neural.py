"""Recurrent PPO fine-tuning of the neural student: python -m tools.ppo_neural (the loop is in Task 3)."""
import numpy as np
from hunter.neural.policy import HEAD_SIZES
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
