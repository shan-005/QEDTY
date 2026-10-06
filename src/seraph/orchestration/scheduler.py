from __future__ import annotations

from .pipeline import Pipeline, Task


class WorldScheduler:
    """Canonical SERAPH world-state scheduler; repository security is an isolated source adapter."""

    def __init__(self):
        self.pipeline = Pipeline([])

    def with_tasks(self, *tasks: Task) -> WorldScheduler:
        self.pipeline = Pipeline(list(tasks))
        return self

    def run(self, context):
        return self.pipeline.execute(context)
