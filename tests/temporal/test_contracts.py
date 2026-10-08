import json
from pathlib import Path

from jsonschema import Draft202012Validator
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[2]


def test_temporal_json_schema() -> None:
    schema = json.loads(
        (ROOT / "contracts/temporal/json-schema/temporal.schema.json").read_text(
            encoding="utf-8-sig"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        {
            "profile": "qedty-temporal@2",
            "extent": {
                "start": "2026-01-01T00:00:00Z",
                "end": "2026-01-02T00:00:00Z",
                "start_inclusive": True,
                "end_inclusive": False,
            },
            "allen_relations": [
                "before",
                "meets",
                "overlaps",
                "starts",
                "during",
                "finishes",
                "equals",
                "started_by",
                "contains",
                "finished_by",
                "overlapped_by",
                "met_by",
                "after",
            ],
            "granularities": [
                "microsecond",
                "millisecond",
                "second",
                "minute",
                "hour",
                "day",
                "week",
                "month",
                "quarter",
                "year",
            ],
        }
    )


def test_temporal_rdf_and_shacl_parse() -> None:
    for path in (
        ROOT / "contracts/temporal/rdf/temporal.ttl",
        ROOT / "contracts/temporal/shacl/temporal.shacl.ttl",
    ):
        graph = Graph()
        graph.parse(path, format="turtle")
        assert len(graph) > 0


def test_protobuf_surface() -> None:
    proto = (ROOT / "proto/qedty/temporal/v1/temporal.proto").read_text(encoding="utf-8-sig")
    for message in (
        "TimestampRange",
        "BitemporalExtent",
        "TemporalInstant",
        "SnapshotMeta",
        "TemporalVersion",
    ):
        assert f"message {message} " in proto
