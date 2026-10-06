from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any


def canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "model_dump"):
        return canonicalize(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): canonicalize(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [canonicalize(v) for v in value]
    if isinstance(value, set):
        return sorted(
            (canonicalize(v) for v in value),
            key=lambda v: json.dumps(v, sort_keys=True, default=str),
        )
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def deterministic_id(kind: str, *parts: object, length: int = 32) -> str:
    if not kind.strip():
        raise ValueError("kind must not be blank")
    return f"{kind}:{sha256_hex({'kind': kind, 'parts': parts})[:length]}"
