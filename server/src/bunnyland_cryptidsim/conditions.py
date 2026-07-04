"""Conditions gate: cryptids only appear (and are only sightable) under cover.

Elusive creatures come out at **night**, in **fog/obscuring weather**, or in the **dark** —
never under a clear bright sky. This module reads the environment (time of day, weather, and
the room's light) and decides whether conditions are *concealing* enough for a cryptid to be
around. The sighting verb enforces it, which is what makes time and weather matter.

Time and weather come from the world clock: :class:`TimeOfDayComponent` /
:class:`WeatherComponent` are read directly when the environment consequence has already set
them, and otherwise derived from the clock's ``game_time_seconds`` via
:func:`~bunnyland.mechanics.environment.time_of_day` / ``weather_for`` — so a bare
``WorldActor`` (whose clock reads ``0`` -> ``night``) is already concealing without needing a
tick to run first.
"""

from __future__ import annotations

from bunnyland.core.components import LightComponent, WorldClockComponent
from bunnyland.mechanics.environment import (
    TimeOfDayComponent,
    WeatherComponent,
    time_of_day,
    weather_for,
)
from relics import Entity, World

#: A room dimmer than this (0..1) counts as dark enough to conceal a cryptid.
DARK_LIGHT_THRESHOLD = 0.35

#: Twilight and night phases hide a creature; broad daylight does not.
CONCEALING_PHASES = frozenset({"night", "dusk", "dawn"})

#: Weather that veils the landscape. Core has no "fog" condition, so the murkier standard
#: conditions stand in for it — anything past a clear sky obscures a distant shape.
OBSCURING_WEATHER = frozenset({"cloudy", "overcast", "rain", "storm", "fog"})


def _clock_reading(world: World) -> tuple[str, str]:
    """Return ``(phase, weather_condition)`` for the world's singleton clock."""
    clocks = list(world.query().with_all([WorldClockComponent]).execute_entities())
    if not clocks:
        return "day", "clear"
    clock = clocks[0]
    seconds = clock.get_component(WorldClockComponent).game_time_seconds
    if clock.has_component(TimeOfDayComponent):
        phase = clock.get_component(TimeOfDayComponent).phase
    else:
        phase = time_of_day(seconds)[2]
    if clock.has_component(WeatherComponent):
        condition = clock.get_component(WeatherComponent).condition
    else:
        condition = weather_for(time_of_day(seconds)[0])[0]
    return phase, condition


def room_light_level(room: Entity | None) -> float:
    """Effective light in ``room`` (0..1); an unlit room is treated as fully lit."""
    if room is not None and room.has_component(LightComponent):
        light = room.get_component(LightComponent)
        return light.level if light.enabled else 0.0
    return 1.0


def is_concealing(world: World, room: Entity | None) -> bool:
    """True when night, obscuring weather, or darkness gives a cryptid cover to appear."""
    phase, condition = _clock_reading(world)
    if phase in CONCEALING_PHASES:
        return True
    if condition in OBSCURING_WEATHER:
        return True
    return room_light_level(room) < DARK_LIGHT_THRESHOLD


__all__ = [
    "CONCEALING_PHASES",
    "DARK_LIGHT_THRESHOLD",
    "OBSCURING_WEATHER",
    "is_concealing",
    "room_light_level",
]
