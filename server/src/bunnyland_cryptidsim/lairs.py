"""Lairs and movement patterns: a cryptid keeps a den and prowls a predictable beat.

A **lair** is a room a cryptid calls home (:class:`LairComponent`), linked to the creature by
a :class:`HauntsLair` **typed edge** (the structural link is its own edge subclass, not a
string field on a component — so "who lairs where" is its own queryable index). A cryptid that
also carries a :class:`MovementPatternComponent` follows a *deterministic* beat: under cover
of night it prowls out to one of the lair's adjacent rooms, and by day it slinks back home.

The beat is chosen by a ``hashlib`` digest over the creature id and the day index, so the same
world always moves the same creature to the same place on the same night — no ``random`` or
``time``. Learning a cryptid's beat (and staking out its lair) is what lets an investigator
put a camera trap in the right room: a sighting made in or beside the lair reads clearer,
because the creature is bold on its own ground.
"""

from __future__ import annotations

import hashlib

from bunnyland.core import (
    ContainmentMode,
    Contains,
    ExitTo,
    remove_from_container,
    spawn_entity,
)
from bunnyland.core.components import RoomComponent
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from pydantic.dataclasses import dataclass
from relics import Component, Edge, Entity, World

from .components import CryptidComponent
from .conditions import is_concealing
from .spatial import room_of

SECONDS_PER_DAY = 24 * 60 * 60

#: Extra clarity a sighting/trap gains when the creature is caught in its own lair room.
LAIR_HOME_BONUS = 0.15


@dataclass(frozen=True)
class LairComponent(Component):
    """Marks a room as an established cryptid lair."""

    habitat: str = "wilderness"
    established_at_epoch: int = 0


@dataclass(frozen=True)
class HauntsLair(Edge):
    """cryptid -> the room that is its lair (a structural, queryable link)."""

    since_epoch: int = 0


@dataclass(frozen=True)
class MovementPatternComponent(Component):
    """A cryptid's nightly beat: prowl under cover, den up by day."""

    pattern: str = "nocturnal_prowl"
    stays_home_by_day: bool = True


class CryptidProwledEvent(DomainEvent):
    """A cryptid moved along its beat between two rooms."""

    cryptid_id: str
    cryptid_name: str
    from_room_id: str
    to_room_id: str


def establish_lair(
    world: World,
    cryptid: Entity,
    *,
    room_id=None,
    habitat: str | None = None,
    epoch: int = 0,
) -> Entity | None:
    """Mark ``room_id`` as ``cryptid``'s lair and link them with a :class:`HauntsLair` edge.

    Returns the lair room, or ``None`` if the room is unknown. Reuses the creature's own
    habitat when one is not given.
    """
    if room_id is None or not world.has_entity(room_id):
        return None
    room = world.get_entity(room_id)
    if habitat is None and cryptid.has_component(CryptidComponent):
        habitat = cryptid.get_component(CryptidComponent).habitat
    if not room.has_component(LairComponent):
        room.add_component(
            LairComponent(habitat=habitat or "wilderness", established_at_epoch=epoch)
        )
    cryptid.add_relationship(HauntsLair(since_epoch=epoch), room.id)
    return room


def lair_room_of(world: World, cryptid: Entity) -> Entity | None:
    """The room ``cryptid`` lairs in, or ``None`` when it keeps no den."""
    for _edge, room_id in cryptid.get_relationships(HauntsLair):
        if world.has_entity(room_id):
            return world.get_entity(room_id)
    return None


def lair_clarity_bonus(world: World, cryptid: Entity, room: Entity | None) -> float:
    """Clarity bonus for catching ``cryptid`` in its own lair room (0 otherwise)."""
    if room is None:
        return 0.0
    lair = lair_room_of(world, cryptid)
    if lair is not None and lair.id == room.id:
        return LAIR_HOME_BONUS
    return 0.0


def _prowl_destination(world: World, lair: Entity, cryptid_id: str, day_index: int):
    """Deterministically pick where a cryptid prowls tonight: its lair, or an adjacent room."""
    neighbors = sorted(
        (target for _edge, target in lair.get_relationships(ExitTo) if world.has_entity(target)),
        key=str,
    )
    options = [lair.id, *neighbors]
    seed = f"{cryptid_id}|{day_index}".encode()
    index = hashlib.sha256(seed).digest()[0] % len(options)
    return options[index]


def _relocate(world: World, entity: Entity, dest_room: Entity) -> None:
    remove_from_container(world, entity.id)
    dest_room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), entity.id)


class LairProwlConsequence:
    """Move patterned cryptids along their deterministic nightly beat each tick."""

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        concealing = is_concealing(world, None)
        day_index = epoch // SECONDS_PER_DAY
        query = world.query().with_all([CryptidComponent, MovementPatternComponent])
        for cryptid in list(query.execute_entities()):
            lair = lair_room_of(world, cryptid)
            if lair is None:
                continue
            pattern = cryptid.get_component(MovementPatternComponent)
            current = room_of(world, cryptid.id)
            if concealing:
                dest_id = _prowl_destination(world, lair, str(cryptid.id), day_index)
            elif pattern.stays_home_by_day:
                dest_id = lair.id
            else:
                continue
            if current is not None and current.id == dest_id:
                continue
            if not world.has_entity(dest_id):
                continue
            dest = world.get_entity(dest_id)
            if not dest.has_component(RoomComponent):
                continue
            _relocate(world, cryptid, dest)
            events.append(
                CryptidProwledEvent(
                    **event_base(
                        epoch,
                        default_visibility=EventVisibility.ROOM,
                        actor_id=str(cryptid.id),
                        room_id=str(dest.id),
                        target_ids=(str(cryptid.id),),
                        cryptid_id=str(cryptid.id),
                        cryptid_name=cryptid.get_component(CryptidComponent).name,
                        from_room_id=str(current.id) if current is not None else "",
                        to_room_id=str(dest.id),
                    )
                )
            )
        return events


def spawn_lair_room(world: World, *, title: str = "Lair", habitat: str = "cave", epoch: int = 0):
    """Spawn a room already marked as a lair (test/worldgen helper)."""
    return spawn_entity(
        world,
        [RoomComponent(title=title), LairComponent(habitat=habitat, established_at_epoch=epoch)],
    )


def install_lairs(actor) -> None:
    """Register the nightly lair-prowl consequence (a ``service_factories`` entry)."""
    actor.register_consequence(LairProwlConsequence())


__all__ = [
    "LAIR_HOME_BONUS",
    "CryptidProwledEvent",
    "HauntsLair",
    "LairComponent",
    "LairProwlConsequence",
    "MovementPatternComponent",
    "establish_lair",
    "install_lairs",
    "lair_clarity_bonus",
    "lair_room_of",
    "spawn_lair_room",
]
