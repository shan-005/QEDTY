from seraph.cli.validate import validate


def test_validate():
    assert validate()["status"] == "ok"
