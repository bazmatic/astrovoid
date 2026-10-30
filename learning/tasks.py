"""Task registry is the only place that knows the available creature/scenario adapters."""
from dataclasses import dataclass, field
import importlib


@dataclass(frozen=True)
class Task:
    key: str
    module: str
    label: str
    fresh_defaults: dict = field(default_factory=dict)
    options: tuple = ()
    replay_module: str | None = None
    replay_hooks: str | None = None   # the module learning.replay asks to rebuild, score and draw this task's episodes

    def replay(self):
        return importlib.import_module(self.replay_module) if self.replay_module else None

    def adapter(self):
        return importlib.import_module(self.module)


TASKS = {
    'hunter': Task('hunter', 'learning.adapters.hunter', 'Hunter'),
    'wallcrawler_team': Task('wallcrawler_team', 'learning.adapters.crawler_scenario', 'Wallcrawler team',
        dict(horizon=60.0,workers=4,iterations=10000),
        ('opponent','budget_seconds','bootstrap_episodes','seed'), 'learning.replay',
        'learning.adapters.crawler_replay'),
    # No imitation bootstrap by default: the scripted Jelly teacher (learning.adapters.jelly.teacher) is weak.
    'jelly_team': Task('jelly_team', 'learning.adapters.jelly_scenario', 'Jelly team',
        dict(horizon=60.0, workers=4, iterations=10000, bootstrap_episodes=0),
        ('budget_seconds','bootstrap_episodes','seed'), 'learning.replay',
        'learning.adapters.jelly_replay'),
}

# Replayable runs recorded before config.json named its task were all Wallcrawler team runs.
UNTAGGED_REPLAY_TASK = 'wallcrawler_team'


def task(key='hunter'):
    try:
        return TASKS[key]
    except KeyError:
        raise ValueError(f'unknown training task: {key}') from None
