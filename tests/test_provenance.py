from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from qedty.evidence.provenance import ProvenanceActivity

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_VECTOR = ROOT / "data" / "contracts" / "golden-vectors" / "evidence" / "provenance.json"


def test_provenance_create() -> None:
    provenance = ProvenanceActivity.create(
        activity="demo",
        agent="qedty",
        started_at=datetime.now(UTC),
        parameters={"x": 1},
    )
    assert len(provenance.parameters_digest) == 64


def test_provenance_identity_matches_existing_golden_vector() -> None:
    vector = json.loads(PROVENANCE_VECTOR.read_text(encoding="utf-8"))
    activity = ProvenanceActivity(
        provenance_id=vector["provenance_id"],
        activity=vector["activity"],
        agent=vector["agent"],
        started_at=datetime.fromisoformat(vector["started_at"].replace("Z", "+00:00")),
        ended_at=datetime.fromisoformat(vector["ended_at"].replace("Z", "+00:00")),
        used_evidence_ids=tuple(vector["used_evidence_ids"]),
        generated_evidence_ids=tuple(vector["generated_evidence_ids"]),
        parent_ids=tuple(vector["parent_ids"]),
        software_name=vector["software_name"],
        software_version=vector["software_version"],
        parameters_digest=vector["parameters_digest"],
        metadata=vector["metadata"],
    )

    assert activity.provenance_id == "prov:42ae4810d2217dec5892239a309d0228"
    assert activity.parameters_digest == "a9e4d7de67b51056d6348813e1b93fd0fe56c22e4b58ad8e8675bacc9489046b"


def test_provenance_identity_excludes_lineage_software_and_metadata() -> None:
    started_at = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
    ended_at = started_at + timedelta(seconds=5)
    common = {
        "activity": "normalize",
        "agent": "qedty",
        "started_at": started_at,
        "ended_at": ended_at,
        "parameters": {"profile": "qedty-normalization@1"},
    }

    first = ProvenanceActivity.create(
        **common,
        used_evidence_ids=("evidence:input-a",),
        generated_evidence_ids=("evidence:output-a",),
        parent_ids=("prov:parent-a",),
        software_name="qedty",
        software_version="0.1a0",
        metadata={"run": "first"},
    )
    second = ProvenanceActivity.create(
        **common,
        used_evidence_ids=("evidence:input-b",),
        generated_evidence_ids=("evidence:output-b",),
        parent_ids=("prov:parent-b",),
        software_name="different-tool",
        software_version="9.9.9",
        metadata={"run": "second"},
    )

    assert first.provenance_id == second.provenance_id
    assert first != second


def test_provenance_identity_changes_when_an_included_input_changes() -> None:
    started_at = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
    ended_at = started_at + timedelta(seconds=5)
    common = {
        "activity": "normalize",
        "agent": "qedty",
        "started_at": started_at,
        "ended_at": ended_at,
        "parameters": {"profile": "qedty-normalization@1"},
    }
    baseline = ProvenanceActivity.create(**common)

    variants = (
        ProvenanceActivity.create(**{**common, "activity": "acquire"}),
        ProvenanceActivity.create(**{**common, "agent": "different-agent"}),
        ProvenanceActivity.create(**{**common, "started_at": started_at + timedelta(seconds=1)}),
        ProvenanceActivity.create(**{**common, "ended_at": ended_at + timedelta(seconds=1)}),
        ProvenanceActivity.create(**{**common, "parameters": {"profile": "qedty-normalization@2"}}),
    )

    assert all(variant.provenance_id != baseline.provenance_id for variant in variants)


def test_provenance_identity_normalizes_equivalent_timezone_offsets() -> None:
    utc_start = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
    offset_start = datetime.fromisoformat("2026-10-06T10:00:00+02:00")

    utc_activity = ProvenanceActivity.create(
        activity="normalize",
        agent="qedty",
        started_at=utc_start,
        parameters={"x": 1},
    )
    offset_activity = ProvenanceActivity.create(
        activity="normalize",
        agent="qedty",
        started_at=offset_start,
        parameters={"x": 1},
    )

    assert utc_activity.started_at == offset_activity.started_at
    assert utc_activity.provenance_id == offset_activity.provenance_id
