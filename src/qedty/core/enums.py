from __future__ import annotations

from enum import StrEnum
from typing import Self


class StableStrEnum(StrEnum):
    """String enum whose values are treated as wire-level stable tokens."""

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """Return values in declaration order for deterministic schemas."""
        return tuple(member.value for member in cls)

    @classmethod
    def from_value(cls, value: str) -> Self:
        """Parse a wire token and preserve the enum's type in the result."""
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"invalid {cls.__name__} value: {value!r}") from exc


class EpistemicStatus(StableStrEnum):
    """Epistemic strength of a QEDTY statement or modeled result."""

    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    MODELED = "modeled"
    COUNTERFACTUAL = "counterfactual"
    UNKNOWN = "unknown"


class EntityType(StableStrEnum):
    SATELLITE = "satellite"
    GROUND_STATION = "ground_station"
    GNSS_SERVICE = "gnss_service"
    FACILITY = "facility"
    PORT = "port"
    AIRPORT = "airport"
    ROAD = "road"
    RAIL = "rail"
    POWER_PLANT = "power_plant"
    POWER_GRID = "power_grid"
    TELECOM_NETWORK = "telecom_network"
    DATA_CENTER = "data_center"
    BANK = "bank"
    PAYMENT_SYSTEM = "payment_system"
    MARKET = "market"
    COMPANY = "company"
    GOVERNMENT = "government"
    REGION = "region"
    COUNTRY = "country"
    SECTOR = "sector"
    SERVICE = "service"
    CAPABILITY = "capability"
    FLOW = "flow"
    OTHER = "other"


class RelationshipType(StableStrEnum):
    PROVIDES = "provides"
    DEPENDS_ON = "depends_on"
    SUPPORTS = "supports"
    CONNECTS_TO = "connects_to"
    LOCATED_IN = "located_in"
    OWNED_BY = "owned_by"
    OPERATED_BY = "operated_by"
    CONTROLLED_BY = "controlled_by"
    SUPPLIES = "supplies"
    USES = "uses"
    TRANSPORTS = "transports"
    POWERS = "powers"
    TIMES = "times"
    ENABLES = "enables"
    BACKS_UP = "backs_up"
    SUBSTITUTES = "substitutes"
    MEMBER_OF = "member_of"
    AFFECTS = "affects"
    SERVES = "serves"
    EXPOSES = "exposes"
    DERIVED_FROM = "derived_from"
    OTHER = "other"


class EventType(StableStrEnum):
    OUTAGE = "outage"
    DEGRADATION = "degradation"
    CAPACITY_LOSS = "capacity_loss"
    PHYSICAL_DAMAGE = "physical_damage"
    SUPPLY_DISRUPTION = "supply_disruption"
    CYBER = "cyber"
    GEOPOLITICAL = "geopolitical"
    NATURAL_HAZARD = "natural_hazard"
    SPACE_WEATHER = "space_weather"
    GNSS_INTERFERENCE = "gnss_interference"
    MARKET_SHOCK = "market_shock"
    POLICY_CHANGE = "policy_change"
    OTHER = "other"


class InterventionType(StableStrEnum):
    REDUNDANCY = "redundancy"
    HARDENING = "hardening"
    DIVERSIFICATION = "diversification"
    STOCKPILE = "stockpile"
    BACKUP_SERVICE = "backup_service"
    ROUTING_CHANGE = "routing_change"
    DEMAND_RESPONSE = "demand_response"
    CAPACITY_EXPANSION = "capacity_expansion"
    SUBSTITUTION = "substitution"
    OTHER = "other"


class RunStatus(StableStrEnum):
    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class EvidenceStatus(StableStrEnum):
    ACQUIRED = "acquired"
    NORMALIZED = "normalized"
    VALIDATED = "validated"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class SourceStatus(StableStrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DEPRECATED = "deprecated"


class ClaimStatus(StableStrEnum):
    PROPOSED = "proposed"
    SUPPORTED = "supported"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ContinuityStatus(StableStrEnum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    DISRUPTED = "disrupted"
    FAILED = "failed"
    RECOVERING = "recovering"


class ImpactType(StableStrEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    INDUCED = "induced"
    SYSTEMIC = "systemic"
    AVOIDED = "avoided"


class UncertaintyMethod(StableStrEnum):
    INTERVAL = "interval"
    ANALYTICAL = "analytical"
    MONTE_CARLO = "monte_carlo"
    SCENARIO_ENVELOPE = "scenario_envelope"
    CONFORMAL = "conformal"
    EMPIRICAL = "empirical"
    EXPERT = "expert"


class TimeScale(StableStrEnum):
    UTC = "UTC"
    TAI = "TAI"
    TT = "TT"
    UT1 = "UT1"


class CoordinateReferenceSystem(StableStrEnum):
    WGS84_2D = "EPSG:4326"
    WGS84_3D = "EPSG:4979"
    WGS84_ECEF = "EPSG:4978"
    OGC_CRS84 = "OGC:CRS84"


class UnitSystem(StableStrEnum):
    SI = "SI"
    UCUM = "UCUM"
    QEDTY = "QEDTY"
