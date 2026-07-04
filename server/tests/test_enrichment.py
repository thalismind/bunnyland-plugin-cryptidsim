from __future__ import annotations

import asyncio

from bunnyland.core import (
    CharacterComponent,
    IdentityComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.components import GenerationIntentComponent
from bunnyland.core.events import CharacterGeneratedEvent, event_base
from bunnyland.plugins import apply_plugins, load_modules

from bunnyland_cryptidsim import CryptidComponent


def _actor():
    actor = WorldActor()
    apply_plugins(load_modules(["bunnyland_cryptidsim"]), actor)
    return actor


def _publish(actor, event):
    asyncio.run(actor.bus.publish(event))


def _character(actor, *, tags=(), description="", character_key="npc"):
    entity = spawn_entity(
        actor.world, [IdentityComponent(name="npc", kind="character"), CharacterComponent()]
    )
    event = CharacterGeneratedEvent(
        **event_base(0),
        seed="seed",
        entity_id=str(entity.id),
        entity_key="npc",
        entity_kind="character",
        generation=GenerationIntentComponent(tags=tuple(tags), description=description),
        character_key=character_key,
        room_id="room_1",
    )
    _publish(actor, event)
    return entity


def test_cryptid_tag_marks_a_generated_creature():
    actor = _actor()
    creature = _character(actor, tags=("cryptid", "hairy hominid"), character_key="sasquatch")
    assert creature.has_component(CryptidComponent)
    assert creature.get_component(CryptidComponent).name == "sasquatch"


def test_cryptid_detected_from_description_text():
    actor = _actor()
    creature = _character(actor, description="a rumored lake monster that surfaces at dusk")
    assert creature.has_component(CryptidComponent)


def test_benign_character_is_not_marked():
    actor = _actor()
    villager = _character(actor, tags=("farmer", "friendly"), description="a cheerful baker")
    assert not villager.has_component(CryptidComponent)


def test_elusive_hint_raises_elusiveness():
    actor = _actor()
    creature = _character(actor, tags=("cryptid", "elusive"))
    assert creature.get_component(CryptidComponent).elusiveness == 0.85


def test_plain_cryptid_keeps_default_elusiveness():
    actor = _actor()
    creature = _character(actor, tags=("cryptid",))
    assert creature.get_component(CryptidComponent).elusiveness == 0.6


def test_habitat_is_inferred_from_biome_words():
    actor = _actor()
    creature = _character(actor, description="a cryptid haunting the deep swamp")
    assert creature.get_component(CryptidComponent).habitat == "swamp"


def test_unknown_biome_falls_back_to_wilderness():
    actor = _actor()
    creature = _character(actor, tags=("cryptid",))
    assert creature.get_component(CryptidComponent).habitat == "wilderness"
