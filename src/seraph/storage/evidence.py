from __future__ import annotations

from pathlib import Path


class EvidenceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
