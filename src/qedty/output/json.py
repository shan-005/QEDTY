from __future__ import annotations

import json
from typing import Any


def canonicalize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): canonicalize(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [canonicalize(v) for v in value]
    return value


def dumps(value: Any, *, indent: int | None = 2) -> str:
    return json.dumps(
        canonicalize(value), sort_keys=True, indent=indent, ensure_ascii=False, default=str
    )
