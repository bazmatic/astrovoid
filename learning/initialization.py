"""One-time actor output damping for an explicit relearning continuation."""
import math
import numpy as np
from learning.policy import RecurrentPolicy
from learning.continuous import INITIAL_LOG_STD


def dampen_actor(policy, factor):
    if not math.isfinite(factor) or not 0<factor<=1:
        raise ValueError('actor scale must be greater than zero and at most one')
    params={key:value.copy() for key,value in policy.params.items()}
    for name,_ in policy.spec.heads:
        params[name+'_w']*=factor
        params[name+'_b']*=factor
        if factor!=1 and name in policy.spec.continuous:
            params[name+'_w'][1]=0
            params[name+'_b'][1]=INITIAL_LOG_STD
    return RecurrentPolicy(params,policy.mean.copy(),policy.scale.copy(),policy.spec)
