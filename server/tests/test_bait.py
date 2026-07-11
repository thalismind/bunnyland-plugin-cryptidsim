from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext

from bunnyland_cryptidsim.bait import (
    BAIT_ACTION_DEFINITIONS,
    BAIT_ACTION_HANDLERS,
    MAX_BAIT_BONUS,
    BaitComponent,
    BaitPlacedEvent,
    PlaceBaitHandler,
    bait_bonus,
    spawn_bait,
)


def _room(world, title="Fen"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room=None):
    character = spawn_entity(
        world, [IdentityComponent(name="Vin", kind="character"), CharacterComponent()]
    )
    if room is not None:
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _cmd(character_id, payload=None):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="place-bait",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload or {},
    )


# -- bait_bonus -------------------------------------------------------------------------


def test_bait_bonus_is_zero_without_a_room():
    actor = WorldActor()
    assert bait_bonus(actor.world, None, "swamp") == 0.0


def test_matching_habitat_beats_generic_beats_mismatch():
    actor = WorldActor()
    swamp = _room(actor.world)
    spawn_bait(actor.world, room_id=swamp.id, habitat="swamp", potency=1.0)
    forest = _room(actor.world)
    spawn_bait(actor.world, room_id=forest.id, habitat="any", potency=1.0)
    desert = _room(actor.world)
    spawn_bait(actor.world, room_id=desert.id, habitat="lake", potency=1.0)

    matched = bait_bonus(actor.world, swamp, "swamp")
    generic = bait_bonus(actor.world, forest, "swamp")
    mismatch = bait_bonus(actor.world, desert, "swamp")
    assert matched > generic > mismatch == 0.0


def test_bait_bonus_is_capped():
    actor = WorldActor()
    room = _room(actor.world)
    for _ in range(10):
        spawn_bait(actor.world, room_id=room.id, habitat="swamp", potency=1.0)
    assert bait_bonus(actor.world, room, "swamp") == MAX_BAIT_BONUS


def test_bait_bonus_skips_non_bait_contents():
    actor = WorldActor()
    room = _room(actor.world)
    # A plain item and a character in the room contribute nothing.
    spawn_entity(actor.world, [IdentityComponent(name="rock", kind="item")])
    _character(actor.world, room)
    assert bait_bonus(actor.world, room, "swamp") == 0.0


# -- spawn_bait -------------------------------------------------------------------------


def test_spawn_bait_uncontained_and_in_a_room():
    actor = WorldActor()
    loose = spawn_bait(actor.world)
    assert loose.has_component(BaitComponent)
    room = _room(actor.world)
    placed = spawn_bait(actor.world, room_id=room.id, kind="fish", habitat="lake")
    assert str(placed.id) in [str(i) for _e, i in room.get_relationships(Contains)]


def test_spawn_bait_ignores_unknown_room():
    actor = WorldActor()
    bait = spawn_bait(actor.world, room_id="entity_9999")
    assert bait.has_component(BaitComponent)


# -- place-bait verb --------------------------------------------------------------------


def test_place_bait_happy_path():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    result = PlaceBaitHandler().execute(
        HandlerContext(world=actor.world, epoch=5),
        _cmd(character.id, {"kind": "carrion", "habitat": "swamp"}),
    )
    assert result.ok
    event = result.events[0]
    assert isinstance(event, BaitPlacedEvent)
    assert event.habitat == "swamp"
    baits = list(actor.world.query().with_all([BaitComponent]).execute_entities())
    assert baits[0].get_component(BaitComponent).placed_by == str(character.id)
    assert str(baits[0].id) == event.bait_id


def test_place_bait_defaults_blank_payload():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    result = PlaceBaitHandler().execute(
        HandlerContext(world=actor.world, epoch=0),
        _cmd(character.id, {"kind": "  ", "habitat": ""}),
    )
    assert result.ok
    baits = list(actor.world.query().with_all([BaitComponent]).execute_entities())
    bait = baits[0].get_component(BaitComponent)
    assert bait.kind == "carrion" and bait.habitat == "any"


def test_place_bait_rejects_invalid_character():
    actor = WorldActor()
    result = PlaceBaitHandler().execute(HandlerContext(world=actor.world, epoch=0), _cmd("???", {}))
    assert not result.ok and result.reason == "invalid character id"


def test_place_bait_rejects_character_with_no_room():
    actor = WorldActor()
    character = _character(actor.world)  # not placed in any room
    result = PlaceBaitHandler().execute(
        HandlerContext(world=actor.world, epoch=0), _cmd(character.id, {})
    )
    assert not result.ok and result.reason == "you are nowhere to set out bait"


def test_bait_action_surface():
    assert BAIT_ACTION_DEFINITIONS[0].command_type == "place-bait"
    assert BAIT_ACTION_HANDLERS[0] is PlaceBaitHandler
