from seraph.pci import main


def test_validate_command() -> None:
    assert main(["validate"]) == 0
