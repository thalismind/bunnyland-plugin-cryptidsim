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
from bunnyland.core.components import WorldClockComponent
from bunnyland.core.ecs import replace_component

from bunnyland_cryptidsim import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    cryptidsim_fragments,
    spawn_cryptid,
)

NOON_CLEAR = 12 * 3600


def _set_clock(actor, seconds):
    clock = list(actor.world.query().with_all([WorldClockComponent]).execute_entities())[0]
    replace_component(
        clock, replace(clock.get_component(WorldClockComponent), game_time_seconds=seconds)
    )


def _room(world, *, light=None):
    components = [RoomComponent(title="Fen")]
    if light is not None:
        components.append(LightComponent(level=light))
    return spawn_entity(world, components)


def _character(world, room):
    character = spawn_entity(
        world, [IdentityComponent(name="Vin", kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _case(world, investigator_id, *, confirmed, sighting_count=1):
    return spawn_entity(
        world,
        [
            CryptidCaseComponent(
                investigator_id=str(investigator_id),
                cryptid_id="beast",
                cryptid_name="mothman",
                sighting_count=sighting_count,
                clear_count=2 if confirmed else 0,
                best_clarity=0.9 if confirmed else 0.3,
                confirmed=confirmed,
            )
        ],
    )


# =======================================================================================
# Dossier lines: hedged vs confirmed
# =======================================================================================


def test_unconfirmed_case_reads_hedged():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    _case(actor.world, character.id, confirmed=False, sighting_count=2)

    lines = cryptidsim_fragments(actor.world, character)

    assert any("Unconfirmed reports of the mothman" in line for line in lines)
    assert not any("confirmed: the mothman is real" in line for line in lines)


def test_confirmed_case_reads_definitively():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    _case(actor.world, character.id, confirmed=True)

    lines = cryptidsim_fragments(actor.world, character)

    assert "Case confirmed: the mothman is real." in lines


def test_single_report_uses_singular_wording():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    _case(actor.world, character.id, confirmed=False, sighting_count=1)

    lines = cryptidsim_fragments(actor.world, character)

    assert any(line.startswith("Unconfirmed report of the mothman") for line in lines)


def test_other_investigators_case_is_not_shown():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    _case(actor.world, "someone_else", confirmed=True)

    assert cryptidsim_fragments(actor.world, character) == []


# =======================================================================================
# Ambient lines: eerie hedged glimpse vs definite presence
# =======================================================================================


def test_present_unconfirmed_cryptid_reads_eerie_at_night():
    actor = WorldActor()  # night -> concealing
    room = _room(actor.world)
    character = _character(actor.world, room)
    spawn_cryptid(actor.world, room_id=room.id, name="mothman", habitat="swamp")

    lines = cryptidsim_fragments(actor.world, character)

    assert "Something large moves beyond the treeline — you can't be sure what it is." in lines


def test_present_confirmed_cryptid_reads_definitively():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman", habitat="swamp")
    replace_component(cryptid, ConfirmedCryptidComponent())

    lines = cryptidsim_fragments(actor.world, character)

    assert "The mothman, a confirmed cryptid, is here in the swamp." in lines


def test_unconfirmed_cryptid_is_silent_in_clear_daylight():
    actor = WorldActor()
    _set_clock(actor, NOON_CLEAR)
    room = _room(actor.world, light=1.0)
    character = _character(actor.world, room)
    spawn_cryptid(actor.world, room_id=room.id, name="mothman")

    # Not concealing and not confirmed: nothing to hint at.
    assert cryptidsim_fragments(actor.world, character) == []


def test_no_fragments_in_an_empty_room():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)

    assert cryptidsim_fragments(actor.world, character) == []


def test_fragments_empty_for_none_character():
    actor = WorldActor()
    assert cryptidsim_fragments(actor.world, None) == []
