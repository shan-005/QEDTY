from qedty.orchestration.pipeline import Pipeline, Task


def main() -> int:
    p = Pipeline([Task("b", lambda x: x + 1, depends_on=("a",)), Task("a", lambda x: x + 1)])
    assert [t.name for t in p.execution_order()] == ["a", "b"]
    assert p.execute(0) == 2
    print("Orchestration DAG: PASS")
    print("Orchestration deterministic order: PASS")
    print("Orchestration execution: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
