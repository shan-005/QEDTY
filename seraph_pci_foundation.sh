#!/usr/bin/env bash
set -euo pipefail

cd ~/seraph

EXPECTED_BRANCH="seraph-pci-migration"

if [[ "$(git branch --show-current)" != "$EXPECTED_BRANCH" ]]; then
  echo "ERROR: expected branch '$EXPECTED_BRANCH', got '$(git branch --show-current)'"
  exit 1
fi

if [[ ! -d "src/seraph/guard" ]]; then
  echo "ERROR: old Seraph Guard tree not found; aborting."
  exit 1
fi

echo "Creating non-destructive Seraph PCI foundation..."

mkdir -p \
  src/seraph/pci/core \
  src/seraph/pci/evidence \
  src/seraph/pci/entities \
  src/seraph/pci/graph \
  src/seraph/pci/sources/space \
  src/seraph/pci/sources/earth \
  src/seraph/pci/sources/economy \
  src/seraph/pci/shocks \
  src/seraph/pci/simulation \
  src/seraph/pci/continuity \
  src/seraph/pci/economics \
  src/seraph/pci/counterfactual \
  src/seraph/pci/optimization \
  src/seraph/pci/uncertainty \
  src/seraph/pci/models \
  src/seraph/pci/storage \
  src/seraph/pci/api \
  src/seraph/pci/cli \
  src/seraph/pci/governance \
  schemas \
  configs \
  benchmarks \
  data/sample \
  docs \
  tests/pci

find src/seraph/pci -type d -exec touch {}/__init__.py \;

cat > src/seraph/pci/__init__.py <<'PY'
"""Seraph Planetary Continuity Intelligence.

The PCI package is the new domain core. The legacy ``seraph.guard`` package
remains untouched during migration and is preserved for historical recovery.
"""

from .core.enums import EpistemicStatus
from .core.types import (
    ContinuityWindow,
    EntityRef,
    Observation,
    Relationship,
    ScenarioRef,
)

__all__ = [
    "ContinuityWindow",
    "EntityRef",
    "EpistemicStatus",
    "Observation",
    "Relationship",
    "ScenarioRef",
]
PY

cat > src/seraph/pci/core/enums.py <<'PY'
from __future__ import annotations

from enum import StrEnum


class EpistemicStatus(StrEnum):
    """What kind of claim a Seraph datum represents."""

    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    MODELED = "MODELED"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    UNKNOWN = "UNKNOWN"


class EntityType(StrEnum):
    SATELLITE = "SATELLITE"
    CONSTELLATION = "CONSTELLATION"
    GROUND_STATION = "GROUND_STATION"
    SIGNAL = "SIGNAL"
    SERVICE = "SERVICE"
    FACILITY = "FACILITY"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    COMPANY = "COMPANY"
    SUPPLIER = "SUPPLIER"
    PRODUCT = "PRODUCT"
    PORT = "PORT"
    AIRPORT = "AIRPORT"
    ROAD = "ROAD"
    RAIL = "RAIL"
    POWER_PLANT = "POWER_PLANT"
    POWER_GRID = "POWER_GRID"
    DATA_CENTER = "DATA_CENTER"
    TELECOM_NETWORK = "TELECOM_NETWORK"
    FINANCIAL_INSTITUTION = "FINANCIAL_INSTITUTION"
    COMMODITY = "COMMODITY"
    SECTOR = "SECTOR"
    REGION = "REGION"
    COUNTRY = "COUNTRY"
    ECONOMIC_FUNCTION = "ECONOMIC_FUNCTION"
    OTHER = "OTHER"


class RelationshipType(StrEnum):
    PROVIDES = "PROVIDES"
    SUPPORTS = "SUPPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    OPERATED_BY = "OPERATED_BY"
    OWNED_BY = "OWNED_BY"
    SUPPLIES = "SUPPLIES"
    LOCATED_AT = "LOCATED_AT"
    CONNECTS_TO = "CONNECTS_TO"
    USES = "USES"
    ENABLES = "ENABLES"
    ALTERNATIVE_TO = "ALTERNATIVE_TO"
    REPLACED_BY = "REPLACED_BY"
    AFFECTS = "AFFECTS"
    PART_OF = "PART_OF"
    OTHER = "OTHER"


class ShockType(StrEnum):
    GNSS_OUTAGE = "GNSS_OUTAGE"
    SATELLITE_LOSS = "SATELLITE_LOSS"
    CONSTELLATION_DEGRADATION = "CONSTELLATION_DEGRADATION"
    GROUND_STATION_OUTAGE = "GROUND_STATION_OUTAGE"
    SPACE_WEATHER = "SPACE_WEATHER"
    JAMMING = "JAMMING"
    SPOOFING = "SPOOFING"
    ORBITAL_DEBRIS = "ORBITAL_DEBRIS"
    POWER_OUTAGE = "POWER_OUTAGE"
    TELECOM_OUTAGE = "TELECOM_OUTAGE"
    PORT_CLOSURE = "PORT_CLOSURE"
    SUPPLIER_LOSS = "SUPPLIER_LOSS"
    EXPORT_RESTRICTION = "EXPORT_RESTRICTION"
    WEATHER_EVENT = "WEATHER_EVENT"
    GEOPOLITICAL_EVENT = "GEOPOLITICAL_EVENT"
    OTHER = "OTHER"


class InterventionType(StrEnum):
    REDUNDANCY = "REDUNDANCY"
    BACKUP_SERVICE = "BACKUP_SERVICE"
    DIVERSIFICATION = "DIVERSIFICATION"
    REROUTING = "REROUTING"
    INVENTORY = "INVENTORY"
    CAPACITY_EXPANSION = "CAPACITY_EXPANSION"
    HARDENING = "HARDENING"
    SUBSTITUTION = "SUBSTITUTION"
    OTHER = "OTHER"
PY

cat > src/seraph/pci/core/ids.py <<'PY'
from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_id(namespace: str, value: Any, *, length: int = 32) -> str:
    """Return a deterministic, namespace-scoped identifier."""
    if length < 8 or length > 64:
        raise ValueError("length must be between 8 and 64")

    if isinstance(value, str):
        canonical = value
    else:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )

    digest = hashlib.sha256(
        f"{namespace}:{canonical}".encode("utf-8")
    ).hexdigest()

    return f"{namespace}:{digest[:length]}"


def entity_id(entity_type: str, canonical_key: str) -> str:
    return stable_id(f"entity/{entity_type.lower()}", canonical_key)


def observation_id(source: str, payload: Any) -> str:
    return stable_id(f"observation/{source.lower()}", payload)


def relationship_id(
    source_entity: str,
    relationship: str,
    target_entity: str,
    valid_from: str | None = None,
) -> str:
    return stable_id(
        "relationship",
        {
            "source": source_entity,
            "relationship": relationship,
            "target": target_entity,
            "valid_from": valid_from,
        },
    )
PY

cat > src/seraph/pci/core/time.py <<'PY'
from __future__ import annotations

from datetime import UTC, datetime


def ensure_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC; reject naive timestamps."""
    if value.tzinfo is None:
        raise ValueError("timezone-aware datetimes are required")
    return value.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)
PY

cat > src/seraph/pci/core/units.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Quantity:
    """A numeric quantity with an explicit unit.

    PCI must never silently mix incompatible units.
    """

    value: float
    unit: str

    def __post_init__(self) -> None:
        if not self.unit.strip():
            raise ValueError("unit must not be empty")
PY

cat > src/seraph/pci/core/types.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import EpistemicStatus, RelationshipType
from .time import ensure_utc


@dataclass(frozen=True, slots=True)
class EntityRef:
    entity_id: str
    entity_type: str


@dataclass(frozen=True, slots=True)
class ScenarioRef:
    scenario_id: str
    name: str


@dataclass(frozen=True, slots=True)
class ContinuityWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        start = ensure_utc(self.start)
        end = ensure_utc(self.end)
        if end <= start:
            raise ValueError("continuity window end must be after start")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(slots=True)
class Observation:
    observation_id: str
    entity_id: str
    observed_at: datetime
    value: Any
    unit: str | None
    source: str
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    confidence: float | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.observed_at = ensure_utc(self.observed_at)

        if self.valid_from is not None:
            self.valid_from = ensure_utc(self.valid_from)
        if self.valid_to is not None:
            self.valid_to = ensure_utc(self.valid_to)

        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")

        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


@dataclass(slots=True)
class Relationship:
    relationship_id: str
    source: EntityRef
    relationship: RelationshipType
    target: EntityRef
    epistemic_status: EpistemicStatus
    confidence: float | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")

        if self.valid_from is not None:
            self.valid_from = ensure_utc(self.valid_from)
        if self.valid_to is not None:
            self.valid_to = ensure_utc(self.valid_to)

        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
PY

cat > src/seraph/pci/evidence/models.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from seraph.pci.core.enums import EpistemicStatus
from seraph.pci.core.time import ensure_utc


@dataclass(slots=True)
class EvidenceRecord:
    evidence_id: str
    source: str
    retrieved_at: datetime
    observed_at: datetime | None
    locator: str | None
    content_hash: str
    epistemic_status: EpistemicStatus
    license_ref: str | None = None
    quality_score: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.retrieved_at = ensure_utc(self.retrieved_at)
        if self.observed_at is not None:
            self.observed_at = ensure_utc(self.observed_at)

        if self.quality_score is not None and not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score must be within [0, 1]")
PY

cat > src/seraph/pci/evidence/provenance.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Provenance:
    """Minimal provenance envelope; designed to map cleanly to W3C PROV concepts."""

    source: str
    activity: str
    agent: str
    parent_evidence_ids: tuple[str, ...] = ()
    notes: str | None = None


@dataclass(slots=True)
class ProvenanceChain:
    records: list[Provenance] = field(default_factory=list)

    def add(self, record: Provenance) -> None:
        self.records.append(record)
PY

cat > src/seraph/pci/evidence/quality.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DataQuality:
    completeness: float
    freshness: float
    consistency: float
    authority: float

    def __post_init__(self) -> None:
        for name, value in (
            ("completeness", self.completeness),
            ("freshness", self.freshness),
            ("consistency", self.consistency),
            ("authority", self.authority),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")
PY

cat > src/seraph/pci/evidence/licensing.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RedistributionPolicy(StrEnum):
    INTERNAL_ONLY = "INTERNAL_ONLY"
    DERIVED_ONLY = "DERIVED_ONLY"
    REDISTRIBUTABLE = "REDISTRIBUTABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class LicensePolicy:
    license_ref: str
    redistribution: RedistributionPolicy
    attribution_required: bool = False
    notes: str | None = None
PY

cat > src/seraph/pci/entities/models.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seraph.pci.core.enums import EntityType


@dataclass(slots=True)
class Entity:
    entity_id: str
    entity_type: EntityType
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
PY

cat > src/seraph/pci/entities/resolver.py <<'PY'
from __future__ import annotations

import re

from seraph.pci.core.ids import entity_id
from seraph.pci.entities.models import Entity
from seraph.pci.core.enums import EntityType


def canonicalize_name(value: str) -> str:
    value = value.strip().casefold()
    value = re.sub(r"\s+", " ", value)
    return value


def make_entity(entity_type: EntityType, name: str) -> Entity:
    canonical = canonicalize_name(name)
    if not canonical:
        raise ValueError("entity name must not be empty")

    return Entity(
        entity_id=entity_id(entity_type.value, canonical),
        entity_type=entity_type,
        canonical_name=canonical,
    )
PY

cat > src/seraph/pci/graph/schema.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GraphSchemaVersion:
    major: int = 1
    minor: int = 0

    @property
    def value(self) -> str:
        return f"{self.major}.{self.minor}"
PY

cat > schemas/observation.schema.json <<'JSON'
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Seraph PCI Observation",
  "type": "object",
  "required": [
    "observation_id",
    "entity_id",
    "observed_at",
    "source",
    "epistemic_status"
  ],
  "properties": {
    "observation_id": {"type": "string", "minLength": 1},
    "entity_id": {"type": "string", "minLength": 1},
    "observed_at": {"type": "string", "format": "date-time"},
    "value": {},
    "unit": {"type": ["string", "null"]},
    "source": {"type": "string", "minLength": 1},
    "epistemic_status": {
      "type": "string",
      "enum": [
        "OBSERVED",
        "DERIVED",
        "INFERRED",
        "MODELED",
        "COUNTERFACTUAL",
        "UNKNOWN"
      ]
    },
    "confidence": {
      "type": ["number", "null"],
      "minimum": 0,
      "maximum": 1
    }
  },
  "additionalProperties": true
}
JSON

cat > tests/pci/test_foundation.py <<'PY'
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from seraph.pci.core.enums import (
    EntityType,
    EpistemicStatus,
    RelationshipType,
)
from seraph.pci.core.ids import entity_id, relationship_id
from seraph.pci.core.types import EntityRef, Observation, Relationship


def test_entity_ids_are_deterministic() -> None:
    assert entity_id("COMPANY", "example inc") == entity_id("COMPANY", "example inc")


def test_relationship_ids_are_deterministic() -> None:
    assert relationship_id("a", "DEPENDS_ON", "b") == relationship_id(
        "a", "DEPENDS_ON", "b"
    )


def test_observation_requires_timezone_aware_timestamp() -> None:
    observed_at = datetime(2026, 1, 1, tzinfo=UTC)
    observation = Observation(
        observation_id="obs:1",
        entity_id="entity:1",
        observed_at=observed_at,
        value=82.0,
        unit="percent",
        source="test",
    )
    assert observation.epistemic_status is EpistemicStatus.OBSERVED


def test_relationship_preserves_inference_status() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=1)

    relationship = Relationship(
        relationship_id="relationship:1",
        source=EntityRef("entity:a", EntityType.FACILITY.value),
        relationship=RelationshipType.DEPENDS_ON,
        target=EntityRef("entity:b", EntityType.SERVICE.value),
        epistemic_status=EpistemicStatus.INFERRED,
        confidence=0.86,
        valid_from=start,
        valid_to=end,
    )

    assert relationship.epistemic_status is EpistemicStatus.INFERRED
    assert relationship.valid_to == end
PY

echo
echo "Foundation created without deleting or changing legacy Guard code."
echo
echo "Run the focused tests:"
echo "  uv run pytest -q tests/pci/test_foundation.py"
echo
echo "Review:"
echo "  git status --short"
echo "  git diff --stat"
echo
echo "Do NOT delete src/seraph/guard yet."
