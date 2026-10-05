"""Deterministic structural-impact prioritization for Seraph findings.

The ranker does not estimate a causal probability.  It combines explicit or
static-graph-inferred structural impact data with bounded remediation effort to
produce a deterministic priority order and an auditable fix plan.

Semantic adjustments are permitted only when qualifying impact evidence is not
available.  This prevents a semantic heuristic from silently rewriting an
already-assessed structural impact measurement/inference.
"""

from __future__ import annotations

import logging
import math

from dataclasses import dataclass
from typing import Any, ClassVar

from seraph.intelligence.impact import ImpactAssessmentEngine
from seraph.sources.repository.scanners.base import BlastRadius, Finding, ScanContext, Severity
from seraph.intelligence.ufic.semantics import SemanticEngine


logger = logging.getLogger(__name__)


@dataclass
class CausalScore:
    """Auditable deterministic prioritization record."""

    blast_radius_reduction: float = 0.0
    fix_effort_minutes: int = 10
    roi_score: float = 0.0
    rank: int = 0
    has_real_data: bool = False
    semantic_reason: str = ""
    impact_provenance: str = "UNKNOWN"
    evidence_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "blast_radius_reduction": round(self.blast_radius_reduction, 4),
            "fix_effort_minutes": self.fix_effort_minutes,
            "roi_score": round(self.roi_score, 4),
            "rank": self.rank,
            "has_real_data": self.has_real_data,
            "semantic_reason": self.semantic_reason,
            "impact_provenance": self.impact_provenance,
            "evidence_count": self.evidence_count,
            "score_type": "structural-impact-priority",
            "semantics": "static structural exposure reduction per remediation effort",
            "causal_probability_claimed": False,
            "priority_model": "structural-impact-per-remediation-effort/v3",
            "priority_unit": "impact_reduction_points_per_fix_hour",
            # R20 canonical compatibility keys retained for existing gate and API consumers.
            "priority_model_version": "2.3.0",
            "roi_units": "structural-impact-points-per-hour",
        }


class CausalRanker:
    """Rank findings by structural impact reduction divided by fix effort."""

    version = "2.3.0"

    FIX_TIME_ESTIMATES: ClassVar[dict[str, int]] = {
        "secret": 5,  # nosec B105
        "vulnerability": 15,
        "policy": 3,
        "pattern": 10,
        "iac": 15,
        "container": 20,
    }

    PROVENANCE_ORDER: ClassVar[dict[str, int]] = {
        "UNKNOWN": 0,
        "ESTIMATED": 1,
        "ASSERTED_ASSESSED": 2,
        "INFERRED": 3,
        "MEASURED": 4,
    }
    VALID_PROVENANCE: ClassVar[frozenset[str]] = frozenset(PROVENANCE_ORDER)

    def __init__(
        self,
        team_behavior: dict[str, Any] | None = None,
        impact_engine: ImpactAssessmentEngine | None = None,
    ) -> None:
        self.team_behavior = dict(team_behavior or {})
        self.semantic_engine = SemanticEngine()
        self.impact_engine = impact_engine or ImpactAssessmentEngine()

    def rank(
        self,
        findings: list[Finding],
        *,
        context: ScanContext | None = None,
        ontology: Any | None = None,
    ) -> list[Finding]:
        """Enrich and deterministically rank findings.

        When a ScanContext is supplied, repository-local structural impact is
        refreshed from the current working tree before ranking.  Ontology is
        accepted as the scheduler integration handle; the authoritative impact
        evidence lives on the Finding and is subsequently serialized into the
        ontology by Scheduler.
        """
        del ontology

        if not findings:
            return findings

        if context is not None:
            # A scan must not consume a stale repository graph from a prior run.
            self.impact_engine.assess_findings(findings, context, force_refresh=True)

        scored = [(finding, self._compute_causal_score(finding)) for finding in findings]
        scored.sort(
            key=lambda pair: (
                -pair[1].roi_score,
                -pair[1].blast_radius_reduction,
                -self._severity_weight(pair[0]),
                -self._provenance_rank(pair[1].impact_provenance),
                str(getattr(pair[0], "id", "")),
                str(getattr(pair[0], "file", "")),
                self._safe_line(pair[0]),
            )
        )

        for rank_number, (finding, score) in enumerate(scored, start=1):
            score.rank = rank_number
            self._set(finding, "causal_rank", rank_number)
            self._ensure_blast_radius(finding, score)
            self._ensure_effective_severity(finding)
            self._metadata(finding)["causal_score"] = score.to_dict()

        return [finding for finding, _ in scored]

    def _compute_causal_score(self, finding: Finding) -> CausalScore:
        category = self._category(finding)
        effort = self.FIX_TIME_ESTIMATES.get(category, 15)

        if getattr(finding, "fix_available", False) and getattr(finding, "fix_command", None):
            effort = max(effort - 2, 1)

        effort = self._team_adjusted_effort(finding, effort)

        if bool(getattr(finding, "is_in_test", False)):
            return CausalScore(
                blast_radius_reduction=0.0,
                fix_effort_minutes=effort,
                roi_score=0.0,
                has_real_data=False,
                semantic_reason="non-production test context",
                impact_provenance="UNKNOWN",
                evidence_count=0,
            )

        has_data, reduction, provenance, evidence_count = self._blast_data(finding)
        semantic_reason = ""

        if not has_data:
            reduction = self._estimate_reduction(self._severity(finding))
            provenance = "ESTIMATED"

            # Semantic context is a bounded heuristic fallback only.  It must
            # never rewrite qualifying assessed/inferred/measured impact data.
            metadata = self._metadata(finding)
            rule_id = (
                metadata.get("rule_id")
                or getattr(finding, "rule_id", "")
                or getattr(finding, "title", "")
            )
            language = str(metadata.get("language", "unknown"))
            evidence_context = str(
                getattr(finding, "evidence", "") or getattr(finding, "description", "") or ""
            )
            try:
                adjustment = self.semantic_engine.get_semantic_adjustment(
                    str(rule_id),
                    language,
                    str(getattr(finding, "file", "")),
                    evidence_context,
                )
                multiplier = _bounded(adjustment.get("blast_radius_multiplier", 1.0), 0.5, 1.5)
                reduction = _bounded(reduction * multiplier, 0.0, 100.0)
                semantic_reason = str(adjustment.get("reason", ""))
            except Exception as exc:
                logger.debug("semantic adjustment unavailable: %s", exc)

        effort_hours = max(effort / 60.0, 1.0 / 60.0)
        roi = reduction / effort_hours

        return CausalScore(
            blast_radius_reduction=round(reduction, 4),
            fix_effort_minutes=effort,
            roi_score=round(roi, 4),
            has_real_data=has_data,
            semantic_reason=semantic_reason,
            impact_provenance=provenance,
            evidence_count=evidence_count,
        )

    def _ensure_blast_radius(self, finding: Finding, score: CausalScore) -> None:
        existing = getattr(finding, "blast_radius", None)
        if existing is None:
            self._set(
                finding,
                "blast_radius",
                {
                    "affected_resources": [],
                    "affected_services": [],
                    "data_at_risk": [],
                    "blast_radius_score": score.blast_radius_reduction,
                    "reduction_if_fixed": score.blast_radius_reduction,
                    "is_assessed": False,
                    "causal_path": [],
                    "provenance": "ESTIMATED",
                    "evidence": [],
                    "assessment_method": "heuristic_severity_estimate",
                    "caveats": ["static structural estimate; not measured business impact"],
                },
            )
            return

        self._normalize_existing_blast(existing)

        # Preserve qualifying assessed/inferred/measured structural evidence.
        if self._is_assessed(existing):
            return

        # An unassessed scanner-provided blast object may still contain useful
        # context.  Keep that context but make the actual ranking score explicit.
        if isinstance(existing, BlastRadius):
            existing.blast_radius_score = _bounded(score.blast_radius_reduction, 0.0, 100.0)
            existing.reduction_if_fixed = _bounded(score.blast_radius_reduction, 0.0, 100.0)
            existing.provenance = "ESTIMATED"
            existing.is_assessed = False
            return

        if isinstance(existing, dict):
            existing["blast_radius_score"] = _bounded(score.blast_radius_reduction, 0.0, 100.0)
            existing["reduction_if_fixed"] = _bounded(score.blast_radius_reduction, 0.0, 100.0)
            existing["is_assessed"] = False
            existing["provenance"] = "ESTIMATED"
            existing.setdefault("evidence", [])
            existing.setdefault("causal_path", [])
            existing.setdefault("assessment_method", "heuristic_severity_estimate")
            return

        self._set(
            finding,
            "blast_radius",
            {
                "affected_resources": [],
                "affected_services": [],
                "data_at_risk": [],
                "blast_radius_score": score.blast_radius_reduction,
                "reduction_if_fixed": score.blast_radius_reduction,
                "is_assessed": False,
                "causal_path": [],
                "provenance": "ESTIMATED",
                "evidence": [],
                "assessment_method": "heuristic_severity_estimate",
            },
        )

    @classmethod
    def _normalize_existing_blast(cls, blast: Any) -> None:
        if isinstance(blast, BlastRadius):
            provenance = str(blast.provenance or "UNKNOWN").upper()
            evidence = blast.evidence if isinstance(blast.evidence, list) else []
            if provenance not in cls.VALID_PROVENANCE or (blast.is_assessed and not evidence):
                blast.provenance = "ESTIMATED"
                blast.is_assessed = False
            elif provenance in {"UNKNOWN", "ESTIMATED"}:
                blast.is_assessed = False
            blast.blast_radius_score = _bounded(blast.blast_radius_score, 0.0, 100.0)
            blast.reduction_if_fixed = _bounded(blast.reduction_if_fixed, 0.0, 100.0)
            return

        if isinstance(blast, dict):
            provenance = str(blast.get("provenance") or "UNKNOWN").upper()
            ev_raw = blast.get("evidence")
            evidence_list: list[Any] = ev_raw if isinstance(ev_raw, list) else []
            blast["evidence"] = evidence_list
            if provenance not in cls.VALID_PROVENANCE or (
                blast.get("is_assessed") and not evidence_list
            ):
                blast["provenance"] = "ESTIMATED"
                blast["is_assessed"] = False
            elif provenance in {"UNKNOWN", "ESTIMATED"}:
                blast["is_assessed"] = False
            blast["blast_radius_score"] = _bounded(blast.get("blast_radius_score"), 0.0, 100.0)
            blast["reduction_if_fixed"] = _bounded(blast.get("reduction_if_fixed"), 0.0, 100.0)

    @classmethod
    def _blast_data(cls, finding: Finding) -> tuple[bool, float, str, int]:
        blast = getattr(finding, "blast_radius", None)
        if blast is None:
            return False, 0.0, "UNKNOWN", 0

        cls._normalize_existing_blast(blast)

        if isinstance(blast, BlastRadius):
            evidence = blast.evidence if isinstance(blast.evidence, list) else []
            provenance = str(blast.provenance or "UNKNOWN").upper()
            assessed = bool(blast.is_assessed)
            if (
                assessed
                and evidence
                and provenance in {"INFERRED", "MEASURED", "ASSERTED_ASSESSED"}
            ):
                return (
                    True,
                    _bounded(blast.reduction_if_fixed, 0.0, 100.0),
                    provenance,
                    len(evidence),
                )
            return False, 0.0, provenance, len(evidence)

        if isinstance(blast, dict):
            ev_raw = blast.get("evidence")
            evidence_list = ev_raw if isinstance(ev_raw, list) else []
            provenance = str(blast.get("provenance") or "UNKNOWN").upper()
            assessed = bool(blast.get("is_assessed"))
            if (
                assessed
                and evidence_list
                and provenance in {"INFERRED", "MEASURED", "ASSERTED_ASSESSED"}
            ):
                return (
                    True,
                    _bounded(blast.get("reduction_if_fixed"), 0.0, 100.0),
                    provenance,
                    len(evidence_list),
                )
            return False, 0.0, provenance, len(evidence_list)

        return False, 0.0, "UNKNOWN", 0

    @staticmethod
    def _is_assessed(blast: Any) -> bool:
        if isinstance(blast, BlastRadius):
            return bool(
                blast.is_assessed
                and isinstance(blast.evidence, list)
                and blast.evidence
                and str(blast.provenance or "UNKNOWN").upper()
                in {"INFERRED", "MEASURED", "ASSERTED_ASSESSED"}
            )
        if isinstance(blast, dict):
            return bool(
                blast.get("is_assessed")
                and isinstance(blast.get("evidence"), list)
                and blast.get("evidence")
                and str(blast.get("provenance") or "UNKNOWN").upper()
                in {"INFERRED", "MEASURED", "ASSERTED_ASSESSED"}
            )
        return False

    def get_fix_plan(
        self,
        findings: list[Finding],
        max_effort_minutes: int = 30,
        *,
        context: ScanContext | None = None,
    ) -> dict[str, Any]:
        ranked = self.rank(findings, context=context)
        steps: list[dict[str, Any]] = []
        total_effort = 0
        remaining_risk = 1.0

        for finding in ranked:
            if bool(getattr(finding, "is_in_test", False)):
                continue

            score_data = self._metadata(finding).get("causal_score", {})
            if not isinstance(score_data, dict):
                continue

            try:
                effort = int(score_data.get("fix_effort_minutes", 10) or 10)
            except (TypeError, ValueError):
                effort = 10
            effort = max(1, effort)
            if total_effort + effort > max_effort_minutes:
                continue

            reduction = _bounded(score_data.get("blast_radius_reduction", 0.0), 0.0, 100.0) / 100.0
            if reduction <= 0.0:
                continue

            before = remaining_risk
            remaining_risk *= 1.0 - reduction
            steps.append(
                {
                    "finding_id": str(getattr(finding, "id", "")),
                    "rank": getattr(finding, "causal_rank", None),
                    "severity": self._severity(finding).value,
                    "effort_minutes": effort,
                    "risk_reduction": round(reduction, 6),
                    "remaining_risk_before": round(before, 6),
                    "remaining_risk_after": round(remaining_risk, 6),
                    "roi_score": _numeric(score_data.get("roi_score", 0.0)),
                    "impact_provenance": score_data.get("impact_provenance", "UNKNOWN"),
                    "evidence_count": int(score_data.get("evidence_count", 0) or 0),
                }
            )
            total_effort += effort

        return {
            "engine_version": self.version,
            "semantics": "static structural exposure reduction per remediation effort",
            "steps": steps,
            "findings_addressed": len(steps),
            "cumulative_reduction": round(1.0 - remaining_risk, 6) if steps else 0.0,
            "total_effort_minutes": total_effort,
            "estimated_remaining_risk": round(remaining_risk, 6),
            "risk_reduction_math": "1 - product(1 - reduction_i)",
        }

    def get_lsp_hover_text(self, finding: Finding) -> str:
        score_data = self._metadata(finding).get("causal_score", {})
        score = score_data if isinstance(score_data, dict) else {}
        blast = getattr(finding, "blast_radius", None)
        if isinstance(blast, BlastRadius):
            br = blast.to_dict()
        elif isinstance(blast, dict):
            br = blast
        else:
            br = {}
        evidence = br.get("evidence", []) or []
        evidence_count = len(evidence) if isinstance(evidence, (list, tuple, set, dict)) else 0
        return "\n".join(
            [
                f"Seraph Guard — {getattr(finding, 'title', '')}",
                f"Severity: {self._severity(finding).value.upper()}",
                f"Priority rank: {getattr(finding, 'causal_rank', 'n/a')}",
                f"Structural impact reduction: {br.get('blast_radius_score', 0)} / 100",
                f"Impact provenance: {br.get('provenance', 'UNKNOWN')}",
                f"Evidence items: {evidence_count}",
                f"Fix effort: {score.get('fix_effort_minutes', 'n/a')} min",
                f"ROI: {score.get('roi_score', 'n/a')}",
            ]
        )

    @staticmethod
    def _metadata(finding: Finding) -> dict[str, Any]:
        metadata = getattr(finding, "metadata", None)
        if isinstance(metadata, dict):
            return metadata
        metadata = {}
        CausalRanker._set(finding, "metadata", metadata)
        return metadata

    @staticmethod
    def _safe_line(finding: Finding) -> int:
        try:
            return int(getattr(finding, "line", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _severity(finding: Finding) -> Severity:
        value = getattr(finding, "effective_severity", None) or getattr(
            finding, "severity", Severity.INFO
        )
        if isinstance(value, Severity):
            return value
        try:
            return Severity(str(getattr(value, "value", value)).lower())
        except ValueError:
            return Severity.INFO

    @staticmethod
    def _severity_weight(finding: Finding) -> int:
        return CausalRanker._severity(finding).weight

    @staticmethod
    def _category(finding: Finding) -> str:
        value = getattr(finding, "category", "vulnerability")
        return str(getattr(value, "value", value)).lower()

    @classmethod
    def _provenance_rank(cls, value: str) -> int:
        return cls.PROVENANCE_ORDER.get(str(value).upper(), 0)

    @staticmethod
    def _estimate_reduction(severity: Severity) -> float:
        return {
            Severity.CRITICAL: 70.0,
            Severity.HIGH: 50.0,
            Severity.MEDIUM: 25.0,
            Severity.LOW: 10.0,
            Severity.INFO: 3.0,
        }.get(severity, 10.0)

    def _team_adjusted_effort(self, finding: Finding, effort: int) -> int:
        meta = self.team_behavior.get(self._category(finding), {})
        try:
            multiplier = float(meta.get("effort_multiplier", 1.0))
        except (AttributeError, TypeError, ValueError):
            multiplier = 1.0
        return max(1, min(240, round(effort * multiplier)))

    @staticmethod
    def _ensure_effective_severity(finding: Finding) -> None:
        if getattr(finding, "effective_severity", None) is not None:
            return
        try:
            severity = finding.computed_effective_severity
        except (AttributeError, TypeError):
            severity = getattr(finding, "severity", Severity.INFO)
        CausalRanker._set(finding, "effective_severity", severity)

    @staticmethod
    def _set(obj: Any, name: str, value: Any) -> None:
        try:
            setattr(obj, name, value)
        except (AttributeError, TypeError):
            object.__setattr__(obj, name, value)


def _bounded(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    if not math.isfinite(number):
        return low
    return max(low, min(high, number))


def _numeric(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


__all__ = ["CausalRanker", "CausalScore"]
