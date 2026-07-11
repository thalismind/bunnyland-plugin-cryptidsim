import asyncio

from bunnyland.core import WorldActor
from bunnyland.plugins import apply_plugins
from bunnyland.worldgen import CharacterSpec, RoomSpec, WorldProposal, instantiate

from bunnyland_cryptidsim import CryptidComponent
from bunnyland_cryptidsim.plugin import bunnyland_plugins as _plugins


def _character(*, key="creature", description="", traits=()):
    actor = WorldActor()
    apply_plugins(_plugins(), actor)
    result = asyncio.run(
        instantiate(
            actor,
            WorldProposal(
                seed="seed",
                rooms=[RoomSpec(key="room", title="Room")],
                characters=[
                    CharacterSpec(
                        key=key, name=key, room_key="room", description=description, traits=traits
                    )
                ],
            ),
        )
    )
    return actor.world.get_entity(result.characters[key])


def test_cryptid_hints_mark_generated_creatures():
    assert _character(key="sasquatch").has_component(CryptidComponent)
    assert _character(description="a rumored lake monster").has_component(CryptidComponent)


def test_plain_creature_is_ignored():
    assert not _character(key="deer").has_component(CryptidComponent)


def test_elusiveness_and_habitat_are_inferred():
    elusive = _character(key="mystery", description="an elusive cryptid in the swamp")
    component = elusive.get_component(CryptidComponent)
    assert component.elusiveness == 0.85
    assert component.habitat == "swamp"
    assert _character(traits=("cryptid",)).get_component(CryptidComponent).habitat == "wilderness"
