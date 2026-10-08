"""Deterministic JSON persistence for the QEDTY graph contract."""

from __future__ import annotations

import contextlib
import gzip
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from qedty.ontology.entities import Entity
from qedty.ontology.relations import Relationship

from .schema import KEY, SERIALIZATION_VERSION, validate_envelope
from .store import TemporalGraph


def _payload(graph: TemporalGraph) -> dict[str, Any]:
    return {
        "schema": KEY,
        "serialization_version": SERIALIZATION_VERSION,
        "entities": [entity.model_dump(mode="json") for entity in graph.entities()],
        "relationships": [
            relationship.model_dump(mode="json") for relationship in graph.relationships()
        ],
    }


def dumps(graph: TemporalGraph, *, indent: int | None = None) -> str:
    """Serialize a graph with a reproducible digest."""

    from qedty.core.hash import sha256_hex

    payload = _payload(graph)
    payload["digest"] = sha256_hex(
        {"entities": payload["entities"], "relationships": payload["relationships"]}
    )
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        separators=None if indent else (",", ":"),
    )


def loads(data: str | bytes, *, verify_digest: bool = True) -> TemporalGraph:
    """Load and optionally verify a serialized graph."""

    text = data.decode("utf-8") if isinstance(data, bytes) else data
    raw = json.loads(text)
    validate_envelope(raw)
    graph = TemporalGraph()
    for item in raw["entities"]:
        graph.add_entity(Entity.model_validate(item, strict=False))
    for item in raw["relationships"]:
        graph.add_relationship(Relationship.model_validate(item, strict=False))
    if verify_digest:
        from qedty.core.hash import sha256_hex

        expected = sha256_hex(
            {
                "entities": raw["entities"],
                "relationships": raw["relationships"],
            }
        )
        if raw["digest"] != expected:
            raise ValueError("graph digest mismatch")
    return graph


def save(graph: TemporalGraph, path: str | Path) -> None:
    """Atomically persist a graph; ``.gz`` paths use gzip compression."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = dumps(graph, indent=2).encode("utf-8")
    if destination.suffix == ".gz":
        payload = gzip.compress(payload, mtime=0)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temp_name).replace(destination)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            Path(temp_name).unlink()
        raise


def load(path: str | Path, *, verify_digest: bool = True) -> TemporalGraph:
    """Load a graph from JSON or deterministic gzip JSON."""

    source = Path(path)
    data = source.read_bytes()
    if source.suffix == ".gz":
        data = gzip.decompress(data)
    return loads(data, verify_digest=verify_digest)
