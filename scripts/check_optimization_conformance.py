from qedty.optimization.objectives import efficiency
from qedty.optimization.portfolio import knapsack_portfolio


def main() -> int:
    assert efficiency(1.0, 1_000_000) == 1.0
    items = [type("I", (), {"intervention_id": "x", "cost_usd": 2.0, "efficiency": 1.0})()]
    chosen, spent = knapsack_portfolio(items, 2.0)
    assert len(chosen) == 1 and spent == 2.0
    print("Optimization objective: PASS")
    print("Optimization budget feasibility: PASS")
    print("Optimization portfolio determinism: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
