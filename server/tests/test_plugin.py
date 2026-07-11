from __future__ import annotations

from bunnyland.core.world_actor import WorldActor
from bunnyland.plugins import apply_plugins

from bunnyland_cryptidsim import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    CryptidComponent,
    CryptidGenerationEnricher,
    SightingComponent,
    cryptidsim_fragments,
)
from bunnyland_cryptidsim.plugin import PLUGIN_ID
from bunnyland_cryptidsim.plugin import bunnyland_plugins as _plugins


def test_plugin_id_is_the_dotted_id():
    # A dotted id is not module-qualified by the loader.
    assert PLUGIN_ID == "bunnyland.cryptidsim"


def test_plugin_loads_with_dotted_id():
    plugins = _plugins()
    assert [p.id for p in plugins] == ["bunnyland.cryptidsim"]


def test_plugin_declares_its_contributions():
    plugin = _plugins()[0]
    for component in (
        CryptidComponent,
        ConfirmedCryptidComponent,
        SightingComponent,
        CryptidCaseComponent,
    ):
        assert component in plugin.ecs.components
    assert CryptidGenerationEnricher in [type(item) for item in plugin.content.generation_enrichers]
    assert cryptidsim_fragments in plugin.content.prompt_fragments


def test_plugin_applies_and_registers_the_sight_verb():
    actor = WorldActor()
    applied = apply_plugins(_plugins(), actor)
    assert applied[0].id == "bunnyland.cryptidsim"
    command_types = {definition.command_type for definition in actor.action_definitions()}
    assert "sight-cryptid" in command_types
