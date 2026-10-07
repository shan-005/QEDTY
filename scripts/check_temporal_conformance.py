from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator
from rdflib import Graph

from seraph.temporal import (
    AllenRelation,
    BitemporalExtent,
    Interval,
    SnapshotMeta,
    SnapshotSelector,
    TemporalExtent,
    TemporalGranularity,
    TemporalHistory,
    TemporalVersion,
    Timeline,
    classify,
    floor_time,
)

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "data/contracts/golden-vectors/temporal"


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    checks = 0
    for path in sorted(VECTORS.glob("*.json")):
        vector = json.loads(path.read_text(encoding="utf-8"))
        kind = vector["kind"]
        if kind == "allen":
            left = Interval(
                start=dt(vector["left"][0]),
                end=dt(vector["left"][1]),
            )
            right = Interval(
                start=dt(vector["right"][0]),
                end=dt(vector["right"][1]),
            )
            actual = classify(left, right).value
            assert actual == vector["expected"], (path, actual, vector["expected"])
        elif kind == "contains":
            extent = TemporalExtent(start=dt(vector["extent"][0]), end=dt(vector["extent"][1]))
            assert extent.contains(dt(vector["instant"])) is vector["expected"]
        elif kind == "intersection":
            left = TemporalExtent(start=dt(vector["left"][0]), end=dt(vector["left"][1]))
            right = TemporalExtent(start=dt(vector["right"][0]), end=dt(vector["right"][1]))
            actual = left.intersection(right)
            assert actual is not None
            assert (
                actual.start == dt(vector["expected"][0])
                and actual.end == dt(vector["expected"][1])
            )
        elif kind == "bitemporal":
            x = BitemporalExtent(
                valid_time=TemporalExtent(start=dt(vector["valid"][0]), end=None),
                transaction_time=TemporalExtent(start=dt(vector["transaction"][0]), end=None),
            )
            assert (
                x.contains(
                    valid_at=dt(vector["valid_at"]),
                    transaction_at=dt(vector["transaction_at"]),
                )
                is vector["expected"]
            )
        elif kind == "granularity":
            actual = floor_time(dt(vector["value"]), TemporalGranularity(vector["granularity"]))
            assert actual == dt(vector["expected"])
        elif kind == "timeline":
            timeline: Timeline[str] = Timeline()
            for at, value in vector["points"]:
                timeline.put(dt(at), value)
            assert timeline.at_or_before(dt(vector["at_or_before"])) == vector["expected"]
        elif kind == "snapshot":
            selector = SnapshotSelector.at(dt(vector["valid_at"]))
            snapshot = SnapshotMeta.create(
                world_digest=vector["world_digest"],
                schema_version=vector["schema_version"],
                selector=selector,
                captured_at=dt(vector["valid_at"]),
            )
            assert snapshot.snapshot_id.startswith(vector["expected_prefix"])
        elif kind == "version":
            valid = TemporalExtent(start=dt(vector["valid"][0]), end=None)
            tx = TemporalExtent(start=dt(vector["transaction"][0]), end=None)
            version = TemporalVersion.create(
                vector["record_key"],
                vector["value"],
                valid_time=valid,
                transaction_time=tx,
            )
            history: TemporalHistory[dict[str, object]] = TemporalHistory()
            history.add(version)
            result = history.as_of(
                valid_at=dt(vector["query_valid"]),
                transaction_at=dt(vector["query_transaction"]),
            )
            assert len(result) == 1 and result[0].version_id == version.version_id
        else:
            raise AssertionError(f"unknown temporal vector kind: {kind}")
        checks += 1
        print(f"PASS {path.relative_to(ROOT)}")

    schema_path = ROOT / "contracts/temporal/json-schema/temporal.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    checks += 1
    print("PASS temporal JSON Schema 2020-12")

    arrow_path = ROOT / "contracts/temporal/arrow/schema.json"
    arrow = json.loads(arrow_path.read_text(encoding="utf-8"))
    assert arrow["format"] == "Apache Arrow"
    checks += 1
    print("PASS Arrow temporal contract")

    for ttl in (
        ROOT / "contracts/temporal/rdf/temporal.ttl",
        ROOT / "contracts/temporal/shacl/temporal.shacl.ttl",
    ):
        graph = Graph()
        graph.parse(ttl, format="turtle")
        assert len(graph) > 0
        checks += 1
        print(f"PASS RDF/SHACL {ttl.name}")

    print(f"PASS: temporal conformance checks complete ({checks} checks)")


if __name__ == "__main__":
    main()
