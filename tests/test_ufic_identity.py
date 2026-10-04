from __future__ import annotations

import os
import subprocess
import sys

from pathlib import Path

from seraph.ufic.classifier import OmissionDetector
from seraph.ufic.engine import UFICEngine, UFICFinding
from seraph.ufic.identity import (
    stable_ufic_api_id,
    stable_ufic_finding_id,
    stable_ufic_object_id,
)


ROOT = Path(__file__).resolve().parents[1]


def _subprocess_ids(seed: str) -> list[str]:
    code = """
from seraph.ufic.identity import stable_ufic_api_id, stable_ufic_finding_id, stable_ufic_object_id
print(stable_ufic_finding_id(rule_id='missing_auth', file_path='./a\\\\b.py', line='7', column='2'))
print(stable_ufic_object_id(rule_id='missing_auth', file_path='./a\\\\b.py', line='7', column='2'))
print(stable_ufic_api_id(file_path='./routes.py', route_signature='@app.get(\"/users\")', route_type='http_route', framework='fastapi'))
"""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = seed
    env["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.splitlines()


def test_same_inputs_produce_same_ids() -> None:
    assert stable_ufic_finding_id(
        rule_id="missing_auth", file_path="a.py", line=10, column=2
    ) == stable_ufic_finding_id(rule_id="missing_auth", file_path="a.py", line=10, column=2)
    assert stable_ufic_object_id(
        rule_id="missing_auth", file_path="a.py", line=10, column=2
    ) == stable_ufic_object_id(rule_id="missing_auth", file_path="a.py", line=10, column=2)
    assert stable_ufic_api_id(
        file_path="routes.py",
        route_signature="@app.get('/users')",
        route_type="http_route",
        framework="fastapi",
    ) == stable_ufic_api_id(
        file_path="routes.py",
        route_signature="@app.get('/users')",
        route_type="http_route",
        framework="fastapi",
    )


def test_identity_changes_when_identity_components_change() -> None:
    base = stable_ufic_finding_id(rule_id="r1", file_path="a.py", line=1, column=1)
    assert base != stable_ufic_finding_id(rule_id="r2", file_path="a.py", line=1, column=1)
    assert base != stable_ufic_finding_id(rule_id="r1", file_path="b.py", line=1, column=1)
    assert base != stable_ufic_finding_id(rule_id="r1", file_path="a.py", line=2, column=1)
    assert base != stable_ufic_finding_id(rule_id="r1", file_path="a.py", line=1, column=2)


def test_path_normalization_is_logical_and_deterministic() -> None:
    assert stable_ufic_finding_id(
        rule_id="r1", file_path="./foo\\bar.py", line=7, column=0
    ) == stable_ufic_finding_id(rule_id="r1", file_path="foo/bar.py", line=7, column=0)


def test_ids_are_stable_across_python_hash_seeds() -> None:
    assert _subprocess_ids("1") == _subprocess_ids("987654")


def test_ufic_finding_uses_stable_identity_helper() -> None:
    finding = UFICFinding(rule_id="missing_auth", file="routes.py", line=19, column=3)
    assert finding.id == stable_ufic_finding_id(
        rule_id="missing_auth",
        file_path="routes.py",
        line=19,
        column=3,
    )


def test_engine_omission_conversion_uses_stable_identity() -> None:
    omission = {
        "rule_id": "missing_auth",
        "title": "Missing Authentication",
        "file": "routes.py",
        "line": 19,
        "column": 3,
        "severity": "critical",
        "confidence_interval": (0.65, 0.95),
        "reason": "API route lacks authentication",
        "omission_type": "absence_of_control",
        "blast_radius_multiplier": 1.3,
    }
    finding = UFICEngine._omission_to_finding(omission, {})
    assert finding.id == stable_ufic_finding_id(
        rule_id="missing_auth",
        file_path="routes.py",
        line=19,
        column=3,
    )


class _FakeOntology:
    def __init__(self) -> None:
        self.objects: list[dict] = []
        self.links: list[dict] = []

    def add_object(self, obj: dict) -> None:
        self.objects.append(obj)

    def add_link(self, link: dict) -> None:
        self.links.append(link)


def test_ontology_omission_identity_and_link_target_are_stable() -> None:
    ontology = _FakeOntology()
    detector = OmissionDetector(ontology=ontology)
    omission = {
        "rule_id": "missing_rls",
        "file": "models/data.py",
        "line": 7,
        "column": 1,
        "confidence_interval": (0.50, 0.85),
    }
    detector._write_omissions_to_ontology([omission])

    assert len(ontology.objects) == 1
    assert len(ontology.links) == 1
    expected = stable_ufic_object_id(
        rule_id="missing_rls",
        file_path="models/data.py",
        line=7,
        column=1,
    )
    assert ontology.objects[0]["id"] == expected
    assert ontology.links[0]["target"] == expected


def test_api_identity_is_distinct_for_endpoint_identity_components() -> None:
    base = stable_ufic_api_id(
        file_path="routes.py",
        route_signature="@app.get('/users')",
        route_type="http_route",
        framework="fastapi",
    )
    assert base != stable_ufic_api_id(
        file_path="routes.py",
        route_signature="@app.post('/users')",
        route_type="http_route",
        framework="fastapi",
    )
    assert base != stable_ufic_api_id(
        file_path="routes.py",
        route_signature="@app.get('/users')",
        route_type="django_url",
        framework="django",
    )


def test_production_ufic_sources_do_not_use_process_randomized_hash_for_identity() -> None:
    source_dir = ROOT / "src" / "seraph" / "ufic"
    for name in ("engine.py", "classifier.py", "topology.py"):
        source = (source_dir / name).read_text(encoding="utf-8")
        identity_lines = [
            line
            for line in source.splitlines()
            if "hash(" in line and not line.lstrip().startswith("#")
        ]
        assert not identity_lines, (
            f"process-randomized hash() remains in {name}: {identity_lines!r}"
        )
