"""Bunnyland plugin entrypoint for the out-of-tree cryptidsim expansion pack."""

from __future__ import annotations

from bunnyland.plugins import (
    CommandContribution,
    ContentContribution,
    DependencyContribution,
    EcsContribution,
    Plugin,
    RuntimeContribution,
)

from .bait import BAIT_ACTION_DEFINITIONS, BAIT_ACTION_HANDLERS, BaitComponent, BaitPlacedEvent
from .camera_traps import (
    CAMERA_TRAP_ACTION_DEFINITIONS,
    CAMERA_TRAP_ACTION_HANDLERS,
    CameraTrapCapturedEvent,
    CameraTrapComponent,
    CameraTrapSetEvent,
    install_camera_traps,
)
from .cases import CryptidConfirmationConsequence
from .components import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    CryptidComponent,
    SightingComponent,
)
from .credibility import (
    CREDIBILITY_ACTION_DEFINITIONS,
    CREDIBILITY_ACTION_HANDLERS,
    CredibilityComponent,
    CryptidDoubtedEvent,
    credibility_fragments,
    install_credibility,
)
from .enrichment import CryptidWorldgenHook
from .events import CryptidConfirmedEvent, SightingRecordedEvent
from .flap import (
    CryptidFlapEndedEvent,
    CryptidFlapPressureComponent,
    CryptidFlapStartedEvent,
    install_flap,
)
from .fragments import cryptidsim_fragments
from .install import install_cryptidsim
from .lairs import (
    CryptidProwledEvent,
    HauntsLair,
    LairComponent,
    MovementPatternComponent,
    install_lairs,
)
from .sighting import SIGHT_ACTION_DEFINITIONS, SIGHT_ACTION_HANDLERS

PLUGIN_ID = "bunnyland.cryptidsim"


def plugin() -> Plugin:
    return Plugin(
        id=PLUGIN_ID,
        name="Bunnyland Cryptidsim",
        version="0.2.0",
        default_enabled=True,
        # Optional synergy: wildsim scent trails and fortunesim luck gently bias sighting
        # clarity when those packs happen to be installed; cryptidsim runs fine without them.
        dependencies=DependencyContribution(
            recommends=("bunnyland.wildsim", "bunnyland.fortunesim"),
        ),
        ecs=EcsContribution(
            components=(
                CryptidComponent,
                ConfirmedCryptidComponent,
                SightingComponent,
                CryptidCaseComponent,
                BaitComponent,
                CameraTrapComponent,
                CredibilityComponent,
                LairComponent,
                MovementPatternComponent,
                CryptidFlapPressureComponent,
            ),
            edges=(HauntsLair,),
        ),
        commands=CommandContribution(
            action_handlers=(
                *SIGHT_ACTION_HANDLERS,
                *BAIT_ACTION_HANDLERS,
                *CAMERA_TRAP_ACTION_HANDLERS,
                *CREDIBILITY_ACTION_HANDLERS,
            ),
            action_definitions=(
                *SIGHT_ACTION_DEFINITIONS,
                *BAIT_ACTION_DEFINITIONS,
                *CAMERA_TRAP_ACTION_DEFINITIONS,
                *CREDIBILITY_ACTION_DEFINITIONS,
            ),
            typed_events=(
                SightingRecordedEvent,
                CryptidConfirmedEvent,
                BaitPlacedEvent,
                CameraTrapSetEvent,
                CameraTrapCapturedEvent,
                CryptidDoubtedEvent,
                CryptidProwledEvent,
                CryptidFlapStartedEvent,
                CryptidFlapEndedEvent,
            ),
        ),
        runtime=RuntimeContribution(
            service_factories=(
                install_cryptidsim,
                install_camera_traps,
                install_lairs,
                install_flap,
                install_credibility,
            ),
        ),
        content=ContentContribution(
            prompt_fragments=(cryptidsim_fragments, credibility_fragments),
            worldgen_hooks=(CryptidWorldgenHook,),
        ),
    )


def bunnyland_plugins() -> list[Plugin]:
    return [plugin()]


__all__ = ["PLUGIN_ID", "CryptidConfirmationConsequence", "bunnyland_plugins", "plugin"]
