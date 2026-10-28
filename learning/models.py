"""Shared Torch model construction and weight conversion; never imported by gameplay."""

def network_class(features, heads):
    import torch
    class Network(torch.nn.Module):
        def __init__(self, hidden=128, embed=64):
            super().__init__()
            self.embed = torch.nn.Linear(features, embed)
            self.gru = torch.nn.GRU(embed, hidden, batch_first=True)
            self.heads = torch.nn.ModuleDict({k: torch.nn.Linear(hidden, n) for k, n in heads.items()})
        def forward(self, x, state=None):
            h, state = self.gru(torch.tanh(self.embed(x)), state)
            return {k: head(h) for k, head in self.heads.items()}, state
    return Network


def parameters(net, heads):
    result = dict(embed_w=net.embed.weight, embed_b=net.embed.bias,
                  gru_w_ih=net.gru.weight_ih_l0, gru_w_hh=net.gru.weight_hh_l0,
                  gru_b_ih=net.gru.bias_ih_l0, gru_b_hh=net.gru.bias_hh_l0)
    for head in heads:
        result[head+'_w'], result[head+'_b'] = net.heads[head].weight, net.heads[head].bias
    return result


def load_into(net, policy, heads):
    import torch
    with torch.no_grad():
        for key, tensor in parameters(net, heads).items():
            tensor.copy_(torch.from_numpy(policy.params[key]))


def export(net, policy):
    from learning.policy import RecurrentPolicy
    params = {k: v.detach().cpu().numpy().copy() for k, v in parameters(net, dict(policy.spec.heads)).items()}
    return RecurrentPolicy(params, policy.mean, policy.scale, policy.spec)
