"""The cryptid flap: a paced storyteller incident, registered into the shared budget.

A **flap** is a surge of cryptid activity — the weeks when every farmhand swears they saw
*something*. This module registers that surge as a **core storyteller incident** rather than
inventing a private one: when sighting buzz pushes pressure over the line under cover of night,
:class:`CryptidFlapConsequence` manifests a bold new creature into an occupied room and stamps
the moment with the core :class:`~bunnyland.mechanics.storyteller.IncidentComponent`
(``kind="cryptid_flap"``), so it shows up in the storyteller prompt like any other world event.

Pacing mirrors the core storyteller (an interval and a next-due epoch on the world clock) and
pressure is *earned*: it climbs with the number of sightings already logged, so a quiet world
never flaps and a well-watched one eventually does. While a flap is live, every sighting reads
a little clearer — the whole world is primed to notice. The flap closes itself once its run
elapses. Deterministic throughout: creature choice is a ``hashlib`` digest over the epoch.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldClockComponent,
    container_of,
    spawn_entity,
)
from bunnyland.core.components import DeadComponent, SuspendedComponent
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.mechanics.storyteller import IncidentComponent
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .components import CryptidComponent, SightingComponent
from .conditions import is_concealing
from .lairs import MovementPatternComponent, establish_lair

SECONDS_PER_DAY = 24 * 60 * 60

#: Creatures a flap can put on everyone's lips, in a stable order (chosen by epoch).
FLAP_CREATURES: tuple[str, ...] = ("mothman", "lake serpent", "hairy hominid", "thunderbird")

#: Pressure needed before a flap actually breaks (base + sighting buzz).
FLAP_THRESHOLD = 0.6

#: Buzz added per logged sighting, and its cap, when computing flap pressure.
BUZZ_PER_SIGHTING = 0.1
MAX_BUZZ = 1.0

#: How long a flap runs before it closes itself.
FLAP_DURATION_SECONDS = 3 * SECONDS_PER_DAY

#: Extra clarity every sighting gains while a flap is live.
FLAP_CLARITY_BONUS = 0.1

#: A flap creature is bold, but still elusive.
FLAP_ELUSIVENESS = 0.7


@dataclass(frozen=True)
class CryptidFlapPressureComponent(Component):
    """World-level pacing/policy for cryptid flaps (rests on the world clock)."""

    enabled: bool = True
    interval_seconds: int = SECONDS_PER_DAY
    next_flap_epoch: int = SECONDS_PER_DAY
    base_pressure: float = 0.3


class CryptidFlapStartedEvent(DomainEvent):
    """A flap broke out: a bold cryptid manifested and buzz spiked."""

    incident_id: str
    cryptid_id: str
    cryptid_name: str
    pressure: float


class CryptidFlapEndedEvent(DomainEvent):
    """A flap ran its course and quieted down."""

    incident_id: str


def ensure_flap_pressure(world: World) -> Entity | None:
    """Seed a :class:`CryptidFlapPressureComponent` onto the world clock (idempotent)."""
    existing = list(world.query().with_all([CryptidFlapPressureComponent]).execute_entities())
    if existing:
        return existing[0]
    clocks = sorted(
        world.query().with_all([WorldClockComponent]).execute_entities(), key=lambda e: str(e.id)
    )
    if not clocks:
        return None
    clock = clocks[0]
    replace_component(clock, CryptidFlapPressureComponent())
    return clock


def sighting_buzz(world: World) -> float:
    """Accumulated buzz from every sighting logged so far, capped."""
    count = len(list(world.query().with_all([SightingComponent]).execute_entities()))
    return min(MAX_BUZZ, BUZZ_PER_SIGHTING * count)


def active_flap(world: World) -> Entity | None:
    """The currently-running flap incident, if any."""
    for entity in world.query().with_all([IncidentComponent]).execute_entities():
        incident = entity.get_component(IncidentComponent)
        if incident.kind == "cryptid_flap" and incident.resolved_at_epoch is None:
            return entity
    return None


def flap_clarity_bonus(world: World) -> float:
    """Extra clarity every sighting gains while a flap is live (0 otherwise)."""
    return FLAP_CLARITY_BONUS if active_flap(world) is not None else 0.0


def _target_room(world: World) -> Entity | None:
    """The room of the lowest-id living, non-cryptid character; else the first room."""
    characters = sorted(
        world.query().with_all([CharacterComponent]).execute_entities(), key=lambda e: str(e.id)
    )
    for character in characters:
        if character.has_component(DeadComponent) or character.has_component(SuspendedComponent):
            continue
        if character.has_component(CryptidComponent):
            continue
        room_id = container_of(character)
        if room_id is not None and world.has_entity(room_id):
            return world.get_entity(room_id)
    rooms = sorted(
        world.query().with_all([RoomComponent]).execute_entities(), key=lambda e: str(e.id)
    )
    return rooms[0] if rooms else None


class CryptidFlapConsequence:
    """Pace and break cryptid flaps as core storyteller incidents; close them when run out."""

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        events.extend(self._expire_flaps(world, epoch))
        markers = sorted(
            world.query().with_all([CryptidFlapPressureComponent]).execute_entities(),
            key=lambda e: str(e.id),
        )
        for marker_entity in markers:
            marker = marker_entity.get_component(CryptidFlapPressureComponent)
            if not marker.enabled or epoch < marker.next_flap_epoch:
                continue
            replace_component(
                marker_entity,
                replace(marker, next_flap_epoch=epoch + marker.interval_seconds),
            )
            if active_flap(world) is not None or not is_concealing(world, None):
                continue
            pressure = marker.base_pressure + sighting_buzz(world)
            if pressure < FLAP_THRESHOLD:
                continue
            event = self._break_flap(world, epoch, pressure)
            if event is not None:
                events.append(event)
        return events

    def _expire_flaps(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        for entity in list(world.query().with_all([IncidentComponent]).execute_entities()):
            incident = entity.get_component(IncidentComponent)
            if incident.kind != "cryptid_flap" or incident.resolved_at_epoch is not None:
                continue
            if epoch < incident.started_at_epoch + FLAP_DURATION_SECONDS:
                continue
            replace_component(entity, replace(incident, resolved_at_epoch=epoch))
            events.append(
                CryptidFlapEndedEvent(
                    **event_base(
                        epoch,
                        default_visibility=EventVisibility.SYSTEM,
                        actor_id=str(entity.id),
                        target_ids=(str(entity.id),),
                        incident_id=str(entity.id),
                    )
                )
            )
        return events

    def _break_flap(self, world: World, epoch: int, pressure: float):
        room = _target_room(world)
        if room is None:
            return None
        name = FLAP_CREATURES[_flap_seed_hash(str(epoch)) % len(FLAP_CREATURES)]
        habitat = (
            room.get_component(RoomComponent).title
            if room.has_component(RoomComponent)
            else "wilderness"
        )
        cryptid = spawn_entity(
            world,
            [
                IdentityComponent(name=name, kind="character", tags=("cryptidsim", "flap")),
                CharacterComponent(),
                CryptidComponent(name=name, elusiveness=FLAP_ELUSIVENESS, habitat=habitat),
                MovementPatternComponent(),
            ],
        )
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), cryptid.id)
        establish_lair(world, cryptid, room_id=room.id, habitat=habitat, epoch=epoch)
        incident = spawn_entity(
            world,
            [
                IdentityComponent(name="cryptid flap", kind="incident"),
                IncidentComponent(
                    kind="cryptid_flap",
                    budget_spent=pressure,
                    started_at_epoch=epoch,
                    room_id=str(room.id),
                ),
            ],
        )
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), incident.id)
        return CryptidFlapStartedEvent(
            **event_base(
                epoch,
                default_visibility=EventVisibility.ROOM,
                actor_id=str(incident.id),
                room_id=str(room.id),
                target_ids=(str(cryptid.id),),
                incident_id=str(incident.id),
                cryptid_id=str(cryptid.id),
                cryptid_name=name,
                pressure=pressure,
            )
        )


def _flap_seed_hash(value: str) -> int:
    """A stable byte from ``value`` (deterministic across a ``PYTHONHASHSEED`` sweep)."""
    return hashlib.sha256(value.encode()).digest()[0]


def install_flap(actor) -> None:
    actor.register_consequence(CryptidFlapConsequence())
    ensure_flap_pressure(actor.world)


__all__ = [
    "BUZZ_PER_SIGHTING",
    "FLAP_CLARITY_BONUS",
    "FLAP_CREATURES",
    "FLAP_DURATION_SECONDS",
    "FLAP_ELUSIVENESS",
    "FLAP_THRESHOLD",
    "MAX_BUZZ",
    "SECONDS_PER_DAY",
    "CryptidFlapConsequence",
    "CryptidFlapEndedEvent",
    "CryptidFlapPressureComponent",
    "CryptidFlapStartedEvent",
    "active_flap",
    "ensure_flap_pressure",
    "flap_clarity_bonus",
    "install_flap",
    "sighting_buzz",
]
