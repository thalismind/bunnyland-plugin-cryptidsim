"""Runtime wiring: register the per-tick confirmation consequence on a world actor."""

from __future__ import annotations

from bunnyland.core.world_actor import WorldActor

from .cases import CryptidConfirmationConsequence


def install_cryptidsim(actor: WorldActor) -> None:
    """Register the case-confirmation consequence (a ``service_factories`` entry)."""
    actor.register_consequence(CryptidConfirmationConsequence())


__all__ = ["install_cryptidsim"]
