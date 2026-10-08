import pytest

from qedty.uncertainty.calibration import split_conformal_interval
from qedty.uncertainty.models import Interval
from qedty.uncertainty.sampling import latin_hypercube
from qedty.uncertainty.sensitivity import spearman


def test_interval_order():
    assert Interval(lower=1, estimate=2, upper=3).upper == 3
    with pytest.raises(ValueError):
        Interval(lower=3, estimate=2, upper=4)


def test_calibration_and_sampling():
    i = split_conformal_interval([1, 2, 3], [2, 2, 4], 0.9)
    assert i.upper >= i.estimate
    assert len(latin_hypercube(7, 8, 2)) == 8


def test_spearman():
    assert spearman([1, 2, 3], [2, 4, 6]) > 0.99
