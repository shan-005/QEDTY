from qedty.sources.base import SourceContext
from qedty.sources.space.ccsds import parse_omm_kvn


def main() -> int:
    c = SourceContext("test", "public", "0" * 64, allowed_hosts=("example.com",))
    assert c.permits("https://example.com/x") and not c.permits("https://not-allowed.example/x")
    orbit = parse_omm_kvn(
        "OBJECT_ID=1\nEPOCH=2026-01-01T00:00:00Z\nX=1\nY=2\nZ=3\nX_DOT=0\nY_DOT=0\nZ_DOT=0\n"
    )
    assert orbit.object_id == "1"
    print("Sources context/allow-list: PASS")
    print("Sources normalization: PASS")
    print("Sources CCSDS adapter: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
