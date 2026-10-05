from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any


def canonical_json(value: Any) -> str:
    """Serialize a value deterministically for identity and hashing."""
    def normalize(item: Any) -> Any:
        if isinstance(item, Enum):
            return item.value
        if hasattr(item, "model_dump"):
            return normalize(item.model_dump(mode="json"))
        if isinstance(item, Mapping):
            return {str(k): normalize(v) for k, v in sorted(item.items(), key=lambda kv: str(kv[0]))}
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        if isinstance(item, set):
            return sorted((normalize(v) for v in item), key=lambda v: json.dumps(v, sort_keys=True))
        return item
    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s:/.-]+", re.UNICODE)


def canonicalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = _PUNCT_RE.sub(" ", normalized)
    normalized = _SPACE_RE.sub(" ", normalized)
    return normalized.strip()


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def deterministic_id(namespace: str, *parts: object, length: int = 32) -> str:
    if not namespace:
        raise ValueError("namespace must be non-empty")
    material = {"namespace": namespace, "parts": parts}
    return f"{namespace}:{sha256_hex(material)[:length]}"


def content_digest(value: object) -> str:
    return sha256_hex(value)
