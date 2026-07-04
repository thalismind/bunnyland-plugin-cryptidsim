"""Spawn factory for cryptid creatures.

The loader does not consume ``ContentContribution.prefabs``, so cryptids are created with
this ``spawn_entity`` helper (from tests, admin tooling, or a worldgen hook). Pass
``room_id`` to place the creature in a room, or leave it out to spawn it uncontained.
"""

from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    spawn_entity,
)
from relics import Entity, World

from .components import CryptidComponent


def _link_into_room(world: World, entity: Entity, room_id) -> None:
    if room_id is None or not world.has_entity(room_id):
        return
    world.get_entity(room_id).add_relationship(
        Contains(mode=ContainmentMode.ROOM_CONTENT), entity.id
    )


def spawn_cryptid(
    world: World,
    *,
    room_id=None,
    name: str = "mothman",
    elusiveness: float = 0.6,
    habitat: str = "wilderness",
) -> Entity:
    """Spawn a cryptid creature, optionally placed in ``room_id``."""
    cryptid = spawn_entity(
        world,
        [
            IdentityComponent(name=name, kind="character", tags=("cryptidsim",)),
            CharacterComponent(),
            CryptidComponent(name=name, elusiveness=elusiveness, habitat=habitat),
        ],
    )
    _link_into_room(world, cryptid, room_id)
    return cryptid


__all__ = ["spawn_cryptid"]
