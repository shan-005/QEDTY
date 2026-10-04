"""seraph.ufic.engine — Unified Framework Intelligence & Classification Engine

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

from seraph.ufic.identity import stable_ufic_finding_id


# Safe imports — never crash cli.py
try:
    from seraph.guard.scanners.base import Finding, ScanContext, Severity
except Exception:

    class Finding:  # type: ignore[no-redef]
        def __init__(self, **kw: Any) -> None:
            for k, v in kw.items():
                setattr(self, k, v)

    class Severity:  # type: ignore[no-redef]
        CRITICAL = "critical"
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
        INFO = "info"

    class ScanContext:  # type: ignore[no-redef]
        pass


try:
    from seraph.ufic.classifier import (
        ClassificationResult,
        FileClassifier,
        OmissionDetector,
        RuleRegistry,
        UFICClassifier,
    )
except Exception:
    ClassificationResult = object  # type: ignore[misc,assignment]
    FileClassifier = object  # type: ignore[misc,assignment]
    OmissionDetector = object  # type: ignore[misc,assignment]
    RuleRegistry = object  # type: ignore[misc,assignment]
    UFICClassifier = object  # type: ignore[misc,assignment]

try:
    from seraph.ufic.semantics import SemanticAdjustment, SemanticEngine
except Exception:
    SemanticAdjustment = object  # type: ignore[misc,assignment]
    SemanticEngine = object  # type: ignore[misc,assignment]

try:
    from seraph.ufic.topology import (
        FrameworkProfile,
        RepoTopology,
        SecurityBoundary,
        TopologyEngine,
    )
except Exception:
    FrameworkProfile = object  # type: ignore[misc,assignment]
    RepoTopology = object  # type: ignore[misc,assignment]
    SecurityBoundary = object  # type: ignore[misc,assignment]
    TopologyEngine = object  # type: ignore[misc,assignment]


logger = logging.getLogger("seraph.ufic.engine")


@dataclass
class UFICFinding(Finding):
    """v2.0 UFIC-enriched finding with conformal confidence and causal context.

    Inherits from Finding (or stub) and adds UFIC-specific fields.
    All fields that cli.py reads via getattr() are explicitly declared.
    """

    id: str = ""
    rule_id: str = ""
    rule_name: str = ""
    title: str = ""
    severity: Any = field(
        default_factory=lambda: Severity.MEDIUM if hasattr(Severity, "MEDIUM") else "medium"
    )
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
    context: str = ""  # cli.py reads this via getattr
    value: str = ""  # cli.py reads this via getattr
    variable_name: str = ""  # cli.py reads this via getattr
    evidence: str = ""  # used by causal ranker
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
        if not self.id:
            self.id = stable_ufic_finding_id(
                rule_id=self.rule_id,
                file_path=self.file,
                line=self.line,
                column=self.column,
            )
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
        self._topology_engine: Any = None
        self._semantic_engine: Any = None
        self._classifier: Any = None
        self._topology_cache: dict[str, Any] = {}

        if TopologyEngine is not object:
            try:
                self._topology_engine = TopologyEngine(ontology=ontology)
            except Exception as e:
                logger.debug("TopologyEngine init failed: %s", e)
        if SemanticEngine is not object:
            try:
                self._semantic_engine = SemanticEngine(ontology=ontology)
            except Exception as e:
                logger.debug("SemanticEngine init failed: %s", e)

    # ------------------------------------------------------------------
    # Scanner Interface (required by Scheduler)
    # ------------------------------------------------------------------

    def is_applicable(self, context: Any) -> bool:
        """UFIC is always applicable (works on any repo)."""
        return self.enabled

    async def scan(self, context: Any) -> list[UFICFinding]:
        """Run the full UFIC pipeline.

        Accepts either a ScanContext object or a Path/str.
        Returns UFICFinding objects that are fully compatible with cli.py's
        _finding_to_dict() via duck typing.
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
            logger.warning("UFICEngine.scan: cannot extract path from %s", type(context))
            return []

        try:
            return self._scan_path(Path(path).resolve())
        except Exception as e:
            logger.error("UFIC scan failed: %s", e)
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
        if self._topology_engine is not None and hasattr(self._topology_engine, "infer"):
            try:
                if root_str in self._topology_cache:
                    topo = self._topology_cache[root_str]
                else:
                    topo = self._topology_engine.infer(root)
                    self._topology_cache[root_str] = topo
                topology_dict = topo.to_ontology() if hasattr(topo, "to_ontology") else {}
            except Exception as e:
                logger.warning("Topology inference failed: %s", e)

        # ── Phase 2: Omission Detection ──
        logger.info("UFIC Phase 2: Omission detection")
        omission_findings: list[dict[str, Any]] = []
        if (
            UFICClassifier is not object
            and hasattr(UFICClassifier, "__init__")
            and OmissionDetector is not object
        ):
            try:
                classifier = UFICClassifier(topology=topology_dict, ontology=self.ontology)
                if hasattr(classifier, "detect_omissions"):
                    omission_findings = classifier.detect_omissions(root)
            except Exception as e:
                logger.warning("Omission detection failed: %s", e)
        else:
            omission_findings = self._fallback_omission_scan(root)

        # ── Phase 3: Convert to UFICFindings ──
        for om in omission_findings:
            uf = self._omission_to_finding(om, topology_dict)
            findings.append(uf)

        # ── Phase 4: Semantic evaluation ──
        logger.info("UFIC Phase 3: Semantic evaluation (%d findings)", len(findings))
        if self._semantic_engine is not None and hasattr(self._semantic_engine, "evaluate"):
            for uf in findings:
                try:
                    adj = self._semantic_engine.evaluate(
                        finding_id=uf.id,
                        rule_id=uf.rule_id,
                        language=uf.language or "unknown",
                        file_path=uf.file or "",
                        context=uf.description or "",
                        topology=topology_dict,
                    )
                    if hasattr(adj, "blast_radius_multiplier"):
                        uf.blast_radius_multiplier = adj.blast_radius_multiplier
                    if hasattr(adj, "confidence_interval"):
                        uf.confidence_interval = adj.confidence_interval
                    if hasattr(adj, "confidence_level"):
                        uf.confidence_level = adj.confidence_level
                    if hasattr(adj, "causal_impact"):
                        uf.causal_impact = adj.causal_impact
                    if hasattr(adj, "recommended_action"):
                        uf.recommended_action = adj.recommended_action
                except Exception as e:
                    logger.debug("Semantic eval failed for %s: %s", uf.id, e)

        logger.info("UFIC scan complete: %d findings", len(findings))
        return findings

    def evaluate_finding(self, finding: Any) -> Any:
        """Evaluate a single finding through the UFIC classifier."""
        if UFICClassifier is object:
            return None
        try:
            classifier = UFICClassifier(ontology=self.ontology)
            if hasattr(classifier, "evaluate_finding"):
                return classifier.evaluate_finding(finding)
        except Exception as e:
            logger.debug("evaluate_finding failed: %s", e)
        return None

    def get_topology(self, path: Path | str) -> Any:
        """Return cached or fresh topology for a repo."""
        root = Path(path).resolve()
        root_str = str(root)
        if root_str not in self._topology_cache:
            if self._topology_engine is not None and hasattr(self._topology_engine, "infer"):
                try:
                    self._topology_cache[root_str] = self._topology_engine.infer(root)
                except Exception as e:
                    logger.warning("get_topology failed: %s", e)
                    return None
            else:
                return None
        return self._topology_cache[root_str]

    # ------------------------------------------------------------------
    # Fallback omission scanner (when ufic.classifier is unavailable)
    # ------------------------------------------------------------------

    def _fallback_omission_scan(self, root: Path) -> list[dict[str, Any]]:
        """Comprehensive omission detection without full classifier.

        Detects:
        - Missing auth on API routes
        - Missing rate limiting
        - Hardcoded secrets
        - Dangerous eval/exec usage
        - Debug mode enabled
        - SQL injection risks
        """
        findings: list[dict[str, Any]] = []

        # Skip directories
        def should_skip(path: Path) -> bool:
            s = str(path)
            return any(
                k in s
                for k in (
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

        # Pattern: missing auth on Python routes
        auth_decorators = re.compile(
            r"@(require_auth|login_required|authenticated|jwt_required|auth_required|protect|authorize)",
            re.IGNORECASE,
        )
        route_decorators = re.compile(
            r"@(app\.route|router\.get|router\.post|router\.put|router\.delete|api_view)",
            re.IGNORECASE,
        )

        # Pattern: hardcoded secrets
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

        # Pattern: dangerous functions
        dangerous_patterns = [
            (re.compile(r"(?i)\beval\s*\("), "dangerous_eval", "critical"),
            (re.compile(r"(?i)\bexec\s*\("), "dangerous_exec", "critical"),
            (re.compile(r"(?i)\bpickle\.load"), "unsafe_pickle", "high"),
            (re.compile(r"(?i)yaml\.load\s*\([^)]*\)"), "unsafe_yaml_load", "high"),
        ]

        # Pattern: debug mode
        debug_patterns = [
            (re.compile(r"(?i)DEBUG\s*=\s*True"), "debug_mode_enabled", "high"),
            (re.compile(r"(?i)FLASK_DEBUG\s*=\s*True"), "debug_mode_enabled", "high"),
        ]

        # Pattern: SQL injection risk
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
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                lines = text.splitlines()
                rel_path = str(py_file.relative_to(root))

                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue

                    # Check for hardcoded secrets
                    for pat, rule_id, sev in secret_patterns:
                        if pat.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": f"Potential Secret Exposure ({rule_id})",
                                    "file": rel_path,
                                    "line": i + 1,
                                    "severity": sev,
                                    "confidence_interval": (0.85, 0.99),
                                    "reason": f"Hardcoded credential pattern detected: {stripped[:80]}",
                                    "omission_type": "secret_exposure",
                                    "blast_radius_multiplier": 1.5,
                                    "language": "python",
                                }
                            )

                    # Check for dangerous functions
                    for pat, rule_id, sev in dangerous_patterns:
                        if pat.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": f"Dangerous Code Pattern ({rule_id})",
                                    "file": rel_path,
                                    "line": i + 1,
                                    "severity": sev,
                                    "confidence_interval": (0.80, 0.95),
                                    "reason": f"Dangerous function call detected: {stripped[:80]}",
                                    "omission_type": "dangerous_pattern",
                                    "blast_radius_multiplier": 1.3,
                                    "language": "python",
                                }
                            )

                    # Check for debug mode
                    for pat, rule_id, sev in debug_patterns:
                        if pat.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": "Debug Mode Enabled in Production",
                                    "file": rel_path,
                                    "line": i + 1,
                                    "severity": sev,
                                    "confidence_interval": (0.75, 0.92),
                                    "reason": "Debug mode should not be enabled in production code",
                                    "omission_type": "misconfiguration",
                                    "blast_radius_multiplier": 1.1,
                                    "language": "python",
                                }
                            )

                    # Check for SQL injection
                    for pat, rule_id, sev in sql_patterns:
                        if pat.search(stripped):
                            findings.append(
                                {
                                    "rule_id": rule_id,
                                    "title": "Potential SQL Injection",
                                    "file": rel_path,
                                    "line": i + 1,
                                    "severity": sev,
                                    "confidence_interval": (0.70, 0.90),
                                    "reason": f"String formatting in SQL query: {stripped[:80]}",
                                    "omission_type": "injection_risk",
                                    "blast_radius_multiplier": 1.4,
                                    "language": "python",
                                }
                            )

                # Check for missing auth on routes (file-level)
                file_text = text
                for match in route_decorators.finditer(file_text):
                    start = max(0, match.start() - 500)
                    snippet = file_text[start : match.end() + 200]
                    if not auth_decorators.search(snippet):
                        line_num = file_text[: match.start()].count("\n") + 1
                        findings.append(
                            {
                                "rule_id": "missing_auth",
                                "title": "Missing Authentication on API Endpoint",
                                "file": rel_path,
                                "line": line_num,
                                "severity": "critical",
                                "confidence_interval": (0.65, 0.95),
                                "reason": "API route defined without auth decorator",
                                "omission_type": "absence_of_control",
                                "blast_radius_multiplier": 1.3,
                                "language": "python",
                            }
                        )

            except Exception as e:
                logger.debug("Fallback scan failed for %s: %s", py_file, e)

            if len(findings) >= 200:
                break

        # Check for missing rate limiting (file-level heuristic)
        rate_limit_keywords = re.compile(
            r"(rate_limit|throttle|@RateLimit|express-rate-limit)", re.IGNORECASE
        )
        for py_file in root.rglob("*.py"):
            if should_skip(py_file):
                continue
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                has_routes = "@app.route" in text or "@router" in text
                lacks_rate_limit = has_routes and not rate_limit_keywords.search(text)
                if has_routes and lacks_rate_limit:
                    rel_path = str(py_file.relative_to(root))
                    # Only add if not already reported for this file
                    if not any(
                        f.get("file") == rel_path and f.get("rule_id") == "missing_rate_limiting"
                        for f in findings
                    ):
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
            except Exception as e:
                logger.debug("Fallback rate-limit scan failed for %s: %s", py_file, e)
            if len(findings) >= 250:
                break

        return findings[:250]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _omission_to_finding(om: dict[str, Any], _topology: dict[str, Any]) -> UFICFinding:
        sev_map = {
            "critical": Severity.CRITICAL if hasattr(Severity, "CRITICAL") else "critical",
            "high": Severity.HIGH if hasattr(Severity, "HIGH") else "high",
            "medium": Severity.MEDIUM if hasattr(Severity, "MEDIUM") else "medium",
            "low": Severity.LOW if hasattr(Severity, "LOW") else "low",
            "info": Severity.INFO if hasattr(Severity, "INFO") else "info",
        }
        severity = sev_map.get(om.get("severity", "medium").lower(), "medium")
        ci = om.get("confidence_interval", (0.50, 0.85))
        if not isinstance(ci, (list, tuple)) or len(ci) < 2:
            ci = (0.50, 0.85)

        file_path = om.get("file", "")
        line_num = om.get("line", 0)
        rule_id = om["rule_id"]

        return UFICFinding(
            id=stable_ufic_finding_id(
                rule_id=rule_id,
                file_path=file_path,
                line=line_num,
                column=om.get("column", 0),
            ),
            rule_id=rule_id,
            rule_name=om.get("title", rule_id),
            title=om.get("title", rule_id),
            severity=severity,
            effective_severity=severity,
            message=om.get("reason", ""),
            description=om.get("reason", ""),
            file=file_path,
            path=file_path,
            line=line_num,
            column=om.get("column", 0),
            category="ufic",
            scanner="ufic",
            confidence=ci[1] if len(ci) > 1 else 0.7,
            conformal_lower=ci[0] if len(ci) > 0 else 0.5,
            conformal_upper=ci[1] if len(ci) > 1 else 0.85,
            blast_radius={
                "blast_radius_score": int(om.get("blast_radius_multiplier", 1.0) * 100),
                "is_assessed": False,
                "reduction_if_fixed": om.get("blast_radius_multiplier", 1.0) * 100,
            },
            intent="production",
            blast_radius_multiplier=om.get("blast_radius_multiplier", 1.0),
            confidence_interval=tuple(ci),
            is_omission=True,
            causal_impact={"omission_type": om.get("omission_type", "")},
            recommended_action="escalate",
            language=om.get("language", "unknown"),
            metadata={
                "rule_id": rule_id,
                "language": om.get("language", "unknown"),
            },
        )
