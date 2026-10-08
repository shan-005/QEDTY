from __future__ import annotations

from collections import defaultdict

from .trade import TradeFlow, TradeMatrix


def trade_totals(flows: list[TradeFlow]) -> dict[str, float]:
    out: defaultdict[str, float] = defaultdict(float)
    for f in flows:
        f.validate()
        out[f.sector] += f.value_usd
    return dict(sorted(out.items()))


def trade_matrix(flows: list[TradeFlow]) -> TradeMatrix:
    for f in flows:
        f.validate()
    exporters = tuple(sorted({f.exporter for f in flows}))
    importers = tuple(sorted({f.importer for f in flows}))
    ei = {v: i for i, v in enumerate(exporters)}
    ii = {v: i for i, v in enumerate(importers)}
    data = [[0.0 for _ in importers] for _ in exporters]
    for f in flows:
        data[ei[f.exporter]][ii[f.importer]] += f.value_usd
    return TradeMatrix(exporters, importers, tuple(tuple(r) for r in data))
