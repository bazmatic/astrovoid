"""One registry per policy family, mapping the "type" name a level file uses to the class that builds it."""
from typing import Any, Dict, Tuple, Type


class PolicyError(ValueError):
    """A level file's policy entry that can't be used."""


class PolicyRegistry:
    """Policy classes of one family, by name. A new policy needs only its class and `@REGISTRY.register`."""

    def __init__(self, family: str) -> None:
        self.family = family
        self._classes: Dict[str, Type] = {}

    def register(self, cls: Type) -> Type:
        if cls.name in self._classes:
            raise ValueError(f'{self.family} "{cls.name}" is registered twice')
        self._classes[cls.name] = cls
        return cls

    def parse(self, data: Any):
        """Build a policy from its JSON entry, raising PolicyError for anything it can't use."""
        if not isinstance(data, dict):
            raise PolicyError(f'expected an object with a "type", got {data!r}')
        name = data.get('type')
        if not isinstance(name, str) or name not in self._classes:
            raise PolicyError(f'unknown {self.family} type {name!r}')
        return self._classes[name].from_json(data)

    def names(self) -> Tuple[str, ...]:
        return tuple(self._classes)

    def starter(self, name: str):
        """A sensible first setting of the named policy, for the editor."""
        return self._classes[name].starter()
