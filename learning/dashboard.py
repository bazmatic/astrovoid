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
    # Their own section, so they come after every task's charts, where the page has always drawn them.
    Metric('kl', 'Distance from the starting policy (KL)', 'How far the policy has moved from where the run started.',
           section='Policy'),
    Metric('entropy', 'Policy entropy', 'Randomness of the controls. Near zero means it has stopped exploring.',
           section='Policy'),
)

# Log keys every trainer writes that are bookkeeping, timing, gate flags or optimiser internals rather than something to
# chart. A task hides its own such keys with HIDDEN in its dashboard module.
HIDDEN_KEYS = frozenset({'iteration', 'rollout_s', 'update_s', 'elapsed_s', 'policy', 'team_size',
                         'selection_gate_passed', 'policy_loss', 'value_loss', 'clip_fraction'})


def declaration(task_key: str) -> SimpleNamespace:
    """The task's declared METRICS, LAYOUT, HIDDEN, REWARD_RULES and cards(config); empty ones for a task with no
    module."""
    spec = task(task_key)
    module = importlib.import_module(spec.dashboard) if spec.dashboard else None
    return SimpleNamespace(
        METRICS=tuple(getattr(module, 'METRICS', ())),
        LAYOUT=getattr(module, 'LAYOUT', Layout()),
        HIDDEN=tuple(getattr(module, 'HIDDEN', ())),
        REWARD_RULES=tuple(getattr(module, 'REWARD_RULES', ())),
        cards=getattr(module, 'cards', lambda config: []))


def resolve(task_key: str) -> dict:
    spec, declared = task(task_key), declaration(task_key)
    return dict(key=spec.key, label=spec.label, capabilities=asdict(spec.capabilities),
                metrics=[dict(asdict(m), aliases=list(m.aliases)) for m in SHARED_METRICS + declared.METRICS],
                sections=list(declared.LAYOUT.sections), strip=list(declared.LAYOUT.strip),
                rewards=[], hidden=sorted(HIDDEN_KEYS | set(declared.HIDDEN)))


def resolve_all() -> list[dict]:
    return [resolve(key) for key in TASKS]


def charted(task_key: str, keys: Iterable[str]) -> list[dict]:
    """The resolved metrics the page draws for a run whose last log row has these keys, in drawing order: a metric is
    drawn iff its key or an alias is present; metrics group by section, sections in the layout's order and then in
    order of first appearance, declaration order within a section."""
    resolved, present = resolve(task_key), set(keys)
    order = list(resolved['sections'])
    order += [m['section'] for m in resolved['metrics'] if m['section'] not in order]
    drawn = [m for m in resolved['metrics'] if present & {m['key'], *m['aliases']}]
    return sorted(drawn, key=lambda m: order.index(m['section']))   # stable: declaration order within a section


def unclaimed(task_key: str, keys: Iterable[str]) -> list[str]:
    declared = declaration(task_key)
    claimed = set(HIDDEN_KEYS) | set(declared.HIDDEN)
    for metric in SHARED_METRICS + declared.METRICS:
        claimed.add(metric.key)
        claimed.update(metric.aliases)
    return sorted(set(keys) - claimed)
