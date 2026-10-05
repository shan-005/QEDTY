"""Deterministic, evidence-backed explanations for Seraph findings.

The explanation layer deliberately does not call an LLM or any remote model.
It turns fields already established by scanners and cognition engines into a
stable, auditable explanation record.  It must never invent evidence, impact,
severity, remediation, or confidence that is absent from the finding.
"""

from __future__ import annotations

import math

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from seraph.sources.repository.scanners.base import Finding, Severity


EXPLANATION_SCHEMA = "seraph-explanation-v2"
EXPLANATION_ENGINE_VERSION = "2.3.0"
SCHEMA = EXPLANATION_SCHEMA
ENGINE_VERSION = EXPLANATION_ENGINE_VERSION
_MAX_EVIDENCE = 24
_MAX_FLOW_STEPS = 24
_MAX_RESOURCES = 40
_MAX_TEXT = 2400
_SENSITIVE_KEYS = {
    "value",
    "secret",
    "secret_value",
    "raw_secret",
    "_raw_secret",
    "token",
    "api_key",
    "password",
    "passwd",
    "credential",
    "private_key",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "client_secret",
    "bearer",
}


def _enum_value(value: Any, default: str = "") -> str:
    raw = getattr(value, "value", value)
    text = str(raw if raw is not None else default).strip()
    return text or default


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _bounded_number(value: Any, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, _finite_float(value, low)))


def _text(value: Any, default: str = "") -> str:
    result = str(value if value is not None else default).strip()
    if len(result) > _MAX_TEXT:
        return result[: _MAX_TEXT - 1].rstrip() + "…"
    return result


def _sanitize(value: Any) -> Any:
    """Redact known sensitive mapping keys before explanation rendering."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            normalized = name.lower().replace("-", "_")
            out[name] = "[REDACTED]" if normalized in _SENSITIVE_KEYS else _sanitize(item)
        return out
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    if isinstance(value, set):
        return [_sanitize(item) for item in sorted(value, key=str)]
    return value


def _redact_known_values(value: Any, secrets: set[str]) -> Any:
    """Redact exact secret values that may have been embedded in text fields.

    Finding scanners can legitimately use a matched secret in a title/message/
    description for diagnostics.  The explanation layer must not reproduce it.
    Only exact values already carried by the finding are redacted; no heuristic
    secret detector is introduced here.
    """
    if not secrets:
        return value
    if isinstance(value, str):
        redacted = value
        for secret in sorted((x for x in secrets if x), key=len, reverse=True):
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    if isinstance(value, Mapping):
        return {str(k): _redact_known_values(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_known_values(v, secrets) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact_known_values(v, secrets) for v in value)
    if isinstance(value, set):
        return {_redact_known_values(v, secrets) for v in value}
    return value


def _string_list(value: Any, limit: int = _MAX_RESOURCES) -> list[str]:
    if isinstance(value, (str, bytes)):
        values = [value]
    elif isinstance(value, set):
        values = sorted(value, key=_text)
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = _text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _finding_dict(finding: Finding | Mapping[str, Any]) -> dict[str, Any]:
    """Return the machine-safe Finding representation used by the engine."""
    known_secrets: set[str] = set()
    if isinstance(finding, Mapping):
        for key in ("value", "secret_value", "_raw_secret"):
            candidate = finding.get(key)
            if isinstance(candidate, str) and candidate:
                known_secrets.add(candidate)
        raw_mapping = _sanitize(dict(finding))
        data = raw_mapping if isinstance(raw_mapping, dict) else {}
        return cast("dict[str, Any]", _redact_known_values(data, known_secrets))

    for key in ("value", "secret_value", "_raw_secret"):
        try:
            candidate = getattr(finding, key, None)
        except Exception:
            candidate = None
        if isinstance(candidate, str) and candidate:
            known_secrets.add(candidate)

    raw_dict: Any = None
    try:
        serializer = getattr(finding, "to_dict", None)
        if callable(serializer):
            raw_dict = serializer()
    except Exception:
        raw_dict = None

    data = _sanitize(dict(raw_dict)) if isinstance(raw_dict, Mapping) else {}
    if not isinstance(data, dict):
        data = {}
    metadata = getattr(finding, "metadata", {})
    data.setdefault("metadata", _sanitize(metadata) if isinstance(metadata, Mapping) else {})

    for key in (
        "id",
        "rule_id",
        "rule_name",
        "scanner",
        "category",
        "severity",
        "effective_severity",
        "confidence",
        "file",
        "path",
        "source_file",
        "line",
        "column",
        "title",
        "description",
        "message",
        "evidence",
        "context",
        "file_context",
        "fix_available",
        "fix_command",
        "fix_description",
        "fix_engine",
        "remediation",
        "cve",
        "cvss_score",
        "cwe",
        "cwe_aliases",
        "conformal_lower",
        "conformal_upper",
        "conformal_confidence",
        "conformal_set",
        "causal_rank",
        "blast_radius",
    ):
        if key not in data:
            try:
                data[key] = _sanitize(getattr(finding, key, None))
            except Exception:
                data[key] = None

    for key in (
        "taint_path",
        "source_function",
        "sink_function",
        "sanitizers_hit",
        "call_depth",
        "cross_file",
    ):
        if key not in data:
            try:
                value = getattr(finding, key, None)
            except Exception:
                value = None
            if value not in (None, "", [], {}):
                data[key] = _sanitize(value)

    if not isinstance(data.get("metadata"), dict):
        data["metadata"] = {}
    return cast("dict[str, Any]", _redact_known_values(data, known_secrets))


def _blast_record(finding_data: dict[str, Any]) -> dict[str, Any]:
    raw = finding_data.get("blast_radius")
    if raw is None:
        return {
            "status": "unassessed",
            "provenance": "UNKNOWN",
            "is_assessed": False,
            "score": None,
            "reduction_if_fixed": None,
            "evidence_count": 0,
            "causal_path": [],
            "affected_resources": [],
            "affected_services": [],
            "data_at_risk": [],
            "api_endpoints": [],
            "evidence": [],
        }

    if hasattr(raw, "to_dict"):
        try:
            raw = raw.to_dict()
        except Exception:
            raw = None

    source = dict(raw) if isinstance(raw, dict) else {}
    provenance = _enum_value(source.get("provenance"), "UNKNOWN").upper()
    evidence = source.get("evidence", [])
    evidence_list = evidence if isinstance(evidence, list) else []
    assessed = (
        bool(source.get("is_assessed", False))
        and bool(evidence_list)
        and provenance in {"MEASURED", "ASSERTED_ASSESSED", "INFERRED"}
    )
    status = "assessed" if assessed else "unassessed"
    if source.get("is_assessed") and (
        not evidence_list or provenance not in {"MEASURED", "ASSERTED_ASSESSED", "INFERRED"}
    ):
        provenance = "ESTIMATED" if evidence_list else "UNKNOWN"

    return {
        "status": status,
        "provenance": provenance,
        "is_assessed": assessed,
        "score": _bounded_number(source.get("blast_radius_score"), 0.0, 100.0)
        if source.get("blast_radius_score") is not None
        else None,
        "reduction_if_fixed": _bounded_number(source.get("reduction_if_fixed"), 0.0, 100.0)
        if source.get("reduction_if_fixed") is not None
        else None,
        "evidence_count": len(evidence_list),
        "causal_path": _string_list(source.get("causal_path"), 32),
        "affected_resources": _string_list(source.get("affected_resources")),
        "affected_services": _string_list(source.get("affected_services")),
        "data_at_risk": _string_list(source.get("data_at_risk")),
        "api_endpoints": _string_list(source.get("api_endpoints")),
        "evidence": [item for item in evidence_list[:_MAX_EVIDENCE] if isinstance(item, dict)],
    }


def _causal_record(finding_data: dict[str, Any]) -> dict[str, Any]:
    metadata = finding_data.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    raw = metadata.get("causal_score")
    raw = raw if isinstance(raw, dict) else {}
    rank = finding_data.get("causal_rank")
    effort = raw.get("fix_effort_minutes")
    roi = raw.get("roi_score")
    return {
        "rank": int(rank) if isinstance(rank, (int, float)) and int(rank) > 0 else None,
        "blast_radius_reduction": _bounded_number(raw.get("blast_radius_reduction"), 0.0, 100.0),
        "fix_effort_minutes": int(effort) if isinstance(effort, (int, float)) else None,
        "roi_score": _finite_float(roi) if roi is not None else None,
        "evidence_count": max(0, int(raw.get("evidence_count", 0) or 0)),
        "has_real_data": bool(raw.get("has_real_data", False)),
        "impact_provenance": _enum_value(raw.get("impact_provenance"), "UNKNOWN").upper(),
        "semantic_reason": _text(raw.get("semantic_reason")),
        "score_type": _text(raw.get("score_type"), "structural-impact-priority"),
        "causal_probability_claimed": bool(raw.get("causal_probability_claimed", False)),
    }


def _flow_record(finding_data: dict[str, Any]) -> dict[str, Any]:
    metadata = finding_data.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    raw_steps = finding_data.get("taint_path") or metadata.get("taint_path") or []
    steps: list[dict[str, Any]] = []
    for raw in raw_steps[:_MAX_FLOW_STEPS] if isinstance(raw_steps, list) else []:
        if isinstance(raw, dict):
            step = {
                "file": _text(raw.get("file")),
                "line": int(raw.get("line", 0) or 0),
                "action": _text(raw.get("action"), "step"),
            }
            if any(step.values()):
                steps.append(step)
        else:
            value = _text(raw)
            if value:
                steps.append({"action": value})

    source = _text(finding_data.get("source_function") or metadata.get("source"))
    sink = _text(finding_data.get("sink_function") or metadata.get("sink"))
    sanitizers = _string_list(
        finding_data.get("sanitizers_hit")
        or metadata.get("sanitizers_hit")
        or metadata.get("sanitizers"),
        24,
    )
    depth_raw = finding_data.get("call_depth") or metadata.get("call_depth") or 0
    try:
        call_depth = max(0, int(depth_raw))
    except (TypeError, ValueError):
        call_depth = 0

    return {
        "source": source,
        "sink": sink,
        "steps": steps,
        "step_count": len(steps),
        "sanitizers": sanitizers,
        "call_depth": call_depth,
        "cross_file": bool(finding_data.get("cross_file") or metadata.get("cross_file", False)),
        "analysis_layer": _text(metadata.get("analysis_layer")),
        "precision": _text(metadata.get("precision")),
    }


def _why_it_matters(category: str) -> str:
    reasons = {
        "secret": "The finding concerns potentially sensitive credential material. The security consequence depends on whether the value is valid, exposed, and usable by an attacker.",  # nosec B105
        "vulnerability": "The finding represents a security-relevant code or dependency condition. Exploitability depends on the surrounding control flow, trust boundary, configuration, and attacker reachability.",
        "policy": "The finding indicates a repository policy condition that can create security or governance risk when the policy is required for the deployment or workflow.",
        "pattern": "The finding identifies a suspicious or security-relevant code pattern. The actual consequence depends on how the pattern is reached and used.",
        "iac": "The finding concerns infrastructure or deployment configuration. Its consequence depends on the resulting runtime or cloud configuration and applicable trust boundaries.",
        "container": "The finding concerns a container image or layer. Risk depends on image provenance, runtime exposure, privileges, and whether the vulnerable component is reachable.",
    }
    return reasons.get(
        category,
        "The finding records a security-relevant condition detected by static analysis; its impact depends on the surrounding repository context.",
    )


class ExplanationEngine:
    """Generate deterministic, repository-agnostic explanation records."""

    ENGINE_VERSION = ENGINE_VERSION
    SCHEMA = SCHEMA

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = templates_dir or Path(__file__).parent / "templates"
        self.templates: dict[str, str] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        template_files = {
            "secret": "secret.md",  # nosec B105
            "vulnerability": "vulnerability.md",
            "policy": "policy.md",
            "pattern": "policy.md",
            "iac": "policy.md",
            "container": "policy.md",
        }
        for category, filename in template_files.items():
            template_path = self.templates_dir / filename
            try:
                self.templates[category] = template_path.read_text(encoding="utf-8")
            except OSError:
                self.templates[category] = self._default_template()

    def explain_record(self, finding: Finding | Mapping[str, Any]) -> dict[str, Any]:
        """Return the complete structured explanation artifact."""
        data = _finding_dict(finding)
        raw_metadata = data.get("metadata")
        metadata: dict[str, Any] = raw_metadata if isinstance(raw_metadata, dict) else {}
        category = _enum_value(data.get("category"), "unknown").lower()
        severity = _enum_value(
            data.get("effective_severity") or data.get("severity"),
            getattr(Severity.INFO, "value", Severity.INFO),
        ).lower()
        blast = _blast_record(data)
        causal = _causal_record(data)
        flow = _flow_record(data)

        summary = _text(
            data.get("message") or data.get("description") or data.get("title"),
            "Security finding detected by static analysis.",
        )
        why = _why_it_matters(category)
        evidence = blast["evidence"]
        evidence_summary: list[dict[str, Any]] = []
        for item in evidence:
            row: dict[str, Any] = {
                "type": _text(item.get("type"), "evidence"),
                "relation": _text(item.get("relation")),
                "source": _text(item.get("source")),
                "target": _text(item.get("target")),
                "basis": _text(item.get("basis")),
            }
            for key in ("path_length", "hop_distance", "bridge"):
                if key in item:
                    value = item.get(key)
                    if isinstance(value, (int, float, str)):
                        row[key] = _text(value) if isinstance(value, str) else value
            evidence_summary.append({k: v for k, v in row.items() if v not in ("", None, [])})

        finding_evidence = data.get("evidence")
        if isinstance(finding_evidence, str) and finding_evidence.strip():
            finding_evidence_summary = [_text(finding_evidence)]
        elif isinstance(finding_evidence, list):
            finding_evidence_summary = [
                _sanitize(item)
                for item in finding_evidence[:_MAX_EVIDENCE]
                if isinstance(item, (dict, str, int, float, bool))
            ]
        else:
            finding_evidence_summary = []

        reasoning: list[str] = []
        if flow["source"] and flow["sink"]:
            qualifier = (
                "across repository-local boundaries"
                if flow["cross_file"]
                else "within the analyzed flow"
            )
            reasoning.append(
                f"The scanner recorded data from `{flow['source']}` reaching `{flow['sink']}` {qualifier}."
            )
        elif data.get("rule_id"):
            reasoning.append(
                f"The rule `{_text(data.get('rule_id'))}` matched this finding location."
            )

        if evidence_summary:
            reasoning.append(
                f"The impact assessment cites {len(evidence_summary)} repository-local evidence record(s)."
            )
        elif finding_evidence_summary:
            reasoning.append(
                f"The scanner recorded {len(finding_evidence_summary)} finding-level evidence item(s); these are not treated as measured impact."
            )
        if blast["affected_resources"]:
            reasoning.append(
                f"The assessment identifies {len(blast['affected_resources'])} affected structural resource(s)."
            )
        if blast["affected_services"] or blast["data_at_risk"] or blast["api_endpoints"]:
            operational = (
                len(blast["affected_services"])
                + len(blast["data_at_risk"])
                + len(blast["api_endpoints"])
            )
            reasoning.append(
                f"The structural graph contributes {operational} service/data/API signal(s)."
            )
        if not reasoning:
            reasoning.append(
                "No additional structural reasoning was available from the finding metadata."
            )

        remediation = {
            "available": bool(data.get("fix_available", False)),
            "description": _text(data.get("fix_description") or data.get("remediation")),
            "command": _text(data.get("fix_command")),
            "engine": _text(data.get("fix_engine")),
            "cve": _text(data.get("cve")),
        }

        conformal_set = _string_list(data.get("conformal_set"), 8)
        conformal_conf = data.get("conformal_confidence")

        conformal_raw = metadata.get("conformal")
        conformal_dict = conformal_raw if isinstance(conformal_raw, dict) else {}
        uncertainty = {
            "status": _text(conformal_dict.get("coverage_status"))
            if conformal_dict
            else ("calibrated" if conformal_set else "uncalibrated"),
            "set": conformal_set,
            "lower": data.get("conformal_lower"),
            "upper": data.get("conformal_upper"),
            "confidence": conformal_conf,
        }

        caveats = [
            "Static analysis does not execute the target application or observe runtime telemetry.",
            "Structural blast-radius values are bounded prioritization scores, not measured loss probabilities or causal-effect estimates.",
        ]
        if blast["status"] != "assessed":
            caveats.append("Impact evidence is unassessed or estimated for this finding.")
        if causal["impact_provenance"] in {"ESTIMATED", "UNKNOWN"}:
            caveats.append(
                "Priority uses estimated impact because assessed structural evidence was not available."
            )
        if uncertainty["status"] == "uncalibrated":
            caveats.append(
                "Conformal metadata is uncalibrated for this prediction; no coverage guarantee is claimed."
            )

        record: dict[str, Any] = {
            "schema": SCHEMA,
            "engine_version": ENGINE_VERSION,
            "finding_id": _text(data.get("id") or data.get("rule_id")),
            "title": _text(data.get("title"), "Security finding"),
            "summary": summary,
            "severity": severity,
            "category": category,
            "scanner": _text(data.get("scanner")),
            "location": {
                "file": _text(data.get("file") or data.get("path") or data.get("source_file")),
                "line": int(data.get("line", 0) or 0),
                "column": int(data.get("column", 0) or 0),
                "context": _text(data.get("file_context")),
            },
            "why_it_matters": why,
            "reasoning": reasoning,
            "flow": flow,
            "finding_evidence": finding_evidence_summary,
            "assessment": {
                "status": blast["status"],
                "provenance": blast["provenance"],
                "is_assessed": blast["is_assessed"],
                "blast_radius_score": blast["score"],
                "reduction_if_fixed": blast["reduction_if_fixed"],
                "evidence_count": blast["evidence_count"],
                "evidence_summary": evidence_summary,
                "affected_resources": blast["affected_resources"],
                "affected_services": blast["affected_services"],
                "data_at_risk": blast["data_at_risk"],
                "api_endpoints": blast["api_endpoints"],
                "structural_path": blast["causal_path"],
            },
            "priority": causal,
            "remediation": remediation,
            "uncertainty": uncertainty,
            "confidence": _finite_float(data.get("confidence"), 0.0),
            "caveats": caveats,
        }
        record["reasoning_steps"] = list(reasoning)
        record["provenance"] = {
            "impact_provenance": blast["provenance"],
            "is_assessed": bool(blast["is_assessed"]),
            "external_model_used": False,
            "llm_used": False,
            "runtime_telemetry_used": False,
            "evidence_grounded": bool(evidence_summary or flow["steps"]),
        }
        record["assessment"]["assessed"] = bool(blast["is_assessed"])
        record["evidence_summary"] = evidence_summary
        record["explanation"] = self._render_markdown(record)
        # R20 exposes a long-form detail field for machine consumers while
        # preserving the Markdown rendering as a separate field.
        record["detail"] = record["explanation"]
        return record

    def build_report(self, finding: Finding | Mapping[str, Any]) -> dict[str, Any]:
        """Compatibility/public API alias returning the structured explanation report."""
        return self.explain_record(finding)

    def attach(self, finding: Finding) -> dict[str, Any]:
        """Attach and return one structured explanation report."""
        record = self.explain_record(finding)
        self._store_record(finding, record)
        return record

    @staticmethod
    def _store_record(finding: Finding, record: dict[str, Any]) -> None:
        metadata = getattr(finding, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            try:
                finding.metadata = metadata
            except (AttributeError, TypeError):
                return
        metadata["explanation"] = record
        metadata["explanation_markdown"] = str(record.get("explanation", ""))
        metadata["explanation_summary"] = str(record.get("summary", ""))
        metadata["explanation_reasoning"] = " ".join(str(x) for x in record.get("reasoning", []))
        metadata["explanation_schema"] = EXPLANATION_SCHEMA
        metadata["explanation_schema_version"] = EXPLANATION_SCHEMA
        metadata["explanation_generated_by"] = EXPLANATION_ENGINE_VERSION
        metadata["explanation_external_model"] = False
        metadata["explanation_runtime_telemetry"] = False
        metadata["explanation_evidence_grounded"] = bool(
            record.get("provenance", {}).get("evidence_grounded")
        )
        metadata["explanation_finding_evidence"] = record.get("finding_evidence", [])

    def explain(self, finding: Finding | Mapping[str, Any]) -> str:
        """Return a complete human-readable explanation, not merely the title."""
        return str(self.explain_record(finding)["explanation"])

    def get_detailed_context(self, finding: Finding | Mapping[str, Any]) -> str:
        """Return the same evidence-backed detail used by the CLI."""
        return self.explain(finding)

    def explain_batch(self, findings: list[Finding | Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Explain findings while preserving the historical batch API."""
        return [self.explain_record(finding) for finding in findings]

    def attach_batch(self, findings: list[Finding], *, limit: int = 100) -> int:
        """Attach structured explanations to up to ``limit`` findings.

        Returns the number of findings actually enriched.  The method exists
        for the Scheduler so explanation generation stays entirely in Layer 2.
        """
        bounded_limit = max(0, int(limit))
        if bounded_limit == 0:
            return 0
        selected = findings[:bounded_limit]
        self.enrich_findings(selected)
        return len(selected)

    def annotate_finding(self, finding: Finding) -> str:
        """Enrich one finding and return its complete human-readable explanation."""
        self.enrich_findings([finding])
        return str(getattr(finding, "metadata", {}).get("explanation_markdown", ""))

    def annotate_findings(self, findings: list[Finding]) -> list[Finding]:
        """Enrich multiple findings; compatibility alias for the Scheduler contract."""
        return self.enrich_findings(findings)

    def enrich_findings(self, findings: list[Finding]) -> list[Finding]:
        """Attach structured explanation metadata to each finding in-place."""
        for finding in findings:
            record = self.explain_record(finding)
            metadata = getattr(finding, "metadata", None)
            if not isinstance(metadata, dict):
                try:
                    finding.metadata = {}
                    metadata = finding.metadata
                except (AttributeError, TypeError):
                    continue
            self._store_record(finding, record)
            metadata["explanation_grounding"] = sorted(
                {
                    "finding_identity",
                    "location",
                    "severity",
                    "category",
                    "scanner",
                    "description",
                    "metadata",
                    *(["finding_evidence"] if record.get("finding_evidence") else []),
                    *(["structural_impact"] if record["assessment"]["evidence_summary"] else []),
                    *(["structural_impact"] if record["assessment"]["evidence_summary"] else []),
                    *(
                        ["data_flow"]
                        if record["flow"]["steps"]
                        or record["flow"]["source"]
                        or record["flow"]["sink"]
                        else []
                    ),
                    *(
                        ["remediation"]
                        if record["remediation"]["description"] or record["remediation"]["command"]
                        else []
                    ),
                }
            )
        return findings

    def _build_variables(self, finding: Finding | Mapping[str, Any]) -> dict[str, str]:
        """Build safe template variables for callers retaining the old API."""
        data = _finding_dict(finding)
        record = self.explain_record(finding)
        blast = record["assessment"]
        priority = record["priority"]
        conformal = record["uncertainty"]
        location = record["location"]
        remediation = record["remediation"]
        return {
            "title": record["title"],
            "severity": str(record["severity"]).upper(),
            "category": str(record["category"]).upper(),
            "scanner": str(record["scanner"]),
            "file": str(location["file"]),
            "line": str(location["line"]),
            "location": f"{location['file']}:{location['line']}",
            "description": record["summary"],
            "evidence": str(blast["evidence_summary"] or "(no structural evidence captured)"),
            "confidence": f"{int(max(0.0, min(1.0, record['confidence'])) * 100)}%",
            "file_context": str(location["context"]),
            "conformal_set": str(conformal["set"] or "N/A"),
            "conformal_confidence": _text(conformal["confidence"], "N/A"),
            "blast_radius_section": self._blast_radius_section(blast),
            "fix_available": "Yes" if remediation["available"] else "No",
            "fix_command": remediation["command"] or "Manual remediation required",
            "fix_description": remediation["description"] or record["summary"],
            "causal_rank": f"#{priority['rank']}" if priority["rank"] else "Not ranked",
            "roi_score": _text(priority["roi_score"], "N/A"),
            "fix_effort": f"{priority['fix_effort_minutes']} min"
            if priority["fix_effort_minutes"] is not None
            else "Not estimated",
            "cve": _text(data.get("cve"), "N/A"),
            "cvss_score": _text(data.get("cvss_score"), "N/A"),
        }

    @staticmethod
    def _blast_radius_section(assessment: dict[str, Any]) -> str:
        if assessment["status"] != "assessed":
            return "Impact not structurally assessed for this finding."
        lines = [
            f"- **Blast-radius score:** {assessment['blast_radius_score']}/100",
            f"- **Reduction if fixed:** {assessment['reduction_if_fixed']}/100",
            f"- **Affected resources:** {', '.join(assessment['affected_resources']) or 'None recorded'}",
            f"- **Affected services:** {', '.join(assessment['affected_services']) or 'None recorded'}",
            f"- **Data at risk:** {', '.join(assessment['data_at_risk']) or 'None recorded'}",
            f"- **API endpoints:** {', '.join(assessment['api_endpoints']) or 'None recorded'}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _default_template() -> str:
        return (
            "## $title\n\n"
            "**Severity:** $severity | **Category:** $category | **Location:** $location\n\n"
            "### What was found\n\n$description\n\n"
            "### Evidence-backed impact\n\n$blast_radius_section\n\n"
            "### Remediation\n\n$fix_description\n\n"
            "**Command:** $fix_command\n"
        )

    def _render_markdown(self, record: dict[str, Any]) -> str:
        location = record["location"]
        assessment = record["assessment"]
        priority = record["priority"]
        flow = record["flow"]
        remediation = record["remediation"]
        uncertainty = record["uncertainty"]

        lines = [
            f"## {record['title']}",
            "",
            f"**Severity:** {str(record['severity']).upper()}  |  **Category:** {str(record['category']).upper()}  |  **Scanner:** {record['scanner'] or 'unknown'}",
            f"**Location:** `{location['file']}:{location['line']}:{location['column']}`  |  **Context:** {location['context'] or 'unknown'}",
            "",
            "### What was found",
            "",
            record["summary"],
            "",
            "### Why it matters",
            "",
            record["why_it_matters"],
            "",
            "### Deterministic reasoning",
            "",
        ]
        lines.extend(f"- {item}" for item in record["reasoning"])

        lines.extend(["", "### Evidence", ""])
        if assessment["evidence_summary"]:
            lines.extend(
                f"- `{item.get('relation') or item.get('type')}`: {item.get('source', '')} → {item.get('target', '')} ({item.get('basis', 'recorded evidence')})"
                for item in assessment["evidence_summary"]
            )
        else:
            lines.append("No structural evidence record is attached to this finding.")

        lines.extend(["", "### Structural impact", ""])
        lines.append(
            f"- **Assessment:** {assessment['status']} / provenance `{assessment['provenance']}`"
        )
        if assessment["blast_radius_score"] is not None:
            lines.append(f"- **Blast-radius score:** {assessment['blast_radius_score']}/100")
            lines.append(f"- **Reduction if fixed:** {assessment['reduction_if_fixed']}/100")
        lines.append(
            f"- **Affected resources:** {', '.join(assessment['affected_resources']) or 'None recorded'}"
        )
        lines.append(
            f"- **Affected services:** {', '.join(assessment['affected_services']) or 'None recorded'}"
        )
        lines.append(
            f"- **Data at risk:** {', '.join(assessment['data_at_risk']) or 'None recorded'}"
        )
        lines.append(
            f"- **API endpoints:** {', '.join(assessment['api_endpoints']) or 'None recorded'}"
        )
        if assessment["structural_path"]:
            lines.append(f"- **Structural path:** `{' -> '.join(assessment['structural_path'])}`")

        if flow["source"] or flow["sink"] or flow["steps"]:
            lines.extend(["", "### Data-flow evidence", ""])
            if flow["source"]:
                lines.append(f"- **Source:** `{flow['source']}`")
            if flow["sink"]:
                lines.append(f"- **Sink:** `{flow['sink']}`")
            if flow["steps"]:
                lines.append(f"- **Recorded steps:** {flow['step_count']}")
                for step in flow["steps"][:12]:
                    step_loc = f"{step.get('file')}:{step.get('line')}" if step.get("file") else ""
                    lines.append(f"  - {step_loc} — {step.get('action', 'step')}".strip())
            if flow["sanitizers"]:
                lines.append(f"- **Sanitizers recorded:** {', '.join(flow['sanitizers'])}")
            lines.append(f"- **Cross-file:** {'yes' if flow['cross_file'] else 'no'}")

        lines.extend(["", "### Priority", ""])
        lines.append(f"- **Causal rank:** {priority['rank'] or 'not ranked'}")
        lines.append(f"- **Priority model:** `{priority['score_type']}`")
        lines.append(f"- **Impact provenance:** `{priority['impact_provenance']}`")
        if priority["roi_score"] is not None:
            lines.append(f"- **ROI score:** {priority['roi_score']:.4f}")
        if priority["fix_effort_minutes"] is not None:
            lines.append(f"- **Estimated fix effort:** {priority['fix_effort_minutes']} minutes")

        lines.extend(
            [
                "",
                "### Remediation",
                "",
                remediation["description"] or "No explicit remediation text was recorded.",
            ]
        )
        lines.append(f"- **Fix available:** {'yes' if remediation['available'] else 'no'}")
        if remediation["command"]:
            lines.append(f"- **Fix command:** `{remediation['command']}`")
        if remediation["engine"]:
            lines.append(f"- **Fix engine:** `{remediation['engine']}`")
        if remediation["cve"]:
            lines.append(f"- **CVE:** `{remediation['cve']}`")

        lines.extend(["", "### Uncertainty", ""])
        lines.append(f"- **Static confidence:** {record['confidence']:.4f}")
        lines.append(f"- **Conformal status:** `{uncertainty['status']}`")
        if uncertainty["set"]:
            lines.append(f"- **Conformal set:** `{', '.join(uncertainty['set'])}`")
        if uncertainty["lower"] is not None and uncertainty["upper"] is not None:
            lines.append(
                f"- **Conformal interval:** `{uncertainty['lower']}` to `{uncertainty['upper']}`"
            )
        if uncertainty["confidence"] is not None:
            lines.append(f"- **Conformal confidence:** `{uncertainty['confidence']}`")

        lines.extend(["", "### Caveats", ""])
        lines.extend(f"- {caveat}" for caveat in record["caveats"])
        lines.append("")
        return "\n".join(lines)


__all__ = ["ENGINE_VERSION", "SCHEMA", "ExplanationEngine"]
