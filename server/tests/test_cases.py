from __future__ import annotations

from bunnyland.core import RoomComponent, WorldActor, spawn_entity

from bunnyland_cryptidsim import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    CryptidConfirmationConsequence,
    CryptidConfirmedEvent,
    find_case,
    record_sighting,
    spawn_cryptid,
)

EPOCH = 100


def _case_of(entity):
    return entity.get_component(CryptidCaseComponent)


# =======================================================================================
# record_sighting / find_case
# =======================================================================================


def test_record_sighting_opens_a_new_case():
    actor = WorldActor()
    entity = record_sighting(
        actor.world,
        investigator_id="hunter",
        cryptid_id="beast",
        cryptid_name="mothman",
        clarity=0.4,
        clear=False,
    )
    case = _case_of(entity)
    assert case.sighting_count == 1
    assert case.clear_count == 0
    assert case.best_clarity == 0.4


def test_record_sighting_accumulates_into_the_same_case():
    actor = WorldActor()
    record_sighting(
        actor.world,
        investigator_id="hunter",
        cryptid_id="beast",
        cryptid_name="mothman",
        clarity=0.4,
        clear=False,
    )
    record_sighting(
        actor.world,
        investigator_id="hunter",
        cryptid_id="beast",
        cryptid_name="mothman",
        clarity=0.8,
        clear=True,
    )
    cases = list(actor.world.query().with_all([CryptidCaseComponent]).execute_entities())
    assert len(cases) == 1
    case = _case_of(cases[0])
    assert case.sighting_count == 2
    assert case.clear_count == 1
    assert case.best_clarity == 0.8


def test_separate_investigators_get_separate_cases():
    actor = WorldActor()
    record_sighting(
        actor.world,
        investigator_id="hunter_a",
        cryptid_id="beast",
        cryptid_name="mothman",
        clarity=0.4,
        clear=False,
    )
    record_sighting(
        actor.world,
        investigator_id="hunter_b",
        cryptid_id="beast",
        cryptid_name="mothman",
        clarity=0.4,
        clear=False,
    )
    cases = list(actor.world.query().with_all([CryptidCaseComponent]).execute_entities())
    assert len(cases) == 2


def test_find_case_returns_none_when_absent():
    actor = WorldActor()
    assert find_case(actor.world, "nobody", "nothing") is None


# =======================================================================================
# CryptidConfirmationConsequence
# =======================================================================================


def _open_case(world, cryptid_id, *, clear_count):
    return spawn_entity(
        world,
        [
            CryptidCaseComponent(
                investigator_id="hunter",
                cryptid_id=cryptid_id,
                cryptid_name="mothman",
                sighting_count=clear_count,
                clear_count=clear_count,
                best_clarity=0.9,
            )
        ],
    )


def test_enough_clear_sightings_confirm_the_case():
    actor = WorldActor()
    room = spawn_entity(actor.world, [RoomComponent(title="Fen")])
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")
    case_entity = _open_case(actor.world, str(cryptid.id), clear_count=2)

    events = CryptidConfirmationConsequence().process(actor.world, EPOCH)

    assert _case_of(case_entity).confirmed
    assert cryptid.has_component(ConfirmedCryptidComponent)
    assert len(events) == 1
    assert isinstance(events[0], CryptidConfirmedEvent)
    assert events[0].cryptid_name == "mothman"
    assert events[0].reputation > 0.0


def test_thin_evidence_does_not_confirm():
    actor = WorldActor()
    room = spawn_entity(actor.world, [RoomComponent(title="Fen")])
    cryptid = spawn_cryptid(actor.world, room_id=room.id)
    case_entity = _open_case(actor.world, str(cryptid.id), clear_count=1)

    events = CryptidConfirmationConsequence().process(actor.world, EPOCH)

    assert not _case_of(case_entity).confirmed
    assert not cryptid.has_component(ConfirmedCryptidComponent)
    assert events == []


def test_already_confirmed_case_is_not_re_emitted():
    actor = WorldActor()
    room = spawn_entity(actor.world, [RoomComponent(title="Fen")])
    cryptid = spawn_cryptid(actor.world, room_id=room.id)
    _open_case(actor.world, str(cryptid.id), clear_count=3)
    consequence = CryptidConfirmationConsequence()

    first = consequence.process(actor.world, EPOCH)
    second = consequence.process(actor.world, EPOCH + 1)

    assert len(first) == 1
    assert second == []


def test_confirmation_tolerates_a_vanished_cryptid():
    actor = WorldActor()
    case_entity = _open_case(actor.world, "entity_9999", clear_count=2)  # id points nowhere

    events = CryptidConfirmationConsequence().process(actor.world, EPOCH)

    assert _case_of(case_entity).confirmed
    assert len(events) == 1
