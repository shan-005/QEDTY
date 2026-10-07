import json
from datetime import datetime
from pathlib import Path

from seraph.temporal import AllenRelation, Interval, classify

ROOT = Path(__file__).resolve().parents[2]


def test_allen_vector() -> None:
    vector = json.loads((ROOT / "data/contracts/golden-vectors/temporal/allen.json").read_text())
    left = Interval(
        start=datetime.fromisoformat(vector["left"][0]),
        end=datetime.fromisoformat(vector["left"][1]),
    )
    right = Interval(
        start=datetime.fromisoformat(vector["right"][0]),
        end=datetime.fromisoformat(vector["right"][1]),
    )
    assert classify(left, right) is AllenRelation(vector["expected"])
