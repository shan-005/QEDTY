from __future__ import annotations

from dataclasses import dataclass
from typing import Final

SCHEMA_VERSION: Final[str] = "1.0.0"
PRODUCT_VERSION: Final[str] = "0.1a0"
WORLD_MODEL_SCHEMA: Final[str] = "qedty-world-model@1.0.0"

CORE_CONTRACT_VERSION: Final[str] = "1.0.0"
CORE_IMPLEMENTATION_VERSION: Final[str] = "1.0.0"
CANONICAL_JSON_PROFILE: Final[str] = "qedty-canonical-json@1"
JCS_PROFILE: Final[str] = "RFC8785"
TIME_PROFILE: Final[str] = "qedty-utc-time@1"
UNIT_PROFILE: Final[str] = "qedty-units@1;UCUM=2.2;BIPM-SI-Brochure=9e-v4.01"
GEOMETRY_PROFILE: Final[str] = "WGS84/EPSG:4326+4979+4978"
IDENTITY_HASH_ALGORITHM: Final[str] = "SHA-256"
ARROW_PROFILE: Final[str] = "qedty-arrow@1;Arrow-Format=1.5"
PROTO_PROFILE: Final[str] = "qedty-proto@1;proto3"
JSON_SCHEMA_PROFILE: Final[str] = "qedty-json-schema@1;draft=2020-12"
CONFORMANCE_PROFILE: Final[str] = "qedty-core-conformance@1"


@dataclass(frozen=True, slots=True)
class CoreVersion:
    """Version tuple persisted independently from the product release version."""

    product_version: str = PRODUCT_VERSION
    core_contract_version: str = CORE_CONTRACT_VERSION
    core_implementation_version: str = CORE_IMPLEMENTATION_VERSION
    world_model_schema: str = WORLD_MODEL_SCHEMA
    canonical_json_profile: str = CANONICAL_JSON_PROFILE
    jcs_profile: str = JCS_PROFILE
    time_profile: str = TIME_PROFILE
    unit_profile: str = UNIT_PROFILE
    geometry_profile: str = GEOMETRY_PROFILE
    arrow_profile: str = ARROW_PROFILE
    proto_profile: str = PROTO_PROFILE
    json_schema_profile: str = JSON_SCHEMA_PROFILE
    conformance_profile: str = CONFORMANCE_PROFILE
    identity_hash_algorithm: str = IDENTITY_HASH_ALGORITHM


CORE_VERSION = CoreVersion()
