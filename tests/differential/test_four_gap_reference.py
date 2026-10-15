from __future__ import annotations

import pytest

from qedty.optimization.knapsack import KnapsackItem, integer_knapsack
from qedty.propagation.models import PropagationAggregation
from qedty.propagation.state import aggregate_impairments
from qedty.spatial.index import PointGridIndex
from qedty.spatial.models import BoundingBox, Point
from qedty.uncertainty.aggregation import weighted_mean


def test_bbox_index_is_closed_and_wraps_antimeridian() -> None:
    index = PointGridIndex(
        {
            "east": Point(latitude=0.0, longitude=179.0),
            "west": Point(latitude=0.0, longitude=-179.0),
            "outside": Point(latitude=0.0, longitude=0.0),
            "edge": Point(latitude=10.0, longitude=180.0),
        }
    )
    assert index.query_bbox(BoundingBox(west=170.0, south=-10.0, east=-170.0, north=10.0)) == (
        "east",
        "edge",
        "west",
    )


def test_propagation_aggregation_reference_rules() -> None:
    assert aggregate_impairments((0.2, 0.8, 0.4), PropagationAggregation.MAX) == 0.8
    assert aggregate_impairments((0.4, 0.35, 0.3), PropagationAggregation.SUM_CAP) == 1.0
    assert aggregate_impairments((0.2, 0.3, 0.4), PropagationAggregation.NOISY_OR) == pytest.approx(
        0.664
    )
    assert aggregate_impairments((), PropagationAggregation.MAX) == 0.0


def test_weighted_mean_reference_rules_and_errors() -> None:
    assert weighted_mean((2.0, 4.0), (1.0, 3.0)) == pytest.approx(3.5)
    assert weighted_mean((1e300, 1e300), (1e300, 1e300)) == 1e300
    with pytest.raises(ValueError, match="positive sum"):
        weighted_mean((2.0,), (0.0,))


def test_integer_knapsack_reference_objective_and_tie_breaking() -> None:
    items = (KnapsackItem("a", 2, 3.0), KnapsackItem("b", 3, 4.0), KnapsackItem("c", 1, 2.0))
    result = integer_knapsack(items, 3)
    assert (result.selected_ids, result.total_weight, result.total_value) == (("a", "c"), 3, 5.0)
    tie = integer_knapsack((KnapsackItem("b", 1, 2.0), KnapsackItem("a", 1, 2.0)), 1)
    assert tie.selected_ids == ("a",)
