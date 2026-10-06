from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropagationEvidence:
    entity_id: str
    reason: str
    input_ids: tuple[str, ...]
    method: str
