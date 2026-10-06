from __future__ import annotations
from pathlib import Path
from typing import Any
from .json import dumps

class ReportWriter:
    def write_json(self, payload: Any, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(dumps(payload) + "\n", encoding="utf-8")
