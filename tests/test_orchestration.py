import pytest

from qedty.orchestration.pipeline import Pipeline, Task
from qedty.orchestration.scheduler import WorldScheduler


def test_topological_order() -> None:
    p = Pipeline([Task("b", lambda x: x + "b", depends_on=("a",)), Task("a", lambda x: x + "a")])
    assert [t.name for t in p.execution_order()] == ["a", "b"]
    assert p.execute("") == "ab"


def test_cycle_rejected() -> None:
    with pytest.raises(ValueError):
        Pipeline(
            [Task("a", lambda x: x, depends_on=("b",)), Task("b", lambda x: x, depends_on=("a",))]
        )


def test_scheduler_interval() -> None:
    s = WorldScheduler().with_tasks(Task("x", lambda x: x + 1)).every(60)
    assert (
        s.tick(
            0,
            now=__import__("datetime").datetime(
                2026, 1, 1, tzinfo=__import__("datetime").timezone.utc
            ),
        )
        == 1
    )
