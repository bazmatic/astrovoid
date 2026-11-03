"""Optional deployment weights, loaded once per encounter; no learner imports."""
import logging
import os
from pathlib import Path


def driver_for(enc):
    from learning.adapters.inchworm import InchwormDriver, load_policy
    if not hasattr(enc, '_inchworm_policy'):
        if hasattr(enc.world, 'inchworm_policy'):
            enc._inchworm_policy = enc.world.inchworm_policy
        else:
            selected = os.getenv('INCHWORM_POLICY')
            path = Path(selected) if selected else Path(__file__).resolve().parents[1]/'assets/neural/inchworm.npz'
            enc._inchworm_policy = None
            if selected != '' and (selected is not None or path.is_file()):
                try:
                    enc._inchworm_policy = load_policy(path)
                except (OSError,ValueError,KeyError,TypeError) as exc:
                    logging.getLogger(__name__).warning('Inchworm policy %s unavailable; using reflex controller: %s',path,exc)
    return InchwormDriver(enc._inchworm_policy) if enc._inchworm_policy is not None else None
