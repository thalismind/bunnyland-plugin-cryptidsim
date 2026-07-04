"""Bunnyland plugin entrypoint for the out-of-tree cryptidsim expansion pack."""

from __future__ import annotations

from bunnyland.plugins import (
    CommandContribution,
    ContentContribution,
    EcsContribution,
    Plugin,
    RuntimeContribution,
)

from .cases import CryptidConfirmationConsequence
from .components import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    CryptidComponent,
    SightingComponent,
)
from .enrichment import CryptidWorldgenHook
from .events import CryptidConfirmedEvent, SightingRecordedEvent
from .fragments import cryptidsim_fragments
from .install import install_cryptidsim
from .sighting import SIGHT_ACTION_DEFINITIONS, SIGHT_ACTION_HANDLERS

PLUGIN_ID = "bunnyland.cryptidsim"


def plugin() -> Plugin:
    return Plugin(
        id=PLUGIN_ID,
        name="Bunnyland Cryptidsim",
        version="0.1.0",
        default_enabled=True,
        ecs=EcsContribution(
            components=(
                CryptidComponent,
                ConfirmedCryptidComponent,
                SightingComponent,
                CryptidCaseComponent,
            ),
        ),
        commands=CommandContribution(
            action_handlers=SIGHT_ACTION_HANDLERS,
            action_definitions=SIGHT_ACTION_DEFINITIONS,
            typed_events=(
                SightingRecordedEvent,
                CryptidConfirmedEvent,
            ),
        ),
        runtime=RuntimeContribution(
            service_factories=(install_cryptidsim,),
        ),
        content=ContentContribution(
            prompt_fragments=(cryptidsim_fragments,),
            worldgen_hooks=(CryptidWorldgenHook,),
        ),
    )


def bunnyland_plugins() -> list[Plugin]:
    return [plugin()]


__all__ = ["PLUGIN_ID", "CryptidConfirmationConsequence", "bunnyland_plugins", "plugin"]
