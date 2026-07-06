"""Bait: lure a cryptid into the open so a camera trap (or a live look) pays off.

An investigator sets out **bait** in the room they stand in. Bait is a deployed item entity
carrying a :class:`BaitComponent`; while it sits in a room it raises the odds that an elusive
creature shows itself there — a small, deterministic clarity bonus folded into both the live
``sight`` verb and the passive camera-trap capture.

Bait whose ``habitat`` matches the creature's own habitat works best (carrion for a swamp
beast, sweet mash for a forest hominid); generic bait still helps a little. The bonus is a
pure function of the bait sitting in the room, so it never introduces randomness.
"""

from __future__ import annotations

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    PortableComponent,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
from bunnyland.core.ecs import contents
from bunnyland.core.events import DomainEvent, EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
)
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .spatial import room_of


@dataclass(frozen=True)
class BaitComponent(Component):
    """Deployed bait sitting in a room, luring cryptids that favour ``habitat``.

    ``potency`` (0..1) scales the clarity bonus; ``habitat`` is the biome the bait appeals to
    ("swamp", "forest", "lake", ...) or ``"any"`` for a generic lure.
    """

    kind: str = "carrion"
    potency: float = 0.5
    habitat: str = "any"
    placed_by: str = ""
    placed_at_epoch: int = 0


class BaitPlacedEvent(DomainEvent):
    """An investigator set out bait in a room."""

    bait_id: str
    kind: str
    habitat: str


#: Fraction of a matching bait's potency added to clarity; a non-matching lure gives half.
BAIT_MATCH_WEIGHT = 0.2
BAIT_GENERIC_WEIGHT = 0.1

#: Bait bonus never lifts clarity by more than this on its own.
MAX_BAIT_BONUS = 0.25


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def bait_bonus(world: World, room: Entity | None, habitat: str) -> float:
    """Summed, capped clarity bonus from bait sitting in ``room`` for a ``habitat`` creature."""
    if room is None:
        return 0.0
    total = 0.0
    for target in contents(room):
        if not world.has_entity(target):
            continue
        entity = world.get_entity(target)
        if not entity.has_component(BaitComponent):
            continue
        bait = entity.get_component(BaitComponent)
        if bait.habitat == "any" or bait.habitat == habitat:
            weight = BAIT_MATCH_WEIGHT if bait.habitat == habitat else BAIT_GENERIC_WEIGHT
        else:
            weight = 0.0
        total += weight * _clamp01(bait.potency)
    return min(MAX_BAIT_BONUS, total)


def spawn_bait(
    world: World,
    *,
    room_id=None,
    kind: str = "carrion",
    potency: float = 0.5,
    habitat: str = "any",
    placed_by: str = "",
    placed_at_epoch: int = 0,
) -> Entity:
    """Spawn a bait item, optionally placed in ``room_id``."""
    bait = spawn_entity(
        world,
        [
            IdentityComponent(name=f"{kind} bait", kind="item", tags=("cryptidsim", "bait")),
            PortableComponent(can_pick_up=True),
            BaitComponent(
                kind=kind,
                potency=potency,
                habitat=habitat,
                placed_by=placed_by,
                placed_at_epoch=placed_at_epoch,
            ),
        ],
    )
    if room_id is not None and world.has_entity(room_id):
        world.get_entity(room_id).add_relationship(
            Contains(mode=ContainmentMode.ROOM_CONTENT), bait.id
        )
    return bait


class PlaceBaitHandler:
    """Set out bait in the room you occupy, luring elusive creatures into view."""

    command_type = "place-bait"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        room = room_of(ctx.world, character_id)
        if room is None:
            return rejected("you are nowhere to set out bait")
        kind = str(command.payload.get("kind", "carrion")).strip() or "carrion"
        habitat = str(command.payload.get("habitat", "any")).strip() or "any"
        bait = spawn_bait(
            ctx.world,
            room_id=room.id,
            kind=kind,
            habitat=habitat,
            potency=0.5,
            placed_by=str(character_id),
            placed_at_epoch=ctx.epoch,
        )
        return ok(
            BaitPlacedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id),
                    target_ids=(str(bait.id),),
                    bait_id=str(bait.id),
                    kind=kind,
                    habitat=habitat,
                )
            )
        )


PLACE_BAIT_DEF = ActionDefinition(
    command_type="place-bait",
    title="Place bait",
    description="Set out bait in your room to lure an elusive creature into the open.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "kind": ActionArgument(
            title="Bait",
            description="What to set out (carrion, sweet mash, fish...).",
            kind="text",
            required=False,
        ),
        "habitat": ActionArgument(
            title="Habitat",
            description="The biome the bait appeals to, or 'any'.",
            kind="text",
            required=False,
        ),
    },
)

BAIT_ACTION_DEFINITIONS = (PLACE_BAIT_DEF,)
BAIT_ACTION_HANDLERS = (PlaceBaitHandler,)


__all__ = [
    "BAIT_ACTION_DEFINITIONS",
    "BAIT_ACTION_HANDLERS",
    "BAIT_GENERIC_WEIGHT",
    "BAIT_MATCH_WEIGHT",
    "MAX_BAIT_BONUS",
    "PLACE_BAIT_DEF",
    "BaitComponent",
    "BaitPlacedEvent",
    "PlaceBaitHandler",
    "bait_bonus",
    "spawn_bait",
]
