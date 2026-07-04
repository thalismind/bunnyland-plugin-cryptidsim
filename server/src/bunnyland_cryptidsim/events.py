"""Domain events emitted by the sighting verb and the confirmation consequence."""

from __future__ import annotations

from bunnyland.core.events import DomainEvent


class SightingRecordedEvent(DomainEvent):
    """A character logged a (possibly blurry) sighting of a cryptid."""

    cryptid_id: str
    cryptid_name: str
    clarity: float
    clear: bool


class CryptidConfirmedEvent(DomainEvent):
    """Enough clear sightings confirmed a cryptid: a discovery/reputation reward."""

    cryptid_id: str
    cryptid_name: str
    investigator_id: str
    clear_count: int
    reputation: float


__all__ = ["CryptidConfirmedEvent", "SightingRecordedEvent"]
