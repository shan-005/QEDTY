"""seraph.guard.scanners.iac — Infrastructure-as-Code Security Scanner

Scans Terraform, CloudFormation, Kubernetes manifests, and Dockerfiles
against CIS benchmarks and built-in policies.

Moats: Semantic Topology, Ontology Compounding
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Safe fallback for base imports
try:
    from seraph.guard.scanners.base import (
        Category as _Category,
        Finding,
        Severity,
    )

    _HAS_BASE = True
except Exception:
    _HAS_BASE = False

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

    class _Category:  # type: ignore[no-redef]
        IAC = "iac"
        POLICY = "policy"


logger = logging.getLogger("seraph.guard.scanners.iac")


# ── Policy dataclass ──
@dataclass
class IaCPolicy:
    """A single IaC policy rule."""

    id: str
    title: str
    severity: Any
    category: str  # terraform | k8s | dockerfile | cloudformation
    patterns: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    message: str = ""
    remediation: str = ""


# ── Built-in policy database ──
BUILTIN_POLICIES: list[IaCPolicy] = [
    # Terraform
    IaCPolicy(
        id="tf-s3-public",
        title="S3 Bucket Public Access Enabled",
        severity=Severity.CRITICAL if hasattr(Severity, "CRITICAL") else "critical",
        category="terraform",
        patterns=[r"aws_s3_bucket.*public_access", r"acl\s*=\s*\"public-read\""],
        message="S3 bucket allows public access.",
        remediation="Set acl = 'private' and use aws_s3_bucket_public_access_block.",
    ),
    IaCPolicy(
        id="tf-sg-wide",
        title="Security Group Allows 0.0.0.0/0",
        severity=Severity.HIGH if hasattr(Severity, "HIGH") else "high",
        category="terraform",
        patterns=[r"cidr_blocks\s*=\s*\[\"0\.0\.0\.0/0\"\]"],
        message="Security group allows unrestricted inbound access.",
        remediation="Restrict CIDR blocks to specific IP ranges.",
    ),
    IaCPolicy(
        id="tf-rds-public",
        title="RDS Instance Publicly Accessible",
        severity=Severity.HIGH if hasattr(Severity, "HIGH") else "high",
        category="terraform",
        patterns=[r"publicly_accessible\s*=\s*true"],
        message="RDS database is exposed to the internet.",
        remediation="Set publicly_accessible = false and use VPC peering.",
    ),
    # Kubernetes
    IaCPolicy(
        id="k8s-privileged",
        title="Privileged Container Detected",
        severity=Severity.CRITICAL if hasattr(Severity, "CRITICAL") else "critical",
        category="k8s",
        patterns=[r"privileged:\s*true"],
        message="Container runs in privileged mode (container escape risk).",
        remediation="Remove privileged: true and use capabilities add/drop.",
    ),
    IaCPolicy(
        id="k8s-missing-security-context",
        title="Missing securityContext",
        severity=Severity.HIGH if hasattr(Severity, "HIGH") else "high",
        category="k8s",
        patterns=[r"kind:\s*(Deployment|Pod|StatefulSet|DaemonSet)"],
        anti_patterns=[r"securityContext:"],
        message="Pod/Container spec lacks securityContext.",
        remediation="Add securityContext with runAsNonRoot, readOnlyRootFilesystem, etc.",
    ),
    IaCPolicy(
        id="k8s-hostpath",
        title="HostPath Volume Mount",
        severity=Severity.HIGH if hasattr(Severity, "HIGH") else "high",
        category="k8s",
        patterns=[r"hostPath:"],
        message="HostPath breaks pod isolation.",
        remediation="Use PersistentVolumeClaim or emptyDir instead.",
    ),
    IaCPolicy(
        id="k8s-latest-tag",
        title="Container Uses 'latest' Tag",
        severity=Severity.MEDIUM if hasattr(Severity, "MEDIUM") else "medium",
        category="k8s",
        patterns=[r"image:\s*[^\n]+:latest"],
        message="'latest' tag is non-reproducible.",
        remediation="Pin to a specific digest or semantic version.",
    ),
    # Dockerfile
    IaCPolicy(
        id="docker-root-user",
        title="Dockerfile Runs as Root",
        severity=Severity.HIGH if hasattr(Severity, "HIGH") else "high",
        category="dockerfile",
        patterns=[r"^FROM\s+"],
        anti_patterns=[r"USER\s+\d+"],
        message="No USER instruction — container runs as root.",
        remediation="Add 'USER 1000' before CMD/ENTRYPOINT.",
    ),
    IaCPolicy(
        id="docker-latest-tag",
        title="Dockerfile Uses 'latest' Tag",
        severity=Severity.MEDIUM if hasattr(Severity, "MEDIUM") else "medium",
        category="dockerfile",
        patterns=[r"FROM\s+[^\n]+:latest"],
        message="Base image uses 'latest' tag.",
        remediation="Pin to a specific version or digest.",
    ),
    IaCPolicy(
        id="docker-missing-healthcheck",
        title="Dockerfile Missing HEALTHCHECK",
        severity=Severity.MEDIUM if hasattr(Severity, "MEDIUM") else "medium",
        category="dockerfile",
        patterns=[r"^FROM\s+"],
        anti_patterns=[r"HEALTHCHECK"],
        message="No HEALTHCHECK instruction defined.",
        remediation="Add HEALTHCHECK for orchestrator health detection.",
    ),
    IaCPolicy(
        id="docker-secrets-in-env",
        title="Sensitive Data in ENV",
        severity=Severity.CRITICAL if hasattr(Severity, "CRITICAL") else "critical",
        category="dockerfile",
        patterns=[r"ENV\s+(PASSWORD|SECRET|TOKEN|KEY|API_KEY)"],
        message="Secrets baked into image layers.",
        remediation="Use BuildKit secret mounts or runtime env injection.",
    ),
]


class IaCScanner:
    """v2.0 IaC Scanner — Terraform, K8s, CloudFormation, Dockerfile."""

    name: str = "iac"

    FILE_PATTERNS: dict[str, list[str]] = {
        "terraform": ["*.tf", "*.tfvars"],
        "k8s": ["*.yaml", "*.yml"],
        "dockerfile": ["Dockerfile", "Dockerfile.*", "*.dockerfile"],
        "cloudformation": ["*.yaml", "*.yml", "*.json"],
    }

    def __init__(
        self,
        policies_dir: Path | str | None = None,
        timeout: int = 300,
    ) -> None:
        self.policies_dir = Path(policies_dir) if policies_dir else None
        self.timeout = timeout
        self.policies: list[IaCPolicy] = list(BUILTIN_POLICIES)
        if self.policies_dir and self.policies_dir.exists():
            self._load_custom_policies()

    # ------------------------------------------------------------------
    # Scanner Interface
    # ------------------------------------------------------------------

    def is_applicable(self, context: Any) -> bool:
        """IaC scanner is always applicable."""
        return True

    async def scan(self, context: Any) -> list[Finding]:
        """Scan all IaC files under the repository path.

        Accepts ScanContext (with .path or .scan_path) or a raw Path/str.
        """
        # Extract path from context
        if hasattr(context, "path"):
            path = context.path
        elif hasattr(context, "scan_path"):
            path = context.scan_path
        elif isinstance(context, (str, Path)):
            path = str(context)
        else:
            logger.warning("IaCScanner.scan: cannot extract path from %s", type(context))
            return []

        # Offload blocking filesystem I/O to a background thread to prevent event loop blocking
        return await asyncio.to_thread(self._scan_path, Path(path).resolve())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_custom_policies(self) -> None:
        """Load custom .yml / .json policies from policies_dir."""
        if not self.policies_dir:
            return

        for p in self.policies_dir.iterdir():
            if p.suffix not in (".yml", ".yaml", ".json"):
                continue
            try:
                if p.suffix == ".json":
                    data = json.loads(p.read_text(encoding="utf-8"))
                else:
                    try:
                        import yaml

                        data = yaml.safe_load(p.read_text(encoding="utf-8"))
                    except ImportError:
                        logger.warning(
                            "PyYAML not installed, skipping YAML policy file: %s", p.name
                        )
                        continue

                if isinstance(data, list):
                    for item in data:
                        self.policies.append(self._dict_to_policy(item))
                elif isinstance(data, dict):
                    self.policies.append(self._dict_to_policy(data))
            except Exception as e:
                logger.debug("Policy load failed for %s: %s", p.name, e)

    @staticmethod
    def _dict_to_policy(d: dict[str, Any]) -> IaCPolicy:
        sev_map = {
            "critical": Severity.CRITICAL if hasattr(Severity, "CRITICAL") else "critical",
            "high": Severity.HIGH if hasattr(Severity, "HIGH") else "high",
            "medium": Severity.MEDIUM if hasattr(Severity, "MEDIUM") else "medium",
            "low": Severity.LOW if hasattr(Severity, "LOW") else "low",
            "info": Severity.INFO if hasattr(Severity, "INFO") else "info",
        }
        return IaCPolicy(
            id=d.get("id", "custom"),
            title=d.get("title", "Custom Policy"),
            severity=sev_map.get(d.get("severity", "medium").lower(), "medium"),
            category=d.get("category", "terraform"),
            patterns=d.get("patterns", []),
            anti_patterns=d.get("anti_patterns", []),
            message=d.get("message", ""),
            remediation=d.get("remediation", ""),
        )

    def _scan_path(self, root: Path) -> list[Finding]:
        findings: list[Finding] = []

        for category, patterns in self.FILE_PATTERNS.items():
            for pat in patterns:
                for file_path in root.rglob(pat):
                    if self._skip_path(file_path):
                        continue
                    findings.extend(self._scan_file(file_path, category))

        logger.info("IaC scan complete: %d findings", len(findings))
        return findings

    def _scan_file(self, file_path: Path, category: str) -> list[Finding]:
        findings: list[Finding] = []
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.debug("Cannot read %s: %s", file_path, e)
            return findings

        # Resolve category safely for both real Enum and fallback class
        # Typed as Any to satisfy mypy when passing to Finding's strict Category enum requirement
        cat_val: Any = getattr(_Category, "IAC", "iac")

        for policy in self.policies:
            if policy.category != category:
                continue

            # Positive pattern match
            matched = False
            match_line = 0
            for pat in policy.patterns:
                for m in re.finditer(pat, text, re.IGNORECASE | re.MULTILINE):
                    matched = True
                    match_line = text[: m.start()].count("\n") + 1
                    break
                if matched:
                    break

            if not matched:
                continue

            # Anti-pattern check (must NOT be present)
            anti_matched = False
            for anti in policy.anti_patterns:
                if re.search(anti, text, re.IGNORECASE | re.MULTILINE):
                    anti_matched = True
                    break

            if policy.anti_patterns and anti_matched:
                continue  # Anti-pattern present → rule satisfied, no finding

            findings.append(
                Finding(
                    id=policy.id,
                    rule_id=policy.id,
                    rule_name=policy.title,
                    title=policy.title,
                    severity=policy.severity,
                    message=policy.message,
                    description=policy.remediation,
                    file=str(file_path),
                    line=match_line,
                    category=cat_val,
                    scanner="iac",
                    confidence=0.85,
                    conformal_lower=0.75,
                    conformal_upper=0.95,
                    blast_radius=None,
                )
            )

        return findings

    @staticmethod
    def _skip_path(path: Path) -> bool:
        """Skip dependency trees and Seraph policy control-plane files."""
        normalized = f"/{str(path).replace('\\', '/').lower().lstrip('/')}"
        skip = (
            "node_modules",
            ".venv",
            "vendor",
            "dist",
            "build",
            ".git",
            ".terraform",
            "__pycache__",
        )

        if any(k in normalized for k in skip):
            return True

        return "/policies/builtin/" in normalized or "/policies/auto-generated/" in normalized
