"""Versioned graph-contract metadata and serialization validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

NAME = "qedty-world-graph"
VERSION = "1.0.0"
KEY = f"{NAME}@{VERSION}"
SERIALIZATION_VERSION = 1

CAPABILITIES: tuple[str, ...] = (
    "directed-property-graph",
    "deterministic-identities",
    "temporal-validity",
    "typed-relationships",
    "weighted-traversal",
    "temporal-snapshots",
    "deterministic-persistence",
    "connectivity-analysis",
    "centrality-analysis",
    "flow-analysis",
    "spatial-integration",
    "arrow-interchange",
)


def metadata() -> dict[str, Any]:
    """Return stable graph-contract metadata suitable for manifests."""

    return {
        "schema": KEY,
        "serialization_version": SERIALIZATION_VERSION,
        "capabilities": list(CAPABILITIES),
    }


def validate_envelope(raw: Mapping[str, Any]) -> None:
    """Validate the structural envelope of a persisted graph."""

    if raw.get("schema") != KEY:
        raise ValueError(f"unsupported graph schema: {raw.get('schema')!r}")
    if raw.get("serialization_version") != SERIALIZATION_VERSION:
        raise ValueError("unsupported graph serialization version")
    if not isinstance(raw.get("entities"), list) or not isinstance(raw.get("relationships"), list):
        raise ValueError("graph envelope requires entity and relationship arrays")
    digest = raw.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("graph envelope requires a SHA-256 digest")
