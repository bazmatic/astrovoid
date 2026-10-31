"""What the trainer dashboard shows for each task: shared metrics plus the task's own declaration module."""
from dataclasses import asdict, dataclass
import importlib
from types import SimpleNamespace
from typing import Iterable

from learning.tasks import TASKS, task


@dataclass(frozen=True)
class Metric:
    key: str
    title: str
    sub: str = ''
    unit: str = ''
    section: str = 'Training'
    higher_is_better: bool | None = None
    optional: bool = False
    aliases: tuple[str, ...] = ()
    wide: bool = False


@dataclass(frozen=True)
class Layout:
    """Ordering overrides; empty means declaration order."""
    sections: tuple[str, ...] = ()
    strip: tuple[str, ...] = ()


SHARED_METRICS = (
    Metric('mean_return', 'Training return', 'Higher is better. What training maximises. Only comparable within a run.',
           higher_is_better=True, wide=True),
    Metric('kl', 'Distance from the starting policy (KL)', 'How far the policy has moved from where the run started.'),
    Metric('entropy', 'Policy entropy', 'Randomness of the controls. Near zero means it has stopped exploring.'),
)

# Log keys that are bookkeeping, timing or gate flags rather than something to chart.
HIDDEN_KEYS = frozenset({'iteration', 'rollout_s', 'update_s', 'elapsed_s', 'policy', 'team_size',
                         'selection_gate_passed'})


def declaration(task_key: str) -> SimpleNamespace:
    """The task's declared METRICS, LAYOUT, REWARD_RULES and cards(config); empty ones for a task with no module."""
    spec = task(task_key)
    module = importlib.import_module(spec.dashboard) if spec.dashboard else None
    return SimpleNamespace(
        METRICS=tuple(getattr(module, 'METRICS', ())),
        LAYOUT=getattr(module, 'LAYOUT', Layout()),
        REWARD_RULES=tuple(getattr(module, 'REWARD_RULES', ())),
        cards=getattr(module, 'cards', lambda config: []))


def resolve(task_key: str) -> dict:
    spec, declared = task(task_key), declaration(task_key)
    return dict(key=spec.key, label=spec.label, capabilities=asdict(spec.capabilities),
                metrics=[dict(asdict(m), aliases=list(m.aliases)) for m in SHARED_METRICS + declared.METRICS],
                sections=list(declared.LAYOUT.sections), strip=list(declared.LAYOUT.strip),
                rewards=[], hidden=sorted(HIDDEN_KEYS))


def resolve_all() -> list[dict]:
    return [resolve(key) for key in TASKS]


def unclaimed(task_key: str, keys: Iterable[str]) -> list[str]:
    claimed = set(HIDDEN_KEYS)
    for metric in SHARED_METRICS + declaration(task_key).METRICS:
        claimed.add(metric.key)
        claimed.update(metric.aliases)
    return sorted(set(keys) - claimed)
