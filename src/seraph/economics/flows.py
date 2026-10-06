from collections import defaultdict

from .trade import TradeFlow


def trade_totals(flows: list[TradeFlow]) -> dict[str, float]:
    out: defaultdict[str, float] = defaultdict(float)
    for f in flows:
        f.validate()
        out[f.sector] += f.value_usd
    return dict(sorted(out.items()))
