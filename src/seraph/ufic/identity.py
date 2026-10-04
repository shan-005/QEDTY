"""Deterministic identity helpers for Seraph UFIC findings and ontology nodes.

Persistent identifiers must not depend on Python's process-randomized ``hash()``.
These helpers use SHA-256 over canonical, explicitly versioned identity material.
The functions do not access the filesystem, so identifiers remain stable when the
same logical source path is represented in different working directories.
"""

from __future__ import annotations

import hashlib
import json
import posixpath

from pathlib import PurePosixPath
from typing import Any


def normalize_identity_path(file_path: object) -> str:
    """Normalize a logical source path without consulting the filesystem."""
    value = str(file_path or "").replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if not value:
        return ""
    normalized = posixpath.normpath(value)
    if normalized == ".":
        return ""
    return str(PurePosixPath(normalized))


def _to_nonnegative_int(value: object) -> int:
    try:
        coerced: Any = value or 0
        return max(0, int(coerced))
    except (TypeError, ValueError, OverflowError):
        return 0


def _digest(parts: tuple[object, ...]) -> str:
    payload = json.dumps(
        list(parts),
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def stable_ufic_finding_id(
    *,
    rule_id: object,
    file_path: object,
    line: object = 0,
    column: object = 0,
) -> str:
    """Return a deterministic UFIC finding identifier."""
    rule = str(rule_id or "").strip()
    path = normalize_identity_path(file_path)
    line_value = _to_nonnegative_int(line)
    column_value = _to_nonnegative_int(column)
    digest = _digest(("ufic-finding-v1", rule, path, line_value, column_value))
    return f"ufic:{rule}:{digest}"


def stable_ufic_object_id(
    *,
    rule_id: object,
    file_path: object,
    line: object = 0,
    column: object = 0,
) -> str:
    """Return a deterministic UFIC omission ontology-object identifier."""
    rule = str(rule_id or "").strip()
    path = normalize_identity_path(file_path)
    line_value = _to_nonnegative_int(line)
    column_value = _to_nonnegative_int(column)
    digest = _digest(("ufic-object-v1", rule, path, line_value, column_value))
    return f"omission:{rule}:{digest}"


def stable_ufic_api_id(
    *,
    file_path: object,
    route_signature: object,
    route_type: object = "",
    framework: object = "",
) -> str:
    """Return a deterministic UFIC API endpoint ontology identifier."""
    path = normalize_identity_path(file_path)
    signature = str(route_signature or "")
    route_kind = str(route_type or "")
    framework_name = str(framework or "")
    digest = _digest(("ufic-api-v1", path, signature, route_kind, framework_name))
    return f"api:{path}:{digest}"
