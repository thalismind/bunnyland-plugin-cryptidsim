"""Camera traps: a patient rig that captures a cryptid on film over time.

Unlike the live ``sight`` verb, a camera trap is passive. An investigator deploys a rig in the
room they occupy; :class:`CameraTrapConsequence` runs each tick and, whenever an elusive
creature shares the rig's room under **concealing** conditions, snaps a still. The capture's
``clarity`` is deterministic — a ``hashlib`` digest over the rig id, the creature id, and the
epoch stands in for "how the shot happened to come out" — and folds in the very same
environmental bonuses the live verb uses (matching bait in the room, the creature caught on its
own lair ground, an active flap, wildsim spoor, fortune's luck).

Each capture files a sighting into the **deploying investigator's** case exactly as a live look
would, so a well-placed rig can confirm a cryptid while its owner sleeps. A rig fires at most
once per ``cooldown_seconds`` so a lingering creature never floods the dossier, and setting one
is the moment an investigator picks up the renowned-cryptozoologist goal.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    PortableComponent,
    contents,
    spawn_entity,
)
from bunnyland.core.actions import ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
from bunnyland.core.components import DeadComponent
from bunnyland.core.ecs import parse_entity_id, replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
)
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .cases import record_sighting
from .components import CryptidComponent, SightingComponent
from .conditions import is_concealing, room_light_level
from .credibility import aspire_to_renown
from .sighting import environment_clarity_bonus, is_clear, sighting_clarity
from .spatial import room_of

SECONDS_PER_HOUR = 60 * 60

#: A rig fires at most once this often, so a lingering creature never floods a dossier.
DEFAULT_COOLDOWN_SECONDS = SECONDS_PER_HOUR


@dataclass(frozen=True)
class CameraTrapComponent(Component):
    """A deployed camera rig watching a room for whatever slinks through it.

    ``placed_by`` is the investigator credited with any capture; ``last_capture_epoch`` is
    ``-1`` until the rig first fires, then holds the epoch of its most recent still.
    """

    placed_by: str = ""
    deployed_at_epoch: int = 0
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    last_capture_epoch: int = -1
    captures: int = 0


class CameraTrapSetEvent(DomainEvent):
    """An investigator deployed a camera trap in a room."""

    camera_id: str


class CameraTrapCapturedEvent(DomainEvent):
    """A camera trap caught a cryptid on film — a (usually blurry) passive sighting."""

    camera_id: str
    cryptid_id: str
    cryptid_name: str
    investigator_id: str
    clarity: float
    clear: bool


def spawn_camera_trap(
    world: World,
    *,
    room_id=None,
    placed_by: str = "",
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    epoch: int = 0,
) -> Entity:
    """Spawn a camera-trap rig, optionally placed in ``room_id``."""
    camera = spawn_entity(
        world,
        [
            IdentityComponent(name="camera trap", kind="item", tags=("cryptidsim", "camera-trap")),
            PortableComponent(can_pick_up=True),
            CameraTrapComponent(
                placed_by=placed_by,
                deployed_at_epoch=epoch,
                cooldown_seconds=cooldown_seconds,
            ),
        ],
    )
    if room_id is not None and world.has_entity(room_id):
        world.get_entity(room_id).add_relationship(
            Contains(mode=ContainmentMode.ROOM_CONTENT), camera.id
        )
    return camera


def _first_cryptid(world: World, room: Entity) -> Entity | None:
    """The lowest-id living cryptid sharing ``room`` (the rig's subject), or ``None``."""
    candidates: list[Entity] = []
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if not entity.has_component(CryptidComponent) or entity.has_component(DeadComponent):
            continue
        candidates.append(entity)
    candidates.sort(key=lambda e: str(e.id))
    return candidates[0] if candidates else None


class CameraTrapConsequence:
    """Snap a still whenever a set rig shares a concealing room with an elusive creature."""

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        cameras = sorted(
            world.query().with_all([CameraTrapComponent]).execute_entities(),
            key=lambda e: str(e.id),
        )
        for camera_entity in cameras:
            event = self._maybe_capture(world, camera_entity, epoch)
            if event is not None:
                events.append(event)
        return events

    def _maybe_capture(self, world: World, camera_entity: Entity, epoch: int):
        rig = camera_entity.get_component(CameraTrapComponent)
        if rig.last_capture_epoch >= 0 and epoch - rig.last_capture_epoch < rig.cooldown_seconds:
            return None
        room = room_of(world, camera_entity.id)
        if room is None or not is_concealing(world, room):
            return None
        cryptid = _first_cryptid(world, room)
        if cryptid is None:
            return None
        details = cryptid.get_component(CryptidComponent)
        investigator_id = parse_entity_id(rig.placed_by)
        clarity = sighting_clarity(
            str(camera_entity.id),
            str(cryptid.id),
            epoch,
            elusiveness=details.elusiveness,
            light_level=room_light_level(room),
            bonus=environment_clarity_bonus(world, investigator_id, cryptid, room),
        )
        clear = is_clear(clarity)
        spawn_entity(
            world,
            [
                SightingComponent(
                    cryptid_id=str(cryptid.id),
                    cryptid_name=details.name,
                    investigator_id=rig.placed_by,
                    clarity=clarity,
                    recorded_at_epoch=epoch,
                    clear=clear,
                )
            ],
        )
        if rig.placed_by:
            record_sighting(
                world,
                investigator_id=rig.placed_by,
                cryptid_id=str(cryptid.id),
                cryptid_name=details.name,
                clarity=clarity,
                clear=clear,
            )
        replace_component(
            camera_entity,
            replace(rig, last_capture_epoch=epoch, captures=rig.captures + 1),
        )
        return CameraTrapCapturedEvent(
            **event_base(
                epoch,
                default_visibility=EventVisibility.ROOM,
                actor_id=str(camera_entity.id),
                room_id=str(room.id),
                target_ids=(str(cryptid.id),),
                camera_id=str(camera_entity.id),
                cryptid_id=str(cryptid.id),
                cryptid_name=details.name,
                investigator_id=rig.placed_by,
                clarity=clarity,
                clear=clear,
            )
        )


class SetCameraTrapHandler:
    """Deploy a camera trap in the room you occupy to watch for elusive creatures."""

    command_type = "set-camera-trap"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        room = room_of(ctx.world, character_id)
        if room is None:
            return rejected("you have nowhere to set a camera trap")
        camera = spawn_camera_trap(
            ctx.world,
            room_id=room.id,
            placed_by=str(character_id),
            epoch=ctx.epoch,
        )
        # Chasing renown is a persona goal an investigator picks up the moment they set traps.
        aspire_to_renown(character)
        return ok(
            CameraTrapSetEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id),
                    target_ids=(str(camera.id),),
                    camera_id=str(camera.id),
                )
            )
        )


SET_CAMERA_TRAP_DEF = ActionDefinition(
    command_type="set-camera-trap",
    title="Set camera trap",
    description="Deploy a camera trap in your room to catch an elusive creature on film.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.EXTENDED),
    arguments={},
)

CAMERA_TRAP_ACTION_DEFINITIONS = (SET_CAMERA_TRAP_DEF,)
CAMERA_TRAP_ACTION_HANDLERS = (SetCameraTrapHandler,)


def install_camera_traps(actor) -> None:
    """Register the passive camera-trap capture consequence (a ``service_factories`` entry)."""
    actor.register_consequence(CameraTrapConsequence())


__all__ = [
    "CAMERA_TRAP_ACTION_DEFINITIONS",
    "CAMERA_TRAP_ACTION_HANDLERS",
    "DEFAULT_COOLDOWN_SECONDS",
    "SECONDS_PER_HOUR",
    "SET_CAMERA_TRAP_DEF",
    "CameraTrapCapturedEvent",
    "CameraTrapComponent",
    "CameraTrapConsequence",
    "CameraTrapSetEvent",
    "SetCameraTrapHandler",
    "install_camera_traps",
    "spawn_camera_trap",
]
