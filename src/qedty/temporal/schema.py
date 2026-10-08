from __future__ import annotations

from dataclasses import dataclass
from typing import Final

TEMPORAL_CONTRACT_VERSION: Final[str] = "2.0.0"
TEMPORAL_IMPLEMENTATION_VERSION: Final[str] = "2.0.0"
TEMPORAL_PROFILE: Final[str] = "qedty-temporal@2"
TEMPORAL_TIME_PROFILE: Final[str] = "ISO8601-1:2019+qedty-utc-time@1"
TEMPORAL_INTERVAL_PROFILE: Final[str] = "Allen-13+OWL-Time"
TEMPORAL_BITEMPORAL_PROFILE: Final[str] = "valid-time+transaction-time@1"
TEMPORAL_STORAGE_PROFILE: Final[str] = "half-open-range@[start,end)"
TEMPORAL_QUERY_PROFILE: Final[str] = "OGC-datetime-compatible@1"
TEMPORAL_JSON_SCHEMA_PROFILE: Final[str] = "JSON-Schema-2020-12"
TEMPORAL_PROTO_PROFILE: Final[str] = "proto3"
TEMPORAL_ARROW_PROFILE: Final[str] = "Apache-Arrow"


@dataclass(frozen=True, slots=True)
class TemporalSchemaVersion:
    contract_version: str = TEMPORAL_CONTRACT_VERSION
    implementation_version: str = TEMPORAL_IMPLEMENTATION_VERSION
    temporal_profile: str = TEMPORAL_PROFILE
    time_profile: str = TEMPORAL_TIME_PROFILE
    interval_profile: str = TEMPORAL_INTERVAL_PROFILE
    bitemporal_profile: str = TEMPORAL_BITEMPORAL_PROFILE
    storage_profile: str = TEMPORAL_STORAGE_PROFILE
    query_profile: str = TEMPORAL_QUERY_PROFILE
    json_schema_profile: str = TEMPORAL_JSON_SCHEMA_PROFILE
    proto_profile: str = TEMPORAL_PROTO_PROFILE
    arrow_profile: str = TEMPORAL_ARROW_PROFILE


TEMPORAL_SCHEMA = TemporalSchemaVersion()
