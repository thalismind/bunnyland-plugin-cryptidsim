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
from bunnyland.core.components import PerceptionComponent, WorldClockComponent
from bunnyland.core.ecs import replace_component
from bunnyland.core.handlers import HandlerContext

from bunnyland_cryptidsim import (
    CryptidCaseComponent,
    SightingComponent,
    SightingRecordedEvent,
    is_clear,
    sighting_clarity,
    spawn_cryptid,
)
from bunnyland_cryptidsim.sighting import SightCryptidHandler

NOON_CLEAR = 12 * 3600  # day 1, hour 12 -> "day", weather "clear"


# =======================================================================================
# Deterministic clarity (hash-seed independent)
# =======================================================================================


def test_clarity_is_exact_for_fixed_inputs():
    # These values come only from hashlib over the ids+epoch, so a PYTHONHASHSEED sweep
    # (see the CI/scripts run) never changes them.
    assert sighting_clarity("seer", "moth", 13, elusiveness=0.1, light_level=1.0) == 0.9
    assert sighting_clarity("seer", "moth", 7, elusiveness=0.1, light_level=1.0) == 0.36
    assert (
        sighting_clarity("investigator_1", "cryptid_1", 100, elusiveness=0.8, light_level=0.2)
        == 0.054
    )


def test_clarity_is_stable_across_repeated_calls():
    first = sighting_clarity("a", "b", 5, elusiveness=0.5, light_level=0.7)
    second = sighting_clarity("a", "b", 5, elusiveness=0.5, light_level=0.7)
    assert first == second


def test_elusiveness_lowers_clarity():
    shy = sighting_clarity("a", "b", 5, elusiveness=0.9, light_level=1.0)
    bold = sighting_clarity("a", "b", 5, elusiveness=0.1, light_level=1.0)
    assert shy < bold


def test_light_raises_clarity():
    dark = sighting_clarity("a", "b", 5, elusiveness=0.3, light_level=0.1)
    lit = sighting_clarity("a", "b", 5, elusiveness=0.3, light_level=1.0)
    assert dark < lit


def test_distance_lowers_clarity():
    near = sighting_clarity("a", "b", 5, elusiveness=0.3, light_level=1.0, distance=0)
    far = sighting_clarity("a", "b", 5, elusiveness=0.3, light_level=1.0, distance=4)
    assert far < near


def test_is_clear_threshold():
    assert is_clear(0.9)
    assert not is_clear(0.36)
    assert is_clear(0.5)


# =======================================================================================
# sight-cryptid verb
# =======================================================================================


def _room(world, *, light=None):
    components = [RoomComponent(title="Fen")]
    if light is not None:
        components.append(LightComponent(level=light))
    return spawn_entity(world, components)


def _investigator(world, room, *, perception=None):
    components = [IdentityComponent(name="Vin", kind="character"), CharacterComponent()]
    if perception is not None:
        components.append(perception)
    character = spawn_entity(world, components)
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _set_clock(actor, seconds):
    clock = list(actor.world.query().with_all([WorldClockComponent]).execute_entities())[0]
    replace_component(
        clock, replace(clock.get_component(WorldClockComponent), game_time_seconds=seconds)
    )


def _cmd(character_id, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="sight-cryptid",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


def _ctx(actor, epoch=0):
    return HandlerContext(world=actor.world, epoch=epoch)


def _sighting(world):
    entities = list(world.query().with_all([SightingComponent]).execute_entities())
    return entities[0].get_component(SightingComponent) if entities else None


def test_sight_records_a_sighting_at_night():
    actor = WorldActor()  # night -> concealing
    room = _room(actor.world)
    investigator = _investigator(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman", elusiveness=0.3)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": str(cryptid.id)})
    )

    assert result.ok
    assert isinstance(result.events[0], SightingRecordedEvent)
    sighting = _sighting(actor.world)
    assert sighting is not None
    assert sighting.cryptid_name == "mothman"
    # The handler uses the deterministic clarity function on the real ids (room is unlit -> 1.0).
    expected = sighting_clarity(
        str(investigator.id), str(cryptid.id), 0, elusiveness=0.3, light_level=1.0
    )
    assert sighting.clarity == expected
    assert result.events[0].clarity == expected


def test_sight_opens_a_case_dossier():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _investigator(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")

    SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": str(cryptid.id)})
    )

    cases = list(actor.world.query().with_all([CryptidCaseComponent]).execute_entities())
    assert len(cases) == 1
    case = cases[0].get_component(CryptidCaseComponent)
    assert case.investigator_id == str(investigator.id)
    assert case.cryptid_id == str(cryptid.id)
    assert case.sighting_count == 1


def test_repeated_sightings_accumulate_in_one_case():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _investigator(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")
    handler = SightCryptidHandler()

    handler.execute(_ctx(actor, 0), _cmd(investigator.id, {"cryptid_id": str(cryptid.id)}))
    handler.execute(_ctx(actor, 1), _cmd(investigator.id, {"cryptid_id": str(cryptid.id)}))

    cases = list(actor.world.query().with_all([CryptidCaseComponent]).execute_entities())
    assert len(cases) == 1
    assert cases[0].get_component(CryptidCaseComponent).sighting_count == 2


# -- rejection paths --------------------------------------------------------------------


def test_sight_rejects_invalid_character():
    actor = WorldActor()
    room = _room(actor.world)
    cryptid = spawn_cryptid(actor.world, room_id=room.id)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd("???", {"cryptid_id": str(cryptid.id)})
    )

    assert not result.ok
    assert result.reason == "invalid character id"


def test_sight_rejects_missing_character():
    actor = WorldActor()
    room = _room(actor.world)
    cryptid = spawn_cryptid(actor.world, room_id=room.id)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd("entity_9999", {"cryptid_id": str(cryptid.id)})
    )

    assert not result.ok
    assert result.reason == "character does not exist"


def test_sight_rejects_invalid_cryptid_id():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _investigator(actor.world, room)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": "???"})
    )

    assert not result.ok
    assert result.reason == "invalid cryptid id"


def test_sight_rejects_missing_cryptid():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _investigator(actor.world, room)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": "entity_9999"})
    )

    assert not result.ok
    assert result.reason == "cryptid does not exist"


def test_sight_rejects_cryptid_out_of_range():
    actor = WorldActor()
    room = _room(actor.world)
    other = _room(actor.world)
    investigator = _investigator(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=other.id)  # a different room

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": str(cryptid.id)})
    )

    assert not result.ok
    assert result.reason == "the cryptid is not within range"


def test_sight_rejects_non_cryptid_target():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _investigator(actor.world, room)
    bystander = spawn_entity(
        actor.world, [IdentityComponent(name="Kell", kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), bystander.id)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": str(bystander.id)})
    )

    assert not result.ok
    assert result.reason == "that is not a cryptid"


def test_sight_rejects_when_perception_inactive():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _investigator(actor.world, room, perception=PerceptionComponent(active=False))
    cryptid = spawn_cryptid(actor.world, room_id=room.id)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": str(cryptid.id)})
    )

    assert not result.ok
    assert result.reason == "you cannot make anything out"


def test_sight_rejects_in_clear_daylight():
    actor = WorldActor()
    _set_clock(actor, NOON_CLEAR)
    room = _room(actor.world, light=1.0)
    investigator = _investigator(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id)

    result = SightCryptidHandler().execute(
        _ctx(actor), _cmd(investigator.id, {"cryptid_id": str(cryptid.id)})
    )

    assert not result.ok
    assert result.reason == "conditions are too clear; nothing stirs"
    # No evidence is logged when the creature never appears.
    assert _sighting(actor.world) is None
