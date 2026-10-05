from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from seraph.graph.store import TemporalGraph


def save_json(graph: TemporalGraph, path: str | Path, *, overwrite: bool = False) -> None:
    """Atomically persist a graph JSON document."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    payload = graph.to_json(indent=2) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def load_json(path: str | Path) -> TemporalGraph:
    return TemporalGraph.from_json(Path(path).read_text(encoding="utf-8"))
