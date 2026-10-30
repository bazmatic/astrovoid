"""Gaussian activation policies; adapters tanh the recorded latent into bounded strength.

Recording the pre-squash activation avoids lossy atanh reconstruction near saturation.
The transform's Jacobian cancels in PPO ratios; entropy includes that Jacobian.
"""
import math
import numpy as np

LOG_STD_MIN = -5.
LOG_STD_MAX = 1.
INITIAL_LOG_STD = math.log(.35)
_NODES, _WEIGHTS = np.polynomial.hermite.hermgauss(16)


def sample_activation(parameters, rng=None, greedy=False, temperature=1.):
    mean, log_std = parameters
    std = math.exp(float(np.clip(log_std, LOG_STD_MIN, LOG_STD_MAX))) * temperature
    return float(np.float32(mean if greedy else rng.normal(mean, std)))


def statistics(parameters, activation):
    """Latent log density and quadrature estimate of tanh-Gaussian entropy."""
    import torch
    mean = parameters[..., 0]
    log_std = parameters[..., 1].clamp(LOG_STD_MIN, LOG_STD_MAX)
    std = log_std.exp()
    logp = -.5*((activation-mean)/std).square()-log_std-.5*math.log(2*math.pi)
    nodes = torch.as_tensor(_NODES, dtype=mean.dtype, device=mean.device)
    weights = torch.as_tensor(_WEIGHTS/math.sqrt(math.pi), dtype=mean.dtype, device=mean.device)
    z = mean[..., None]+math.sqrt(2)*std[..., None]*nodes
    log_jacobian = 2*(math.log(2)-z-torch.nn.functional.softplus(-2*z))
    entropy = log_std+.5*math.log(2*math.pi*math.e)+(log_jacobian*weights).sum(-1)
    return logp, entropy
