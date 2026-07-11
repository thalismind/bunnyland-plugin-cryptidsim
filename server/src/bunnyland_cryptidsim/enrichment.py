"""Declarative rare-cryptid generation enrichment."""

from bunnyland.core.generation import GenerationDelta, GenerationRequest

from .components import CryptidComponent

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
VERY_ELUSIVE_TERMS = ("elusive", "unconfirmed", "mythical", "legendary")
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


class CryptidGenerationEnricher:
    capabilities: tuple[str, ...] = ()

    def enrich(self, request: GenerationRequest) -> GenerationDelta:
        if request.entity_kind != "character" or any(
            isinstance(item, CryptidComponent)
            for item in request.context.get("base_components", ())
        ):
            return GenerationDelta()
        text = " ".join((request.source_key, request.description, *request.tags)).casefold()
        if not any(term in text for term in CRYPTID_TERMS):
            return GenerationDelta()
        habitat = next((habitat for term, habitat in _HABITAT_TERMS if term in text), "wilderness")
        elusiveness = 0.85 if any(term in text for term in VERY_ELUSIVE_TERMS) else 0.6
        return GenerationDelta(
            components=(
                CryptidComponent(
                    name=request.source_key or "unknown cryptid",
                    elusiveness=elusiveness,
                    habitat=habitat,
                ),
            )
        )


__all__ = ["CRYPTID_TERMS", "CryptidGenerationEnricher", "VERY_ELUSIVE_TERMS"]
