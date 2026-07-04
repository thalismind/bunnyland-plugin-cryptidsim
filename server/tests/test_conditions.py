from __future__ import annotations

from dataclasses import replace

from bunnyland.core import LightComponent, RoomComponent, WorldActor, spawn_entity
from bunnyland.core.components import WorldClockComponent
from bunnyland.core.ecs import replace_component

from bunnyland_cryptidsim import is_concealing, room_light_level

# Second-of-game-time that lands the clock in a given phase/day.
NOON_CLEAR = 12 * 3600  # day 1, hour 12 -> "day", weather "clear"
NOON_OVERCAST = 3 * 86400 + 12 * 3600  # day 4, hour 12 -> "day", weather "overcast"


def _set_clock(actor, seconds):
    clock = list(actor.world.query().with_all([WorldClockComponent]).execute_entities())[0]
    replace_component(
        clock, replace(clock.get_component(WorldClockComponent), game_time_seconds=seconds)
    )


def _room(world, *, light=None):
    components = [RoomComponent(title="Marsh", indoor=False)]
    if light is not None:
        components.append(LightComponent(level=light))
    return spawn_entity(world, components)


def test_default_bare_clock_is_night_and_concealing():
    actor = WorldActor()  # clock reads 0 -> night
    room = _room(actor.world)
    assert is_concealing(actor.world, room)


def test_clear_daylight_is_not_concealing():
    actor = WorldActor()
    _set_clock(actor, NOON_CLEAR)
    room = _room(actor.world, light=1.0)
    assert not is_concealing(actor.world, room)


def test_obscuring_weather_conceals_even_at_noon():
    actor = WorldActor()
    _set_clock(actor, NOON_OVERCAST)
    room = _room(actor.world, light=0.9)
    assert is_concealing(actor.world, room)


def test_darkness_conceals_in_clear_daylight():
    actor = WorldActor()
    _set_clock(actor, NOON_CLEAR)
    room = _room(actor.world, light=0.1)
    assert is_concealing(actor.world, room)


def test_room_light_level_defaults_to_lit_without_a_light_component():
    actor = WorldActor()
    room = _room(actor.world)
    assert room_light_level(room) == 1.0


def test_room_light_level_reads_disabled_light_as_dark():
    actor = WorldActor()
    room = spawn_entity(
        actor.world, [RoomComponent(title="Cave"), LightComponent(level=1.0, enabled=False)]
    )
    assert room_light_level(room) == 0.0


def test_no_clock_defaults_to_daylight():
    actor = WorldActor()
    clock = list(actor.world.query().with_all([WorldClockComponent]).execute_entities())[0]
    actor.world.remove(clock.id)
    room = _room(actor.world, light=1.0)
    assert not is_concealing(actor.world, room)
