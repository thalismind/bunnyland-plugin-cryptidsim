"""Credibility and fame: confirmed cryptids make (or break) a cryptozoologist's name.

Confirming a cryptid is the payoff of the whole loop. When it happens this module:

- bumps the investigator's :class:`CredibilityComponent` (a running fame score + tally),
- **publishes** their standing onto the shared, core ``ReputationComponent`` (the connector
  every pack reads) so a museum curator or gossip sheet can recognise them,
- turns everyone who witnessed it into a **believer** — a warm, trusting core ``SocialBond``
  *toward* the investigator (believer/skeptic standing is affective, so it rides the core
  bond edge, never a bespoke list), and
- routes an illustrated "blurry photo" moment into world **history** so imagegen can render it.

The flip side is the ``doubt-cryptid`` verb: a bystander who thinks a still-*unconfirmed* case
is bunk becomes a **skeptic** — a distrustful, resentful bond toward the claimant. Chasing
renown is a persona **goal** (``become a renowned cryptozoologist``) an investigator picks up
the moment they start setting traps.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import contents
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
from bunnyland.core.components import CharacterComponent
from bunnyland.core.ecs import parse_entity_id, replace_component
from bunnyland.core.events import DomainEvent, EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_entity,
)
from bunnyland.imagegen.components import ImageRequestComponent
from bunnyland.imagegen.spec import ImagePurpose
from bunnyland.mechanics.history import record_world_history
from bunnyland.mechanics.lifesim import ReputationComponent
from bunnyland.mechanics.persona import GoalComponent
from bunnyland.mechanics.social import adjust_bond, bond_between
from bunnyland.prompts import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .cases import find_case
from .components import CryptidCaseComponent
from .events import CryptidConfirmedEvent
from .spatial import room_of

#: The persona goal a cryptozoologist chases.
RENOWN_GOAL = "become a renowned cryptozoologist"

#: Fame added to an investigator's credibility per confirmed cryptid.
CREDIBILITY_PER_CONFIRMATION = 10.0

#: Bond deltas applied when a witness becomes a believer / a skeptic.
BELIEVER_DELTAS = {"affinity": 0.15, "trust": 0.12}
SKEPTIC_DELTAS = {"trust": -0.12, "resentment": 0.12}


@dataclass(frozen=True)
class CredibilityComponent(Component):
    """A cryptozoologist's standing: fame ``score`` and their confirmed-cryptid tally."""

    score: float = 0.0
    confirmations: int = 0
    renowned: bool = False

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if not ctx.is_first_person or self.confirmations == 0:
            return ()
        tail = " You are a renowned cryptozoologist." if self.renowned else ""
        plural = "cryptid" if self.confirmations == 1 else "cryptids"
        return (
            f"You have confirmed {self.confirmations} {plural} "
            f"(credibility {self.score:g}).{tail}",
        )


class CryptidDoubtedEvent(DomainEvent):
    """A skeptic publicly disputed an investigator's unconfirmed case."""

    skeptic_id: str
    investigator_id: str
    cryptid_id: str


#: A cryptozoologist is "renowned" once they clear this many confirmations.
RENOWN_THRESHOLD = 3


def aspire_to_renown(character: Entity) -> None:
    """Give a character the renowned-cryptozoologist goal (idempotent, merges with others)."""
    if character.has_component(GoalComponent):
        goals = character.get_component(GoalComponent).active_goals
        if RENOWN_GOAL in goals:
            return
        replace_component(
            character, GoalComponent(active_goals=(*goals, RENOWN_GOAL))
        )
    else:
        character.add_component(GoalComponent(active_goals=(RENOWN_GOAL,)))


def _publish_reputation(character: Entity, score: float) -> None:
    """Fold cryptozoology fame into the shared, core ``ReputationComponent``."""
    if character.has_component(ReputationComponent):
        current = character.get_component(ReputationComponent)
        known_for = tuple(dict.fromkeys((*current.known_for, "cryptozoology")))
        replace_component(
            character, replace(current, score=current.score + score, known_for=known_for)
        )
    else:
        character.add_component(ReputationComponent(score=score, known_for=("cryptozoology",)))


def _award_credibility(character: Entity) -> CredibilityComponent:
    current = (
        character.get_component(CredibilityComponent)
        if character.has_component(CredibilityComponent)
        else CredibilityComponent()
    )
    confirmations = current.confirmations + 1
    updated = CredibilityComponent(
        score=current.score + CREDIBILITY_PER_CONFIRMATION,
        confirmations=confirmations,
        renowned=confirmations >= RENOWN_THRESHOLD,
    )
    if character.has_component(CredibilityComponent):
        replace_component(character, updated)
    else:
        character.add_component(updated)
    return updated


def _make_believers(world: World, investigator: Entity) -> list[str]:
    """Every other character sharing the investigator's room becomes a believer."""
    room = room_of(world, investigator.id)
    believers: list[str] = []
    if room is None:
        return believers
    for member_id in contents(room):
        if member_id == investigator.id or not world.has_entity(member_id):
            continue
        member = world.get_entity(member_id)
        if not member.has_component(CharacterComponent):
            continue
        adjust_bond(world, member_id, investigator.id, BELIEVER_DELTAS)
        believers.append(str(member_id))
    return believers


def record_confirmation_photo(world: World, event: CryptidConfirmedEvent) -> None:
    """File the confirmation into world **history** and request its **imagegen** photo.

    The blurry photo that finally proves the creature real is the headline moment: it lands a
    durable history record (deduped on the source event) and stamps the confirmed cryptid with
    an :class:`ImageRequestComponent` so core imagegen renders the still a museum wing or a
    gossip sheet can display.
    """
    cryptid_id = parse_entity_id(event.cryptid_id)
    location_id = ""
    cryptid = None
    if cryptid_id is not None and world.has_entity(cryptid_id):
        cryptid = world.get_entity(cryptid_id)
        room = room_of(world, cryptid_id)
        location_id = str(room.id) if room is not None else ""
    record_world_history(
        world,
        summary=f"The {event.cryptid_name} was confirmed real — the blurry photo that proves it.",
        source_event_id=event.event_id,
        event_type="cryptidsim.confirmation",
        created_at_epoch=event.world_epoch,
        location_id=location_id,
        actor_ids=(event.investigator_id,),
        target_ids=(event.cryptid_id,),
        tags=("cryptid", "confirmation", "cryptozoology"),
        salience=2.0,
    )
    if cryptid is not None and not cryptid.has_component(ImageRequestComponent):
        cryptid.add_component(
            ImageRequestComponent(
                purpose=ImagePurpose.ENTITY.value,
                requested_at_epoch=event.world_epoch,
                requested_by=event.investigator_id,
            )
        )


class CryptidRenownReactor:
    """React to confirmations: credibility, reputation, believers, and a history photo."""

    def __init__(self, world: World, *, on_confirmed=()):
        self.world = world
        # Extra sync callbacks (history/imagegen, museum publish) run in registration order.
        self._on_confirmed = tuple(on_confirmed)

    def subscribe(self, bus) -> None:
        bus.subscribe(CryptidConfirmedEvent, self._on_confirmed_event)

    def _on_confirmed_event(self, event: CryptidConfirmedEvent) -> None:
        investigator_id = parse_entity_id(event.investigator_id)
        if investigator_id is None or not self.world.has_entity(investigator_id):
            return
        investigator = self.world.get_entity(investigator_id)
        _award_credibility(investigator)
        _publish_reputation(investigator, event.reputation)
        aspire_to_renown(investigator)
        _make_believers(self.world, investigator)
        for hook in self._on_confirmed:
            hook(self.world, event)


class DoubtCryptidHandler:
    """Publicly dispute a claimant's still-unconfirmed cryptid; become a skeptic."""

    command_type = "doubt-cryptid"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        skeptic_id, _skeptic, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        investigator_id, investigator, rejection = require_entity(
            ctx,
            command.payload.get("investigator_id"),
            invalid_reason="invalid investigator id",
            missing_reason="investigator does not exist",
        )
        if rejection is not None:
            return rejection
        if not investigator.has_component(CharacterComponent):
            return rejected("that is not an investigator")
        cryptid_id = str(command.payload.get("cryptid_id", "")).strip()
        case_entity = find_case(ctx.world, str(investigator_id), cryptid_id)
        if case_entity is None:
            return rejected("they hold no such case to dispute")
        case = case_entity.get_component(CryptidCaseComponent)
        if case.confirmed:
            return rejected("the evidence is undeniable; there is nothing to dispute")
        adjust_bond(ctx.world, skeptic_id, investigator_id, SKEPTIC_DELTAS)
        return ok(
            CryptidDoubtedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(skeptic_id),
                    target_ids=(str(investigator_id),),
                    skeptic_id=str(skeptic_id),
                    investigator_id=str(investigator_id),
                    cryptid_id=cryptid_id,
                )
            )
        )


def standing_toward(world: World, viewer_id, investigator_id) -> str | None:
    """Classify a viewer's standing toward a cryptozoologist as believer/skeptic/None."""
    bond = bond_between(world, viewer_id, investigator_id)
    if bond is None:
        return None
    if bond.resentment >= 0.1 and bond.trust < 0.0:
        return "skeptic"
    if bond.affinity >= 0.1 and bond.trust >= 0.1:
        return "believer"
    return None


DOUBT_CRYPTID_DEF = ActionDefinition(
    command_type="doubt-cryptid",
    title="Doubt cryptid",
    description="Publicly dispute a claimant's unconfirmed cryptid case.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "investigator_id": ActionArgument(
            title="Claimant",
            description="The investigator whose case you dispute.",
            kind="entity",
            required=True,
        ),
        "cryptid_id": ActionArgument(
            title="Cryptid",
            description="The disputed cryptid's id.",
            kind="text",
            required=True,
        ),
    },
)

CREDIBILITY_ACTION_DEFINITIONS = (DOUBT_CRYPTID_DEF,)
CREDIBILITY_ACTION_HANDLERS = (DoubtCryptidHandler,)


def credibility_fragments(world: World, character: Entity) -> list[str]:
    """Prompt lines describing the character's cryptozoology fame."""
    if character is None or not character.has_component(CredibilityComponent):
        return []
    ctx = ComponentPromptContext.for_entity(world, character)
    return sorted(character.get_component(CredibilityComponent).prompt_fragments(ctx))


def install_credibility(actor) -> None:
    """Wire the renown reactor with the history/imagegen photo hook (a ``service_factories``)."""
    reactor = CryptidRenownReactor(actor.world, on_confirmed=(record_confirmation_photo,))
    reactor.subscribe(actor.bus)


__all__ = [
    "BELIEVER_DELTAS",
    "CREDIBILITY_ACTION_DEFINITIONS",
    "CREDIBILITY_ACTION_HANDLERS",
    "CREDIBILITY_PER_CONFIRMATION",
    "DOUBT_CRYPTID_DEF",
    "RENOWN_GOAL",
    "RENOWN_THRESHOLD",
    "SKEPTIC_DELTAS",
    "CredibilityComponent",
    "CryptidDoubtedEvent",
    "CryptidRenownReactor",
    "DoubtCryptidHandler",
    "aspire_to_renown",
    "credibility_fragments",
    "install_credibility",
    "record_confirmation_photo",
    "standing_toward",
]
