"""seraph.intelligence.ufic.findings — UFIC Finding Types & Data Models

Defines the core data structures for UFIC (Unified Framework Intelligence
& Classification) findings, including ontology-native representations.

Moats: Ontology Compounding, Conformal Truth
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seraph.sources.repository.scanners.base import Finding, Severity


@dataclass
class UFICFinding(Finding):
    """v2.0 UFIC-enriched finding.

    Extends base Finding with:
    - Intent classification (production, test, docs, etc.)
    - Blast radius multiplier (0.0 = suppress, 1.3 = escalate)
    - Conformal confidence interval [lower, upper] with mathematical guarantee
    - Causal impact annotations for the Digital Twin
    - Ontology-native objects and links
    - Omission flag (true = this finding represents a *missing* control)
    """

    # ── Intent & Context ──
    intent: str = "production"
    language: str = "unknown"
    framework: str = ""

    # ── Conformal Truth ──
    confidence_interval: tuple[float, float] = (0.0, 1.0)
    confidence_level: float = 0.95

    # ── Blast Radius & Causal Impact ──
    blast_radius_multiplier: float = 1.0
    causal_impact: dict[str, Any] = field(default_factory=dict)

    # ── Action Recommendation ──
    recommended_action: str = "none"  # none | suppress | investigate | escalate

    # ── Omission Detection ──
    is_omission: bool = False
    omission_type: str = ""  # absence_of_control | unused_asset | misconfiguration

    # ── Ontology Bridge ──
    ontology_objects: list[dict[str, Any]] = field(default_factory=list)
    ontology_links: list[dict[str, Any]] = field(default_factory=list)

    # ── Semantic Context ──
    semantic_reason: str = ""
    suppression_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UFICFinding:
        """Deserialize from dict."""
        sev_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return cls(
            id=data.get("id", ""),
            rule_id=data.get("rule_id", ""),
            rule_name=data.get("rule_name", ""),
            title=data.get("title", ""),
            severity=sev_map.get(data.get("severity", "medium").lower(), Severity.MEDIUM),
            message=data.get("message", ""),
            description=data.get("description", ""),
            file=data.get("file", ""),
            path=data.get("file", ""),
            line=data.get("line", 0),
            column=data.get("column", 0),
            category=data.get("category", ""),
            scanner=data.get("scanner", ""),
            confidence=data.get("confidence", 0.0),
            conformal_lower=data.get("conformal_lower"),
            conformal_upper=data.get("conformal_upper"),
            blast_radius=data.get("blast_radius"),
            fix_available=data.get("fix_available", False),
            fix_command=data.get("fix_command", ""),
            cve=data.get("cve", ""),
            tags=data.get("tags", []),
            intent=data.get("intent", "production"),
            language=data.get("language", "unknown"),
            framework=data.get("framework", ""),
            confidence_interval=tuple(data.get("confidence_interval", [0.0, 1.0])),
            confidence_level=data.get("confidence_level", 0.95),
            blast_radius_multiplier=data.get("blast_radius_multiplier", 1.0),
            causal_impact=data.get("causal_impact", {}),
            recommended_action=data.get("recommended_action", "none"),
            is_omission=data.get("is_omission", False),
            omission_type=data.get("omission_type", ""),
            semantic_reason=data.get("semantic_reason", ""),
            suppression_reason=data.get("suppression_reason"),
        )
