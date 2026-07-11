from __future__ import annotations

import asyncio

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
from bunnyland.core.events import EventVisibility, event_base
from bunnyland.core.handlers import HandlerContext
from bunnyland.foundation.history.mechanics import WorldHistoryRecordComponent
from bunnyland.foundation.persona.mechanics import GoalComponent
from bunnyland.imagegen.components import ImageRequestComponent
from bunnyland.prompts import ComponentPromptContext, PromptPerspective
from bunnyland.simpacks.lifesim.mechanics import ReputationComponent

from bunnyland_cryptidsim.cases import CryptidConfirmationConsequence, record_sighting
from bunnyland_cryptidsim.components import CryptidCaseComponent
from bunnyland_cryptidsim.credibility import (
    RENOWN_GOAL,
    RENOWN_THRESHOLD,
    CredibilityComponent,
    CryptidDoubtedEvent,
    CryptidRenownReactor,
    DoubtCryptidHandler,
    aspire_to_renown,
    credibility_fragments,
    install_credibility,
    record_confirmation_photo,
    standing_toward,
)
from bunnyland_cryptidsim.events import CryptidConfirmedEvent
from bunnyland_cryptidsim.prefabs import spawn_cryptid


def _room(world, title="Fen"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room=None, name="Vin"):
    character = spawn_entity(
        world, [IdentityComponent(name=name, kind="character"), CharacterComponent()]
    )
    if room is not None:
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _confirmed_event(world, investigator, cryptid, epoch=0):
    return CryptidConfirmedEvent(
        **event_base(
            epoch,
            default_visibility=EventVisibility.PRIVATE,
            actor_id=str(investigator.id),
            target_ids=(str(cryptid.id),),
            cryptid_id=str(cryptid.id),
            cryptid_name="mothman",
            investigator_id=str(investigator.id),
            clear_count=2,
            reputation=10.0,
        )
    )


def _doubt_cmd(character_id, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="doubt-cryptid",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


# -- CredibilityComponent prompt --------------------------------------------------------


def test_credibility_prompt_first_person_and_renowned():
    actor = WorldActor()
    character = _character(actor.world)
    character.add_component(CredibilityComponent(score=30.0, confirmations=3, renowned=True))
    lines = credibility_fragments(actor.world, character)
    assert any("renowned" in line for line in lines)
    assert any("3 cryptids" in line for line in lines)


def test_credibility_prompt_singular_and_not_renowned():
    actor = WorldActor()
    character = _character(actor.world)
    character.add_component(CredibilityComponent(score=10.0, confirmations=1, renowned=False))
    lines = credibility_fragments(actor.world, character)
    assert any("1 cryptid " in line for line in lines)
    assert not any("renowned" in line for line in lines)


def test_credibility_prompt_empty_without_confirmations():
    actor = WorldActor()
    character = _character(actor.world)
    comp = CredibilityComponent(score=0.0, confirmations=0)
    ctx = ComponentPromptContext.for_entity(actor.world, character)
    assert comp.prompt_fragments(ctx) == ()


def test_credibility_prompt_third_person_is_silent():
    actor = WorldActor()
    subject = _character(actor.world, name="Vin")
    viewer = _character(actor.world, name="Kell")
    subject.add_component(CredibilityComponent(score=10.0, confirmations=1))
    ctx = ComponentPromptContext.for_entity(
        actor.world, subject, perspective=PromptPerspective(viewer=viewer)
    )
    assert subject.get_component(CredibilityComponent).prompt_fragments(ctx) == ()


def test_credibility_fragments_helper():
    actor = WorldActor()
    character = _character(actor.world)
    assert credibility_fragments(actor.world, character) == []
    assert credibility_fragments(actor.world, None) == []
    character.add_component(CredibilityComponent(score=10.0, confirmations=1))
    # for_entity defaults to first-person, so the fragment surfaces.
    assert credibility_fragments(actor.world, character)


# -- aspire_to_renown -------------------------------------------------------------------


def test_aspire_to_renown_adds_and_is_idempotent():
    actor = WorldActor()
    character = _character(actor.world)
    aspire_to_renown(character)
    assert character.get_component(GoalComponent).active_goals == (RENOWN_GOAL,)
    aspire_to_renown(character)  # idempotent
    assert character.get_component(GoalComponent).active_goals == (RENOWN_GOAL,)


def test_aspire_to_renown_merges_with_existing_goals():
    actor = WorldActor()
    character = _character(actor.world)
    character.add_component(GoalComponent(active_goals=("find water",)))
    aspire_to_renown(character)
    assert set(character.get_component(GoalComponent).active_goals) == {"find water", RENOWN_GOAL}


# -- CryptidRenownReactor ---------------------------------------------------------------


def test_reactor_awards_credibility_reputation_believers_and_goal():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room, name="Vin")
    witness = _character(actor.world, room, name="Kell")
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")

    reactor = CryptidRenownReactor(actor.world)
    reactor._on_confirmed_event(_confirmed_event(actor.world, investigator, cryptid))

    cred = investigator.get_component(CredibilityComponent)
    assert cred.confirmations == 1 and cred.score == 10.0
    assert investigator.get_component(ReputationComponent).known_for == ("cryptozoology",)
    assert RENOWN_GOAL in investigator.get_component(GoalComponent).active_goals
    # The witness became a believer.
    assert standing_toward(actor.world, witness.id, investigator.id) == "believer"


def test_reactor_becomes_renowned_after_threshold():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id)
    reactor = CryptidRenownReactor(actor.world)
    for _ in range(RENOWN_THRESHOLD):
        reactor._on_confirmed_event(_confirmed_event(actor.world, investigator, cryptid))
    cred = investigator.get_component(CredibilityComponent)
    assert cred.confirmations == RENOWN_THRESHOLD and cred.renowned


def test_reactor_ignores_missing_investigator():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id)
    event = _confirmed_event(actor.world, investigator, cryptid)
    actor.world.remove(investigator.id)
    reactor = CryptidRenownReactor(actor.world)
    reactor._on_confirmed_event(event)  # no crash, nothing awarded
    assert not list(actor.world.query().with_all([CredibilityComponent]).execute_entities())


def test_reactor_publishes_reputation_onto_existing_component():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room)
    investigator.add_component(ReputationComponent(score=5.0, known_for=("fishing",)))
    cryptid = spawn_cryptid(actor.world, room_id=room.id)
    CryptidRenownReactor(actor.world)._on_confirmed_event(
        _confirmed_event(actor.world, investigator, cryptid)
    )
    rep = investigator.get_component(ReputationComponent)
    assert rep.score == 15.0 and set(rep.known_for) == {"fishing", "cryptozoology"}


def test_reactor_believers_helper_ignores_roomless_and_non_characters():
    actor = WorldActor()
    investigator = _character(actor.world)  # no room
    cryptid = spawn_cryptid(actor.world, name="mothman")
    CryptidRenownReactor(actor.world)._on_confirmed_event(
        _confirmed_event(actor.world, investigator, cryptid)
    )
    # Roomless investigator still gets credibility, just no believers.
    assert investigator.get_component(CredibilityComponent).confirmations == 1


# -- record_confirmation_photo (history + imagegen) -------------------------------------


def test_confirmation_photo_records_history_and_requests_image():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")
    event = _confirmed_event(actor.world, investigator, cryptid)

    record_confirmation_photo(actor.world, event)

    records = list(actor.world.query().with_all([WorldHistoryRecordComponent]).execute_entities())
    assert records
    assert records[0].get_component(WorldHistoryRecordComponent).location_id == str(room.id)
    assert cryptid.has_component(ImageRequestComponent)
    # Idempotent: a second call does not double the image request or the history record.
    record_confirmation_photo(actor.world, event)
    again = list(actor.world.query().with_all([WorldHistoryRecordComponent]).execute_entities())
    assert len(again) == len(records)


def test_confirmation_photo_tolerates_vanished_cryptid():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")
    event = _confirmed_event(actor.world, investigator, cryptid)
    actor.world.remove(cryptid.id)
    record_confirmation_photo(actor.world, event)  # no crash
    records = list(actor.world.query().with_all([WorldHistoryRecordComponent]).execute_entities())
    assert records[0].get_component(WorldHistoryRecordComponent).location_id == ""


def test_install_credibility_end_to_end_over_the_bus():
    actor = WorldActor()
    install_credibility(actor)
    room = _room(actor.world)
    investigator = _character(actor.world, room)
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")
    # Build a confirmed case and let the confirmation consequence emit the event.
    record_sighting(
        actor.world,
        investigator_id=str(investigator.id),
        cryptid_id=str(cryptid.id),
        cryptid_name="mothman",
        clarity=0.9,
        clear=True,
    )
    case = list(actor.world.query().with_all([CryptidCaseComponent]).execute_entities())[0]
    from dataclasses import replace as _replace

    from bunnyland.core.ecs import replace_component

    replace_component(case, _replace(case.get_component(CryptidCaseComponent), clear_count=2))
    events = CryptidConfirmationConsequence().process(actor.world, 0)
    for event in events:
        asyncio.run(actor.bus.publish(event))
    assert investigator.get_component(CredibilityComponent).confirmations == 1
    assert cryptid.has_component(ImageRequestComponent)


# -- doubt-cryptid verb -----------------------------------------------------------------


def test_doubt_makes_a_skeptic():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room, name="Vin")
    skeptic = _character(actor.world, room, name="Doubt")
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")
    record_sighting(
        actor.world,
        investigator_id=str(investigator.id),
        cryptid_id=str(cryptid.id),
        cryptid_name="mothman",
        clarity=0.2,
        clear=False,
    )
    result = DoubtCryptidHandler().execute(
        HandlerContext(world=actor.world, epoch=0),
        _doubt_cmd(
            skeptic.id, {"investigator_id": str(investigator.id), "cryptid_id": str(cryptid.id)}
        ),
    )
    assert result.ok and isinstance(result.events[0], CryptidDoubtedEvent)
    assert standing_toward(actor.world, skeptic.id, investigator.id) == "skeptic"


def test_doubt_rejects_invalid_skeptic():
    actor = WorldActor()
    result = DoubtCryptidHandler().execute(
        HandlerContext(world=actor.world, epoch=0),
        _doubt_cmd("???", {"investigator_id": "entity_1", "cryptid_id": "c"}),
    )
    assert not result.ok and result.reason == "invalid character id"


def test_doubt_rejects_missing_investigator():
    actor = WorldActor()
    room = _room(actor.world)
    skeptic = _character(actor.world, room)
    result = DoubtCryptidHandler().execute(
        HandlerContext(world=actor.world, epoch=0),
        _doubt_cmd(skeptic.id, {"investigator_id": "entity_9999", "cryptid_id": "c"}),
    )
    assert not result.ok and result.reason == "investigator does not exist"


def test_doubt_rejects_non_character_investigator():
    actor = WorldActor()
    room = _room(actor.world)
    skeptic = _character(actor.world, room)
    rock = spawn_entity(actor.world, [IdentityComponent(name="rock", kind="item")])
    result = DoubtCryptidHandler().execute(
        HandlerContext(world=actor.world, epoch=0),
        _doubt_cmd(skeptic.id, {"investigator_id": str(rock.id), "cryptid_id": "c"}),
    )
    assert not result.ok and result.reason == "that is not an investigator"


def test_doubt_rejects_when_no_case_exists():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room, name="Vin")
    skeptic = _character(actor.world, room, name="Doubt")
    result = DoubtCryptidHandler().execute(
        HandlerContext(world=actor.world, epoch=0),
        _doubt_cmd(skeptic.id, {"investigator_id": str(investigator.id), "cryptid_id": "c"}),
    )
    assert not result.ok and result.reason == "they hold no such case to dispute"


def test_doubt_rejects_confirmed_case():
    actor = WorldActor()
    room = _room(actor.world)
    investigator = _character(actor.world, room, name="Vin")
    skeptic = _character(actor.world, room, name="Doubt")
    cryptid = spawn_cryptid(actor.world, room_id=room.id, name="mothman")
    case = record_sighting(
        actor.world,
        investigator_id=str(investigator.id),
        cryptid_id=str(cryptid.id),
        cryptid_name="mothman",
        clarity=0.9,
        clear=True,
    )
    from dataclasses import replace as _replace

    from bunnyland.core.ecs import replace_component

    replace_component(case, _replace(case.get_component(CryptidCaseComponent), confirmed=True))
    result = DoubtCryptidHandler().execute(
        HandlerContext(world=actor.world, epoch=0),
        _doubt_cmd(
            skeptic.id, {"investigator_id": str(investigator.id), "cryptid_id": str(cryptid.id)}
        ),
    )
    assert not result.ok
    assert result.reason == "the evidence is undeniable; there is nothing to dispute"


def test_standing_toward_none_without_bond():
    actor = WorldActor()
    a = _character(actor.world)
    b = _character(actor.world)
    assert standing_toward(actor.world, a.id, b.id) is None
