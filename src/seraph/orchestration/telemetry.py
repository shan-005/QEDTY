from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(slots=True)
class Span:
    name: str
    started: float = field(default_factory=perf_counter)
    ended: float | None = None
    attributes: dict[str, str] = field(default_factory=dict)

    def finish(self) -> float:
        self.ended = perf_counter()
        return self.ended - self.started


def trace_task(name: str, fn: Callable[[Any], Any], context: Any) -> Any:
    span = Span(name)
    try:
        return fn(context)
    finally:
        span.finish()
