from __future__ import annotations

import json
import sys

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from seraph.guard.deduplication import DeduplicationEngine  # noqa: E402
from seraph.guard.explanation.engine import ExplanationEngine  # noqa: E402
from seraph.guard.intelligence.causal import CausalRanker  # noqa: E402
from seraph.guard.scanners.base import BlastRadius, Category, Finding, Severity  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_causal_semantics(monkeypatch):
    """Neutralize semantic scoring without mutating global import state."""
    from seraph.guard.intelligence import causal as causal_module

    class NoOpSemanticEngine:
        def get_semantic_adjustment(self, *_args, **_kwargs):
            return {}

        def evaluate(self, *_args, **_kwargs):
            return {}

    monkeypatch.setattr(causal_module, "SemanticEngine", NoOpSemanticEngine)


def finding(category: Category = Category.VULNERABILITY) -> Finding:
    f = Finding(
        scanner="Gate5",
        category=category,
        severity=Severity.HIGH,
        confidence=0.9,
        file="src/app.py",
        line=10,
        column=2,
        title="controlled finding",
        description="Controlled evidence for the universal Gate 5 contract.",
        message="Untrusted input reaches a security-sensitive sink.",
        rule_id="CWE-78",
        metadata={"source": "request.args", "sink": "subprocess.run"},
    )
    f.blast_radius = BlastRadius(
        affected_resources=["file:src/app.py", "file:src/worker.py", "file:src/store.py"],
        affected_services=["worker"],
        data_at_risk=["data:redis"],
        blast_radius_score=64,
        reduction_if_fixed=64,
        is_assessed=True,
        causal_path=["src/app.py", "src/worker.py"],
        provenance="INFERRED",
        evidence=[
            {
                "type": "repository_graph",
                "relation": "downstream_dependent",
                "source": "file:src/app.py",
                "target": "file:src/worker.py",
                "basis": "repository graph",
            }
        ],
    )
    return f


def test_all_gate5_detection_domains_have_one_common_intelligence_contract():
    for category in (
        Category.SECRET,
        Category.VULNERABILITY,
        Category.POLICY,
        Category.PATTERN,
        Category.IAC,
        Category.CONTAINER,
    ):
        f = finding(category)
        CausalRanker().rank([f])
        report = ExplanationEngine().attach(f)
        assert report["schema"] == "seraph-explanation-v2"
        assert report["engine_version"] == "2.3.0"
        assert report["provenance"]["external_model_used"] is False
        assert report["assessment"]["is_assessed"] is True
        assert report["evidence_summary"]


def test_secret_never_reappears_in_explanation():
    secret = "SYNTHETIC_SECRET_DO_NOT_LEAK"
    f = finding(Category.SECRET)
    f.value = secret
    f.secret_value = secret
    f.message = f"secret observed: {secret}"
    report = ExplanationEngine().attach(f)
    payload = json.dumps(report, sort_keys=True)
    assert secret not in payload
    assert secret not in f.metadata["explanation_markdown"]


def test_dedup_is_deterministic_and_does_not_merge_distinct_cwe_scope():
    engine = DeduplicationEngine()
    a = {
        "id": "a",
        "file": "src/a.py",
        "line": 10,
        "column": 1,
        "rule_id": "CWE-78",
        "category": "vulnerability",
        "severity": "high",
        "scanner": "TaintScanner",
        "message": "same observation",
    }
    b = dict(a, id="b", line=11)
    c = dict(a, id="c", file="src/c.py", rule_id="CWE-89")
    first = engine.deduplicate([a, b, c])
    second = engine.deduplicate([c, b, a])
    first_ids = [row["id"] for row in first]
    second_ids = [row["id"] for row in second]
    assert len(first) == 2
    assert first_ids == second_ids
    assert any(row["rule_id"] == "CWE-89" for row in first)


def test_blast_radius_contract_and_scheduler_explanation_wiring():
    f = finding(Category.VULNERABILITY)
    f.blast_radius.api_endpoints = ["src/api.py#/run"]
    serialized = f.blast_radius.to_dict()
    assert serialized["api_endpoints"] == ["src/api.py#/run"]

    scheduler_source = (
        ROOT / "src" / "seraph" / "guard" / "orchestration" / "scheduler.py"
    ).read_text(encoding="utf-8")
    assert "from seraph.guard.explanation.engine import ExplanationEngine" in scheduler_source
    assert "context=context" in scheduler_source
    assert "ontology=self.ontology" in scheduler_source
    assert "self._explainer.enrich_findings(selected)" in scheduler_source
    assert "result.explanation_applied = bool(result.explanations)" in scheduler_source


def test_repository_graph_parses_multiple_source_families_without_repo_specific_paths():
    import tempfile

    from seraph.guard.intelligence.impact import RepositoryGraph

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        files = {
            "py/pkg/a.py": "from pkg.b import thing\n",
            "py/pkg/b.py": "def thing(): pass\n",
            "js/a.ts": 'import { b } from "./b";\n',
            "js/b.ts": "export const b = 1;\n",
            "go/a.go": 'package a\nimport "example.com/proj/b"\n',
            "go/b/b.go": "package b\n",
            "java/a.java": "package com.example;\nimport com.example.b.B;\nclass A{}\n",
            "java/b/B.java": "package com.example.b;\nclass B{}\n",
            "rust/src/lib.rs": "mod b;\n",
            "rust/src/b.rs": "pub fn x(){}\n",
            "cpp/a.cpp": '#include "b.hpp"\n',
            "cpp/b.hpp": "int x;\n",
        }
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        graph = RepositoryGraph.build(root)
        assert {
            "python",
            "javascript-typescript",
            "go",
            "jvm",
            "rust",
            "c-cpp-objectivec",
        } <= graph.parsed_families
        assert len(graph.files) == len(files)
        assert len(graph.edge_evidence) >= 3
