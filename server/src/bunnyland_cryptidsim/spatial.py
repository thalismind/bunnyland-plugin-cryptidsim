"""Spatial helpers: find the holder of an item, and the room an entity is in.

The core ``container_of`` only returns an entity's *direct* ``Contains`` parent. These
helpers resolve the two questions the sighting logic actually asks:

- ``holder_of(item)`` — who is carrying this item (``None`` if it is loose in a room)?
- ``room_of(entity)`` — which room is this entity ultimately in, whether it is loose on the
  floor or nested in a character's inventory?
"""

from __future__ import annotations

from bunnyland.core import RoomComponent, container_of
from relics import Entity, World

#: Guard against pathological containment cycles while walking up to a room.
_MAX_CONTAINMENT_DEPTH = 8


def holder_of(world: World, item_id) -> Entity | None:
    """Return the entity holding ``item_id``, or ``None`` if it is loose or uncontained."""
    if not world.has_entity(item_id):
        return None
    parent_id = container_of(world.get_entity(item_id))
    if parent_id is None or not world.has_entity(parent_id):
        return None
    parent = world.get_entity(parent_id)
    if parent.has_component(RoomComponent):
        return None
    return parent


def room_of(world: World, entity_id) -> Entity | None:
    """Return the room ``entity_id`` is ultimately in, resolving through any holder."""
    if not world.has_entity(entity_id):
        return None
    current = world.get_entity(entity_id)
    for _ in range(_MAX_CONTAINMENT_DEPTH):
        parent_id = container_of(current)
        if parent_id is None or not world.has_entity(parent_id):
            return None
        parent = world.get_entity(parent_id)
        if parent.has_component(RoomComponent):
            return parent
        current = parent
    return None


__all__ = ["holder_of", "room_of"]
