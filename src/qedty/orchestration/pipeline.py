from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic, sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.backoff_seconds < 0 or self.backoff_multiplier < 1:
            raise ValueError("invalid retry policy")


@dataclass(frozen=True, slots=True)
class Task:
    name: str
    run: Callable[[object], object]
    depends_on: tuple[str, ...] = ()
    retry: RetryPolicy = RetryPolicy()
    timeout_seconds: float | None = None
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("task name must not be blank")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout must be positive")


class Pipeline:
    def __init__(self, tasks: list[Task]) -> None:
        names = [t.name for t in tasks]
        if len(names) != len(set(names)):
            raise ValueError("duplicate task names")
        self.tasks = list(tasks)
        self._validate_dag()

    def _validate_dag(self) -> None:
        known = {t.name for t in self.tasks}
        for task in self.tasks:
            missing = set(task.depends_on) - known
            if missing:
                raise ValueError(f"unknown task dependency: {sorted(missing)}")
        indegree = {t.name: len(t.depends_on) for t in self.tasks}
        children: dict[str, list[str]] = {t.name: [] for t in self.tasks}
        for t in self.tasks:
            for parent in t.depends_on:
                children[parent].append(t.name)
        q = deque(sorted(k for k, v in indegree.items() if v == 0))
        seen = 0
        while q:
            cur = q.popleft()
            seen += 1
            for child in sorted(children[cur]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    q.append(child)
        if seen != len(self.tasks):
            raise ValueError("task graph contains a cycle")

    def execution_order(self) -> tuple[Task, ...]:
        pending = {t.name: t for t in self.tasks}
        done: set[str] = set()
        out: list[Task] = []
        while pending:
            ready = sorted(name for name, t in pending.items() if set(t.depends_on) <= done)
            if not ready:
                raise RuntimeError("unable to resolve task order")
            for name in ready:
                out.append(pending.pop(name))
                done.add(name)
        return tuple(out)

    def _run_task(self, task: Task, context: object) -> object:
        delay = task.retry.backoff_seconds
        last: BaseException | None = None
        for attempt in range(task.retry.max_attempts):
            started = monotonic()
            try:
                result = task.run(context)
                if (
                    task.timeout_seconds is not None
                    and monotonic() - started > task.timeout_seconds
                ):
                    raise TimeoutError(f"task {task.name} exceeded timeout")
                return result
            except BaseException as exc:
                last = exc
                if attempt + 1 == task.retry.max_attempts:
                    break
                if delay > 0:
                    sleep(delay)
                delay *= task.retry.backoff_multiplier

        if last is None:
            raise RuntimeError("Task failed without a recorded exception")
        raise last

    def execute(self, context: object) -> object:
        current = context
        for task in self.execution_order():
            current = self._run_task(task, current)
        return current
