from __future__ import annotations

from enum import StrEnum


class AssertionKind(StrEnum):
    CLASSIFICATION = "classification"
    RELATIONSHIP = "relationship"
    ATTRIBUTE = "attribute"
    MEASUREMENT = "measurement"
    OBSERVATION = "observation"
    DERIVATION = "derivation"
    HYPOTHESIS = "hypothesis"


class EntityLifecycle(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    RETIRED = "retired"
    DESTROYED = "destroyed"
    UNKNOWN = "unknown"


class ResolutionMethod(StrEnum):
    EXACT_EXTERNAL_ID = "exact_external_id"
    EXACT_NAME = "exact_name"
    ALIAS_MATCH = "alias_match"
    STRUCTURAL = "structural"
    SPATIAL = "spatial"
    COMPOSITE = "composite"
    MANUAL = "manual"
    MODEL = "model"


class ResolutionDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVIEW = "review"


class CapabilityKind(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    POWER = "power"
    COMMUNICATION = "communication"
    POSITIONING = "positioning"
    SENSING = "sensing"
    TRANSPORT = "transport"
    PROCESSING = "processing"
    OTHER = "other"


class FlowKind(StrEnum):
    MATERIAL = "material"
    ENERGY = "energy"
    DATA = "data"
    FINANCIAL = "financial"
    SERVICE = "service"
    LOGISTICS = "logistics"
    PEOPLE = "people"
    OTHER = "other"


class EventPhase(StrEnum):
    ONSET = "onset"
    ACTIVE = "active"
    RECOVERY = "recovery"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"
