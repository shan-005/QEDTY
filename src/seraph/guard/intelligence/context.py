from __future__ import annotations

import dataclasses
import logging

from typing import Any

from seraph.guard.scanners.base import Finding, Severity, is_test_file


logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class IntelligenceConfig:
    """Configuration for the intelligence layer algorithms."""

    scanner_alphas: dict[str, float] = dataclasses.field(
        default_factory=lambda: {
            "PolicyScanner": 0.05,
            "PatternScanner": 0.15,
            "SecretScanner": 0.10,
            "SBOMScanner": 0.20,
            "Default": 0.10,
        }
    )
    weight_severity: float = 10.0
    weight_blast_radius_score: float = 0.2
    weight_blast_radius_reduction: float = 0.1
    non_production_penalty: float = 0.4

    test_downgrades: dict[Severity, Severity] = dataclasses.field(
        default_factory=lambda: {
            Severity.CRITICAL: Severity.INFO,
            Severity.HIGH: Severity.INFO,
            Severity.MEDIUM: Severity.LOW,
            Severity.LOW: Severity.INFO,
        }
    )
    framework_downgrades: dict[Severity, Severity] = dataclasses.field(
        default_factory=lambda: {
            Severity.CRITICAL: Severity.MEDIUM,
            Severity.HIGH: Severity.LOW,
            Severity.MEDIUM: Severity.LOW,
        }
    )
    build_downgrades: dict[Severity, Severity] = dataclasses.field(
        default_factory=lambda: {
            Severity.CRITICAL: Severity.HIGH,
            Severity.HIGH: Severity.MEDIUM,
        }
    )


DEFAULT_CONFIG = IntelligenceConfig()


class ConformalPredictor:
    @staticmethod
    def apply(finding: Finding, config: IntelligenceConfig = DEFAULT_CONFIG) -> Finding:
        alpha = config.scanner_alphas.get(finding.scanner, config.scanner_alphas["Default"])
        conf = finding.confidence if finding.confidence is not None else 0.5
        base_sev = finding.severity

        if conf >= (1.0 - alpha):
            conformal_set = [base_sev.value.upper()]
        elif conf >= (1.0 - (alpha * 2)):
            conformal_set = ConformalPredictor._get_adjacent_severities(base_sev)
        else:
            conformal_set = sorted(
                {"INFO", base_sev.value.upper()},
                key=lambda s: (
                    Severity(s.lower()).weight if s.lower() in [e.value for e in Severity] else -1
                ),
                reverse=True,
            )

        # FIX: Use dataclasses.replace to safely update frozen dataclasses
        return dataclasses.replace(
            finding, conformal_set=conformal_set, conformal_confidence=round(conf * 100, 2)
        )

    @staticmethod
    def _get_adjacent_severities(sev: Severity) -> list[str]:
        order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        if sev not in order:
            return [sev.value.upper()]
        idx = order.index(sev)
        adj = [sev.value.upper()]
        if idx > 0:
            adj.append(order[idx - 1].value.upper())
        if idx < len(order) - 1:
            adj.append(order[idx + 1].value.upper())
        adj.sort(key=lambda s: Severity(s.lower()).weight, reverse=True)
        return adj


class CausalRanker:
    @staticmethod
    def rank(findings: list[Finding], config: IntelligenceConfig = DEFAULT_CONFIG) -> list[Finding]:
        def impact_score(f: Finding) -> float:
            try:
                sev = f.effective_severity or f.severity or Severity.INFO
                base_score = sev.weight * config.weight_severity
                br_bonus = 0.0
                br = getattr(f, "blast_radius", None)
                if br and getattr(br, "is_assessed", False):
                    br_bonus += (
                        getattr(br, "blast_radius_score", 0) * config.weight_blast_radius_score
                    )
                    br_bonus += (
                        getattr(br, "reduction_if_fixed", 0) * config.weight_blast_radius_reduction
                    )

                ctx_mult = (
                    config.non_production_penalty
                    if not getattr(f, "is_production_code", True)
                    else 1.0
                )
                conf_mult = 0.5 + (getattr(f, "confidence", 0.5) or 0.5)
                return (base_score + br_bonus) * conf_mult * ctx_mult
            except Exception as e:
                logger.warning(
                    "Error calculating impact score for finding %s: %s",
                    getattr(f, "id", "unknown"),
                    e,
                )
                return 0.0

        sorted_findings = sorted(findings, key=impact_score, reverse=True)

        # FIX: Use dataclasses.replace to safely assign causal_rank to frozen dataclasses
        ranked_findings = []
        for i, f in enumerate(sorted_findings):
            ranked_findings.append(dataclasses.replace(f, causal_rank=i + 1))

        return ranked_findings


class ContextManager:
    @staticmethod
    def apply_downgrades(
        finding: Finding, config: IntelligenceConfig = DEFAULT_CONFIG
    ) -> tuple[Finding, str | None]:
        file_path = getattr(finding, "file", "")
        rel = file_path.lower()
        title = getattr(finding, "title", "")
        title_lower = title.lower() if title else ""

        new_attrs: dict[str, Any] = {}

        # 1. Test files → downgraded to INFO
        if is_test_file(file_path):
            if finding.severity in config.test_downgrades:
                new_attrs["severity"] = config.test_downgrades[finding.severity]
                new_attrs["is_suppressed"] = True
                new_attrs["suppression_reason"] = "Test finding auto-downgraded"
            if new_attrs:
                return dataclasses.replace(finding, **new_attrs), "test"
            return finding, "test"

        # 2. Framework internals → downgraded to LOW
        is_fw = False
        if (
            "airflow" in rel
            and any(
                p in rel
                for p in (
                    "airflow-core/src/airflow/",
                    "providers/amazon/",
                    "providers/common/sql/",
                    "providers/databricks/",
                    "providers/docker/",
                    "providers/edge3/",
                    "providers/jenkins/",
                    "providers/microsoft/azure/",
                    "providers/singularity/",
                    "task-sdk/src/airflow/sdk/",
                )
            )
            and any(
                r in title_lower
                for r in ("eval", "exec", "pickle", "__import__", "hardcoded password")
            )
        ):
            is_fw = True

        if any(
            p in rel
            for p in (
                "builtin/credential/",
                "builtin/logical/database/",
                "plugins/database/",
                "sdk/database/helper/",
                "ui/mirage/",
            )
        ) and ("hardcoded" in title_lower or "password" in title_lower):
            is_fw = True

        if is_fw:
            if finding.severity in config.framework_downgrades:
                new_attrs["severity"] = config.framework_downgrades[finding.severity]
                new_attrs["is_suppressed"] = True
                new_attrs["suppression_reason"] = "Framework internal auto-downgraded"
            if new_attrs:
                return dataclasses.replace(finding, **new_attrs), "framework"
            return finding, "framework"

        # 3. Build scripts → downgraded to LOW
        if any(
            p in rel
            for p in ("scripts/", "devtools/", "build/", "gruntfile", "gulpfile", "webpack")
        ):
            if finding.severity in config.build_downgrades:
                new_attrs["severity"] = config.build_downgrades[finding.severity]
                new_attrs["is_suppressed"] = True
                new_attrs["suppression_reason"] = "Build script auto-downgraded"
            if new_attrs:
                return dataclasses.replace(finding, **new_attrs), "build"
            return finding, "build"

        return finding, None


class IntelligenceLayer:
    @classmethod
    def process(
        cls, findings: list[Finding], config: IntelligenceConfig = DEFAULT_CONFIG
    ) -> tuple[list[Finding], dict[str, int]]:
        enriched: list[Finding] = []
        stats = {
            "test_downgraded": 0,
            "framework_downgraded": 0,
            "build_downgraded": 0,
            "errors": 0,
        }

        for raw_f in findings:
            try:
                f = ConformalPredictor.apply(raw_f, config)
                f, category = ContextManager.apply_downgrades(f, config)
                if category:
                    stats[f"{category}_downgraded"] += 1
                enriched.append(f)
            except Exception:
                logger.exception(
                    "Intelligence Layer failed on finding %s", getattr(raw_f, "location", "unknown")
                )
                stats["errors"] += 1
                enriched.append(raw_f)

        ranked = CausalRanker.rank(enriched, config)

        logger.info(
            "Intelligence Layer: %d findings processed. %d test downgraded, %d framework downgraded, %d build downgraded. %d errors.",
            len(ranked),
            stats["test_downgraded"],
            stats["framework_downgraded"],
            stats["build_downgraded"],
            stats["errors"],
        )
        return ranked, stats
