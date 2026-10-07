from __future__ import annotations

from importlib import import_module
from typing import Any

from .errors import InteroperabilityError
from .version import ARROW_PROFILE

ARROW_CONTRACT_NAME = "seraph.core.contract_result"


def arrow_schema() -> Any:
    """Build the canonical Arrow schema when PyArrow is installed.

    Arrow is treated as a data-plane representation. Semantic meaning is
    carried by explicit field names and schema metadata; Arrow does not replace
    the JSON Schema or Protobuf contracts.
    """
    try:
        pa: Any = import_module("pyarrow")
    except ImportError as exc:
        raise InteroperabilityError(
            "Arrow support requires the optional 'pyarrow' package",
            details={"profile": ARROW_PROFILE},
        ) from exc

    metadata = {
        b"seraph.contract": ARROW_CONTRACT_NAME.encode(),
        b"seraph.profile": ARROW_PROFILE.encode(),
        b"seraph.value.encoding": b"canonical-json",
        b"seraph.hash.algorithm": b"SHA-256",
    }
    return pa.schema(
        [
            pa.field("value_json", pa.large_string(), nullable=False),
            pa.field("epistemic_state", pa.string(), nullable=False),
            pa.field("evidence_ids", pa.list_(pa.string()), nullable=False),
            pa.field("provenance_ids", pa.list_(pa.string()), nullable=False),
            pa.field("assumptions", pa.list_(pa.string()), nullable=False),
            pa.field("model_id", pa.string(), nullable=True),
            pa.field("model_version", pa.string(), nullable=True),
            pa.field("valid_at", pa.timestamp("us", tz="UTC"), nullable=True),
            pa.field("uncertainty_json", pa.large_string(), nullable=True),
            pa.field("metadata_json", pa.large_string(), nullable=False),
        ],
        metadata=metadata,
    )
