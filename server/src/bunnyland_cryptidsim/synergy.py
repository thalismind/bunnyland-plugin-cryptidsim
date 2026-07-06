"""Optional cross-pack synergies, wired through **safe conditional imports**.

Cryptidsim runs perfectly well on its own. When a partner pack *happens* to be installed
alongside it, a couple of small biases switch on:

- **wildsim `Scent`** — a room where creatures have left a strong scent trail makes a
  camera-trap capture (and a live sighting) a little clearer: you are tracking fresh spoor.
- **fortunesim `Luck`** — a lucky investigator's readings come out a touch clearer, an
  unlucky one's a touch blurrier (a small clarity *bias*, never a hard gate).

Each partner is imported with a bare ``try/except ImportError``; if the pack is absent the
symbol is ``None``, the ``HAS_*`` flag is ``False``, and the corresponding bias helper simply
returns ``0.0`` — the feature is *off*, not broken. Nothing here reaches into another pack's
private state: it only reads the pack's own **published, open component** (its connector
surface).
"""

from __future__ import annotations

from relics import Entity, World

try:  # wildsim publishes ScentTrailComponent on rooms it has scent in.
    from bunnyland_wildsim.components import ScentTrailComponent
except ImportError:  # pragma: no cover - exercised via the dormant-path test with monkeypatch
    ScentTrailComponent = None

try:  # fortunesim publishes LuckComponent as an open, readable stat.
    from bunnyland_fortunesim.components import LuckComponent
except ImportError:  # pragma: no cover - exercised via the dormant-path test with monkeypatch
    LuckComponent = None

#: Whether the wildsim scent surface is available to fold in.
HAS_WILDSIM = ScentTrailComponent is not None

#: Whether the fortunesim luck surface is available to fold in.
HAS_FORTUNESIM = LuckComponent is not None

#: Ceiling on the clarity bonus a strong scent trail can contribute.
MAX_SCENT_BONUS = 0.15

#: Ceiling (magnitude) on the clarity bias luck can contribute either way.
MAX_LUCK_BIAS = 0.1


def scent_clarity_bonus(world: World, room: Entity | None) -> float:
    """A small, non-negative clarity bonus from fresh spoor in ``room`` (0 when off).

    Reads wildsim's own ``ScentTrailComponent`` if that pack is loaded; otherwise the
    feature is dormant and this returns ``0.0``.
    """
    if not HAS_WILDSIM or room is None or not room.has_component(ScentTrailComponent):
        return 0.0
    strength = room.get_component(ScentTrailComponent).strength
    return min(MAX_SCENT_BONUS, max(0.0, 0.05 * strength))


def luck_clarity_bias(world: World, character_id) -> float:
    """A small clarity bias (positive or negative) from an investigator's luck (0 when off).

    Reads fortunesim's own ``LuckComponent.value`` if that pack is loaded; otherwise dormant.
    """
    if not HAS_FORTUNESIM or character_id is None or not world.has_entity(character_id):
        return 0.0
    entity = world.get_entity(character_id)
    if not entity.has_component(LuckComponent):
        return 0.0
    value = entity.get_component(LuckComponent).value
    return max(-MAX_LUCK_BIAS, min(MAX_LUCK_BIAS, 0.1 * value))


__all__ = [
    "HAS_FORTUNESIM",
    "HAS_WILDSIM",
    "MAX_LUCK_BIAS",
    "MAX_SCENT_BONUS",
    "luck_clarity_bias",
    "scent_clarity_bonus",
]
