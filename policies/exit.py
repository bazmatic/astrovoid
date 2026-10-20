"""When a level's exit opens. Each policy reads only an ExitState, never the game."""
import math
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Iterable, List, Mapping, Optional, Protocol, Tuple

import enemy_kinds
from policies.registry import PolicyError, PolicyRegistry


@dataclass(frozen=True)
class ExitState:
    """What an exit policy may look at: play time so far, and how many of each kind of enemy are alive."""
    elapsed_seconds: float
    active: Mapping[str, int]

    def left(self, kinds: Optional[Iterable[str]] = None) -> int:
        """Enemies alive of these kinds, or of every kind."""
        if kinds is None:
            return sum(self.active.values())
        return sum(self.active.get(kind, 0) for kind in kinds)


class ExitPolicy(Protocol):
    name: ClassVar[str]

    def is_open(self, state: ExitState) -> bool: ...

    def describe(self, state: ExitState) -> List[str]:
        """The EXIT panel's lines while the exit is shut."""
        ...

    def label(self) -> str:
        """A one-line summary for the editor."""
        ...

    def to_json(self) -> Dict[str, Any]: ...

    @classmethod
    def from_json(cls, data: Mapping) -> 'ExitPolicy': ...

    @classmethod
    def starter(cls) -> 'ExitPolicy': ...


EXIT_POLICIES = PolicyRegistry('exit policy')


@EXIT_POLICIES.register
@dataclass(frozen=True)
class AlwaysOpen:
    name: ClassVar[str] = 'always_open'

    def is_open(self, state: ExitState) -> bool:
        return True

    def describe(self, state: ExitState) -> List[str]:
        return []

    def label(self) -> str:
        return 'Always open'

    def to_json(self) -> Dict[str, Any]:
        return {'type': self.name}

    @classmethod
    def from_json(cls, data: Mapping) -> 'AlwaysOpen':
        return cls()

    @classmethod
    def starter(cls) -> 'AlwaysOpen':
        return cls()


@EXIT_POLICIES.register
@dataclass(frozen=True)
class OpenAfterTime:
    seconds: float
    name: ClassVar[str] = 'timer'

    def is_open(self, state: ExitState) -> bool:
        return state.elapsed_seconds >= self.seconds

    def describe(self, state: ExitState) -> List[str]:
        wait = max(0, math.ceil(self.seconds - state.elapsed_seconds))
        return ['OPENS IN', f'{wait // 60}:{wait % 60:02d}']

    def label(self) -> str:
        return f'Timer {self._json_seconds()}s'

    def to_json(self) -> Dict[str, Any]:
        return {'type': self.name, 'seconds': self._json_seconds()}

    def _json_seconds(self):
        return int(self.seconds) if float(self.seconds).is_integer() else self.seconds

    @classmethod
    def from_json(cls, data: Mapping) -> 'OpenAfterTime':
        seconds = data.get('seconds')
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 <= seconds < math.inf:
            raise PolicyError(f'a timer needs "seconds" of 0 or more, got {seconds!r}')
        return cls(seconds)

    @classmethod
    def starter(cls) -> 'OpenAfterTime':
        return cls(60)


@EXIT_POLICIES.register
@dataclass(frozen=True)
class TypeCleared:
    enemy_types: Tuple[str, ...]
    name: ClassVar[str] = 'type_cleared'

    def is_open(self, state: ExitState) -> bool:
        return state.left(self.enemy_types) == 0

    def describe(self, state: ExitState) -> List[str]:
        return ['KILL ' + self._plurals().upper(), f'{state.left(self.enemy_types)} LEFT']

    def label(self) -> str:
        return 'Kill ' + self._plurals()

    def _plurals(self) -> str:
        return ', '.join(enemy_kinds.plural(kind) for kind in self.enemy_types)

    def to_json(self) -> Dict[str, Any]:
        return {'type': self.name, 'enemy_types': list(self.enemy_types)}

    @classmethod
    def from_json(cls, data: Mapping) -> 'TypeCleared':
        kinds = data.get('enemy_types')
        if not isinstance(kinds, list) or not kinds or not all(kind in enemy_kinds.kinds() for kind in kinds):
            raise PolicyError(f'"enemy_types" must list enemy kinds from {enemy_kinds.kinds()}, got {kinds!r}')
        return cls(tuple(dict.fromkeys(kinds)))  # a kind named twice still counts once

    @classmethod
    def starter(cls) -> 'TypeCleared':
        return cls(('egg',))


@EXIT_POLICIES.register
@dataclass(frozen=True)
class AllCleared:
    name: ClassVar[str] = 'all_cleared'

    def is_open(self, state: ExitState) -> bool:
        return state.left() == 0

    def describe(self, state: ExitState) -> List[str]:
        return ['KILL ALL', f'{state.left()} LEFT']

    def label(self) -> str:
        return 'Kill all'

    def to_json(self) -> Dict[str, Any]:
        return {'type': self.name}

    @classmethod
    def from_json(cls, data: Mapping) -> 'AllCleared':
        return cls()

    @classmethod
    def starter(cls) -> 'AllCleared':
        return cls()


DEFAULT_EXIT_POLICY = AlwaysOpen()
