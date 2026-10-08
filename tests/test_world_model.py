from qedty.ontology.world import WorldModel


def test_summary():
    assert WorldModel().summary()["entities"] == 0
