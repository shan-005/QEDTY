from __future__ import annotations

import base64
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from .errors import IdentityError, InteroperabilityError
from .time import to_rfc3339

CANONICAL_JSON_PROFILE = "qedty-canonical-json@1"
JCS_PROFILE = "RFC8785"
HASH_ALGORITHM = "SHA-256"


def canonicalize(value: Any) -> Any:
    """Convert supported values into deterministic JSON-compatible values.

    This is QEDTY's implementation-neutral preprocessing layer. It does not
    silently stringify arbitrary Python objects: unsupported values fail fast.
    RFC 8785/JCS number serialization is exposed separately through
    ``jcs_canonical_json`` so existing deterministic QEDTY identifiers remain
    stable while the cross-language JCS profile can be adopted explicitly.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IdentityError("non-finite float cannot be canonicalized")
        return value
    if isinstance(value, Enum):
        return canonicalize(value.value)
    if isinstance(value, datetime):
        return to_rfc3339(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return {"$bytes_base64url": base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")}
    if hasattr(value, "model_dump"):
        return canonicalize(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return canonicalize(asdict(value))
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise IdentityError("canonical JSON object keys must be strings")
            result[key] = canonicalize(item)
        return {key: result[key] for key in sorted(result)}
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, set | frozenset):
        normalized = [canonicalize(item) for item in value]
        return sorted(normalized, key=lambda item: canonical_json(item))
    raise IdentityError(f"unsupported value for canonicalization: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize using the stable QEDTY JSON profile.

    Objects are recursively key-sorted, non-finite numbers are rejected, and
    output contains no insignificant whitespace. For cryptographic JCS
    interoperability, use ``jcs_canonical_json``.
    """
    try:
        return json.dumps(
            canonicalize(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, IdentityError):
            raise
        raise IdentityError(f"canonical JSON serialization failed: {exc}") from exc


def jcs_canonical_bytes(value: Any) -> bytes:
    """Return RFC 8785 JCS bytes using the maintained Python implementation.

    The dependency is intentionally optional at the core layer. Installing the
    optional ``rfc8785`` package makes the exact RFC 8785 serializer available;
    without it QEDTY raises instead of silently claiming JCS compliance.
    """
    from collections.abc import Callable
    from importlib import import_module
    from typing import cast

    try:
        module = import_module("rfc8785")
    except ImportError as exc:
        raise InteroperabilityError(
            "RFC 8785 support requires the optional 'rfc8785' package",
            details={"profile": JCS_PROFILE},
        ) from exc
    dumps = cast("Callable[[Any], bytes]", module.dumps)
    return dumps(canonicalize(value))


def jcs_canonical_json(value: Any) -> str:
    """Return RFC 8785 canonical JSON as UTF-8 decoded text."""
    return jcs_canonical_bytes(value).decode("utf-8")


def sha256_bytes(value: Any) -> bytes:
    """Hash QEDTY canonical JSON with SHA-256."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).digest()


def sha256_hex(value: Any) -> str:
    """Return a lowercase SHA-256 digest of QEDTY canonical JSON."""
    return sha256_bytes(value).hex()


def sha256_hex_jcs(value: Any) -> str:
    """Return a SHA-256 digest of RFC 8785 canonical JSON."""
    return hashlib.sha256(jcs_canonical_bytes(value)).hexdigest()


def identity_preimage(kind: str, parts: Sequence[object]) -> dict[str, Any]:
    """Build the structured identity preimage used by deterministic IDs."""
    if not kind.strip():
        raise IdentityError("kind must not be blank")
    return {"kind": kind, "parts": list(parts)}


def deterministic_id(kind: str, *parts: object, length: int = 32) -> str:
    """Create the stable QEDTY identifier used by the current domain models."""
    if not 1 <= length <= 64:
        raise IdentityError("identifier digest length must be between 1 and 64")
    # Use the JSON-based preimage to match the expected golden hashes
    digest = sha256_hex(identity_preimage(kind, parts))[:length]
    return f"{kind}:{digest}"


def deterministic_id_jcs(kind: str, *parts: object, length: int = 32) -> str:
    """Create a cross-language RFC 8785-backed deterministic identifier."""
    if not 1 <= length <= 64:
        raise IdentityError("identifier digest length must be between 1 and 64")
    digest = sha256_hex_jcs(identity_preimage(kind, parts))[:length]
    return f"{kind}:{digest}"