import pytest

from qedty.uncertainty.calibration import split_conformal_interval
from qedty.uncertainty.models import Interval
from qedty.uncertainty.sampling import deterministic_uniform, latin_hypercube, sobol
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


def test_deterministic_uniform_replays_the_same_seed():
    assert deterministic_uniform(17, 16) == deterministic_uniform(17, 16)
    assert deterministic_uniform(17, 16) != deterministic_uniform(18, 16)


def test_sobol_uses_the_requested_seed_and_replays_exactly():
    first = sobol(17, 16, 3)
    second = sobol(17, 16, 3)
    different_seed = sobol(18, 16, 3)

    assert first == second
    assert first != different_seed
    assert len(first) == 16
    assert all(len(row) == 3 for row in first)
    assert all(0.0 <= value < 1.0 for row in first for value in row)


def test_sobol_rejects_non_power_of_two_sample_sizes_when_available():
    pytest.importorskip("scipy")
    from qedty.uncertainty.sampling import sobol

    with pytest.raises(ValueError, match="power of two"):
        sobol(17, 7, 2)
