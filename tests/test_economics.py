from seraph.economics.io import IOModel


def test_io_converges():
    m = IOModel(("a",), ((0.2,),))
    assert round(m.total_output((10,))[0], 5) == 12.5
