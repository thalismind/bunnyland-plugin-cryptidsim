"""World-generation enrichment: seed rare cryptids sparsely into generated worlds.

Generated characters expose semantic ``tags``/``wants``/``needs`` and an intent
``description``. This hook scans that text for cryptozoological hints and, only when it finds
them, attaches a :class:`~bunnyland_cryptidsim.components.CryptidComponent` — so cryptids
stay *rare* (nothing is marked by default) without the core generator knowing this plugin
exists. Elusiveness and habitat are inferred from the same text.
"""

from __future__ import annotations

from bunnyland.core.ecs import parse_entity_id, replace_component
from bunnyland.core.events import CharacterGeneratedEvent, GeneratedEntityEvent
from bunnyland.core.world_actor import WorldActor

from .components import CryptidComponent

#: Words that flag a generated character as a candidate cryptid.
CRYPTID_TERMS = (
    "cryptid",
    "sasquatch",
    "bigfoot",
    "yeti",
    "mothman",
    "chupacabra",
    "wendigo",
    "thunderbird",
    "jackalope",
    "lake monster",
    "sea serpent",
    "elusive",
    "unconfirmed",
    "legendary beast",
    "hairy hominid",
    "mystery creature",
)

#: Extra hints that a candidate is especially hard to pin down (raises elusiveness).
VERY_ELUSIVE_TERMS = ("elusive", "unconfirmed", "mythical", "legendary")

#: Biome keyword -> habitat label, first match wins.
_HABITAT_TERMS = (
    ("swamp", "swamp"),
    ("marsh", "swamp"),
    ("bog", "swamp"),
    ("lake", "lake"),
    ("river", "lake"),
    ("mountain", "mountain"),
    ("peak", "mountain"),
    ("snow", "mountain"),
    ("desert", "desert"),
    ("cave", "cave"),
    ("forest", "forest"),
    ("wood", "forest"),
)


def _text(event: GeneratedEntityEvent) -> str:
    generation = event.generation
    return " ".join(
        (
            event.entity_kind,
            generation.description,
            *generation.tags,
            *generation.wants,
            *generation.needs,
        )
    ).casefold()


def _infer_habitat(text: str) -> str:
    for keyword, habitat in _HABITAT_TERMS:
        if keyword in text:
            return habitat
    return "wilderness"


def _infer_name(event: CharacterGeneratedEvent) -> str:
    key = (event.character_key or event.entity_key or "").strip()
    return key or "unknown cryptid"


class CryptidWorldgenHook:
    """Attach a rare :class:`CryptidComponent` to hinted generated characters."""

    def subscribe(self, actor: WorldActor) -> None:
        self._actor = actor
        actor.bus.subscribe(CharacterGeneratedEvent, self._on_character)

    def _entity(self, entity_id: str):
        parsed = parse_entity_id(entity_id)
        if parsed is None or not self._actor.world.has_entity(parsed):
            return None
        return self._actor.world.get_entity(parsed)

    def _on_character(self, event: CharacterGeneratedEvent) -> None:
        entity = self._entity(event.entity_id)
        if entity is None or entity.has_component(CryptidComponent):
            return
        text = _text(event)
        if not any(term in text for term in CRYPTID_TERMS):
            return
        elusiveness = 0.85 if any(term in text for term in VERY_ELUSIVE_TERMS) else 0.6
        replace_component(
            entity,
            CryptidComponent(
                name=_infer_name(event),
                elusiveness=elusiveness,
                habitat=_infer_habitat(text),
            ),
        )


__all__ = ["CRYPTID_TERMS", "VERY_ELUSIVE_TERMS", "CryptidWorldgenHook"]
