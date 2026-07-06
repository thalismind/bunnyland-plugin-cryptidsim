"""Optional cross-pack synergies: dormant by default, active when a partner is present.

The partner packs (wildsim, fortunesim) are not installed alongside cryptidsim in CI, so the
active branches are exercised by flipping the ``HAS_*`` flags and injecting a stand-in of the
partner's published component — the same open surface the real partner exposes.
"""

from __future__ import annotations

from bunnyland.core import IdentityComponent, RoomComponent, WorldActor, spawn_entity
from pydantic.dataclasses import dataclass
from relics import Component

from bunnyland_cryptidsim import synergy


@dataclass(frozen=True)
class _FakeScentTrail(Component):
    strength: float = 0.0


@dataclass(frozen=True)
class _FakeLuck(Component):
    value: float = 0.0


# -- scent (wildsim) --------------------------------------------------------------------


def test_scent_bonus_is_dormant_without_wildsim():
    actor = WorldActor()
    room = spawn_entity(actor.world, [RoomComponent(title="Bog")])
    assert synergy.scent_clarity_bonus(actor.world, room) == 0.0
    assert synergy.scent_clarity_bonus(actor.world, None) == 0.0


def test_scent_bonus_active_when_wildsim_present(monkeypatch):
    monkeypatch.setattr(synergy, "ScentTrailComponent", _FakeScentTrail)
    monkeypatch.setattr(synergy, "HAS_WILDSIM", True)
    actor = WorldActor()
    bare = spawn_entity(actor.world, [RoomComponent(title="Clearing")])
    assert synergy.scent_clarity_bonus(actor.world, bare) == 0.0  # no trail on this room
    trail = spawn_entity(
        actor.world, [RoomComponent(title="Bog"), _FakeScentTrail(strength=2.0)]
    )
    assert round(synergy.scent_clarity_bonus(actor.world, trail), 6) == 0.1
    strong = spawn_entity(
        actor.world, [RoomComponent(title="Fen"), _FakeScentTrail(strength=100.0)]
    )
    assert synergy.scent_clarity_bonus(actor.world, strong) == synergy.MAX_SCENT_BONUS


# -- luck (fortunesim) ------------------------------------------------------------------


def test_luck_bias_is_dormant_without_fortunesim():
    actor = WorldActor()
    who = spawn_entity(actor.world, [IdentityComponent(name="Ada", kind="character")])
    assert synergy.luck_clarity_bias(actor.world, who.id) == 0.0
    assert synergy.luck_clarity_bias(actor.world, None) == 0.0


def test_luck_bias_active_when_fortunesim_present(monkeypatch):
    monkeypatch.setattr(synergy, "LuckComponent", _FakeLuck)
    monkeypatch.setattr(synergy, "HAS_FORTUNESIM", True)
    actor = WorldActor()
    plain = spawn_entity(actor.world, [IdentityComponent(name="Ada", kind="character")])
    assert synergy.luck_clarity_bias(actor.world, plain.id) == 0.0  # no LuckComponent
    lucky = spawn_entity(
        actor.world, [IdentityComponent(name="Bo", kind="character"), _FakeLuck(value=1.0)]
    )
    assert round(synergy.luck_clarity_bias(actor.world, lucky.id), 6) == 0.1
    unlucky = spawn_entity(
        actor.world, [IdentityComponent(name="Cy", kind="character"), _FakeLuck(value=-5.0)]
    )
    assert synergy.luck_clarity_bias(actor.world, unlucky.id) == -synergy.MAX_LUCK_BIAS
    # A missing id short-circuits even when the surface is live.
    removed = plain.id
    actor.world.remove(removed)
    assert synergy.luck_clarity_bias(actor.world, removed) == 0.0
