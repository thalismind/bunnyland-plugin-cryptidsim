"""Out-of-tree Bunnyland plugin: cryptozoology / mysterious-creatures expansion pack.

Rare, elusive, flesh-and-blood mystery creatures leave *uncertain* evidence. Investigate a
cryptid under cover of night or fog to log a sighting whose clarity is deterministic but
doubtful; enough clear looks confirm the creature and reward the discovery. Distinct from
ghost detection (no spirits, no banishing) and from certain common-creature lore (these are
rare and unconfirmed until proven).
"""

from .cases import (
    CONFIRM_CLEAR_SIGHTINGS,
    CONFIRM_REPUTATION,
    CryptidConfirmationConsequence,
    find_case,
    record_sighting,
)
from .components import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    CryptidComponent,
    SightingComponent,
)
from .conditions import (
    DARK_LIGHT_THRESHOLD,
    OBSCURING_WEATHER,
    is_concealing,
    room_light_level,
)
from .enrichment import CryptidWorldgenHook
from .events import CryptidConfirmedEvent, SightingRecordedEvent
from .fragments import cryptidsim_fragments
from .install import install_cryptidsim
from .plugin import PLUGIN_ID, bunnyland_plugins, plugin
from .prefabs import spawn_cryptid
from .sighting import (
    CLEAR_CLARITY,
    SIGHT_ACTION_DEFINITIONS,
    SIGHT_ACTION_HANDLERS,
    SightCryptidHandler,
    is_clear,
    sighting_clarity,
)
from .spatial import holder_of, room_of

__all__ = [
    "CLEAR_CLARITY",
    "CONFIRM_CLEAR_SIGHTINGS",
    "CONFIRM_REPUTATION",
    "DARK_LIGHT_THRESHOLD",
    "OBSCURING_WEATHER",
    "PLUGIN_ID",
    "SIGHT_ACTION_DEFINITIONS",
    "SIGHT_ACTION_HANDLERS",
    "ConfirmedCryptidComponent",
    "CryptidCaseComponent",
    "CryptidComponent",
    "CryptidConfirmationConsequence",
    "CryptidConfirmedEvent",
    "CryptidWorldgenHook",
    "SightCryptidHandler",
    "SightingComponent",
    "SightingRecordedEvent",
    "bunnyland_plugins",
    "cryptidsim_fragments",
    "find_case",
    "holder_of",
    "install_cryptidsim",
    "is_clear",
    "is_concealing",
    "plugin",
    "record_sighting",
    "room_light_level",
    "room_of",
    "sighting_clarity",
    "spawn_cryptid",
]
