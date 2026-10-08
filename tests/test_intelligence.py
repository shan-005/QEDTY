from qedty.intelligence.anomaly import cusum, robust_zscore, score
from qedty.intelligence.forecast import holt_linear
from qedty.intelligence.fusion import FusionRecord, fuse
from qedty.intelligence.impact import combine


def test_anomaly_and_cusum_deterministic() -> None:
    assert robust_zscore(4.0, 2.0, 1.0) > 1
    assert score(10.0, [1.0, 1.1, 0.9, 1.0]).anomalous
    assert cusum([0.0, 0.0, 2.0], threshold=1.0) == (2,)


def test_forecast_interval_and_fusion() -> None:
    f = holt_linear([1.0, 2.0, 3.0], "h1")
    assert f.lower <= f.estimate <= f.upper
    a = FusionRecord("x", {"v": 1}, ("e1",), 0.9)
    b = FusionRecord("x", {"v": 1}, ("e2",), 0.8)
    assert fuse([a, b]).confidence > 0


def test_impact_monotone_and_nonnegative() -> None:
    low = combine(0.1, 0.1, 0.1)
    high = combine(0.2, 0.1, 0.1)
    assert high.combined > low.combined
