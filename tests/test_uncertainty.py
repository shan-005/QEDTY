import pytest

from seraph.uncertainty.models import Interval


def test_interval_order():
    assert Interval(lower=1, estimate=2, upper=3).upper == 3
    with pytest.raises(ValueError):
        Interval(lower=3, estimate=2, upper=4)
