from __future__ import annotations

from bunnyland.core.world_actor import WorldActor
from bunnyland.plugins import apply_plugins, load_modules

from bunnyland_cryptidsim import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    CryptidComponent,
    CryptidWorldgenHook,
    SightingComponent,
    cryptidsim_fragments,
)
from bunnyland_cryptidsim.plugin import PLUGIN_ID


def test_plugin_id_is_the_dotted_id():
    # A dotted id is not module-qualified by the loader.
    assert PLUGIN_ID == "bunnyland.cryptidsim"


def test_plugin_loads_with_dotted_id():
    plugins = load_modules(["bunnyland_cryptidsim"])
    assert [p.id for p in plugins] == ["bunnyland.cryptidsim"]


def test_plugin_declares_its_contributions():
    plugin = load_modules(["bunnyland_cryptidsim"])[0]
    for component in (
        CryptidComponent,
        ConfirmedCryptidComponent,
        SightingComponent,
        CryptidCaseComponent,
    ):
        assert component in plugin.ecs.components
    assert CryptidWorldgenHook in plugin.content.worldgen_hooks
    assert cryptidsim_fragments in plugin.content.prompt_fragments


def test_plugin_applies_and_registers_the_sight_verb():
    actor = WorldActor()
    applied = apply_plugins(load_modules(["bunnyland_cryptidsim"]), actor)
    assert applied[0].id == "bunnyland.cryptidsim"
    command_types = {definition.command_type for definition in actor.action_definitions()}
    assert "sight-cryptid" in command_types
