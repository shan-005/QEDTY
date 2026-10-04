"""Seraph Guard v2.1 — The Ontological Conductor

Implements the 3-Layer Security Nervous System:
  L1: PERCEPTION  → Multi-Agent Scanner Swarm
  L2: COGNITION   → Intelligence Meta-Agent (Ontology + Engines)
  L3: ACTION      → Remediation & Prevention

Architectural Rules:
  1. cli.py is thin (argument parsing only).
  2. scheduler.py is the conductor.
  3. No scanner talks directly to another scanner.
  4. All communication goes through the Seraph Ontology.
"""

from __future__ import annotations

import asyncio
import logging

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Core Seraph imports
from seraph.guard.config import SeraphConfig
from seraph.guard.deduplication import DeduplicationEngine
from seraph.guard.explanation.engine import ExplanationEngine

# Layer 3: Action
from seraph.guard.intelligence.causal import CausalRanker

# Layer 2: Intelligence / Cognition
from seraph.guard.intelligence.conformal import ConformalPredictionEngine
from seraph.guard.intelligence.learning import AdaptiveLearningEngine

# Ontology — the central knowledge graph
from seraph.guard.ontology import SeraphOntology

# Discovery
from seraph.guard.orchestration.discovery import RepoDiscovery, RepoProfile
from seraph.guard.scanners.base import Finding, ScanContext, Scanner

# Layer 2: Suppression & Dedup
from seraph.guard.suppression.engine import SuppressionEngine


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Layer Result Data Classes
# ═══════════════════════════════════════════════════════════════


@dataclass
class Layer1Result:
    """Raw output from the Perception Layer (Scanner Swarm)."""

    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scan_duration_ms: float = 0.0
    scanners_executed: list[str] = field(default_factory=list)
    scanners_skipped: list[str] = field(default_factory=list)
    scanner_status: dict[str, str] = field(default_factory=dict)
    scanner_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class Layer2Result:
    """Enriched output from the Cognition Layer (Intelligence Meta-Agent)."""

    findings: list[Finding] = field(default_factory=list)
    suppressed_findings: list[Finding] = field(default_factory=list)
    suppression_stats: dict[str, int] = field(default_factory=dict)
    conformal_applied: bool = False
    causal_applied: bool = False
    learning_applied: bool = False
    dedup_applied: bool = False
    explanation_applied: bool = False
    explanations_generated: int = 0
    explanations: list[dict[str, Any]] = field(default_factory=list)
    ontology_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class Layer3Result:
    """Actionable output from the Action Layer (Remediation & Prevention)."""

    fixes_applied: list[dict[str, Any]] = field(default_factory=list)
    fixes_failed: list[dict[str, Any]] = field(default_factory=list)
    lsp_diagnostics_pushed: int = 0
    report_paths: list[str] = field(default_factory=list)
    team_sync_exported: bool = False


@dataclass
class PipelineResult:
    """Complete result from the 3-Layer Ontological Pipeline.

    This is the unified output that cli.py consumes for rendering.
    """

    layer1: Layer1Result = field(default_factory=Layer1Result)
    layer2: Layer2Result = field(default_factory=Layer2Result)
    layer3: Layer3Result = field(default_factory=Layer3Result)
    repo_profile: RepoProfile | None = None
    scan_duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # ══ v1.x backward-compatibility properties ══
    @property
    def findings(self) -> list[Finding]:
        """Returns production findings (post-cognition) for v1.x compatibility."""
        return self.layer2.findings

    @property
    def errors(self) -> list[str]:
        return self.layer1.errors

    @property
    def warnings(self) -> list[str]:
        return self.layer1.warnings

    @property
    def scanners_executed(self) -> list[str]:
        return self.layer1.scanners_executed

    @property
    def scanners_skipped(self) -> list[str]:
        return self.layer1.scanners_skipped

    @property
    def scanner_status(self) -> dict[str, str]:
        return self.layer1.scanner_status

    @property
    def scanner_metadata(self) -> dict[str, dict[str, Any]]:
        return self.layer1.scanner_metadata

    @property
    def total_raw_findings(self) -> int:
        return len(self.layer1.findings)

    @property
    def total_production_findings(self) -> int:
        return len(self.layer2.findings)

    @property
    def total_suppressed(self) -> int:
        return len(self.layer2.suppressed_findings)

    @property
    def has_errors(self) -> bool:
        """True when any scanner or pipeline execution error occurred."""
        return bool(self.layer1.errors)

    @property
    def scan_status(self) -> str:
        """Machine-readable terminal status for the pipeline.

        A pipeline with any Layer 1 or fatal pipeline error is never
        considered successful, even when it produced zero findings.
        """
        return "failed" if self.has_errors else "completed"

    @property
    def success(self) -> bool:
        """True only when the pipeline completed without execution errors."""
        return not self.has_errors


# v1.x alias for external imports that expect ScanResult
ScanResult = PipelineResult


# ═══════════════════════════════════════════════════════════════
# The Conductor
# ═══════════════════════════════════════════════════════════════


class Scheduler:
    """Seraph Guard v2.0 Scheduler — The Ontological Conductor.

    This is the ONLY component that may coordinate between scanners.
    Scanners do NOT talk to each other. All inter-scanner state flows
    through the Seraph Ontology (built and enriched here).
    """

    ontology: SeraphOntology

    def __init__(self, config: SeraphConfig) -> None:
        self.config = config

        # Safe extraction of nested config attributes to prevent AttributeError
        # if the Pydantic sub-models are None or missing.
        scanners_cfg = getattr(config, "scanners", None)
        self.timeout = (
            getattr(scanners_cfg, "timeout_seconds", 900) if scanners_cfg is not None else 900
        )
        self.parallel_workers = (
            getattr(scanners_cfg, "parallel_workers", 4) if scanners_cfg is not None else 4
        )

        # Layer 2: Intelligence Engines
        intel_cfg = getattr(config, "intelligence", None)
        alpha = getattr(intel_cfg, "conformal_alpha", 0.1) if intel_cfg is not None else 0.1
        min_cal = getattr(intel_cfg, "min_calibration_samples", 30) if intel_cfg is not None else 30

        self._conformal = ConformalPredictionEngine(
            alpha=alpha,
            min_calibration_size=min_cal,
        )
        self._causal = CausalRanker()
        self._explainer = ExplanationEngine()

        learn_cfg = getattr(config, "learning", None)
        configured_cache_dir = (
            getattr(learn_cfg, "cache_dir", Path(".seraph-learn"))
            if learn_cfg is not None
            else Path(".seraph-learn")
        )
        self._learning_cache_dir = (
            Path(configured_cache_dir)
            if configured_cache_dir is not None
            else Path(".seraph-learn")
        )
        # Adaptive learning is lazy because engine initialization may create
        # persistent state. A normal scan must not create .seraph-learn.
        self._learning: AdaptiveLearningEngine | None = None
        self._dedup = DeduplicationEngine()

        # SuppressionEngine must not write engine-generated suppressions into adaptive learning.
        # It is initialized strictly with the scan path to prevent self-poisoning of the learning cache.
        scan_path = getattr(config, "scan_path", ".")
        self._suppression = SuppressionEngine(str(scan_path))

        # The Ontology — mandatory central knowledge graph.
        self.ontology = SeraphOntology()

    # ── Public API ────────────────────────────────────────────

    async def run(
        self,
        context: ScanContext,
        scanners: list[Scanner],
        pipeline_options: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Execute the full 3-Layer Ontological Pipeline.

        Phase 0: Discovery      → Build repo profile (if not provided)
        Phase 1: Perception     → Run scanner swarm
        Phase 2: Cognition      → Ontology + Intelligence Meta-Agent
        Phase 3: Action         → Remediation & Prevention

        Args:
            context: ScanContext with path, config, optional profile
            scanners: List of Scanner instances to execute
            pipeline_options: Dict controlling layer behavior:
                - deduplication: bool (default True)
                - suppression: bool (default True)
                - learn: bool (default from config)
                - rank_by_impact: bool (default False)
                - explain: bool (default False)
                - fix: bool (default False)
                - fix_all: bool (default False)
                - baseline_path: str | None
        """
        opts = dict(pipeline_options or {})

        # A Scheduler is reusable, but ontology state is scan-local. Reset before
        # every run so findings from a previous repository cannot contaminate the
        # current repository's impact or explanation evidence.
        self.ontology.reset()
        context.ontology = self.ontology
        result = PipelineResult()
        t0 = asyncio.get_running_loop().time()

        logger.info("[Scheduler] ═══════════════════════════════════════")
        logger.info("[Scheduler] Seraph Guard v2.0 Pipeline Starting")
        logger.info("[Scheduler] ═══════════════════════════════════════")

        try:
            # ── Phase 0: Discovery ──
            if context.profile is None:
                logger.info("[Scheduler] Phase 0: Repository Discovery")
                discovery = RepoDiscovery(Path(context.path))
                context.profile = discovery.discover()
            result.repo_profile = context.profile

            # ── Layer 1: PERCEPTION ──
            logger.info("[Scheduler] Layer 1: PERCEPTION — Scanner Swarm")
            result.layer1 = await self._layer1_perceive(context, scanners)

            # Scanner failures are execution failures, not an empty scan.
            # We retain successful findings for diagnostics/output, but the
            # failure state is deliberately preserved through Layers 2/3 so
            # callers can never mistake a partial scan for a clean scan.
            if result.layer1.errors:
                logger.error(
                    "[Scheduler] Layer 1 completed with %d scanner error(s); "
                    "pipeline remains FAILED",
                    len(result.layer1.errors),
                )

            # Build / update ontology with raw findings
            if self.ontology is not None:
                self.ontology.ingest_findings(result.layer1.findings, context)
                logger.info(
                    "[Scheduler] Ontology: %d objects, %d links",
                    getattr(self.ontology, "object_count", 0),
                    getattr(self.ontology, "link_count", 0),
                )

            # ── Layer 2: COGNITION ──
            logger.info("[Scheduler] Layer 2: COGNITION — Intelligence Meta-Agent")
            context.ontology = self.ontology
            result.layer2 = self._layer2_cognize(
                raw_findings=result.layer1.findings,
                context=context,
                options=opts,
            )

            # Enrich ontology with post-cognition findings
            if self.ontology is not None:
                self.ontology.enrich_findings(result.layer2.findings)
                result.layer2.ontology_snapshot = self.ontology.to_dict()

            # ── Layer 3: ACTION ──
            logger.info("[Scheduler] Layer 3: ACTION — Remediation & Prevention")
            result.layer3 = await self._layer3_act(
                findings=result.layer2.findings,
                context=context,
                options=opts,
            )

        except Exception as exc:
            # Never convert a scheduler failure into an apparently clean result.
            # Keep the result object usable for CLI/output diagnostics, while
            # recording the fatal condition in the same error channel consumed
            # by the CLI's fail-closed exit-code logic.
            logger.exception("[Scheduler] Pipeline fatal error")
            message = f"Pipeline fatal error: {type(exc).__name__}: {exc}"
            if message not in result.layer1.errors:
                result.layer1.errors.append(message)

            if result.layer1.scanner_status.get("Scheduler") is None:
                result.layer1.scanner_status["Scheduler"] = f"✗ FATAL: {type(exc).__name__}"

        finally:
            elapsed = asyncio.get_running_loop().time() - t0
            result.scan_duration_ms = round(elapsed * 1000, 2)
            logger.info(
                "[Scheduler] Pipeline complete in %.2fms | Raw: %d | Production: %d | Suppressed: %d",
                result.scan_duration_ms,
                result.total_raw_findings,
                result.total_production_findings,
                result.total_suppressed,
            )

        return result

    # ── Layer 1: PERCEPTION ───────────────────────────────────

    async def _layer1_perceive(
        self,
        context: ScanContext,
        scanners: list[Scanner],
    ) -> Layer1Result:
        """Layer 1: PERCEPTION — The Multi-Agent Scanner Swarm.

        Each scanner is an autonomous agent with its own ontological view.
        They execute concurrently. Findings are tagged with scanner provenance
        before entering the shared ontology.
        """
        result = Layer1Result()
        t0 = asyncio.get_running_loop().time()

        applicable: list[Scanner] = []
        for scanner in scanners:
            name = getattr(scanner, "name", scanner.__class__.__name__)
            try:
                is_applicable = scanner.is_applicable(context)
            except Exception as exc:
                msg = f"{name}: applicability check failed: {type(exc).__name__}: {exc}"
                result.errors.append(msg)
                result.scanner_status[name] = f"✗ ERROR: {type(exc).__name__}"
                logger.warning(msg)
                continue

            if is_applicable:
                applicable.append(scanner)
                result.scanners_executed.append(name)
                result.scanner_status[name] = "✓ APPLICABLE"
            else:
                result.scanners_skipped.append(name)
                result.scanner_status[name] = "✗ NOT APPLICABLE"

        if not applicable:
            if not result.errors:
                result.warnings.append("No applicable scanners found for this repository context")
            return result

        # Execute the swarm concurrently, with a bounded number of workers and
        # an explicit per-scanner timeout. Individual failures are collected so
        # successful scanner results are retained for diagnostics, while any
        # failure remains fatal to the overall scan status.
        try:
            worker_limit = max(1, int(self.parallel_workers or 1))
        except (TypeError, ValueError):
            worker_limit = 1
        semaphore = asyncio.Semaphore(worker_limit)

        async def run_one(scanner: Scanner) -> list[Finding]:
            async with semaphore:
                try:
                    timeout_seconds = max(1.0, float(self.timeout)) + 15.0
                except (TypeError, ValueError):
                    timeout_seconds = 915.0
                return await asyncio.wait_for(
                    self._safe_scan(scanner, context),
                    timeout=timeout_seconds,
                )

        tasks = [asyncio.create_task(run_one(scanner)) for scanner in applicable]
        outputs = await asyncio.gather(*tasks, return_exceptions=True)

        for idx, output in enumerate(outputs):
            name = getattr(applicable[idx], "name", applicable[idx].__class__.__name__)
            if isinstance(output, Exception):
                # asyncio.TimeoutError is an alias of built-in TimeoutError on
                # supported Python versions, but keep the status explicit.
                if isinstance(output, TimeoutError):
                    error_type = "TimeoutError"
                else:
                    error_type = type(output).__name__
                msg = f"{name}: {error_type}: {output}"
                result.errors.append(msg)
                result.scanner_status[name] = f"✗ ERROR: {error_type}"
                logger.warning(msg)
                continue

            if not isinstance(output, list):
                msg = f"{name}: invalid scanner return type: {type(output).__name__}"
                result.errors.append(msg)
                result.scanner_status[name] = "✗ INVALID RETURN"
                logger.warning(msg)
                continue

            invalid_items = [item for item in output if not isinstance(item, Finding)]
            if invalid_items:
                msg = (
                    f"{name}: invalid scanner result: expected list[Finding], "
                    f"received {len(invalid_items)} invalid item(s)"
                )
                result.errors.append(msg)
                result.scanner_status[name] = "✗ INVALID RETURN"
                logger.warning(msg)
                continue

            # Tag provenance and enrich the ontology-bound stream without changing
            # scanner semantics. Scanner-generated metadata remains authoritative.
            scanner_version = str(getattr(applicable[idx], "version", "unknown"))
            for finding in output:
                finding.scanner = name
                if not isinstance(getattr(finding, "metadata", None), dict):
                    finding.metadata = {}
                finding.metadata.setdefault("scanner", name)
                finding.metadata.setdefault("scanner_version", scanner_version)
                finding.metadata.setdefault("scan_id", context.scan_id)
                finding.metadata.setdefault("file_context", getattr(finding, "file_context", ""))
            result.findings.extend(output)
            result.scanner_status[name] = f"✓ {len(output)} findings"

        # Scanners may publish non-fatal coverage/diagnostic metadata through the
        # shared ScanContext. Surface it without changing fail-closed semantics.
        raw_scanner_metadata = context.metadata.get("scanners", {})
        if isinstance(raw_scanner_metadata, dict):
            for scanner_name, scanner_meta in raw_scanner_metadata.items():
                if isinstance(scanner_meta, dict):
                    result.scanner_metadata[str(scanner_name)] = dict(scanner_meta)
                    if scanner_meta.get("coverage_status") == "partial":
                        current = result.scanner_status.get(str(scanner_name), "")
                        if current.startswith("✓") and "partial coverage" not in current.lower():
                            result.scanner_status[str(scanner_name)] = (
                                f"{current} (partial coverage)"
                            )

        raw_warnings = context.metadata.get("warnings", [])
        if isinstance(raw_warnings, list):
            for warning in raw_warnings:
                warning_text = str(warning)
                if warning_text and warning_text not in result.warnings:
                    result.warnings.append(warning_text)

        result.scan_duration_ms = round((asyncio.get_running_loop().time() - t0) * 1000, 2)
        logger.info(
            "[L1] Perception complete: %d raw findings from %d scanners in %.2fms",
            len(result.findings),
            len(result.scanners_executed),
            result.scan_duration_ms,
        )
        return result

    # ── Layer 2: COGNITION ────────────────────────────────────

    def _layer2_cognize(
        self,
        raw_findings: list[Finding],
        context: ScanContext,
        options: dict[str, Any],
    ) -> Layer2Result:
        """Layer 2: COGNITION — The Intelligence Meta-Agent.

        Six first-class cognition stages, executed in order:
          1. SuppressionEngine   → file/rule policy decisions
          2. DedupEngine         → semantic clustering of duplicate observations
          3. AdaptiveEngine      → optional local historical suppression learning
          4. ConformalEngine     → deterministic ordinal prediction sets
          5. CausalEngine        → repository-local structural impact prioritization
          6. ExplanationEngine  → deterministic evidence-backed explanation records

        The learning engine does not claim formal differential privacy, and the
        impact/ranking layer does not claim causal probabilities or measured loss.

        All state is written back to the Seraph Ontology.
        """
        result = Layer2Result()
        findings = list(raw_findings)

        # 1. Suppression
        if options.get("suppression", True):
            findings, suppressed, stats = self._apply_suppression(findings)
            result.suppressed_findings = suppressed
            result.suppression_stats = stats

        # 2. Semantic Deduplication
        if options.get("deduplication", True):
            findings = self._apply_dedup(findings)
            result.dedup_applied = True

        # 3. Adaptive Learning
        learn_cfg = getattr(self.config, "learning", None)
        configured_learning_enabled = (
            getattr(learn_cfg, "enabled", False) if learn_cfg is not None else False
        )

        # An explicit pipeline option is authoritative for this scan. This is
        # important for CLI invocations because LearningConfig defaults to
        # enabled=True, while `--learn` defaults to false. When the caller does
        # not provide the option, preserve direct Scheduler/config semantics.
        if "learn" in options:
            learn_enabled = bool(options["learn"])
        else:
            learn_enabled = bool(configured_learning_enabled)

        if learn_enabled:
            if self._learning is None:
                self._learning = AdaptiveLearningEngine(cache_dir=self._learning_cache_dir)
            findings = self._learning.apply_learning(findings)
            result.learning_applied = True

        # 4. Conformal Prediction (mathematical truth, not heuristic confidence)
        findings = self._conformal.apply(findings)
        result.conformal_applied = True

        # 5. Structural impact prioritization with repository-local evidence.
        if options.get("rank_by_impact", False) or options.get("explain", False):
            # Structural impact is computed from the current repository context.
            # The ontology remains the shared scan state and is supplied to the
            # ranker for integration/traceability.
            findings = self._causal.rank(
                findings,
                context=context,
                ontology=self.ontology,
            )
            result.causal_applied = True

        # Explanations are generated only after structural impact and priority
        # metadata exist. They are deterministic and evidence-backed; no LLM or
        # remote model is involved.
        if options.get("explain", False) and findings:
            try:
                explanation_limit = max(1, int(options.get("explanation_limit", 100)))
            except (TypeError, ValueError):
                explanation_limit = 100
            selected = findings[:explanation_limit]
            self._explainer.enrich_findings(selected)
            result.explanations = [
                dict(getattr(finding, "metadata", {}).get("explanation", {}))
                for finding in selected
                if isinstance(getattr(finding, "metadata", {}).get("explanation"), dict)
            ]
            result.explanations_generated = len(result.explanations)
            result.explanation_applied = bool(result.explanations)
            for finding in findings[explanation_limit:]:
                metadata = getattr(finding, "metadata", None)
                if not isinstance(metadata, dict):
                    metadata = {}
                    self._set(finding, "metadata", metadata)
                metadata.setdefault("explanation_status", "not_generated")
                metadata.setdefault("explanation_limit", explanation_limit)

        result.findings = findings
        logger.info(
            "[L2] Cognition complete: %d production findings "
            "(suppressed=%d, conformal=%s, causal=%s, learning=%s, dedup=%s, explain=%s/%d)",
            len(findings),
            len(result.suppressed_findings),
            result.conformal_applied,
            result.causal_applied,
            result.learning_applied,
            result.dedup_applied,
            result.explanation_applied,
            result.explanations_generated,
        )
        return result

    def _apply_suppression(
        self,
        findings: list[Finding],
    ) -> tuple[list[Finding], list[Finding], dict[str, int]]:
        """Apply the Suppression Engine.

        Returns: (production_findings, suppressed_findings, stats)
        """
        production: list[Finding] = []
        suppressed: list[Finding] = []
        stats: dict[str, int] = {
            "test_suppressed": 0,
            "example_suppressed": 0,
            "doc_suppressed": 0,
            "build_suppressed": 0,
            "framework_suppressed": 0,
            "generated_suppressed": 0,
            "dev_tooling_suppressed": 0,
            "rule_override_suppressed": 0,
            "rule_override_downgraded": 0,
        }

        for finding in findings:
            file_path = (
                getattr(finding, "file", "")
                or getattr(finding, "path", "")
                or getattr(finding, "source_file", "")
            )

            classification = self._suppression.classify_file(file_path)
            should_scan, _ = self._suppression.should_scan_file(file_path)

            if not should_scan:
                suppressed.append(finding)
                key = f"{classification.category.value}_suppressed"
                stats[key] = stats.get(key, 0) + 1
                continue

            fdict = self._finding_to_dict(finding)
            is_suppressed, new_sev, _reason = self._suppression.apply_suppression(
                fdict, classification
            )

            if is_suppressed:
                suppressed.append(finding)
                stats["rule_override_suppressed"] += 1
                continue

            if new_sev:
                self._set_effective_severity(finding, new_sev)
                stats["rule_override_downgraded"] += 1

            # A critical/high test finding intentionally bypasses the
            # suppression engine's severity exception, but it must still never
            # enter the production gate. Finding.file_context is the canonical
            # classification established by scanners.base.Finding.
            if not getattr(finding, "is_production_code", False):
                suppressed.append(finding)
                context_name = (
                    getattr(finding, "file_context", "non_production") or "non_production"
                )
                key = f"{context_name}_suppressed"
                stats[key] = stats.get(key, 0) + 1
                try:
                    object.__setattr__(
                        finding,
                        "is_suppressed",
                        True,
                    )
                    object.__setattr__(
                        finding,
                        "suppression_reason",
                        f"Excluded from production evaluation: {context_name} code",
                    )
                except (AttributeError, TypeError):
                    pass
                continue

            production.append(finding)

        return production, suppressed, stats

    def _apply_dedup(self, findings: list[Finding]) -> list[Finding]:
        """Semantic deduplication via graph clustering (not hash-based)."""
        dicts: list[dict[str, Any]] = []
        for f in findings:
            d = self._finding_to_dict(f)
            d["_original"] = f
            dicts.append(d)

        deduped = self._dedup.deduplicate(dicts)
        out: list[Finding] = []
        for d in deduped:
            orig = d.get("_original")
            if orig is not None:
                # Rehydrate canonical dedup metadata onto the representative Finding.
                for attr, default in (
                    ("dedup_cluster_id", None),
                    ("locations", []),
                    ("location_count", 1),
                    ("affected_files", []),
                ):
                    if attr in d:
                        try:
                            object.__setattr__(orig, attr, d.get(attr, default))
                        except (AttributeError, TypeError):
                            pass
                merged_meta = d.get("metadata")
                if isinstance(merged_meta, dict):
                    try:
                        object.__setattr__(orig, "metadata", dict(merged_meta))
                    except (AttributeError, TypeError):
                        pass
                out.append(orig)
            else:
                out.append(d)  # type: ignore[arg-type]
        return out

    # ── Layer 3: ACTION ───────────────────────────────────────

    async def _layer3_act(
        self,
        findings: list[Finding],
        context: ScanContext,
        options: dict[str, Any],
    ) -> Layer3Result:
        """Layer 3: ACTION — Remediation & Prevention.

        FixEngine     → File-type routing (Python, IaC, Config, Dependency)
        LSPEngine     → Real-time IDE warnings via LSP
        TeamSync      → FL+DP pattern aggregation without code exfiltration
        ReportEngine  → Flask dashboard server with live ontology API
        """
        result = Layer3Result()

        # FixEngine is invoked directly by cli.py (_cmd_fix) to handle
        # dry-runs, user prompts, and backup management. It is not
        # instantiated here so the scheduler never creates a discarded fixer.

        # LSPEngine, TeamSync, ReportEngine are triggered by cli.py
        # but orchestrated here for completeness.
        return result

    # ── Utilities ─────────────────────────────────────────────

    async def _safe_scan(self, scanner: Scanner, context: ScanContext) -> list[Finding]:
        """Run one scanner while preserving a precise failure identity.

        The Layer 1 caller intentionally collects these exceptions rather than
        allowing one scanner to cancel successful scanners. The collected error
        is then surfaced through ``PipelineResult.errors`` and consumed by the
        CLI's fail-closed exit path.
        """
        name = getattr(scanner, "name", scanner.__class__.__name__)
        try:
            output = await scanner.scan(context)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise TimeoutError(f"{name} exceeded {self.timeout}s scanner timeout") from None
        except Exception as exc:
            raise RuntimeError(f"{name} runtime failure: {exc}") from exc

        if not isinstance(output, list):
            raise TypeError(f"{name} returned {type(output).__name__}; expected list[Finding]")
        return output

    @staticmethod
    def _finding_to_dict(finding: Finding) -> dict[str, Any]:
        """Normalize a Finding into a dict for engine consumption."""
        metadata = getattr(finding, "metadata", None)

        return {
            "id": getattr(finding, "id", ""),
            "file": getattr(finding, "file", "") or getattr(finding, "path", ""),
            "line": getattr(finding, "line", 0),
            "column": getattr(finding, "column", 0),
            "rule_id": getattr(finding, "rule_id", getattr(finding, "id", "")),
            "rule_name": getattr(finding, "rule_name", ""),
            "severity": str(getattr(finding, "severity", "info")).lower(),
            "effective_severity": str(getattr(finding, "effective_severity", "")).lower(),
            "message": getattr(finding, "message", ""),
            "description": getattr(finding, "description", ""),
            "context": getattr(finding, "context", ""),
            "contains_sensitive_value": bool(
                getattr(finding, "secret_value", "")
                or getattr(finding, "value", "")
                or getattr(finding, "_raw_secret", "")
            ),
            "variable_name": getattr(finding, "variable_name", ""),
            "tags": getattr(finding, "tags", []),
            "category": str(getattr(finding, "category", "")),
            "scanner": getattr(finding, "scanner", ""),
            "confidence": getattr(finding, "confidence", 0.0),
            "conformal_lower": getattr(finding, "conformal_lower", None),
            "conformal_upper": getattr(finding, "conformal_upper", None),
            "conformal_confidence": getattr(finding, "conformal_confidence", None),
            "blast_radius": getattr(finding, "blast_radius", None),
            "causal_rank": getattr(finding, "causal_rank", None),
            "fix_available": getattr(finding, "fix_available", False),
            "fix_command": getattr(finding, "fix_command", ""),
            "cve": getattr(finding, "cve", ""),
            "commit": (metadata or {}).get("commit", ""),
            "cwe": getattr(finding, "cwe", None),
            "cwe_aliases": getattr(finding, "cwe_aliases", []),
            "file_context": getattr(finding, "file_context", ""),
            "metadata": getattr(finding, "to_dict", lambda: {"metadata": metadata or {}})().get(
                "metadata", metadata or {}
            ),
        }

    @staticmethod
    def _set_effective_severity(finding: Finding, new_sev: Any) -> None:
        """Robust severity setter with frozen-dataclass fallback."""
        try:
            object.__setattr__(finding, "effective_severity", new_sev)
        except (AttributeError, TypeError, ValueError):
            try:
                finding.severity = new_sev
            except (AttributeError, TypeError, ValueError):
                object.__setattr__(finding, "severity", new_sev)

    @staticmethod
    def _set(obj: Any, name: str, value: Any) -> None:
        """Robust attribute setter with frozen-dataclass fallback."""
        try:
            setattr(obj, name, value)
        except (AttributeError, TypeError):
            object.__setattr__(obj, name, value)
