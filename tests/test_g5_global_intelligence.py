from __future__ import annotations

from typing import TYPE_CHECKING

from seraph.guard.intelligence.causal import CausalRanker
from seraph.guard.intelligence.impact import ImpactAssessmentEngine
from seraph.guard.scanners.base import Category, Finding, ScanContext, Severity


if TYPE_CHECKING:
    from pathlib import Path


def _finding(path: str = "app/service.py") -> Finding:
    return Finding(
        scanner="Gate5Global",
        category=Category.VULNERABILITY,
        severity=Severity.HIGH,
        confidence=0.95,
        file=path,
        line=12,
        title="controlled global impact finding",
        description="controlled finding",
        rule_id="gate5-global",
        metadata={"language": "python", "rule_id": "gate5-global"},
    )


def test_global_impact_infers_repository_relationships(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "services").mkdir()
    (tmp_path / "app/service.py").write_text(
        "from services.store import write\n\n\ndef handler(value):\n    return write(value)\n",
        encoding="utf-8",
    )
    (tmp_path / "services/store.py").write_text(
        "import redis\n\ndef write(value):\n    return redis.Redis().set('k', value)\n",
        encoding="utf-8",
    )
    (tmp_path / "routes.py").write_text(
        "from app.service import handler\nfrom flask import Flask\napp=Flask(__name__)\n@app.post('/write')\ndef write_route():\n    return handler('x')\n",
        encoding="utf-8",
    )

    finding = _finding()
    context = ScanContext(path=str(tmp_path))
    ImpactAssessmentEngine(max_files=1000).assess_findings([finding], context)

    blast = finding.blast_radius
    assert blast is not None
    assert blast.is_assessed is True
    assert getattr(blast, "provenance", "UNKNOWN") == "INFERRED"
    assert len(blast.affected_resources) >= 2
    assert blast.data_at_risk
    assert blast.causal_path


def test_global_impact_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import sqlite3\n", encoding="utf-8")
    (tmp_path / "c.py").write_text("from a import x\n", encoding="utf-8")

    def run_once() -> tuple[tuple[str, ...], float, str]:
        f = _finding("a.py")
        ImpactAssessmentEngine(max_files=1000).assess_findings([f], ScanContext(path=str(tmp_path)))
        blast = f.blast_radius
        assert blast is not None
        return (
            tuple(blast.affected_resources),
            float(blast.blast_radius_score),
            str(blast.provenance),
        )

    assert run_once() == run_once()


def test_ranker_preserves_unassessed_without_context() -> None:
    finding = _finding("missing.py")
    ranked = CausalRanker().rank([finding])
    assert ranked[0].metadata["causal_score"]["impact_provenance"] == "ESTIMATED"
    assert finding.blast_radius is not None
    assert not finding.blast_radius["is_assessed"]
