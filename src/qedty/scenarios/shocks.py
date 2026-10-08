"""Shock helpers and deterministic scheduling semantics."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qedty.core.time import ensure_utc

from .models import Shock

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["Shock", "active_shocks", "normalize_shocks", "shock_targets"]


def shock_targets(shock: Shock) -> tuple[str, ...]:
    """Return deterministic target ids, defaulting to the source entity."""
    targets = set(shock.target_entity_ids)
    targets.add(shock.source_entity_id)
    targets.update(shock.capacity_multipliers)
    targets.update(patch.entity_id for patch in shock.patches)
    return tuple(sorted(targets))


def active_shocks(shocks: tuple[Shock, ...], at: datetime) -> tuple[Shock, ...]:
    instant = ensure_utc(at)
    return tuple(
        sorted((shock for shock in shocks if shock.active_at(instant)), key=lambda x: x.shock_id)
    )


def normalize_shocks(shocks: tuple[Shock, ...]) -> tuple[Shock, ...]:
    return tuple(
        sorted(
            (shock.normalized() for shock in shocks),
            key=lambda x: (x.starts_at, x.shock_id),
        )
    )


def shock_window_overlap(a: Shock, b: Shock) -> bool:
    return a.starts_at < b.ends_at and b.starts_at < a.ends_at


# Force Pydantic to resolve forward references for Shock in this module's namespace
