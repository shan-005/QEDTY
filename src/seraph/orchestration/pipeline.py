from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
@dataclass(frozen=True)
class Task:
    name:str; run:Callable[[object],object]
class Pipeline:
    def __init__(self,tasks:list[Task]):self.tasks=tasks
    def execute(self,context):
        current=context
        for task in self.tasks:current=task.run(current)
        return current
