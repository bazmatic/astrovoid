"""Whether a level's ammo runs out."""
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Mapping, Protocol

from policies.registry import PolicyRegistry


class AmmoPolicy(Protocol):
    name: ClassVar[str]

    def charges_for_shots(self) -> bool:
        """Whether each shot takes ammo from the ship's stock."""
        ...

    def label(self) -> str: ...

    def to_json(self) -> Dict[str, Any]: ...

    @classmethod
    def from_json(cls, data: Mapping) -> 'AmmoPolicy': ...

    @classmethod
    def starter(cls) -> 'AmmoPolicy': ...


AMMO_POLICIES = PolicyRegistry('ammo policy')


@dataclass(frozen=True)
class _SettinglessAmmo:
    name: ClassVar[str]

    def to_json(self) -> Dict[str, Any]:
        return {'type': self.name}

    @classmethod
    def from_json(cls, data: Mapping):
        return cls()

    @classmethod
    def starter(cls):
        return cls()


@AMMO_POLICIES.register
@dataclass(frozen=True)
class LimitedAmmo(_SettinglessAmmo):
    """A stock of initialAmmo, topped up by powerups and kills."""
    name: ClassVar[str] = 'limited'

    def charges_for_shots(self) -> bool:
        return True

    def label(self) -> str:
        return 'Limited ammo'


@AMMO_POLICIES.register
@dataclass(frozen=True)
class UnlimitedAmmo(_SettinglessAmmo):
    name: ClassVar[str] = 'unlimited'

    def charges_for_shots(self) -> bool:
        return False

    def label(self) -> str:
        return 'Unlimited ammo'


DEFAULT_AMMO_POLICY = LimitedAmmo()
