"""The ``sight`` verb and its uncertain-evidence model.

Investigating a cryptid you share a room with produces a
:class:`~bunnyland_cryptidsim.components.SightingComponent` whose ``clarity`` is deliberately
*uncertain*. Clarity is computed **deterministically** — a ``hashlib`` digest over the stable
investigator id, cryptid id, and epoch stands in for "how the look happened to go" — and
folded together with the creature's elusiveness, the room's light, and the range. The same
attempt in the same world always yields the same photo, so worlds stay reproducible and no
:mod:`random`/:mod:`time` call ever leaks in.

Validation order follows the project convention: invalid id -> missing entity -> reachability
-> wrong-kind -> invalid state (perception, then conditions) -> record.
"""

from __future__ import annotations

import hashlib

from bunnyland.core import reachable_ids, spawn_entity
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
from bunnyland.core.components import PerceptionComponent
from bunnyland.core.events import EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_entity,
)

from .bait import bait_bonus
from .cases import record_sighting
from .components import CryptidComponent, SightingComponent
from .conditions import is_concealing, room_light_level
from .events import SightingRecordedEvent
from .flap import flap_clarity_bonus
from .lairs import lair_clarity_bonus
from .spatial import room_of
from .synergy import luck_clarity_bias, scent_clarity_bonus

#: A sighting at or above this clarity is a "clear look" that can build a case; below it the
#: evidence is just another blurry, unconfirmed report.
CLEAR_CLARITY = 0.5


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def sighting_clarity(
    character_id: str,
    cryptid_id: str,
    epoch: int,
    *,
    elusiveness: float,
    light_level: float,
    distance: int = 0,
    bonus: float = 0.0,
) -> float:
    """Deterministic clarity (0..1) for a sighting attempt.

    Blends the creature's elusiveness (blurs the look), the room's light (a distant shape in
    good light reads clearer), the range, a stable per-attempt jitter derived from a
    ``hashlib`` digest, and an environmental ``bonus`` (bait, lair ground, a flap, optional
    synergies) — never :mod:`random` or :mod:`time`, so it survives a ``PYTHONHASHSEED`` sweep
    unchanged.
    """
    seed = f"{character_id}|{cryptid_id}|{epoch}".encode()
    jitter = hashlib.sha256(seed).digest()[0] / 255.0
    base = max(0.0, 1.0 - elusiveness)
    visibility = 0.2 + 0.8 * _clamp01(light_level)
    distance_factor = 1.0 / (1.0 + max(0, distance))
    raw = base * visibility * distance_factor * (0.4 + 0.6 * jitter) + bonus
    return round(_clamp01(raw), 3)


def environment_clarity_bonus(world, character_id, cryptid, room) -> float:
    """Summed clarity bonus from bait, lair ground, a live flap, and optional synergies.

    Reused by both the live ``sight`` verb and the passive camera trap so a stakeout pays off
    the same way however the still is taken. Pure and deterministic: every term is a function
    of world state, never :mod:`random`.
    """
    habitat = cryptid.get_component(CryptidComponent).habitat
    total = bait_bonus(world, room, habitat)
    total += lair_clarity_bonus(world, cryptid, room)
    total += flap_clarity_bonus(world)
    total += scent_clarity_bonus(world, room)
    total += luck_clarity_bias(world, character_id)
    return total


def is_clear(clarity: float) -> bool:
    """Whether a clarity value counts as a clear, case-building look."""
    return clarity >= CLEAR_CLARITY


class SightCryptidHandler:
    """Investigate a cryptid in your room and log a (possibly blurry) sighting."""

    command_type = "sight-cryptid"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        cryptid_id, cryptid, rejection = require_entity(
            ctx,
            command.payload.get("cryptid_id"),
            invalid_reason="invalid cryptid id",
            missing_reason="cryptid does not exist",
        )
        if rejection is not None:
            return rejection
        if cryptid_id not in reachable_ids(ctx.world, character):
            return rejected("the cryptid is not within range")
        if not cryptid.has_component(CryptidComponent):
            return rejected("that is not a cryptid")
        if character.has_component(PerceptionComponent) and not character.get_component(
            PerceptionComponent
        ).active:
            return rejected("you cannot make anything out")
        room = room_of(ctx.world, character_id)
        if not is_concealing(ctx.world, room):
            return rejected("conditions are too clear; nothing stirs")

        details = cryptid.get_component(CryptidComponent)
        clarity = sighting_clarity(
            str(character_id),
            str(cryptid_id),
            ctx.epoch,
            elusiveness=details.elusiveness,
            light_level=room_light_level(room),
            bonus=environment_clarity_bonus(ctx.world, character_id, cryptid, room),
        )
        clear = is_clear(clarity)
        self._spawn_sighting(ctx, character_id, cryptid_id, details, clarity, clear)
        record_sighting(
            ctx.world,
            investigator_id=str(character_id),
            cryptid_id=str(cryptid_id),
            cryptid_name=details.name,
            clarity=clarity,
            clear=clear,
        )
        return ok(
            SightingRecordedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id) if room is not None else None,
                    target_ids=(str(cryptid_id),),
                    cryptid_id=str(cryptid_id),
                    cryptid_name=details.name,
                    clarity=clarity,
                    clear=clear,
                )
            )
        )

    @staticmethod
    def _spawn_sighting(ctx, character_id, cryptid_id, details, clarity, clear) -> None:
        spawn_entity(
            ctx.world,
            [
                SightingComponent(
                    cryptid_id=str(cryptid_id),
                    cryptid_name=details.name,
                    investigator_id=str(character_id),
                    clarity=clarity,
                    recorded_at_epoch=ctx.epoch,
                    clear=clear,
                )
            ],
        )


SIGHT_DEF = ActionDefinition(
    command_type="sight-cryptid",
    title="Sight cryptid",
    description="Investigate a cryptid in your room and record a sighting.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "cryptid_id": ActionArgument(
            title="Cryptid",
            description="The elusive creature to investigate.",
            kind="entity",
            required=True,
        ),
    },
)

SIGHT_ACTION_DEFINITIONS = (SIGHT_DEF,)
SIGHT_ACTION_HANDLERS = (SightCryptidHandler,)


__all__ = [
    "CLEAR_CLARITY",
    "SIGHT_ACTION_DEFINITIONS",
    "SIGHT_ACTION_HANDLERS",
    "SIGHT_DEF",
    "SightCryptidHandler",
    "environment_clarity_bonus",
    "is_clear",
    "sighting_clarity",
]
