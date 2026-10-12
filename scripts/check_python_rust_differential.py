#!/usr/bin/env python3
"""Run QEDTY's Python reference and native Rust core on identical JSON cases.

The runner is intentionally fail-closed: missing Rust tooling, unknown operations,
missing response lines, unexpected errors, and mismatches all return non-zero.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shlex
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qedty.core.contracts import ContractResult  # noqa: E402
from qedty.core.geometry import GeodeticPoint, geodetic_to_ecef, haversine_km  # noqa: E402
from qedty.core.hash import canonical_json, deterministic_id  # noqa: E402
from qedty.core.time import in_window, parse_rfc3339, to_rfc3339  # noqa: E402
from qedty.core.units import convert_value  # noqa: E402
from qedty.graph.algorithms import (  # noqa: E402
    static_bfs_labels,
    static_scc_labels,
    static_shortest_path_labels,
)
from qedty.spatial.models import Point  # noqa: E402
from qedty.temporal.index import TemporalIndex  # noqa: E402
from qedty.temporal.intervals import Interval, TemporalExtent, classify  # noqa: E402
from qedty.temporal.models import BitemporalExtent, TemporalVersion  # noqa: E402
from qedty.temporal.timeline import Timeline  # noqa: E402
from qedty.temporal.versioning import TemporalHistory  # noqa: E402

SUPPORTED_OPERATIONS = {
    "canonical_json",
    "identity",
    "quantity.convert",
    "time.normalize",
    "geometry.ecef",
    "contract_result",
    "interval.contains",
    "temporal.relation",
    "graph.static.bfs",
    "graph.static.scc",
    "graph.static.shortest_path",
    "spatial.distance.haversine",
    "spatial.radius.query",
    "bitemporal.contains",
    "temporal.bitemporal.contains",
    "temporal.timeline.query",
    "temporal.index.query",
    "temporal.history.query",
    "temporal.graph.snapshot",
}
DEFAULT_RUST_COMMAND = [
    "cargo",
    "run",
    "--locked",
    "--quiet",
    "-p",
    "qedty-conformance",
    "--bin",
    "qedty-differential",
]


def _error_category(operation: str, error: Exception) -> str:
    message = str(error).casefold()
    name = type(error).__name__.casefold()
    if operation in {
        "graph.static.bfs",
        "graph.static.scc",
        "graph.static.shortest_path",
        "temporal.graph.snapshot",
    }:
        if operation == "temporal.graph.snapshot" and "interval" in message:
            return "invalid_interval"
        if operation == "temporal.graph.snapshot" and any(
            token in message
            for token in ("timestamp", "timezone", "date is invalid", "time-of-day", "offset")
        ):
            return "invalid_timestamp"
        return "invalid_input"
    if operation == "spatial.distance.haversine":
        if any(
            token in message
            for token in ("must be a number", "must be numbers", "must be an object")
        ):
            return "invalid_input"
        if any(token in message for token in ("latitude", "longitude", "coordinate")):
            return "invalid_coordinate"
        return "invalid_input"
    if operation == "spatial.radius.query":
        if any(
            token in message
            for token in ("must be a number", "must be numbers", "must be an object")
        ):
            return "invalid_input"
        if "radius" in message:
            return "invalid_radius"
        if "cell size" in message or "cell_degrees" in message:
            return "invalid_cell_size"
        if any(token in message for token in ("latitude", "longitude", "coordinate")):
            return "invalid_coordinate"
        return "invalid_input"
    if operation == "identity":
        return "invalid_digest_length" if "length" in message else "invalid_identity"
    if operation == "quantity.convert":
        if "incompatible" in message or "cannot convert" in message:
            return "incompatible_units"
        if "finite" in message or "nan" in message or "infinity" in message:
            return "non_finite"
        if "unknown unit" in message or "unsupported unit" in message:
            return "unknown_unit"
        if "division by zero" in message:
            return "division_by_zero"
        return "invalid_unit"
    if operation == "temporal.history.query":
        if "version collision" in message:
            return "version_collision"
        if "does not match canonical version identity" in message:
            return "version_id_mismatch"
        if "missing temporal version" in message or "version not found" in message:
            return "missing_version"
        if "start < end" in message or "invalid interval" in message:
            return "invalid_interval"
        if any(
            token in message
            for token in (
                "timestamp",
                "timezone",
                "date is invalid",
                "time-of-day",
                "offset",
            )
        ):
            return "invalid_timestamp"
        return "invalid_input"
    if operation == "temporal.index.query":
        if "temporal index collision" in message:
            return "temporal_index_collision"
        if "keyerror" in name or "temporal index key not found" in message:
            return "missing_key"
        if "start < end" in message or "invalid interval" in message:
            return "invalid_interval"
        if any(
            token in message
            for token in (
                "timestamp",
                "timezone",
                "date is invalid",
                "time-of-day",
                "offset",
            )
        ):
            return "invalid_timestamp"
        return "invalid_input"
    if operation == "temporal.timeline.query":
        if (
            "interval" in message
            or "start < end" in message
            or "end must not precede start" in message
        ):
            return "invalid_interval"
        if any(
            token in message
            for token in (
                "timestamp",
                "timezone",
                "date is invalid",
                "time-of-day",
                "offset",
            )
        ):
            return "invalid_timestamp"
        return "invalid_input"
    if operation == "temporal.bitemporal.contains":
        if (
            "interval" in message
            or "start < end" in message
            or "end must be after start" in message
        ):
            return "invalid_interval"
        if any(
            token in message
            for token in (
                "timestamp",
                "timezone",
                "date is invalid",
                "time-of-day",
                "offset",
            )
        ):
            return "invalid_timestamp"
        return "invalid_input"
    if operation in {
        "time.normalize",
        "interval.contains",
        "temporal.relation",
        "bitemporal.contains",
    }:
        if (
            "interval" in message
            or "start < end" in message
            or "end must be after start" in message
        ):
            return "invalid_interval"
        return "invalid_timestamp"
    if operation == "geometry.ecef":
        return "invalid_coordinate"
    if operation == "contract_result":
        return "invalid_contract"
    if operation == "canonical_json":
        return "invalid_input"
    if "keyerror" in name:
        return "invalid_input"
    return "invalid_input"


def _contract_result_from_input(data: dict[str, Any]) -> str:
    valid_at = parse_rfc3339(data["valid_at"]) if data.get("valid_at") else None
    result = ContractResult(
        value=data["value"],
        epistemic_state=data["epistemic_state"],
        evidence_ids=tuple(data.get("evidence_ids", ())),
        provenance_ids=tuple(data.get("provenance_ids", ())),
        assumptions=tuple(data.get("assumptions", ())),
        model_id=data.get("model_id"),
        model_version=data.get("model_version"),
        valid_at=valid_at,
        uncertainty=data.get("uncertainty"),
        metadata=data.get("metadata", {}),
    )
    return canonical_json(result.to_dict())


def _extent_from_input(data: Any) -> TemporalExtent:
    if not isinstance(data, dict):
        raise ValueError("temporal extent must be an object")
    if "start" not in data or "end" not in data:
        raise ValueError("temporal extent requires start and end fields")

    def parse_bound(name: str) -> datetime | None:
        value = data[name]
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"temporal extent {name} must be a timestamp or null")
        return parse_rfc3339(value)

    return TemporalExtent(start=parse_bound("start"), end=parse_bound("end"))


def _temporal_index_entry_from_input(data: Any) -> tuple[str, TemporalExtent, str]:
    if not isinstance(data, dict):
        raise ValueError("temporal index entry must be an object")
    key = data.get("key")
    if not isinstance(key, str):
        raise ValueError("temporal index key must be a string")
    value = data.get("value")
    if not isinstance(value, str):
        raise ValueError("temporal index value must be a string")
    if "extent" not in data:
        raise ValueError("temporal index entry is missing extent")
    return key, _extent_from_input(data["extent"]), value


def _temporal_index_entry_dict(entry: Any) -> dict[str, Any]:
    return {
        "key": entry.key,
        "extent": {
            "start": None if entry.extent.start is None else to_rfc3339(entry.extent.start),
            "end": None if entry.extent.end is None else to_rfc3339(entry.extent.end),
        },
        "value": entry.value,
    }


def _temporal_version_extent_from_input(data: Any) -> TemporalExtent:
    if not isinstance(data, dict):
        raise ValueError("temporal version extent must be an object")
    allowed = {"start", "end", "start_inclusive", "end_inclusive"}
    if set(data) - allowed:
        raise ValueError("temporal version extent has unknown fields")

    def parse_bound(name: str) -> datetime | None:
        value = data.get(name)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"temporal version extent {name} must be a timestamp or null")
        return parse_rfc3339(value)

    start_inclusive = data.get("start_inclusive", True)
    end_inclusive = data.get("end_inclusive", False)
    if not isinstance(start_inclusive, bool) or not isinstance(end_inclusive, bool):
        raise ValueError("temporal extent inclusion flags must be booleans")
    return TemporalExtent(
        start=parse_bound("start"),
        end=parse_bound("end"),
        start_inclusive=start_inclusive,
        end_inclusive=end_inclusive,
    )


def _temporal_version_from_input(
    data: Any, *, require_version_id: bool = True
) -> TemporalVersion[Any]:
    if not isinstance(data, dict):
        raise ValueError("temporal version must be an object")
    allowed = {"record_key", "value", "valid_time", "transaction_time", "supersedes", "metadata"}
    if require_version_id:
        allowed.add("version_id")
    if set(data) - allowed:
        raise ValueError("temporal version has unknown fields")
    record_key = data.get("record_key")
    if not isinstance(record_key, str) or not 1 <= len(record_key) <= 512:
        raise ValueError("record_key must contain between 1 and 512 characters")
    if "value" not in data:
        raise ValueError("temporal version is missing value")
    valid_time = _temporal_version_extent_from_input(data.get("valid_time"))
    transaction_time = _temporal_version_extent_from_input(data.get("transaction_time"))
    supersedes = data.get("supersedes", [])
    if not isinstance(supersedes, list) or any(not isinstance(item, str) for item in supersedes):
        raise ValueError("supersedes must be an array of strings")
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    version = TemporalVersion.create(
        record_key,
        data["value"],
        valid_time=valid_time,
        transaction_time=transaction_time,
        supersedes=tuple(supersedes),
        metadata=metadata,
    )
    if require_version_id:
        supplied_id = data.get("version_id")
        if not isinstance(supplied_id, str) or not 1 <= len(supplied_id) <= 256:
            raise ValueError("version_id must contain between 1 and 256 characters")
        if supplied_id != version.version_id:
            raise ValueError("version_id does not match canonical version identity")
    return version


def _temporal_version_dict(version: TemporalVersion[Any]) -> dict[str, Any]:
    return version.model_dump(mode="json")


def _temporal_history_from_input(data: dict[str, Any]) -> TemporalHistory[Any]:
    raw_versions = data.get("versions")
    if not isinstance(raw_versions, list):
        raise ValueError("temporal history versions must be an array")
    history: TemporalHistory[Any] = TemporalHistory()
    for raw_version in raw_versions:
        history.add(_temporal_version_from_input(raw_version))
    return history


def _temporal_graph_snapshot_reference(data: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic node/relationship membership at one valid-time instant."""
    at = parse_rfc3339(data["at"])
    raw_nodes = data.get("nodes")
    raw_relationships = data.get("relationships")
    if not isinstance(raw_nodes, list) or not isinstance(raw_relationships, list):
        raise ValueError("nodes and relationships must be arrays")
    nodes: set[str] = set()
    for node in raw_nodes:
        if not isinstance(node, str) or not node.strip():
            raise ValueError("node IDs must be non-blank strings")
        nodes.add(node)
    relationships: dict[str, tuple[str, str, datetime | None, datetime | None]] = {}
    for item in raw_relationships:
        if not isinstance(item, dict):
            raise ValueError("each relationship must be an object")
        rid, source, target = item.get("id"), item.get("source"), item.get("target")
        if any(not isinstance(value, str) or not value.strip() for value in (rid, source, target)):
            raise ValueError("relationship id and endpoints must be non-blank strings")
        if source not in nodes or target not in nodes:
            raise ValueError("relationship endpoint missing from graph")
        start = parse_rfc3339(item["valid_start"]) if item.get("valid_start") is not None else None
        end = parse_rfc3339(item["valid_end"]) if item.get("valid_end") is not None else None
        if start is not None and end is not None and end <= start:
            raise ValueError("invalid interval: relationship end must be after start")
        record = (source, target, start, end)
        previous = relationships.get(rid)
        if previous is not None and previous != record:
            raise ValueError(f"relationship collision: {rid}")
        relationships[rid] = record
    active_ids = sorted(
        rid
        for rid, (_, _, start, end) in relationships.items()
        if (start is None or start <= at) and (end is None or at < end)
    )
    return {"at": to_rfc3339(at), "entity_ids": sorted(nodes), "relationship_ids": active_ids}


def _timeline_point_dict(point: Any) -> dict[str, Any]:
    return {
        "at": to_rfc3339(point.at),
        "value": point.value,
        "sequence": point.sequence,
    }


def _timeline_from_input(data: dict[str, Any]) -> Timeline[str]:
    raw_points = data.get("points")
    if not isinstance(raw_points, list):
        raise ValueError("`points` must be an array")
    timeline: Timeline[str] = Timeline()
    for point in raw_points:
        if not isinstance(point, dict):
            raise ValueError("each timeline point must be an object")
        at = parse_rfc3339(point["at"])
        value = point["value"]
        if not isinstance(value, str):
            raise ValueError("timeline point value must be a string")
        sequence = point.get("sequence")
        if sequence is not None and (isinstance(sequence, bool) or not isinstance(sequence, int)):
            raise ValueError("timeline sequence must be an integer or null")
        timeline.put(at, value, sequence=sequence)
    return timeline


def _spatial_point_from_input(value: Any) -> Point:
    """Validate one XY geographic position for the named spherical contracts."""
    if not isinstance(value, dict):
        raise ValueError("point must be an object")
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    if (
        isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
    ):
        raise ValueError("point latitude and longitude must be numbers")
    return Point(latitude=float(latitude), longitude=float(longitude))


def _spherical_radius_reference(data: dict[str, Any]) -> list[str]:
    """Independent brute-force oracle for spatial.radius.query.

    It deliberately does not use Python's WGS-84 PointGridIndex. The metric is
    the named mean-Earth-radius Haversine surface distance, and output IDs match
    the native grid contract's last-write-wins and (distance, ID) ordering.
    """
    center = _spatial_point_from_input(data.get("center"))
    raw_radius = data.get("radius_m")
    if isinstance(raw_radius, bool) or not isinstance(raw_radius, (int, float)):
        raise ValueError("radius must be a number")
    radius_m = float(raw_radius)
    if not math.isfinite(radius_m) or radius_m < 0.0:
        raise ValueError("radius must be finite and non-negative")

    raw_cell = data.get("cell_degrees", 1.0)
    if isinstance(raw_cell, bool) or not isinstance(raw_cell, (int, float)):
        raise ValueError("cell size must be a number")
    cell_degrees = float(raw_cell)
    if not math.isfinite(cell_degrees) or not 0.01 <= cell_degrees <= 180.0:
        raise ValueError("cell size must be finite and in [0.01, 180]")

    raw_points = data.get("points")
    if not isinstance(raw_points, list):
        raise ValueError("points must be an array")

    points: dict[str, Point] = {}
    for item in raw_points:
        if not isinstance(item, dict):
            raise ValueError("each point must be an object")
        point_id = item.get("id")
        if not isinstance(point_id, str):
            raise ValueError("point identifier must be a string")
        point_id = point_id.strip()
        if not point_id:
            raise ValueError("point identifier must not be blank")
        points[point_id] = _spatial_point_from_input(item)

    matches: list[tuple[float, str]] = []
    for point_id, point in points.items():
        distance_m = (
            haversine_km(
                center.latitude,
                center.longitude,
                point.latitude,
                point.longitude,
            )
            * 1000.0
        )
        if distance_m <= radius_m + 1e-7:
            matches.append((distance_m, point_id))
    matches.sort(key=lambda item: (item[0], item[1]))
    return [point_id for _, point_id in matches]


def evaluate_reference(operation: str, data: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a case with the real QEDTY Python reference functions."""
    try:
        if operation == "canonical_json":
            result: Any = canonical_json(data["value"])
        elif operation == "identity":
            parts = data["parts"]
            result = deterministic_id(data["kind"], *parts, length=int(data["length"]))
        elif operation == "quantity.convert":
            converted = convert_value(
                Decimal(str(data["value"])), data["from_unit"], data["to_unit"]
            )
            result = float(converted)
            if not math.isfinite(result):
                raise ValueError("quantity result is not finite")
        elif operation == "time.normalize":
            result = to_rfc3339(parse_rfc3339(data["timestamp"]))
        elif operation == "geometry.ecef":
            point = GeodeticPoint(
                latitude=float(data["latitude_deg"]),
                longitude=float(data["longitude_deg"]),
                height_m=float(data["height_m"]),
            )
            result = list(geodetic_to_ecef(point))
        elif operation == "contract_result":
            result = _contract_result_from_input(data["contract"])
        elif operation == "interval.contains":
            result = in_window(
                parse_rfc3339(data["instant"]),
                parse_rfc3339(data["start"]) if data.get("start") is not None else None,
                parse_rfc3339(data["end"]) if data.get("end") is not None else None,
            )
        elif operation == "temporal.relation":
            left = Interval(
                start=parse_rfc3339(data["left"]["start"]),
                end=parse_rfc3339(data["left"]["end"]),
            )
            right = Interval(
                start=parse_rfc3339(data["right"]["start"]),
                end=parse_rfc3339(data["right"]["end"]),
            )
            result = classify(left, right).value
        elif operation == "bitemporal.contains":
            valid_extent = TemporalExtent(
                start=(
                    parse_rfc3339(data["valid_start"])
                    if data.get("valid_start") is not None
                    else None
                ),
                end=(
                    parse_rfc3339(data["valid_end"]) if data.get("valid_end") is not None else None
                ),
            )
            transaction_extent = TemporalExtent(
                start=(
                    parse_rfc3339(data["transaction_start"])
                    if data.get("transaction_start") is not None
                    else None
                ),
                end=(
                    parse_rfc3339(data["transaction_end"])
                    if data.get("transaction_end") is not None
                    else None
                ),
            )
            valid_at = parse_rfc3339(data["valid_at"])
            transaction_at = parse_rfc3339(data["transaction_at"])
            result = valid_extent.contains(valid_at) and transaction_extent.contains(transaction_at)
        elif operation == "graph.static.bfs":
            result = list(static_bfs_labels(data["nodes"], data["edges"], data["source"]))
        elif operation == "graph.static.scc":
            result = [
                list(component) for component in static_scc_labels(data["nodes"], data["edges"])
            ]
        elif operation == "graph.static.shortest_path":
            result = static_shortest_path_labels(
                data["nodes"], data["edges"], data["source"], data["target"]
            )
        elif operation == "spatial.distance.haversine":
            first = _spatial_point_from_input(data["first"])
            second = _spatial_point_from_input(data["second"])
            result = (
                haversine_km(first.latitude, first.longitude, second.latitude, second.longitude)
                * 1000.0
            )
        elif operation == "spatial.radius.query":
            result = _spherical_radius_reference(data)
        elif operation == "temporal.graph.snapshot":
            result = _temporal_graph_snapshot_reference(data)
        elif operation == "temporal.history.query":
            mode = data.get("mode")
            if not isinstance(mode, str):
                raise ValueError("temporal history mode must be a string")
            if mode == "create":
                version = _temporal_version_from_input(
                    data.get("version"), require_version_id=False
                )
                result = _temporal_version_dict(version)
            else:
                history = _temporal_history_from_input(data)
                if mode == "all":
                    result = [_temporal_version_dict(version) for version in history.all()]
                elif mode == "get":
                    version_id = data.get("version_id")
                    if not isinstance(version_id, str):
                        raise ValueError("temporal history get requires a string version_id")
                    try:
                        version = history.get(version_id)
                    except KeyError as error:
                        raise ValueError(f"missing temporal version: {version_id}") from error
                    result = _temporal_version_dict(version)
                elif mode == "as_of":
                    valid_at = parse_rfc3339(data["valid_at"])
                    transaction_at = parse_rfc3339(data["transaction_at"])
                    result = [
                        _temporal_version_dict(version)
                        for version in history.as_of(
                            valid_at=valid_at, transaction_at=transaction_at
                        )
                    ]
                elif mode == "latest_known":
                    record_key = data.get("record_key")
                    if not isinstance(record_key, str):
                        raise ValueError(
                            "temporal history latest_known requires a string record_key"
                        )
                    transaction_at = parse_rfc3339(data["transaction_at"])
                    version = history.latest_known(record_key, transaction_at)
                    result = None if version is None else _temporal_version_dict(version)
                elif mode == "add":
                    new_version = _temporal_version_from_input(data.get("new_version"))
                    history.add(new_version)
                    result = [_temporal_version_dict(version) for version in history.all()]
                else:
                    raise ValueError(f"unsupported temporal history mode {mode!r}")
        elif operation == "temporal.index.query":
            raw_entries = data.get("entries")
            if not isinstance(raw_entries, list):
                raise ValueError("temporal index entries must be an array")
            index: TemporalIndex[str] = TemporalIndex()
            for raw_entry in raw_entries:
                key, extent, value = _temporal_index_entry_from_input(raw_entry)
                index.add(key, extent, value)

            mode = data.get("mode")
            if not isinstance(mode, str):
                raise ValueError("temporal index mode must be a string")
            if mode == "at":
                instant = data.get("instant")
                if not isinstance(instant, str):
                    raise ValueError("temporal index at mode requires an instant timestamp")
                result = list(index.at(parse_rfc3339(instant)))
            elif mode == "overlapping":
                result = list(index.overlapping(_extent_from_input(data.get("query"))))
            elif mode == "all":
                result = [_temporal_index_entry_dict(entry) for entry in index.all()]
            elif mode == "get":
                key = data.get("key")
                if not isinstance(key, str):
                    raise ValueError("temporal index get mode requires a string key")
                result = _temporal_index_entry_dict(index.get(key))
            elif mode == "remove":
                key = data.get("key")
                if not isinstance(key, str):
                    raise ValueError("temporal index remove mode requires a string key")
                result = _temporal_index_entry_dict(index.remove(key))
            elif mode == "len":
                result = len(index)
            elif mode == "clear":
                index.clear()
                result = len(index)
            elif mode == "add":
                key, extent, value = _temporal_index_entry_from_input(data.get("new_entry"))
                index.add(key, extent, value)
                result = len(index)
            else:
                raise ValueError(f"unsupported temporal index mode {mode!r}")
        elif operation == "temporal.bitemporal.contains":
            result = BitemporalExtent(
                valid_time=_extent_from_input(data["valid_time"]),
                transaction_time=_extent_from_input(data["transaction_time"]),
            ).contains(
                valid_at=parse_rfc3339(data["valid_at"]),
                transaction_at=parse_rfc3339(data["transaction_at"]),
            )
        elif operation == "temporal.timeline.query":
            timeline = _timeline_from_input(data)
            mode = data["mode"]
            if mode == "at_or_before":
                result = timeline.at_or_before(parse_rfc3339(data["at"]))
            elif mode == "at_or_after":
                result = timeline.at_or_after(parse_rfc3339(data["at"]))
            elif mode == "between":
                start = parse_rfc3339(data["start"])
                end = parse_rfc3339(data["end"])
                include_end = data.get("include_end", False)
                if not isinstance(include_end, bool):
                    raise ValueError("`include_end` must be a boolean")
                result = [
                    _timeline_point_dict(point)
                    for point in timeline.between(start, end, include_end=include_end)
                ]
            elif mode == "latest":
                point = timeline.latest()
                result = None if point is None else _timeline_point_dict(point)
            elif mode == "ordered":
                result = [_timeline_point_dict(point) for point in timeline.ordered()]
            elif mode == "values":
                result = list(timeline.values())
            else:
                raise ValueError(f"unsupported timeline query mode {mode!r}")
        else:
            return {
                "ok": False,
                "error": {"category": "unsupported_operation", "message": operation},
            }
        return {"ok": True, "result": result}
    except Exception as error:  # classify errors for differential reporting.
        return {
            "ok": False,
            "error": {
                "category": _error_category(operation, error),
                "message": f"{type(error).__name__}: {error}",
            },
        }


def _case(case: dict[str, Any], source: str) -> None:
    required = {"case_id", "operation", "input", "comparison"}
    missing = required - case.keys()
    if missing:
        raise ValueError(f"{source}: case misses required keys {sorted(missing)}")
    if not isinstance(case["case_id"], str) or not case["case_id"].strip():
        raise ValueError(f"{source}: case_id must be a non-empty string")
    if case["operation"] not in SUPPORTED_OPERATIONS:
        raise ValueError(f"{source}/{case['case_id']}: unsupported operation in fixture")
    if not isinstance(case["input"], dict):
        raise ValueError(f"{source}/{case['case_id']}: input must be an object")
    if not isinstance(case["comparison"], dict) or case["comparison"].get("mode") not in {
        "exact",
        "numeric",
        "vector_tolerance",
    }:
        raise ValueError(f"{source}/{case['case_id']}: invalid comparison mode")
    if case["comparison"]["mode"] != "exact":
        for field in ("absolute_tolerance", "relative_tolerance"):
            tolerance = case["comparison"].get(field)
            if (
                isinstance(tolerance, bool)
                or not isinstance(tolerance, (int, float))
                or not math.isfinite(float(tolerance))
                or tolerance < 0
            ):
                raise ValueError(
                    f"{source}/{case['case_id']}: {field} must be finite and non-negative"
                )
    if "expected_error" in case and not isinstance(case["expected_error"], str):
        raise ValueError(
            f"{source}/{case['case_id']}: expected_error must be a string when present"
        )


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant is forbidden: {value}")


def _load_strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        parse_constant=_reject_nonstandard_json_constant,
    )


def load_cases(directory: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    schema_path = ROOT / "contracts" / "json-schema" / "differential-cases.schema.json"
    schema = _load_strict_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    files = sorted(directory.glob("*.json"))
    if not files:
        raise ValueError(f"no differential case files found under {directory}")
    for path in files:
        document = _load_strict_json(path)
        validator.validate(document)
        if document.get("schema_version") != "qedty-differential-cases@1":
            raise ValueError(f"{path}: unsupported/missing schema_version")
        items = document.get("cases")
        if not isinstance(items, list):
            raise ValueError(f"{path}: `cases` must be an array")
        for case in items:
            _case(case, str(path.relative_to(ROOT)))
            if case["case_id"] in seen:
                raise ValueError(f"duplicate differential case ID: {case['case_id']}")
            seen.add(case["case_id"])
            cases.append(case)
    return cases


def _iso_seconds(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def generate_cases(count: int, seed: int) -> list[dict[str, Any]]:
    """Generate deterministic, replayable cases. `count` is cases per family."""
    rng = random.Random(seed)
    generated: list[dict[str, Any]] = []
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(count):
        generated.extend(
            [
                {
                    "case_id": f"generated-{seed}-canonical-{i:04d}",
                    "operation": "canonical_json",
                    "input": {"value": {"i": i, "flag": i % 2 == 0, "nested": [seed, f"v-{i}"]}},
                    "comparison": {"mode": "exact"},
                },
                {
                    "case_id": f"generated-{seed}-identity-{i:04d}",
                    "operation": "identity",
                    "input": {
                        "kind": "generated",
                        "parts": ["qedty", f"item-{i}", rng.randrange(0, 1_000_000)],
                        "length": 32,
                    },
                    "comparison": {"mode": "exact"},
                },
                {
                    "case_id": f"generated-{seed}-quantity-{i:04d}",
                    "operation": "quantity.convert",
                    "input": {
                        "value": str(rng.randrange(-1_000_000, 1_000_001) / 4),
                        "from_unit": "km",
                        "to_unit": "m",
                    },
                    "comparison": {
                        "mode": "numeric",
                        "absolute_tolerance": 1e-8,
                        "relative_tolerance": 1e-12,
                    },
                },
                {
                    "case_id": f"generated-{seed}-geometry-{i:04d}",
                    "operation": "geometry.ecef",
                    "input": {
                        "latitude_deg": rng.uniform(-90.0, 90.0),
                        "longitude_deg": rng.uniform(-180.0, 180.0),
                        "height_m": rng.uniform(-1000.0, 10000.0),
                    },
                    "comparison": {
                        "mode": "vector_tolerance",
                        "absolute_tolerance": 2e-6,
                        "relative_tolerance": 0.0,
                    },
                },
                {
                    "case_id": f"generated-{seed}-time-{i:04d}",
                    "operation": "time.normalize",
                    "input": {
                        "timestamp": _iso_seconds(
                            base + timedelta(seconds=i * 7919 + rng.randrange(0, 3000))
                        )
                    },
                    "comparison": {"mode": "exact"},
                },
            ]
        )
    # Temporal generators extend the original five deterministic families without
    # changing their RNG stream or previously accepted case outputs.
    relation_patterns = (
        ("before", (0, 1), (3, 4)),
        ("meets", (0, 1), (1, 3)),
        ("overlaps", (0, 2), (1, 3)),
        ("starts", (0, 1), (0, 3)),
        ("during", (1, 2), (0, 3)),
        ("finishes", (2, 3), (0, 3)),
        ("equals", (0, 3), (0, 3)),
        ("started_by", (0, 3), (0, 1)),
        ("contains", (0, 3), (1, 2)),
        ("finished_by", (0, 3), (2, 3)),
        ("overlapped_by", (1, 3), (0, 2)),
        ("met_by", (1, 3), (0, 1)),
        ("after", (3, 4), (0, 1)),
    )

    def relation_time(origin: datetime, tick: int, tick_seconds: int) -> str:
        return _iso_seconds(origin + timedelta(seconds=tick * tick_seconds))

    for i in range(count):
        interval_start = base + timedelta(seconds=i * 100_000)
        duration = 2 + (i % 19)
        interval_end = interval_start + timedelta(seconds=duration)
        mode = i % 6
        if mode == 0:
            instant = interval_start  # included lower bound
            lower, upper = interval_start, interval_end
        elif mode == 1:
            instant = interval_end  # excluded upper bound
            lower, upper = interval_start, interval_end
        elif mode == 2:
            instant = interval_start + timedelta(seconds=1 + (i % (duration - 1)))
            lower, upper = interval_start, interval_end
        elif mode == 3:
            instant = interval_start - timedelta(seconds=1)
            lower, upper = None, interval_end
        elif mode == 4:
            instant = interval_end + timedelta(seconds=1)
            lower, upper = interval_start, None
        else:
            instant = interval_start - timedelta(seconds=1)
            lower, upper = None, None
        generated.append(
            {
                "case_id": f"generated-{seed}-interval-{i:04d}",
                "operation": "interval.contains",
                "input": {
                    "instant": _iso_seconds(instant),
                    "start": None if lower is None else _iso_seconds(lower),
                    "end": None if upper is None else _iso_seconds(upper),
                },
                "comparison": {"mode": "exact"},
            }
        )

        _, left_bounds, right_bounds = relation_patterns[i % len(relation_patterns)]
        tick_seconds = 1 + (i % 7)
        generated.append(
            {
                "case_id": f"generated-{seed}-relation-{i:04d}",
                "operation": "temporal.relation",
                "input": {
                    "left": {
                        "start": relation_time(interval_start, left_bounds[0], tick_seconds),
                        "end": relation_time(interval_start, left_bounds[1], tick_seconds),
                    },
                    "right": {
                        "start": relation_time(interval_start, right_bounds[0], tick_seconds),
                        "end": relation_time(interval_start, right_bounds[1], tick_seconds),
                    },
                },
                "comparison": {"mode": "exact"},
            }
        )
    # Eighth deterministic family. Its RNG is isolated so existing generated
    # sequences remain unchanged when this operation is added.
    graph_rng = random.Random(seed ^ 0x5EEDB5F)
    for i in range(count):
        graph_nodes = [f"g{i:03d}-n{j}" for j in range(6)]
        graph_edges = [
            [left, right]
            for left in graph_nodes
            for right in graph_nodes
            if left != right and graph_rng.random() < 0.22
        ]
        generated.append(
            {
                "case_id": f"generated-{seed}-graph-bfs-{i:04d}",
                "operation": "graph.static.bfs",
                "input": {
                    "nodes": graph_nodes,
                    "edges": graph_edges,
                    "source": graph_nodes[graph_rng.randrange(len(graph_nodes))],
                },
                "comparison": {"mode": "exact"},
            }
        )

    # Ninth deterministic family: bitemporal valid-time/transaction-time
    # membership with nullable open bounds. Its RNG is isolated from prior families.
    bitemporal_rng = random.Random(seed ^ 0xB17E2026)
    for i in range(count):
        origin = base + timedelta(seconds=i * 100_000)
        valid_start = (
            None if i % 4 == 0 else origin + timedelta(seconds=bitemporal_rng.randrange(0, 30))
        )
        valid_end = (
            None
            if i % 5 == 0
            else (valid_start or origin) + timedelta(seconds=bitemporal_rng.randrange(1, 60))
        )
        transaction_origin = origin + timedelta(seconds=200)
        transaction_start = (
            None
            if i % 3 == 0
            else transaction_origin + timedelta(seconds=bitemporal_rng.randrange(0, 30))
        )
        transaction_end = (
            None
            if i % 4 == 0
            else (transaction_start or transaction_origin)
            + timedelta(seconds=bitemporal_rng.randrange(1, 60))
        )
        valid_at = origin + timedelta(seconds=bitemporal_rng.randrange(-5, 90))
        transaction_at = transaction_origin + timedelta(seconds=bitemporal_rng.randrange(-5, 90))
        generated.append(
            {
                "case_id": f"generated-{seed}-bitemporal-{i:04d}",
                "operation": "temporal.bitemporal.contains",
                "input": {
                    "valid_time": {
                        "start": None if valid_start is None else _iso_seconds(valid_start),
                        "end": None if valid_end is None else _iso_seconds(valid_end),
                    },
                    "transaction_time": {
                        "start": (
                            None if transaction_start is None else _iso_seconds(transaction_start)
                        ),
                        "end": None if transaction_end is None else _iso_seconds(transaction_end),
                    },
                    "valid_at": _iso_seconds(valid_at),
                    "transaction_at": _iso_seconds(transaction_at),
                },
                "comparison": {"mode": "exact"},
            }
        )

    # Tenth deterministic family: event timeline modes, duplicate instants and
    # explicit/default sequence ties. The separate RNG preserves previous outputs.
    timeline_rng = random.Random(seed ^ 0x71AE1A1)
    timeline_modes = ("at_or_before", "at_or_after", "between", "latest", "ordered", "values")
    for i in range(count):
        origin = base + timedelta(seconds=i * 86_400)
        points: list[dict[str, Any]] = []
        point_count = 3 + timeline_rng.randrange(0, 4)
        for j in range(point_count):
            point: dict[str, Any] = {
                "at": _iso_seconds(origin + timedelta(seconds=(j // 2) * 10)),
                "value": f"event-{i}-{j}",
            }
            if (i + j) % 3 != 0:
                point["sequence"] = timeline_rng.randrange(-2, 5)
            points.append(point)
        mode = timeline_modes[i % len(timeline_modes)]
        timeline_input: dict[str, Any] = {"mode": mode, "points": points}
        if mode in {"at_or_before", "at_or_after"}:
            timeline_input["at"] = _iso_seconds(
                origin + timedelta(seconds=timeline_rng.randrange(0, 31))
            )
        elif mode == "between":
            start = origin + timedelta(seconds=timeline_rng.randrange(0, 21))
            end = start + timedelta(seconds=timeline_rng.randrange(1, 31))
            timeline_input["start"] = _iso_seconds(start)
            timeline_input["end"] = _iso_seconds(end)
            timeline_input["include_end"] = i % 2 == 0
        generated.append(
            {
                "case_id": f"generated-{seed}-timeline-{i:04d}",
                "operation": "temporal.timeline.query",
                "input": timeline_input,
                "comparison": {"mode": "exact"},
            }
        )

    # Eleventh deterministic family: label-only strongly connected components.
    # Its RNG and case IDs are isolated so earlier generated cases stay stable.
    scc_rng = random.Random(seed ^ 0x5CC02026)
    for i in range(count):
        scc_nodes = [f"s{i:03d}-n{j}" for j in range(7)]
        scc_edges = [
            [left, right]
            for left in scc_nodes
            for right in scc_nodes
            if left != right and scc_rng.random() < 0.18
        ]
        if i % 2 == 0:
            scc_edges.extend([[scc_nodes[0], scc_nodes[1]], [scc_nodes[1], scc_nodes[0]]])
        if i % 3 == 0:
            scc_edges.extend([[scc_nodes[2], scc_nodes[3]], [scc_nodes[3], scc_nodes[2]]])
        generated.append(
            {
                "case_id": f"generated-{seed}-graph-scc-{i:04d}",
                "operation": "graph.static.scc",
                "input": {"nodes": scc_nodes, "edges": scc_edges},
                "comparison": {"mode": "exact"},
            }
        )

    # Twelfth family: named spherical mean-Earth-radius Haversine distances.
    # This independent RNG stream leaves earlier generated families unchanged.
    distance_rng = random.Random(seed ^ 0xD157A9CE)
    for i in range(count):
        if i % 8 == 0:
            first = {"latitude": 0.0, "longitude": 179.5}
            second = {"latitude": 0.0, "longitude": -179.5}
        elif i % 8 == 1:
            first = {"latitude": 89.9, "longitude": distance_rng.uniform(-180.0, 180.0)}
            second = {"latitude": 89.9, "longitude": distance_rng.uniform(-180.0, 180.0)}
        else:
            first = {
                "latitude": distance_rng.uniform(-90.0, 90.0),
                "longitude": distance_rng.uniform(-180.0, 180.0),
            }
            second = {
                "latitude": distance_rng.uniform(-90.0, 90.0),
                "longitude": distance_rng.uniform(-180.0, 180.0),
            }
        generated.append(
            {
                "case_id": f"generated-{seed}-spatial-distance-{i:04d}",
                "operation": "spatial.distance.haversine",
                "input": {"first": first, "second": second},
                "comparison": {
                    "mode": "numeric",
                    "absolute_tolerance": 1e-6,
                    "relative_tolerance": 1e-12,
                },
            }
        )

    # Thirteenth family: indexed radius queries checked against an independent
    # brute-force oracle, including poles, antimeridian wrap, and duplicate IDs.
    radius_rng = random.Random(seed ^ 0x52A11D26)
    radius_values = (0.0, 500.0, 10_000.0, 100_000.0, 1_000_000.0, 5_000_000.0, 20_015_114.4421)
    cell_values = (0.01, 0.2, 1.0, 15.0, 90.0, 180.0)
    for i in range(count):
        if i % 7 == 0:
            center = {"latitude": 89.9, "longitude": 179.8}
        else:
            center = {
                "latitude": radius_rng.uniform(-89.95, 89.95),
                "longitude": radius_rng.uniform(-180.0, 180.0),
            }
        points = [
            {"id": "center", "latitude": center["latitude"], "longitude": center["longitude"]},
            {
                "id": "near",
                "latitude": max(
                    -90.0,
                    min(90.0, center["latitude"] + radius_rng.choice((-0.1, -0.01, 0.01, 0.1))),
                ),
                "longitude": center["longitude"],
            },
        ]
        for j in range(12):
            points.append(
                {
                    "id": f"p{j:02d}",
                    "latitude": radius_rng.uniform(-90.0, 90.0),
                    "longitude": radius_rng.uniform(-180.0, 180.0),
                }
            )
        if i % 5 == 0:
            points.append(
                {"id": "near", "latitude": center["latitude"], "longitude": center["longitude"]}
            )
        generated.append(
            {
                "case_id": f"generated-{seed}-spatial-radius-{i:04d}",
                "operation": "spatial.radius.query",
                "input": {
                    "center": center,
                    "points": points,
                    "radius_m": radius_values[i % len(radius_values)],
                    "cell_degrees": cell_values[radius_rng.randrange(len(cell_values))],
                },
                "comparison": {"mode": "exact"},
            }
        )

    # Fourteenth deterministic family: temporal-index scans, ordering, and key semantics.
    # Its isolated RNG keeps all previously accepted generated inputs unchanged.
    index_rng = random.Random(seed ^ 0x7E4D1A26)
    index_modes = ("at", "overlapping", "all", "get", "remove", "len", "add", "clear")
    for i in range(count):
        origin = base + timedelta(seconds=i * 100_000)
        entries = [
            {
                "key": "everywhere",
                "extent": {"start": None, "end": None},
                "value": "all-time",
            },
            {
                "key": "left",
                "extent": {"start": None, "end": _iso_seconds(origin + timedelta(seconds=10))},
                "value": "left",
            },
            {
                "key": "start",
                "extent": {
                    "start": _iso_seconds(origin),
                    "end": _iso_seconds(origin + timedelta(seconds=20)),
                },
                "value": "start",
            },
            {
                "key": "middle",
                "extent": {
                    "start": _iso_seconds(origin + timedelta(seconds=10)),
                    "end": _iso_seconds(origin + timedelta(seconds=30)),
                },
                "value": "middle",
            },
            {
                "key": "right",
                "extent": {"start": _iso_seconds(origin + timedelta(seconds=30)), "end": None},
                "value": "right",
            },
        ]
        mode = index_modes[i % len(index_modes)]
        index_input: dict[str, Any] = {"mode": mode, "entries": entries}
        if mode == "at":
            index_input["instant"] = _iso_seconds(
                origin + timedelta(seconds=(10 if i % 2 == 0 else 20))
            )
        elif mode == "overlapping":
            query_start = origin + timedelta(seconds=20)
            query_end = query_start + timedelta(seconds=1 + index_rng.randrange(1, 10))
            index_input["query"] = {
                "start": _iso_seconds(query_start),
                "end": _iso_seconds(query_end),
            }
        elif mode == "get":
            index_input["key"] = "middle"
        elif mode == "remove":
            index_input["key"] = "start"
        elif mode == "add":
            index_input["new_entry"] = {
                "key": f"added-{i:04d}",
                "extent": {
                    "start": _iso_seconds(origin + timedelta(seconds=5)),
                    "end": _iso_seconds(origin + timedelta(seconds=25)),
                },
                "value": f"added-{i:04d}",
            }
        generated.append(
            {
                "case_id": f"generated-{seed}-temporal-index-{i:04d}",
                "operation": "temporal.index.query",
                "input": index_input,
                "comparison": {"mode": "exact"},
            }
        )

    # Fifteenth deterministic family: TemporalVersion identity and history selection.
    # The family is built from the actual Python reference objects and does not
    # consume or alter the random streams used by any previously accepted family.
    def generated_version(
        record_key: str,
        value: Any,
        valid_start: datetime,
        valid_end: datetime | None,
        transaction_start: datetime,
        transaction_end: datetime | None,
    ) -> dict[str, Any]:
        return _temporal_version_dict(
            TemporalVersion.create(
                record_key,
                value,
                valid_time=TemporalExtent(start=valid_start, end=valid_end),
                transaction_time=TemporalExtent(start=transaction_start, end=transaction_end),
            )
        )

    for i in range(count):
        origin = base + timedelta(seconds=i * 100_000)
        record_key = f"asset-{i % 5:02d}"
        first = generated_version(
            record_key,
            {"revision": i, "slot": "first"},
            origin - timedelta(seconds=20),
            origin + timedelta(seconds=300),
            origin - timedelta(seconds=30),
            origin + timedelta(seconds=40),
        )
        second = generated_version(
            record_key,
            {"revision": i + 10_000, "slot": "second"},
            origin + timedelta(seconds=100),
            None,
            origin + timedelta(seconds=40),
            None,
        )
        other = generated_version(
            f"asset-other-{i:04d}",
            {"revision": i, "slot": "other"},
            origin - timedelta(seconds=20),
            origin + timedelta(seconds=300),
            origin - timedelta(seconds=10),
            None,
        )
        mode = ("create", "all", "get", "as_of", "latest_known", "add")[i % 6]
        if mode == "create":
            version_payload = dict(first)
            version_payload.pop("version_id")
            history_input: dict[str, Any] = {
                "mode": "create",
                "version": version_payload,
            }
        elif mode == "all":
            history_input = {"mode": "all", "versions": [second, first, other]}
        elif mode == "get":
            history_input = {
                "mode": "get",
                "versions": [first, second, other],
                "version_id": second["version_id"],
            }
        elif mode == "as_of":
            history_input = {
                "mode": "as_of",
                "versions": [first, second, other],
                "valid_at": _iso_seconds(origin + timedelta(seconds=50)),
                "transaction_at": _iso_seconds(origin + timedelta(seconds=20)),
            }
        elif mode == "latest_known":
            history_input = {
                "mode": "latest_known",
                "versions": [first, second, other],
                "record_key": record_key,
                "transaction_at": _iso_seconds(origin + timedelta(seconds=80)),
            }
        else:
            history_input = {
                "mode": "add",
                "versions": [first, other],
                "new_version": second,
            }
        generated.append(
            {
                "case_id": f"generated-{seed}-temporal-history-{i:04d}",
                "operation": "temporal.history.query",
                "input": history_input,
                "comparison": {"mode": "exact"},
            }
        )

    # Sixteenth family: bounded weighted static shortest paths. Its isolated RNG
    # keeps all earlier generated case IDs and values stable.
    shortest_rng = random.Random(seed ^ 0x5A071E57)
    for i in range(count):
        shortest_nodes = [f"p{i:03d}-n{j}" for j in range(7)]
        shortest_edges: list[list[object]] = []
        for left in shortest_nodes:
            shortest_edges.extend(
                [
                    left,
                    right,
                    shortest_rng.randrange(0, 21) / 2.0,
                ]
                for right in shortest_nodes
                if left != right and shortest_rng.random() < 0.24
            )
        generated.append(
            {
                "case_id": f"generated-{seed}-graph-shortest-path-{i:04d}",
                "operation": "graph.static.shortest_path",
                "input": {
                    "nodes": shortest_nodes,
                    "edges": shortest_edges,
                    "source": shortest_nodes[shortest_rng.randrange(len(shortest_nodes))],
                    "target": shortest_nodes[shortest_rng.randrange(len(shortest_nodes))],
                },
                "comparison": {"mode": "exact"},
            }
        )

    # Seventeenth family: valid-time graph snapshots. Keep its RNG independent.
    snapshot_rng = random.Random(seed ^ 0x7E6F5A90)
    for i in range(count):
        origin = base + timedelta(seconds=i * 10_000)
        at = origin + timedelta(seconds=10)
        nodes = [f"s{i:03d}-n{j}" for j in range(5)]
        relationships = []
        for j in range(7):
            start_tick = snapshot_rng.randrange(0, 20)
            end_tick = start_tick + snapshot_rng.randrange(1, 15)
            relationships.append(
                {
                    "id": f"s{i:03d}-r{j}",
                    "source": nodes[snapshot_rng.randrange(len(nodes))],
                    "target": nodes[snapshot_rng.randrange(len(nodes))],
                    "valid_start": _iso_seconds(origin + timedelta(seconds=start_tick)),
                    "valid_end": _iso_seconds(origin + timedelta(seconds=end_tick)),
                }
            )
        generated.append(
            {
                "case_id": f"generated-{seed}-temporal-graph-snapshot-{i:04d}",
                "operation": "temporal.graph.snapshot",
                "input": {"at": _iso_seconds(at), "nodes": nodes, "relationships": relationships},
                "comparison": {"mode": "exact"},
            }
        )

    return generated


def _compare_values(
    case: dict[str, Any], left: Any, right: Any, *, labels: tuple[str, str]
) -> str | None:
    mode = case["comparison"]["mode"]
    if mode == "exact":
        if left == right:
            return None
        return f"exact mismatch: {labels[0]}={left!r}, {labels[1]}={right!r}"

    abs_tol = float(case["comparison"].get("absolute_tolerance", 0.0))
    rel_tol = float(case["comparison"].get("relative_tolerance", 0.0))
    if mode == "numeric":
        try:
            pairs = [(float(left), float(right))]
        except (TypeError, ValueError) as exc:
            return (
                f"numeric comparator received non-numeric result: {exc}; "
                f"{labels[0]}={left!r}, {labels[1]}={right!r}"
            )
    else:
        if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
            return f"vector shape mismatch: {labels[0]}={left!r}, {labels[1]}={right!r}"
        try:
            pairs = [(float(a), float(b)) for a, b in zip(left, right, strict=True)]
        except (TypeError, ValueError) as exc:
            return f"vector comparator received non-numeric item: {exc}"

    for index, (a, b) in enumerate(pairs):
        if not math.isfinite(a) or not math.isfinite(b):
            return (
                f"non-finite numerical result at component {index}: "
                f"{labels[0]}={a}, {labels[1]}={b}"
            )
        allowed = abs_tol + rel_tol * abs(a)
        if abs(a - b) > allowed:
            return (
                f"tolerance mismatch at component {index}: {labels[0]}={a:.17g}, "
                f"{labels[1]}={b:.17g}, delta={abs(a - b):.17g}, allowed={allowed:.17g}"
            )
    return None


def _compare(case: dict[str, Any], reference: dict[str, Any], native: dict[str, Any]) -> str | None:
    expected_error = case.get("expected_error")
    if expected_error is not None:
        if reference.get("ok") is not False:
            return f"expected Python error {expected_error!r}, got success"
        if native.get("ok") is not False:
            return f"expected Rust error {expected_error!r}, got success"
        ref_category = reference.get("error", {}).get("category")
        rust_category = native.get("error", {}).get("category")
        if ref_category != expected_error or rust_category != expected_error:
            return (
                f"error category mismatch: expected={expected_error!r}, "
                f"Python={ref_category!r}, Rust={rust_category!r}; "
                f"Python error={reference.get('error')}; Rust error={native.get('error')}"
            )
        return None

    if reference.get("ok") is not True or native.get("ok") is not True:
        return f"unexpected error: Python={reference.get('error')}; Rust={native.get('error')}"

    left, right = reference.get("result"), native.get("result")
    if "expected_result" in case:
        expected = case["expected_result"]
        oracle_mismatch = _compare_values(case, left, expected, labels=("Python", "expected"))
        if oracle_mismatch is not None:
            return f"Python oracle mismatch: {oracle_mismatch}"
        oracle_mismatch = _compare_values(case, right, expected, labels=("Rust", "expected"))
        if oracle_mismatch is not None:
            return f"Rust oracle mismatch: {oracle_mismatch}"
    return _compare_values(case, left, right, labels=("Python", "Rust"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases-dir", type=Path, default=ROOT / "data/contracts/differential/cases"
    )
    parser.add_argument(
        "--generated-count",
        type=int,
        default=64,
        help="deterministic cases per generated family; 0 disables generation",
    )
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    if not 0 <= args.generated_count <= 10_000:
        parser.error("--generated-count must be between 0 and 10000")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        cases = load_cases(args.cases_dir)
        generated = generate_cases(args.generated_count, args.seed)
        seen = {case["case_id"] for case in cases}
        duplicate_generated = seen.intersection(case["case_id"] for case in generated)
        if duplicate_generated:
            raise ValueError(
                f"generated cases collide with fixture IDs: {sorted(duplicate_generated)[:3]}"
            )
        cases.extend(generated)
    except Exception as error:  # malformed fixtures must fail with a clear report.
        print(f"ERROR: differential case validation failed: {error}", file=sys.stderr)
        return 2

    command_text = os.environ.get("QEDTY_DIFFERENTIAL_RUST_COMMAND")
    command = shlex.split(command_text) if command_text else DEFAULT_RUST_COMMAND
    requests = [
        {"case_id": case["case_id"], "operation": case["operation"], "input": case["input"]}
        for case in cases
    ]
    payload = "".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
        for item in requests
    )
    try:
        process = subprocess.run(
            command,
            input=payload,
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=args.timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"ERROR: could not execute Rust differential runner: {error}", file=sys.stderr)
        print(f"Command: {shlex.join(command)}", file=sys.stderr)
        return 2

    if process.returncode != 0:
        print(f"ERROR: Rust runner exited {process.returncode}", file=sys.stderr)
        if process.stderr:
            print(process.stderr[-12000:], file=sys.stderr)
        return 2
    responses: list[dict[str, Any]] = []
    for line_number, line in enumerate(process.stdout.splitlines(), start=1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            print(
                f"ERROR: Rust runner emitted non-JSON stdout on line {line_number}: "
                f"{line!r} ({error})",
                file=sys.stderr,
            )
            if process.stderr:
                print(process.stderr[-6000:], file=sys.stderr)
            return 2
        if not isinstance(item, dict):
            print(f"ERROR: Rust response line {line_number} must be a JSON object", file=sys.stderr)
            return 2
        if not isinstance(item.get("ok"), bool):
            print(
                f"ERROR: Rust response line {line_number} lacks boolean `ok`",
                file=sys.stderr,
            )
            return 2
        if item["ok"] and "result" not in item:
            print(
                f"ERROR: Rust success response line {line_number} lacks `result`",
                file=sys.stderr,
            )
            return 2
        if not item["ok"]:
            error = item.get("error")
            if not isinstance(error, dict) or not isinstance(error.get("category"), str):
                print(
                    f"ERROR: Rust error response line {line_number} lacks an error category",
                    file=sys.stderr,
                )
                return 2
        responses.append(item)
    if len(responses) != len(cases):
        print(
            f"ERROR: protocol response count mismatch: cases={len(cases)}, "
            f"Rust responses={len(responses)}",
            file=sys.stderr,
        )
        if process.stderr:
            print(process.stderr[-6000:], file=sys.stderr)
        return 2

    failures: list[tuple[str, str]] = []
    passed = 0
    operation_totals: dict[str, list[int]] = {}
    for case, response in zip(cases, responses, strict=True):
        case_id = case["case_id"]
        operation_totals.setdefault(case["operation"], [0, 0])
        operation_totals[case["operation"]][1] += 1
        if response.get("case_id") != case_id:
            failure = (
                f"protocol case_id mismatch: expected {case_id!r}, got {response.get('case_id')!r}"
            )
        else:
            reference = evaluate_reference(case["operation"], case["input"])
            failure = _compare(case, reference, response)
        if failure is None:
            passed += 1
            operation_totals[case["operation"]][0] += 1
        else:
            failures.append((case_id, failure))
            print(f"FAIL {case_id}: {failure}", file=sys.stderr)

    print(
        f"QEDTY Python–Rust differential result: {passed}/{len(cases)} cases passed; "
        f"seed={args.seed}; generated_per_family={args.generated_count}"
    )
    for operation, (ok_count, total) in sorted(operation_totals.items()):
        print(f"  {operation}: {ok_count}/{total}")
    if failures:
        print(
            f"FAILED: {len(failures)} mismatch(es). "
            "Promote each confirmed mismatch to a fixed regression case.",
            file=sys.stderr,
        )
        return 1
    print(
        "PASS: no unexpected skips; Python and Rust matched under each case's "
        "declared comparison contract."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
