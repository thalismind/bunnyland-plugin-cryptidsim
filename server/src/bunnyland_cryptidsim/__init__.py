"""Out-of-tree Bunnyland plugin: cryptozoology / mysterious-creatures expansion pack.

Rare, elusive, flesh-and-blood mystery creatures leave *uncertain* evidence. Investigate a
cryptid under cover of night or fog to log a sighting whose clarity is deterministic but
doubtful; enough clear looks confirm the creature and reward the discovery. v2 adds the
headline loop — **bait + camera traps → credibility/fame** — plus **lairs and nightly
movement patterns**, a paced **cryptid-flap** storyteller incident, and optional wildsim/
fortunesim synergies. Distinct from ghost detection (no spirits, no banishing) and from
certain common-creature lore (these are rare and unconfirmed until proven).
"""

from .bait import (
    BAIT_ACTION_DEFINITIONS,
    BAIT_ACTION_HANDLERS,
    BaitComponent,
    BaitPlacedEvent,
    bait_bonus,
    spawn_bait,
)
from .camera_traps import (
    CAMERA_TRAP_ACTION_DEFINITIONS,
    CAMERA_TRAP_ACTION_HANDLERS,
    CameraTrapCapturedEvent,
    CameraTrapComponent,
    CameraTrapConsequence,
    CameraTrapSetEvent,
    SetCameraTrapHandler,
    install_camera_traps,
    spawn_camera_trap,
)
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
from .credibility import (
    CREDIBILITY_ACTION_DEFINITIONS,
    CREDIBILITY_ACTION_HANDLERS,
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
from .enrichment import CryptidGenerationEnricher
from .events import CryptidConfirmedEvent, SightingRecordedEvent
from .flap import (
    CryptidFlapConsequence,
    CryptidFlapEndedEvent,
    CryptidFlapPressureComponent,
    CryptidFlapStartedEvent,
    active_flap,
    ensure_flap_pressure,
    flap_clarity_bonus,
    install_flap,
    sighting_buzz,
)
from .fragments import cryptidsim_fragments
from .install import install_cryptidsim
from .lairs import (
    CryptidProwledEvent,
    HauntsLair,
    LairComponent,
    LairProwlConsequence,
    MovementPatternComponent,
    establish_lair,
    install_lairs,
    lair_clarity_bonus,
    lair_room_of,
    spawn_lair_room,
)
from .plugin import PLUGIN_ID, bunnyland_plugins, plugin
from .prefabs import spawn_cryptid
from .sighting import (
    CLEAR_CLARITY,
    SIGHT_ACTION_DEFINITIONS,
    SIGHT_ACTION_HANDLERS,
    SightCryptidHandler,
    environment_clarity_bonus,
    is_clear,
    sighting_clarity,
)
from .spatial import holder_of, room_of
from .synergy import (
    HAS_FORTUNESIM,
    HAS_WILDSIM,
    luck_clarity_bias,
    scent_clarity_bonus,
)

__all__ = [
    "BAIT_ACTION_DEFINITIONS",
    "BAIT_ACTION_HANDLERS",
    "CAMERA_TRAP_ACTION_DEFINITIONS",
    "CAMERA_TRAP_ACTION_HANDLERS",
    "CLEAR_CLARITY",
    "CONFIRM_CLEAR_SIGHTINGS",
    "CONFIRM_REPUTATION",
    "CREDIBILITY_ACTION_DEFINITIONS",
    "CREDIBILITY_ACTION_HANDLERS",
    "DARK_LIGHT_THRESHOLD",
    "HAS_FORTUNESIM",
    "HAS_WILDSIM",
    "OBSCURING_WEATHER",
    "PLUGIN_ID",
    "RENOWN_GOAL",
    "RENOWN_THRESHOLD",
    "SIGHT_ACTION_DEFINITIONS",
    "SIGHT_ACTION_HANDLERS",
    "BaitComponent",
    "BaitPlacedEvent",
    "CameraTrapCapturedEvent",
    "CameraTrapComponent",
    "CameraTrapConsequence",
    "CameraTrapSetEvent",
    "ConfirmedCryptidComponent",
    "CredibilityComponent",
    "CryptidCaseComponent",
    "CryptidComponent",
    "CryptidConfirmationConsequence",
    "CryptidConfirmedEvent",
    "CryptidDoubtedEvent",
    "CryptidFlapConsequence",
    "CryptidFlapEndedEvent",
    "CryptidFlapPressureComponent",
    "CryptidFlapStartedEvent",
    "CryptidProwledEvent",
    "CryptidRenownReactor",
    "CryptidGenerationEnricher",
    "DoubtCryptidHandler",
    "HauntsLair",
    "LairComponent",
    "LairProwlConsequence",
    "MovementPatternComponent",
    "SetCameraTrapHandler",
    "SightCryptidHandler",
    "SightingComponent",
    "SightingRecordedEvent",
    "active_flap",
    "aspire_to_renown",
    "bait_bonus",
    "bunnyland_plugins",
    "credibility_fragments",
    "cryptidsim_fragments",
    "ensure_flap_pressure",
    "environment_clarity_bonus",
    "establish_lair",
    "find_case",
    "flap_clarity_bonus",
    "holder_of",
    "install_camera_traps",
    "install_credibility",
    "install_cryptidsim",
    "install_flap",
    "install_lairs",
    "is_clear",
    "is_concealing",
    "lair_clarity_bonus",
    "lair_room_of",
    "luck_clarity_bias",
    "plugin",
    "record_confirmation_photo",
    "record_sighting",
    "room_light_level",
    "room_of",
    "scent_clarity_bonus",
    "sighting_buzz",
    "sighting_clarity",
    "spawn_bait",
    "spawn_camera_trap",
    "spawn_cryptid",
    "spawn_lair_room",
    "standing_toward",
]
