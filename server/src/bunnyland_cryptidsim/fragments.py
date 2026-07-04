"""Field-report prompt fragments: doubt for the unconfirmed, certainty for the confirmed.

Two kinds of line feed into a character's prompt:

- **Ambient** — a cryptid sharing the character's room reads as an eerie, hedged glimpse
  while it is still unconfirmed ("something large moves beyond the treeline — you can't be
  sure"), and only reads definitively once a case has confirmed it.
- **Dossier** — the character's own open cases surface as either hedged "unconfirmed
  reports" or a confirmed find, so an investigator can see their progress in the prompt.

Unconfirmed evidence always hedges; confirmation is what earns a plain, certain sentence.
"""

from __future__ import annotations

from bunnyland.core.ecs import contents
from relics import Entity, World

from .components import (
    ConfirmedCryptidComponent,
    CryptidCaseComponent,
    CryptidComponent,
)
from .conditions import is_concealing
from .spatial import room_of


def _ambient_line(world: World, room: Entity | None) -> list[str]:
    """Hedged-or-certain lines for cryptids currently in the room."""
    if room is None:
        return []
    lines: list[str] = []
    concealing = is_concealing(world, room)
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if not entity.has_component(CryptidComponent):
            continue
        details = entity.get_component(CryptidComponent)
        if entity.has_component(ConfirmedCryptidComponent):
            lines.append(
                f"The {details.name}, a confirmed cryptid, is here in the {details.habitat}."
            )
        elif concealing:
            lines.append(
                "Something large moves beyond the treeline — you can't be sure what it is."
            )
    return lines


def _dossier_lines(world: World, character: Entity) -> list[str]:
    """The character's own open cases, hedged until confirmed."""
    lines: list[str] = []
    investigator_id = str(character.id)
    for entity in world.query().with_all([CryptidCaseComponent]).execute_entities():
        case = entity.get_component(CryptidCaseComponent)
        if case.investigator_id != investigator_id or case.sighting_count == 0:
            continue
        if case.confirmed:
            lines.append(f"Case confirmed: the {case.cryptid_name} is real.")
        else:
            reports = "report" if case.sighting_count == 1 else "reports"
            lines.append(
                f"Unconfirmed {reports} of the {case.cryptid_name}: "
                f"{case.sighting_count} sighting(s) logged, nothing conclusive yet."
            )
    return lines


def cryptidsim_fragments(world: World, character: Entity) -> list[str]:
    """Ambient cryptid glimpses plus the character's own case dossier, sorted and unique."""
    if character is None:
        return []
    room = room_of(world, character.id)
    lines = _ambient_line(world, room) + _dossier_lines(world, character)
    return sorted(dict.fromkeys(lines))


__all__ = ["cryptidsim_fragments"]
