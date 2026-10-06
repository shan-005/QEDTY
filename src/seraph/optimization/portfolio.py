from __future__ import annotations


def greedy_portfolio(items, budget_usd: float):
    chosen = []
    spent = 0.0
    for item in sorted(items, key=lambda x: (-x.efficiency, x.intervention_id)):
        if spent + item.cost_usd <= budget_usd:
            chosen.append(item)
            spent += item.cost_usd
    return tuple(chosen), spent
