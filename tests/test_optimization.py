from seraph.optimization.objectives import cvar, efficiency
from seraph.optimization.portfolio import knapsack_portfolio


def test_efficiency() -> None:
    assert efficiency(0.5, 1_000_000) == 0.5


def test_cvar_and_portfolio() -> None:
    assert cvar([1.0, 2.0, 3.0], 0.9) == 1.0
    items = [
        type("I", (), {"intervention_id": "a", "cost_usd": 4.0, "efficiency": 1.0})(),
        type("I", (), {"intervention_id": "b", "cost_usd": 6.0, "efficiency": 2.0})(),
    ]
    chosen, spent = knapsack_portfolio(items, 6.0)
    assert spent == 6.0
    assert [x.intervention_id for x in chosen] == ["b"]
