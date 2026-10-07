from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .json import dumps


class ReportWriter:
    def write_json(self, payload: Any, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(dumps(payload) + "\n", encoding="utf-8")

    def write_text(self, payload: str, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(payload, encoding="utf-8")

    def write_jsonl(self, rows: list[dict[str, Any]], path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
