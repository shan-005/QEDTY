from seraph.cli.scenario import demo_payload


def test_counterfactual_gain():
    assert demo_payload()["continuity_gain"] >= 0
