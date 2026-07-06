"""The cryptid flap: paced storyteller incidents that break, run, and quiet down."""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.components import DeadComponent, SuspendedComponent, WorldClockComponent
from bunnyland.core.ecs import replace_component
from bunnyland.mechanics.environment import TimeOfDayComponent, WeatherComponent

from bunnyland_cryptidsim.components import SightingComponent
from bunnyland_cryptidsim.flap import (
    FLAP_CREATURES,
    FLAP_DURATION_SECONDS,
    CryptidFlapConsequence,
    CryptidFlapEndedEvent,
    CryptidFlapPressureComponent,
    CryptidFlapStartedEvent,
    _flap_seed_hash,
    _target_room,
    active_flap,
    ensure_flap_pressure,
    flap_clarity_bonus,
    install_flap,
    sighting_buzz,
)
from bunnyland_cryptidsim.prefabs import spawn_cryptid


def _room(world, title="Hollow"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _char(world, room=None, *extra):
    person = spawn_entity(
        world, [IdentityComponent(name="Ada", kind="character"), CharacterComponent(), *extra]
    )
    if room is not None:
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), person.id)
    return person


def _sightings(world, count):
    for i in range(count):
        spawn_entity(world, [SightingComponent(cryptid_name="x", recorded_at_epoch=i)])


def _ready(actor, **fields):
    """Seed the flap marker and overwrite the given policy fields."""
    clock = ensure_flap_pressure(actor.world)
    replace_component(clock, replace(clock.get_component(CryptidFlapPressureComponent), **fields))
    return clock


# -- ensure_flap_pressure / sighting_buzz -----------------------------------------------


def test_ensure_flap_pressure_is_idempotent():
    actor = WorldActor()
    first = ensure_flap_pressure(actor.world)
    second = ensure_flap_pressure(actor.world)
    assert first is not None and first.id == second.id


def test_ensure_flap_pressure_without_a_clock_returns_none():
    actor = WorldActor()
    for clock in list(actor.world.query().with_all([WorldClockComponent]).execute_entities()):
        actor.world.remove(clock.id)
    assert ensure_flap_pressure(actor.world) is None


def test_sighting_buzz_counts_and_caps():
    actor = WorldActor()
    assert sighting_buzz(actor.world) == 0.0
    _sightings(actor.world, 3)
    assert round(sighting_buzz(actor.world), 6) == 0.3
    _sightings(actor.world, 30)
    assert sighting_buzz(actor.world) == 1.0  # capped at MAX_BUZZ


def test_flap_seed_hash_is_stable_and_bounded():
    assert _flap_seed_hash("0") == _flap_seed_hash("0")
    assert 0 <= _flap_seed_hash("42") < 256


# -- _target_room -----------------------------------------------------------------------


def test_target_room_prefers_a_living_characters_room():
    actor = WorldActor()
    room = _room(actor.world)
    _char(actor.world, room)
    assert _target_room(actor.world).id == room.id


def test_target_room_skips_dead_suspended_and_cryptids_then_falls_back():
    actor = WorldActor()
    room = _room(actor.world)
    _char(actor.world, room, DeadComponent(died_at_epoch=0, cause="natural"))
    _char(actor.world, room, SuspendedComponent())
    spawn_cryptid(actor.world, room_id=room.id)  # a cryptid character is skipped
    # No eligible living non-cryptid character, so it falls back to the first room.
    assert _target_room(actor.world).id == room.id


def test_target_room_none_when_world_is_empty():
    actor = WorldActor()
    assert _target_room(actor.world) is None


# -- CryptidFlapConsequence.process -----------------------------------------------------


def test_process_breaks_a_flap_when_due_and_pressured():
    actor = WorldActor()
    room = _room(actor.world)
    _char(actor.world, room)
    _ready(actor, next_flap_epoch=0, base_pressure=0.9)
    events = CryptidFlapConsequence().process(actor.world, 0)
    started = [e for e in events if isinstance(e, CryptidFlapStartedEvent)]
    assert started and started[0].cryptid_name in FLAP_CREATURES
    assert active_flap(actor.world) is not None
    assert flap_clarity_bonus(actor.world) > 0.0


def test_no_flap_when_pressure_is_below_threshold():
    actor = WorldActor()
    _char(actor.world, _room(actor.world))
    _ready(actor, next_flap_epoch=0, base_pressure=0.1)  # no sightings -> under 0.6
    assert CryptidFlapConsequence().process(actor.world, 0) == []


def test_no_flap_before_the_next_due_epoch():
    actor = WorldActor()
    _char(actor.world, _room(actor.world))
    _ready(actor, next_flap_epoch=10_000, base_pressure=0.9)
    assert CryptidFlapConsequence().process(actor.world, 0) == []


def test_disabled_marker_never_flaps():
    actor = WorldActor()
    _char(actor.world, _room(actor.world))
    _ready(actor, enabled=False, next_flap_epoch=0, base_pressure=0.9)
    assert CryptidFlapConsequence().process(actor.world, 0) == []


def test_no_flap_when_conditions_are_not_concealing():
    actor = WorldActor()
    _char(actor.world, _room(actor.world))
    clock = _ready(actor, next_flap_epoch=0, base_pressure=0.9)
    # Broad daylight, clear sky: not concealing, so nothing appears.
    clock.add_component(TimeOfDayComponent(phase="day"))
    clock.add_component(WeatherComponent(condition="clear"))
    assert CryptidFlapConsequence().process(actor.world, 0) == []


def test_no_second_flap_while_one_is_live():
    actor = WorldActor()
    _char(actor.world, _room(actor.world))
    _ready(actor, next_flap_epoch=0, base_pressure=0.9)
    CryptidFlapConsequence().process(actor.world, 0)
    _ready(actor, next_flap_epoch=100, base_pressure=0.9)  # due again, but a flap is live
    assert CryptidFlapConsequence().process(actor.world, 100) == []


def test_no_flap_event_when_there_is_nowhere_to_send_one():
    actor = WorldActor()
    _ready(actor, next_flap_epoch=0, base_pressure=0.9)  # no rooms, no characters
    assert CryptidFlapConsequence().process(actor.world, 0) == []


def test_flap_expires_after_its_run():
    actor = WorldActor()
    _char(actor.world, _room(actor.world))
    _ready(actor, next_flap_epoch=0, base_pressure=0.9)
    CryptidFlapConsequence().process(actor.world, 0)
    assert active_flap(actor.world) is not None
    _ready(actor, enabled=False)  # keep a fresh flap from breaking on the expiry tick
    ended = CryptidFlapConsequence().process(actor.world, FLAP_DURATION_SECONDS)
    assert any(isinstance(e, CryptidFlapEndedEvent) for e in ended)
    assert active_flap(actor.world) is None


def test_install_flap_registers_and_seeds_pressure():
    actor = WorldActor()
    install_flap(actor)
    assert ensure_flap_pressure(actor.world) is not None
