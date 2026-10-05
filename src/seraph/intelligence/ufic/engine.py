"""seraph.intelligence.ufic.engine — Unified Framework Intelligence & Classification Engine

The UFIC engine is the v2.0 orchestrator that bridges:
  - Topology inference (repo structure, frameworks, boundaries)
  - Semantic evaluation (blast radius, conformal confidence, causal impact)
  - Classification (intent detection, suppression, omission detection)

Moats: Semantic Topology, Conformal Truth, Ontology Compounding, Causal Digital Twin
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, override

from seraph.sources.repository.scanners.base import Finding, Severity
from seraph.intelligence.ufic.classifier import ClassificationResult, UFICClassifier
from seraph.intelligence.ufic.identity import stable_ufic_finding_id
from seraph.intelligence.ufic.semantics import SemanticEngine
from seraph.intelligence.ufic.topology import TopologyEngine


logger = logging.getLogger("seraph.intelligence.ufic.engine")


@dataclass
class UFICFinding(Finding):
    """v2.0 UFIC-enriched finding with conformal confidence and causal context.

    This subclasses the canonical scanner Finding directly.  UFIC does not
    maintain a second fallback Finding type because doing so creates incompatible
    type identities and can hide real contract violations from static analysis.
    """

    id: str = ""
    rule_id: str = ""
    rule_name: str = ""
    title: str = ""
    severity: Any = field(default_factory=lambda: Severity.MEDIUM)
    effective_severity: Any = None
    message: str = ""
    description: str = ""
    file: str = ""
    path: str = ""
    line: int = 0
    column: int = 0
    category: Any = "ufic"
    scanner: str = "ufic"
    confidence: float = 0.0
    conformal_lower: float | None = None
    conformal_upper: float | None = None
    blast_radius: Any = None
    causal_rank: int | None = None
    fix_available: bool = False
    fix_command: str | None = ""
    cve: str | None = ""
    tags: list[str] = field(default_factory=list)
    context: str = ""
    value: str = ""
    variable_name: str = ""
    evidence: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # UFIC-specific fields
    intent: str = "production"
    language: str = "unknown"
    blast_radius_multiplier: float = 1.0
    confidence_interval: tuple[float, float] = (0.0, 1.0)
    confidence_level: float = 0.95
    causal_impact: dict[str, Any] = field(default_factory=dict)
    recommended_action: str = "none"
    is_omission: bool = False
    is_suppressed: bool = False
    suppression_reason: str | None = ""
    ontology_objects: list[dict[str, Any]] = field(default_factory=list)
    ontology_links: list[dict[str, Any]] = field(default_factory=list)

    @override
    def __post_init__(self) -> None:
        # Compute the canonical UFIC identity before invoking the base
        # Finding initialization contract. Some base Finding implementations
        # auto-generate process-local IDs when `id` is empty. UFIC findings
        # must instead use deterministic logical identity for deduplication,
        # caching, ontology linking, and explanation stability.
        stable_id = stable_ufic_finding_id(
            rule_id=self.rule_id,
            file_path=self.file,
            line=self.line,
            column=self.column,
        )

        if not self.id:
            self.id = stable_id

        # Preserve the canonical Finding initialization contract.
        super().__post_init__()

        # If the base class replaced or generated a non-UFIC ID, restore the
        # deterministic UFIC identity. This is intentional: UFIC findings are
        # governed by stable logical identity, not by inherited auto-generated
        # identifiers.
        if self.scanner == "ufic" and self.id != stable_id:
            self.id = stable_id

        if self.effective_severity is None:
            self.effective_severity = self.severity


class UFICEngine:
    """v2.0 UFIC Engine — Scheduler-compatible scanner interface.

    Pipeline:
      1. Topology inference → repo structure, frameworks, security boundaries
      2. Omission detection → missing auth, RLS, rate limiting, CSRF, validation
      3. Semantic evaluation → blast radius, conformal confidence, causal impact
      4. Classification → intent detection, suppression, ontology actions
    """

    name: str = "ufic"

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        enabled: bool = True,
        ontology: Any | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.enabled = enabled
        self.ontology = ontology
        self._topology_engine: TopologyEngine | None = None
        self._semantic_engine: SemanticEngine | None = None
        self._classifier: UFICClassifier | None = None
        self._topology_cache: dict[str, Any] = {}

        # These are internal UFIC components.  They are part of the package
        # contract, so their imports are intentionally typed and explicit.
        # Constructor failures are still isolated so an optional intelligence
        # failure cannot take down the CLI.
        try:
            self._topology_engine = TopologyEngine(ontology=ontology)
        except Exception as exc:
            logger.debug("TopologyEngine init failed: %s", exc)

        try:
            self._semantic_engine = SemanticEngine(ontology=ontology)
        except Exception as exc:
            logger.debug("SemanticEngine init failed: %s", exc)

    # ------------------------------------------------------------------
    # Scanner Interface (required by Scheduler)
    # ------------------------------------------------------------------

    def is_applicable(self, context: Any) -> bool:
        """UFIC is always applicable (works on any repo)."""
        return self.enabled

    async def scan(self, context: Any) -> list[UFICFinding]:
        """Run the full UFIC pipeline.

        Accepts either a ScanContext-like object or a Path/str.
        Returns UFICFinding objects compatible with the CLI finding serializer.
        """
        if not self.enabled:
            return []

        if hasattr(context, "path"):
            path = context.path
        elif hasattr(context, "scan_path"):
            path = context.scan_path
        elif isinstance(context, (str, Path)):
            path = str(context)
        else:
            logger.warning(
                "UFICEngine.scan: cannot extract path from %s",
                type(context),
            )
            return []

        try:
            return self._scan_path(Path(path).resolve())
        except Exception as exc:
            logger.error("UFIC scan failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _scan_path(self, root: Path) -> list[UFICFinding]:
        root_str = str(root)
        findings: list[UFICFinding] = []

        # ── Phase 1: Topology Inference ──
        logger.info("UFIC Phase 1: Topology inference for %s", root)
        topology_dict: dict[str, Any] = {}

        if self._topology_engine is not None:
            try:
                if root_str in self._topology_cache:
                    topo = self._topology_cache[root_str]
                else:
                    topo = self._topology_engine.infer(root)
                    self._topology_cache[root_str] = topo

                if hasattr(topo, "to_ontology"):
                    topology_dict = topo.to_ontology()
            except Exception as exc:
                logger.warning("Topology inference failed: %s", exc)

        # ── Phase 2: Omission Detection ──
        logger.info("UFIC Phase 2: Omission detection")
        omission_findings: list[dict[str, Any]] = []

        try:
            classifier = UFICClassifier(
                topology=topology_dict,
                ontology=self.ontology,
            )
            omission_findings = classifier.detect_omissions(root)
        except Exception as exc:
            logger.warning(
                "UFIC omission detector unavailable/failed; using fallback: %s",
                exc,
            )
            omission_findings = self._fallback_omission_scan(root)

        # ── Phase 3: Convert to UFICFindings ──
        for omission in omission_findings:
            findings.append(self._omission_to_finding(omission, topology_dict))

        # ── Phase 4: Semantic evaluation ──
        logger.info(
            "UFIC Phase 3: Semantic evaluation (%d findings)",
            len(findings),
        )

        if self._semantic_engine is not None:
            for finding in findings:
                try:
                    adjustment = self._semantic_engine.evaluate(
                        finding_id=finding.id,
                        rule_id=finding.rule_id,
                        language=finding.language or "unknown",
                        file_path=finding.file or "",
                        context=finding.description or "",
                        topology=topology_dict,
                    )

                    finding.blast_radius_multiplier = adjustment.blast_radius_multiplier
                    finding.confidence_interval = adjustment.confidence_interval
                    finding.confidence_level = adjustment.confidence_level
                    finding.causal_impact = adjustment.causal_impact
                    finding.recommended_action = adjustment.recommended_action

                except Exception as exc:
                    logger.debug(
                        "Semantic eval failed for %s: %s",
                        finding.id,
                        exc,
                    )

        logger.info(
            "UFIC scan complete: %d findings",
            len(findings),
        )
        return findings

    def evaluate_finding(
        self,
        finding: Any,
    ) -> ClassificationResult | None:
        """Evaluate a single finding through the UFIC classifier."""
        try:
            classifier = UFICClassifier(ontology=self.ontology)
            return classifier.evaluate_finding(finding)
        except Exception as exc:
            logger.debug("evaluate_finding failed: %s", exc)
            return None

    def get_topology(self, path: Path | str) -> Any:
        """Return cached or fresh topology for a repo."""
        root = Path(path).resolve()
        root_str = str(root)

        if root_str not in self._topology_cache:
            if self._topology_engine is None:
                return None

            try:
                self._topology_cache[root_str] = self._topology_engine.infer(root)
            except Exception as exc:
                logger.warning("get_topology failed: %s", exc)
                return None

        return self._topology_cache[root_str]

    # ------------------------------------------------------------------
    # Fallback omission scanner
    # ------------------------------------------------------------------

    def _fallback_omission_scan(
        self,
        root: Path,
    ) -> list[dict[str, Any]]:
        """Comprehensive omission detection without the UFIC classifier.

        Detects:
        - Missing auth on API routes
        - Missing rate limiting
        - Hardcoded secrets
        - Dangerous eval/exec usage
        - Debug mode enabled
        - SQL injection risks
        """
        findings: list[dict[str, Any]] = []

        def should_skip(path: Path) -> bool:
            path_string = str(path)
            return any(
                name in path_string
                for name in (
                    "node_modules",
                    ".venv",
                    "__pycache__",
                    "dist",
                    "build",
                    ".git",
                    ".tox",
                    ".pytest_cache",
                )
            )

        auth_decorators = re.compile(
            r"@(require_auth|login_required|authenticated|jwt_required|"
            r"auth_required|protect|authorize)",
            re.IGNORECASE,
        )
        route_decorators = re.compile(
            r"@(app\.route|router\.get|router\.post|router\.put|"
            r"router\.delete|api_view)",
            re.IGNORECASE,
        )

        secret_patterns = [
            (
                re.compile(
                    r"""(?i)(SECRET_KEY|API_KEY|PASSWORD|TOKEN|ACCESS_KEY)\s*=\s*['"][^'"]{4,}['"]"""
                ),
                "hardcoded_secret",
                "critical",
            ),
            (
                re.compile(
                    r"""(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*['"]?[A-Z0-9]{16,}['"]?"""
                ),
                "aws_key_exposed",
                "critical",
            ),
            (
                re.compile(r"""(?i)(private_key|ssh_key)\s*[:=]\s*['"]?-----BEGIN"""),
                "private_key_exposed",
                "critical",
            ),
        ]

        dangerous_patterns = [
            (
                re.compile(r"(?i)\beval\s*\("),
                "dangerous_eval",
                "critical",
            ),
            (
                re.compile(r"(?i)\bexec\s*\("),
                "dangerous_exec",
                "critical",
            ),
            (
                re.compile(r"(?i)\bpickle\.load"),
                "unsafe_pickle",
                "high",
            ),
            (
                re.compile(r"(?i)yaml\.load\s*\([^)]*\)"),
                "unsafe_yaml_load",
                "high",
            ),
        ]

        debug_patterns = [
            (
                re.compile(r"(?i)DEBUG\s*=\s*True"),
                "debug_mode_enabled",
                "high",
            ),
            (
                re.compile(r"(?i)FLASK_DEBUG\s*=\s*True"),
                "debug_mode_enabled",
                "high",
            ),
        ]

        sql_patterns = [
            (
                re.compile(r"(?i)(execute|cursor\.execute)\s*\(.*%s.*\)"),
                "sql_injection_risk",
                "critical",
            ),
            (
                re.compile(r"""(?i)(execute|cursor\.execute)\s*\(.*f["'].*\{.*\}.*["'].*\)"""),
                "sql_injection_risk",
                "critical",
            ),
        ]

        for py_file in root.rglob("*.py"):
            if should_skip(py_file):
                continue

            try:
                text = py_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
                lines = text.splitlines()
                rel_path = str(py_file.relative_to(root))

                for index, line in enumerate(lines):
                    stripped = line.strip()

                    if not stripped or stripped.startswith("#"):
                        continue

                    for pattern, rule_id, severity in secret_patterns:
                        if pattern.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": (f"Potential Secret Exposure ({rule_id})"),
                                    "file": rel_path,
                                    "line": index + 1,
                                    "severity": severity,
                                    "confidence_interval": (0.85, 0.99),
                                    "reason": (
                                        f"Hardcoded credential pattern detected: {stripped[:80]}"
                                    ),
                                    "omission_type": "secret_exposure",
                                    "blast_radius_multiplier": 1.5,
                                    "language": "python",
                                }
                            )

                    for pattern, rule_id, severity in dangerous_patterns:
                        if pattern.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": (f"Dangerous Code Pattern ({rule_id})"),
                                    "file": rel_path,
                                    "line": index + 1,
                                    "severity": severity,
                                    "confidence_interval": (0.80, 0.95),
                                    "reason": (
                                        f"Dangerous function call detected: {stripped[:80]}"
                                    ),
                                    "omission_type": "dangerous_pattern",
                                    "blast_radius_multiplier": 1.3,
                                    "language": "python",
                                }
                            )

                    for pattern, rule_id, severity in debug_patterns:
                        if pattern.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": "Debug Mode Enabled in Production",
                                    "file": rel_path,
                                    "line": index + 1,
                                    "severity": severity,
                                    "confidence_interval": (0.75, 0.92),
                                    "reason": (
                                        "Debug mode should not be enabled in production code"
                                    ),
                                    "omission_type": "misconfiguration",
                                    "blast_radius_multiplier": 1.1,
                                    "language": "python",
                                }
                            )

                    for pattern, rule_id, severity in sql_patterns:
                        if pattern.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": "Potential SQL Injection",
                                    "file": rel_path,
                                    "line": index + 1,
                                    "severity": severity,
                                    "confidence_interval": (0.70, 0.90),
                                    "reason": (f"String formatting in SQL query: {stripped[:80]}"),
                                    "omission_type": "injection_risk",
                                    "blast_radius_multiplier": 1.4,
                                    "language": "python",
                                }
                            )

                file_text = text

                for match in route_decorators.finditer(file_text):
                    start = max(0, match.start() - 500)
                    snippet = file_text[start : match.end() + 200]

                    if not auth_decorators.search(snippet):
                        line_num = file_text[: match.start()].count("\n") + 1
                        findings.append(
                            {
                                "rule_id": "missing_auth",
                                "title": ("Missing Authentication on API Endpoint"),
                                "file": rel_path,
                                "line": line_num,
                                "severity": "critical",
                                "confidence_interval": (0.65, 0.95),
                                "reason": ("API route defined without auth decorator"),
                                "omission_type": "absence_of_control",
                                "blast_radius_multiplier": 1.3,
                                "language": "python",
                            }
                        )

            except Exception as exc:
                logger.debug(
                    "Fallback scan failed for %s: %s",
                    py_file,
                    exc,
                )

            if len(findings) >= 200:
                break

        rate_limit_keywords = re.compile(
            r"(rate_limit|throttle|@RateLimit|express-rate-limit)",
            re.IGNORECASE,
        )

        for py_file in root.rglob("*.py"):
            if should_skip(py_file):
                continue

            try:
                text = py_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
                has_routes = "@app.route" in text or "@router" in text
                lacks_rate_limit = has_routes and not rate_limit_keywords.search(text)

                if has_routes and lacks_rate_limit:
                    rel_path = str(py_file.relative_to(root))

                    already_reported = any(
                        finding.get("file") == rel_path
                        and finding.get("rule_id") == "missing_rate_limiting"
                        for finding in findings
                    )

                    if not already_reported:
                        findings.append(
                            {
                                "rule_id": "missing_rate_limiting",
                                "title": "Missing Rate Limiting on Public API",
                                "file": rel_path,
                                "severity": "medium",
                                "confidence_interval": (0.40, 0.75),
                                "reason": "Route file has no rate limiting",
                                "omission_type": "absence_of_control",
                                "blast_radius_multiplier": 1.1,
                                "language": "python",
                            }
                        )

            except Exception as exc:
                logger.debug(
                    "Fallback rate-limit scan failed for %s: %s",
                    py_file,
                    exc,
                )

            if len(findings) >= 250:
                break

        return findings[:250]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_confidence_interval(
        value: object,
    ) -> tuple[float, float]:
        """Normalize external confidence-interval data to an exact 2-tuple."""
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                lower = float(value[0])
                upper = float(value[1])
                return (lower, upper)
            except (TypeError, ValueError):
                pass

        return (0.50, 0.85)

    @staticmethod
    def _omission_to_finding(
        om: dict[str, Any],
        _topology: dict[str, Any],
    ) -> UFICFinding:
        sev_map: dict[str, Severity] = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }

        raw_severity = str(om.get("severity", "medium")).lower()
        severity = sev_map.get(raw_severity, Severity.MEDIUM)

        confidence_interval = UFICEngine._normalize_confidence_interval(
            om.get("confidence_interval")
        )
        confidence_lower, confidence_upper = confidence_interval

        file_path = str(om.get("file", ""))
        line_num = int(om.get("line", 0) or 0)
        column_num = int(om.get("column", 0) or 0)
        rule_id = str(om["rule_id"])
        multiplier = float(om.get("blast_radius_multiplier", 1.0) or 1.0)

        return UFICFinding(
            id=stable_ufic_finding_id(
                rule_id=rule_id,
                file_path=file_path,
                line=line_num,
                column=column_num,
            ),
            rule_id=rule_id,
            rule_name=str(om.get("title", rule_id)),
            title=str(om.get("title", rule_id)),
            severity=severity,
            effective_severity=severity,
            message=str(om.get("reason", "")),
            description=str(om.get("reason", "")),
            file=file_path,
            path=file_path,
            line=line_num,
            column=column_num,
            category="ufic",
            scanner="ufic",
            confidence=confidence_upper,
            conformal_lower=confidence_lower,
            conformal_upper=confidence_upper,
            blast_radius={
                "blast_radius_score": int(multiplier * 100),
                "is_assessed": False,
                "reduction_if_fixed": multiplier * 100,
            },
            intent="production",
            blast_radius_multiplier=multiplier,
            confidence_interval=confidence_interval,
            is_omission=True,
            causal_impact={"omission_type": str(om.get("omission_type", ""))},
            recommended_action="escalate",
            language=str(om.get("language", "unknown")),
            metadata={
                "rule_id": rule_id,
                "language": str(om.get("language", "unknown")),
            },
        )
