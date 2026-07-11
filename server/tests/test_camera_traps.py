from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    LightComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.components import DeadComponent, WorldClockComponent
from bunnyland.core.ecs import replace_component
from bunnyland.core.handlers import HandlerContext
from bunnyland.foundation.persona.mechanics import GoalComponent

from bunnyland_cryptidsim.bait import spawn_bait
from bunnyland_cryptidsim.camera_traps import (
    CAMERA_TRAP_ACTION_DEFINITIONS,
    CAMERA_TRAP_ACTION_HANDLERS,
    CameraTrapCapturedEvent,
    CameraTrapComponent,
    CameraTrapConsequence,
    CameraTrapSetEvent,
    SetCameraTrapHandler,
    install_camera_traps,
    spawn_camera_trap,
)
from bunnyland_cryptidsim.cases import CryptidCaseComponent
from bunnyland_cryptidsim.components import SightingComponent
from bunnyland_cryptidsim.credibility import RENOWN_GOAL
from bunnyland_cryptidsim.prefabs import spawn_cryptid

NOON_CLEAR = 12 * 3600


def _room(world, *, light=None, title="Fen"):
    components = [RoomComponent(title=title)]
    if light is not None:
        components.append(LightComponent(level=light))
    return spawn_entity(world, components)


def _character(world, room):
    character = spawn_entity(
        world, [IdentityComponent(name="Vin", kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _set_clock(actor, seconds):
    clock = list(actor.world.query().with_all([WorldClockComponent]).execute_entities())[0]
    replace_component(
        clock, replace(clock.get_component(WorldClockComponent), game_time_seconds=seconds)
    )


def _cmd(character_id):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="set-camera-trap",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload={},
    )


# -- set-camera-trap verb ---------------------------------------------------------------


def test_set_camera_trap_happy_and_aspires_to_renown():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    result = SetCameraTrapHandler().execute(
        HandlerContext(world=actor.world, epoch=3), _cmd(character.id)
    )
    assert result.ok
    assert isinstance(result.events[0], CameraTrapSetEvent)
    cams = list(actor.world.query().with_all([CameraTrapComponent]).execute_entities())
    assert cams[0].get_component(CameraTrapComponent).placed_by == str(character.id)
    # Setting a trap makes the investigator chase renown.
    assert RENOWN_GOAL in character.get_component(GoalComponent).active_goals


def test_set_camera_trap_rejects_invalid_character():
    actor = WorldActor()
    result = SetCameraTrapHandler().execute(HandlerContext(world=actor.world, epoch=0), _cmd("???"))
    assert not result.ok and result.reason == "invalid character id"


def test_set_camera_trap_rejects_no_room():
    actor = WorldActor()
    character = spawn_entity(
        actor.world, [IdentityComponent(name="Vin", kind="character"), CharacterComponent()]
    )
    result = SetCameraTrapHandler().execute(
        HandlerContext(world=actor.world, epoch=0), _cmd(character.id)
    )
    assert not result.ok and result.reason == "you have nowhere to set a camera trap"


def test_camera_trap_action_surface():
    assert CAMERA_TRAP_ACTION_DEFINITIONS[0].command_type == "set-camera-trap"
    assert CAMERA_TRAP_ACTION_HANDLERS[0] is SetCameraTrapHandler


# -- passive capture consequence --------------------------------------------------------


def test_camera_captures_cryptid_at_night_and_files_a_case():
    actor = WorldActor()  # night -> concealing
    room = _room(actor.world)
    investigator = _character(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman", elusiveness=0.3)
    spawn_camera_trap(actor.world, room_id=room.id, placed_by=str(investigator.id))

    events = CameraTrapConsequence().process(actor.world, 100)

    assert len(events) == 1
    captured = events[0]
    assert isinstance(captured, CameraTrapCapturedEvent)
    assert captured.cryptid_name == "mothman"
    assert captured.investigator_id == str(investigator.id)
    # A passive sighting entity + a dossier crediting the trap's owner.
    sightings = list(actor.world.query().with_all([SightingComponent]).execute_entities())
    assert sightings[0].get_component(SightingComponent).investigator_id == str(investigator.id)
    cases = list(actor.world.query().with_all([CryptidCaseComponent]).execute_entities())
    assert cases[0].get_component(CryptidCaseComponent).investigator_id == str(investigator.id)
    assert str(cryptid.id) == captured.cryptid_id


def test_camera_bait_in_room_raises_capture_clarity():
    room_a = WorldActor()
    plain_room = _room(room_a.world)
    inv_a = _character(room_a.world, plain_room)
    spawn_cryptid(
        room_a.world, room_id=plain_room.id, name="mothman", elusiveness=0.3, habitat="swamp"
    )
    spawn_camera_trap(room_a.world, room_id=plain_room.id, placed_by=str(inv_a.id))
    plain = CameraTrapConsequence().process(room_a.world, 100)[0].clarity

    room_b = WorldActor()
    baited_room = _room(room_b.world)
    inv_b = _character(room_b.world, baited_room)
    spawn_cryptid(
        room_b.world, room_id=baited_room.id, name="mothman", elusiveness=0.3, habitat="swamp"
    )
    spawn_bait(room_b.world, room_id=baited_room.id, habitat="swamp", potency=1.0)
    spawn_camera_trap(room_b.world, room_id=baited_room.id, placed_by=str(inv_b.id))
    baited = CameraTrapConsequence().process(room_b.world, 100)[0].clarity

    assert baited > plain


def test_camera_does_not_fire_in_clear_daylight():
    actor = WorldActor()
    _set_clock(actor, NOON_CLEAR)
    room = _room(actor.world, light=1.0)
    _character(actor.world, room)
    spawn_cryptid(actor.world, room_id=room.id)
    spawn_camera_trap(actor.world, room_id=room.id, placed_by="entity_1")
    assert CameraTrapConsequence().process(actor.world, 100) == []


def test_camera_does_not_fire_without_a_cryptid():
    actor = WorldActor()
    room = _room(actor.world)
    spawn_camera_trap(actor.world, room_id=room.id, placed_by="entity_1")
    assert CameraTrapConsequence().process(actor.world, 100) == []


def test_camera_skips_dead_cryptid():
    actor = WorldActor()
    room = _room(actor.world)
    cryptid = spawn_cryptid(actor.world, room_id=room.id)
    cryptid.add_component(DeadComponent(died_at_epoch=0, cause="natural"))
    spawn_camera_trap(actor.world, room_id=room.id, placed_by="entity_1")
    assert CameraTrapConsequence().process(actor.world, 100) == []


def test_camera_uncontained_rig_is_skipped():
    actor = WorldActor()
    spawn_camera_trap(actor.world, placed_by="entity_1")  # no room
    assert CameraTrapConsequence().process(actor.world, 100) == []


def test_camera_respects_cooldown_then_fires_again():
    actor = WorldActor()
    room = _room(actor.world)
    spawn_cryptid(actor.world, room_id=room.id, elusiveness=0.3)
    spawn_camera_trap(actor.world, room_id=room.id, placed_by="entity_1", cooldown_seconds=3600)

    first = CameraTrapConsequence().process(actor.world, 0)
    assert len(first) == 1
    # Still within the cooldown window -> no second capture.
    assert CameraTrapConsequence().process(actor.world, 1000) == []
    # Past the cooldown -> fires again.
    assert len(CameraTrapConsequence().process(actor.world, 3600)) == 1
    cam = list(actor.world.query().with_all([CameraTrapComponent]).execute_entities())[0]
    assert cam.get_component(CameraTrapComponent).captures == 2


def test_camera_without_owner_still_captures_but_files_no_case():
    actor = WorldActor()
    room = _room(actor.world)
    spawn_cryptid(actor.world, room_id=room.id, elusiveness=0.3)
    spawn_camera_trap(actor.world, room_id=room.id, placed_by="")  # ownerless rig
    events = CameraTrapConsequence().process(actor.world, 0)
    assert len(events) == 1
    # No owner -> a sighting still spawns, but no case dossier is opened.
    assert not list(actor.world.query().with_all([CryptidCaseComponent]).execute_entities())


def test_install_camera_traps_registers_consequence():
    actor = WorldActor()
    install_camera_traps(actor)
    assert any(isinstance(c, CameraTrapConsequence) for c in actor._consequences)
