from seraph.economics.flows import trade_matrix
from seraph.economics.io import IOModel
from seraph.economics.trade import TradeFlow


def test_io_converges():
    m = IOModel(("a",), ((0.2,),))
    assert round(m.total_output((10,))[0], 5) == 12.5


def test_trade_matrix():
    m = trade_matrix([TradeFlow("A", "B", "x", 10), TradeFlow("A", "C", "x", 5)])
    assert m.total() == 15
    assert m.exporter_hhi() == 1.0
