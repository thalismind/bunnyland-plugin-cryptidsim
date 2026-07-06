from __future__ import annotations

from bunnyland.core import (
    ExitTo,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.components import WorldClockComponent

from bunnyland_cryptidsim.lairs import (
    LAIR_HOME_BONUS,
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
from bunnyland_cryptidsim.prefabs import spawn_cryptid

DAY = 24 * 60 * 60
NOON_CLEAR = 12 * 3600


def _room(world, title="Cave"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _link(a, b):
    a.add_relationship(ExitTo(), b.id)


def _day_clock(actor):
    from dataclasses import replace

    from bunnyland.core.ecs import replace_component

    clock = list(actor.world.query().with_all([WorldClockComponent]).execute_entities())[0]
    replace_component(
        clock, replace(clock.get_component(WorldClockComponent), game_time_seconds=NOON_CLEAR)
    )


# -- establish_lair / lair_room_of ------------------------------------------------------


def test_establish_lair_marks_room_and_links_edge():
    actor = WorldActor()
    lair = _room(actor.world)
    cryptid = spawn_cryptid(actor.world, name="mothman", habitat="swamp")
    result = establish_lair(actor.world, cryptid, room_id=lair.id, epoch=5)
    assert result is not None and lair.has_component(LairComponent)
    assert lair.get_component(LairComponent).habitat == "swamp"
    assert lair_room_of(actor.world, cryptid).id == lair.id


def test_establish_lair_unknown_room_returns_none():
    actor = WorldActor()
    cryptid = spawn_cryptid(actor.world)
    assert establish_lair(actor.world, cryptid, room_id="entity_9999") is None
    assert establish_lair(actor.world, cryptid, room_id=None) is None


def test_lair_room_of_none_without_den():
    actor = WorldActor()
    cryptid = spawn_cryptid(actor.world)
    assert lair_room_of(actor.world, cryptid) is None


def test_lair_clarity_bonus_only_on_home_ground():
    actor = WorldActor()
    lair = _room(actor.world)
    elsewhere = _room(actor.world)
    cryptid = spawn_cryptid(actor.world)
    establish_lair(actor.world, cryptid, room_id=lair.id)
    assert lair_clarity_bonus(actor.world, cryptid, lair) == LAIR_HOME_BONUS
    assert lair_clarity_bonus(actor.world, cryptid, elsewhere) == 0.0
    assert lair_clarity_bonus(actor.world, cryptid, None) == 0.0


def test_spawn_lair_room_is_prelabelled():
    actor = WorldActor()
    room = spawn_lair_room(actor.world, title="Den", habitat="cave")
    assert room.has_component(LairComponent) and room.has_component(RoomComponent)


# -- LairProwlConsequence ---------------------------------------------------------------


def test_cryptid_returns_home_by_day():
    actor = WorldActor()
    _day_clock(actor)  # not concealing -> slink home
    lair = _room(actor.world, "Lair")
    away = _room(actor.world, "Field")
    cryptid = spawn_cryptid(actor.world, room_id=away.id, name="mothman")
    cryptid.add_component(MovementPatternComponent())
    establish_lair(actor.world, cryptid, room_id=lair.id)

    events = LairProwlConsequence().process(actor.world, NOON_CLEAR)
    assert len(events) == 1 and isinstance(events[0], CryptidProwledEvent)
    assert events[0].to_room_id == str(lair.id)


def test_cryptid_prowls_at_night_deterministically():
    actor = WorldActor()  # night -> concealing
    lair = _room(actor.world, "Lair")
    neighbor = _room(actor.world, "Trail")
    start = _room(actor.world, "Ridge")
    _link(lair, neighbor)
    cryptid = spawn_cryptid(actor.world, room_id=start.id, name="mothman")
    cryptid.add_component(MovementPatternComponent())
    establish_lair(actor.world, cryptid, room_id=lair.id)

    first = LairProwlConsequence().process(actor.world, DAY)
    # It leaves the ridge for its lair beat (lair itself or an adjacent room).
    assert len(first) == 1
    assert first[0].to_room_id in {str(lair.id), str(neighbor.id)}
    # Deterministic: the same world/day always chooses the same destination.
    second_world_dest = first[0].to_room_id
    assert first[0].from_room_id == str(start.id)
    assert second_world_dest == first[0].to_room_id


def test_prowl_skips_patternless_and_lairless_cryptids():
    actor = WorldActor()
    # A cryptid with no lair, and one with no movement pattern -> neither moves.
    lair = _room(actor.world)
    homeless = spawn_cryptid(actor.world, room_id=lair.id)
    homeless.add_component(MovementPatternComponent())  # pattern but no lair
    assert LairProwlConsequence().process(actor.world, DAY) == []


def test_prowl_noop_when_already_at_destination_by_day():
    actor = WorldActor()
    _day_clock(actor)
    lair = _room(actor.world, "Lair")
    cryptid = spawn_cryptid(actor.world, room_id=lair.id, name="mothman")
    cryptid.add_component(MovementPatternComponent())
    establish_lair(actor.world, cryptid, room_id=lair.id)
    # Already home during the day -> no movement event.
    assert LairProwlConsequence().process(actor.world, NOON_CLEAR) == []


def test_prowl_skips_daytime_wanderer_that_never_dens():
    actor = WorldActor()
    _day_clock(actor)
    lair = _room(actor.world, "Lair")
    away = _room(actor.world, "Field")
    cryptid = spawn_cryptid(actor.world, room_id=away.id, name="mothman")
    cryptid.add_component(MovementPatternComponent(stays_home_by_day=False))
    establish_lair(actor.world, cryptid, room_id=lair.id)
    # By day, a non-homing pattern stays put.
    assert LairProwlConsequence().process(actor.world, NOON_CLEAR) == []


def test_install_lairs_registers_consequence():
    actor = WorldActor()
    install_lairs(actor)
    assert any(isinstance(c, LairProwlConsequence) for c in actor._consequences)


def test_haunts_lair_edge_is_queryable():
    actor = WorldActor()
    lair = _room(actor.world)
    cryptid = spawn_cryptid(actor.world)
    establish_lair(actor.world, cryptid, room_id=lair.id, epoch=7)
    edges = list(cryptid.get_relationships(HauntsLair))
    assert edges and edges[0][0].since_epoch == 7
