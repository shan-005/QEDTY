"""Durable QEDTY storage primitives."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .evidence import EvidenceStore
    from .provenance import ProvenanceStore
    from .snapshots import SnapshotStore
    from .sqlite import SQLiteWorldStore

__all__ = ["EvidenceStore", "ProvenanceStore", "SQLiteWorldStore", "SnapshotStore"]


def __getattr__(name: str) -> Any:
    if name == "EvidenceStore":
        from .evidence import EvidenceStore

        return EvidenceStore
    if name == "ProvenanceStore":
        from .provenance import ProvenanceStore

        return ProvenanceStore
    if name == "SnapshotStore":
        from .snapshots import SnapshotStore

        return SnapshotStore
    if name == "SQLiteWorldStore":
        from .sqlite import SQLiteWorldStore

        return SQLiteWorldStore
    raise AttributeError(name)
