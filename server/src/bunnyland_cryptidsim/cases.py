"""Case files and confirmation.

Sightings accumulate into a :class:`~bunnyland_cryptidsim.components.CryptidCaseComponent`
dossier — one dedicated case entity per ``(investigator, cryptid)`` pair. Each new sighting
bumps the running totals; a *high-clarity* look also bumps ``clear_count``.

A per-tick :class:`CryptidConfirmationConsequence` watches those dossiers: once a case has
gathered enough clear sightings it flips to ``confirmed``, marks the cryptid entity with
:class:`~bunnyland_cryptidsim.components.ConfirmedCryptidComponent` (the discovery reward),
and emits a :class:`~bunnyland_cryptidsim.events.CryptidConfirmedEvent` carrying a reputation
payout. Low-clarity cases stay open as "unconfirmed reports."
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import spawn_entity
from bunnyland.core.ecs import parse_entity_id, replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from relics import Entity, World

from .components import ConfirmedCryptidComponent, CryptidCaseComponent
from .events import CryptidConfirmedEvent

#: Clear sightings needed before a case confirms the cryptid.
CONFIRM_CLEAR_SIGHTINGS = 2

#: Reputation/discovery payout granted when a cryptid is confirmed.
CONFIRM_REPUTATION = 10.0


def find_case(world: World, investigator_id: str, cryptid_id: str) -> Entity | None:
    """Return the open case an investigator holds on a cryptid, or ``None``."""
    for entity in world.query().with_all([CryptidCaseComponent]).execute_entities():
        case = entity.get_component(CryptidCaseComponent)
        if case.investigator_id == investigator_id and case.cryptid_id == cryptid_id:
            return entity
    return None


def record_sighting(
    world: World,
    *,
    investigator_id: str,
    cryptid_id: str,
    cryptid_name: str,
    clarity: float,
    clear: bool,
) -> Entity:
    """Fold one sighting into the matching case, creating the dossier if it is new."""
    case_entity = find_case(world, investigator_id, cryptid_id)
    if case_entity is None:
        return spawn_entity(
            world,
            [
                CryptidCaseComponent(
                    investigator_id=investigator_id,
                    cryptid_id=cryptid_id,
                    cryptid_name=cryptid_name,
                    sighting_count=1,
                    clear_count=1 if clear else 0,
                    best_clarity=clarity,
                )
            ],
        )
    case = case_entity.get_component(CryptidCaseComponent)
    replace_component(
        case_entity,
        replace(
            case,
            sighting_count=case.sighting_count + 1,
            clear_count=case.clear_count + (1 if clear else 0),
            best_clarity=max(case.best_clarity, clarity),
        ),
    )
    return case_entity


class CryptidConfirmationConsequence:
    """Confirm any case that has gathered enough clear sightings each tick."""

    def __init__(
        self,
        *,
        required_clear: int = CONFIRM_CLEAR_SIGHTINGS,
        reputation: float = CONFIRM_REPUTATION,
    ):
        self.required_clear = required_clear
        self.reputation = reputation

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        for entity in list(world.query().with_all([CryptidCaseComponent]).execute_entities()):
            case = entity.get_component(CryptidCaseComponent)
            if case.confirmed or case.clear_count < self.required_clear:
                continue
            replace_component(entity, replace(case, confirmed=True))
            self._mark_cryptid_confirmed(world, case.cryptid_id, epoch)
            events.append(
                CryptidConfirmedEvent(
                    **event_base(
                        epoch,
                        default_visibility=EventVisibility.PRIVATE,
                        actor_id=case.investigator_id,
                        target_ids=(case.cryptid_id,),
                        cryptid_id=case.cryptid_id,
                        cryptid_name=case.cryptid_name,
                        investigator_id=case.investigator_id,
                        clear_count=case.clear_count,
                        reputation=self.reputation,
                    )
                )
            )
        return events

    @staticmethod
    def _mark_cryptid_confirmed(world: World, cryptid_id: str, epoch: int) -> None:
        parsed = parse_entity_id(cryptid_id)
        if parsed is None or not world.has_entity(parsed):
            return
        cryptid = world.get_entity(parsed)
        if not cryptid.has_component(ConfirmedCryptidComponent):
            replace_component(cryptid, ConfirmedCryptidComponent(confirmed_at_epoch=epoch))


__all__ = [
    "CONFIRM_CLEAR_SIGHTINGS",
    "CONFIRM_REPUTATION",
    "CryptidConfirmationConsequence",
    "find_case",
    "record_sighting",
]
