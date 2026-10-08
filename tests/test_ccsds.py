from qedty.sources.space.ccsds import parse_omm_kvn


def test_omm():
    t = "\n".join(
        [
            "OBJECT_ID = TEST",
            "EPOCH = 2026-01-01T00:00:00Z",
            "X = 1",
            "Y = 2",
            "Z = 3",
            "X_DOT = 0.1",
            "Y_DOT = 0.2",
            "Z_DOT = 0.3",
        ]
    )
    assert parse_omm_kvn(t).object_id == "TEST"
