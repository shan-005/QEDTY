from seraph.cli.scenario import demo_payload
def test_pattern_smoke(): assert demo_payload()["relationships"]>0
