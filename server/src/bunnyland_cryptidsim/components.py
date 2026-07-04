"""Cryptid, sighting, and case-file components.

A **cryptid** is a rare, elusive, flesh-and-blood mystery creature — never a ghost, never a
common catalogued animal. It appears only under concealing conditions (night, fog, low
light) and leaves *uncertain* evidence: a blurry photo, a half-glimpsed shape. Confirming
one is a slow, doubt-ridden process, which is what the sighting/case machinery models.

All components are immutable frozen dataclasses subclassing :class:`relics.Component`; every
update swaps a whole value with ``replace_component(entity, replace(component, ...))``.
"""

from __future__ import annotations

from pydantic.dataclasses import dataclass
from relics import Component


@dataclass(frozen=True)
class CryptidComponent(Component):
    """Marks an entity as a rare, elusive mystery creature.

    ``elusiveness`` (0..1) is how hard it is to get a clear look — higher values blur the
    evidence. ``habitat`` is the remote biome it favours (forest, swamp, mountain, lake…),
    used for flavour and worldgen placement.
    """

    name: str = "unknown cryptid"
    elusiveness: float = 0.6
    habitat: str = "wilderness"


@dataclass(frozen=True)
class ConfirmedCryptidComponent(Component):
    """Set on a cryptid once a case confirms it: it now reads as definitively real."""

    confirmed_at_epoch: int = 0


@dataclass(frozen=True)
class SightingComponent(Component):
    """A single piece of uncertain evidence produced by the ``sight`` verb.

    ``clarity`` (0..1) is how good the look was — a blurry photo scores low, a clear
    daylight-in-fog encounter scores high. It is deterministic, not random.
    """

    cryptid_id: str = ""
    cryptid_name: str = ""
    investigator_id: str = ""
    clarity: float = 0.0
    recorded_at_epoch: int = 0
    clear: bool = False


@dataclass(frozen=True)
class CryptidCaseComponent(Component):
    """An investigator's dossier on one cryptid, accumulating sightings over time.

    A case lives on its own dedicated entity — one per ``(investigator, cryptid)`` pair —
    because an investigator can hold many open cases at once. ``clear_count`` is how many
    high-clarity sightings back the case; enough of them confirm the cryptid.
    """

    investigator_id: str = ""
    cryptid_id: str = ""
    cryptid_name: str = ""
    sighting_count: int = 0
    clear_count: int = 0
    best_clarity: float = 0.0
    confirmed: bool = False


__all__ = [
    "ConfirmedCryptidComponent",
    "CryptidCaseComponent",
    "CryptidComponent",
    "SightingComponent",
]
