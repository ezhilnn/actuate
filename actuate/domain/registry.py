"""actuate.domain.registry — the CapabilityRegistry.

Registers capability factories under an open `(kind, name)` namespace,
carrying `CapabilityDescriptor` metadata (version, author, description,
config schema, compatibility) for discovery/tooling — richer than a bare
name -> factory dict. `pluggy` (Phase G, capabilities/ package) is the
mechanism that *populates* a registry from installed plugins; this class
is the registry itself and has no pluggy dependency, so it's usable
standalone (tests, scripts, embedding) without pulling in the plugin
discovery machinery.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from actuate.domain.capability import CapabilityDescriptor, CapabilityKind
from actuate.domain.exceptions import CapabilityResolutionError

_Key = tuple[CapabilityKind, str]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._factories: dict[_Key, Callable[..., Any]] = {}
        self._descriptors: dict[_Key, CapabilityDescriptor] = {}

    def register(self, descriptor: CapabilityDescriptor, factory: Callable[..., Any]) -> None:
        key = (descriptor.kind, descriptor.name)
        self._factories[key] = factory
        self._descriptors[key] = descriptor

    def resolve(self, kind: CapabilityKind, name: str, **params: Any) -> Any:
        key = (kind, name)
        factory = self._factories.get(key)
        if factory is None:
            raise CapabilityResolutionError(
                f"No capability registered for kind='{kind}' name='{name}'."
            )
        return factory(**params)

    def describe(self, kind: CapabilityKind, name: str) -> CapabilityDescriptor:
        key = (kind, name)
        descriptor = self._descriptors.get(key)
        if descriptor is None:
            raise CapabilityResolutionError(
                f"No capability registered for kind='{kind}' name='{name}'."
            )
        return descriptor

    def list_names(self, kind: CapabilityKind) -> list[str]:
        return sorted(name for (k, name) in self._factories if k == kind)

    def list_kinds(self) -> list[CapabilityKind]:
        return sorted({k for (k, _name) in self._factories})

    def list_descriptors(self, kind: CapabilityKind | None = None) -> list[CapabilityDescriptor]:
        descriptors = list(self._descriptors.values())
        if kind is not None:
            descriptors = [d for d in descriptors if d.kind == kind]
        return sorted(descriptors, key=lambda d: (d.kind, d.name))
