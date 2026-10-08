from qedty.intelligence.anomaly import score
from qedty.intelligence.forecast import holt_linear
from qedty.intelligence.fusion import FusionRecord, fuse


def main() -> int:
    a = score(5.0, [1.0, 1.1, 0.9])
    b = score(5.0, [1.0, 1.1, 0.9])
    assert a == b
    f = holt_linear([1.0, 2.0, 3.0], "h")
    assert f.lower <= f.estimate <= f.upper
    r = fuse([FusionRecord("x", {"a": 1}, ("e1",), 0.9)])
    assert r.subject_id == "x"
    print("Intelligence contract: PASS")
    print("Intelligence determinism: PASS")
    print("Intelligence interval/fusion: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
