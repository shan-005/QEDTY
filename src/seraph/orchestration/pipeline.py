from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    name: str
    run: Callable[[object], object]


class Pipeline:
    def __init__(self, tasks: list[Task]):
        self.tasks = tasks

    def execute(self, context):
        current = context
        for task in self.tasks:
            current = task.run(current)
        return current
