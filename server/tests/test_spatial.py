"""Spatial helpers: holder_of and room_of resolve carriers and containing rooms."""

from __future__ import annotations

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)

from bunnyland_cryptidsim.spatial import holder_of, room_of


def _item(world, name="thing"):
    return spawn_entity(world, [IdentityComponent(name=name, kind="item")])


def _room(world):
    return spawn_entity(world, [RoomComponent(title="Cave")])


def _hold(holder, item, mode=ContainmentMode.INVENTORY):
    holder.add_relationship(Contains(mode=mode), item.id)


# -- holder_of --------------------------------------------------------------------------


def test_holder_of_missing_item_is_none():
    actor = WorldActor()
    item = _item(actor.world)
    removed = item.id
    actor.world.remove(removed)
    assert holder_of(actor.world, removed) is None


def test_holder_of_uncontained_item_is_none():
    actor = WorldActor()
    item = _item(actor.world)
    assert holder_of(actor.world, item.id) is None


def test_holder_of_loose_in_room_is_none():
    actor = WorldActor()
    room = _room(actor.world)
    item = _item(actor.world)
    _hold(room, item, ContainmentMode.ROOM_CONTENT)
    assert holder_of(actor.world, item.id) is None


def test_holder_of_carried_item_returns_the_holder():
    actor = WorldActor()
    room = _room(actor.world)
    holder = _item(actor.world, "person")
    _hold(room, holder, ContainmentMode.ROOM_CONTENT)
    item = _item(actor.world)
    _hold(holder, item)
    assert holder_of(actor.world, item.id).id == holder.id


# -- room_of ----------------------------------------------------------------------------


def test_room_of_missing_entity_is_none():
    actor = WorldActor()
    item = _item(actor.world)
    removed = item.id
    actor.world.remove(removed)
    assert room_of(actor.world, removed) is None


def test_room_of_loose_entity_finds_its_room():
    actor = WorldActor()
    room = _room(actor.world)
    item = _item(actor.world)
    _hold(room, item, ContainmentMode.ROOM_CONTENT)
    assert room_of(actor.world, item.id).id == room.id


def test_room_of_resolves_through_a_holder():
    actor = WorldActor()
    room = _room(actor.world)
    holder = _item(actor.world, "person")
    _hold(room, holder, ContainmentMode.ROOM_CONTENT)
    item = _item(actor.world)
    _hold(holder, item)
    assert room_of(actor.world, item.id).id == room.id


def test_room_of_uncontained_is_none():
    actor = WorldActor()
    item = _item(actor.world)
    assert room_of(actor.world, item.id) is None


def test_room_of_gives_up_past_the_depth_limit():
    actor = WorldActor()
    chain = [_item(actor.world, f"box{i}") for i in range(10)]
    for parent, child in zip(chain, chain[1:], strict=False):
        _hold(parent, child)
    # No room anywhere and the nesting is deeper than the guard: resolves to None.
    assert room_of(actor.world, chain[-1].id) is None
