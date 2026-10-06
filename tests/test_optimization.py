from seraph.optimization.objectives import efficiency


def test_efficiency():
    assert efficiency(0.5, 1_000_000) == 0.5
