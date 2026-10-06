from seraph.cli.scenario import demo_payload


def test_demo_propagation():
    p = demo_payload()
    assert p["baseline_capacity"] < 1 and p["counterfactual_capacity"] >= p["baseline_capacity"]
