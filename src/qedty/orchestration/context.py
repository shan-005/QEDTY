from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PipelineContext:
    run_id: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        if not key.strip():
            raise ValueError("artifact key must not be blank")
        self.artifacts[key] = value

    def warn(self, message: str) -> None:
        if message.strip():
            self.warnings.append(message)
