"""seraph/core/base.py — Ontological Scanner Foundation (v2.1)

The base module for Seraph Guard v2.0. Every scanner, formatter, and
intelligence engine operates on the Seraph Ontology — not flat findings.

Changes from v1.x:
- Finding now emits OntologyObjects + OntologyLinks for graph construction.
- BlastRadius is computed by the CausalEngine, not guessed by scanners.
- Conformal prediction intervals are first-class fields.
- Deduplication happens via semantic proximity (graph clustering), not hash.
- Scanners declare their ontological view (what objects + links they produce).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, override

from seraph.ufic.constants import TEST_ONLY_PATTERNS


# ═══════════════════════════════════════════════════════════════════════════════
#  ONTOLOGY PRIMITIVES — The Seraph Ontology Graph
# ═══════════════════════════════════════════════════════════════════════════════


class OntologyType(StrEnum):
    """Semantic object types in the security ontology."""

    FILE = "file"
    FINDING = "finding"
    FUNCTION = "function"
    CLASS = "class"
    SECRET = "secret"  # nosec B105 | noqa: S105
    DEPENDENCY = "dependency"
    VULNERABILITY = "vulnerability"
    POLICY_VIOLATION = "policy_violation"
    CONTAINER_LAYER = "container_layer"
    CONFIG = "config"
    SERVICE = "service"
    DATA_STORE = "data_store"
    API_ENDPOINT = "api_endpoint"
    AUTH_BOUNDARY = "auth_boundary"


class LinkType(StrEnum):
    """Semantic link types between ontology objects."""

    CALLS = "calls"
    IMPORTS = "imports"
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    EXPOSES = "exposes"
    AUTHORIZES = "authorizes"
    ACCESSES = "accesses"
    DATA_FLOW = "data_flow"
    TRUSTS = "trusts"
    INFLUENCES = "influences"
    BLAST_RADIUS = "blast_radius"


class ActionType(StrEnum):
    """Kinetic actions the system can take on ontology objects."""

    FIX = "fix"
    PREVENT = "prevent"
    ISOLATE = "isolate"
    PATCH = "patch"
    ALERT = "alert"
    SUPPRESS = "suppress"
    LEARN = "learn"


@dataclass
class OntologyObject:
    """A node in the Seraph Ontology — the atomic unit of knowledge."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    type: OntologyType = OntologyType.FILE
    name: str = ""
    path: str = ""
    line: int = 0
    column: int = 0
    properties: dict[str, Any] = field(default_factory=dict)
    scanner: str = ""
    confidence: float = 0.0
    conformal_lower: float | None = None
    conformal_upper: float | None = None
    created_at: str = ""  # ISO timestamp
    version: int = 1  # For compounding — increments when re-enriched

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "properties": self.properties,
            "scanner": self.scanner,
            "confidence": self.confidence,
            "conformal_lower": self.conformal_lower,
            "conformal_upper": self.conformal_upper,
            "created_at": self.created_at,
            "version": self.version,
        }

    def merge(self, other: OntologyObject) -> OntologyObject:
        """Ontology compounding: merge another object into this one."""
        self.properties.update(other.properties)
        self.confidence = max(self.confidence, other.confidence)
        if other.conformal_lower is not None:
            self.conformal_lower = (
                min(self.conformal_lower, other.conformal_lower)
                if self.conformal_lower is not None
                else other.conformal_lower
            )
        if other.conformal_upper is not None:
            self.conformal_upper = (
                max(self.conformal_upper, other.conformal_upper)
                if self.conformal_upper is not None
                else other.conformal_upper
            )
        self.version += 1
        return self


@dataclass
class OntologyLink:
    """An edge in the Seraph Ontology — relationships between objects."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    source_id: str = ""
    target_id: str = ""
    type: LinkType = LinkType.DEPENDS_ON
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)
    scanner: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type.value,
            "weight": self.weight,
            "properties": self.properties,
            "scanner": self.scanner,
        }


@dataclass
class OntologyAction:
    """A kinetic action attached to an ontology object."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    object_id: str = ""
    action_type: ActionType = ActionType.ALERT
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | in_progress | completed | failed
    created_by: str = ""  # engine or scanner that created it

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "object_id": self.object_id,
            "action_type": self.action_type.value,
            "payload": self.payload,
            "status": self.status,
            "created_by": self.created_by,
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  SEVERITY & CATEGORY ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def weight(self) -> int:
        weights = {"critical": 100, "high": 75, "medium": 50, "low": 25, "info": 10}
        return weights.get(self.value, 0)


class Category(StrEnum):
    SECRET = "secret"  # nosec B105 | noqa: S105
    VULNERABILITY = "vulnerability"
    POLICY = "policy"
    PATTERN = "pattern"
    IAC = "iac"
    CONTAINER = "container"


# ═══════════════════════════════════════════════════════════════════════════════
#  FILE CONTEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def is_test_file(file_path: str) -> bool:
    """Return True when a path matches Seraph's test-only path patterns.

    TEST_ONLY_PATTERNS historically assume a directory separator before names
    such as ``test_*.py``. That misses a root-level file such as
    ``test_ufic.py`` when the scan target itself is the tests directory.
    Check both the supplied path and a synthetic rooted form so the same
    patterns work for relative, absolute, and root-level paths.
    """
    rel = Path(file_path).as_posix().lower().lstrip("./")
    if any(pattern.search(rel) for pattern in TEST_ONLY_PATTERNS):
        return True

    rooted = f"/{rel.lstrip('/')}"
    return any(pattern.search(rooted) for pattern in TEST_ONLY_PATTERNS)


def is_build_script(file_path: str) -> bool:
    """Classify dedicated build/automation files without suppressing ordinary source.

    Path-only classification is necessarily conservative.  Generic substrings such
    as ``release`` or ``deploy`` are intentionally not treated as build markers
    because legitimate production modules can contain those words in their names.
    """
    normalized = Path(file_path).as_posix().lower()
    parts = {part for part in Path(normalized).parts if part not in {"", "/"}}
    filename = Path(normalized).name
    build_dirs = {
        "scripts",
        "tools",
        "tooling",
        "ci",
        ".github",
        ".circleci",
        ".gitlab",
        ".buildkite",
        ".jenkins",
        "build-aux",
    }
    build_files = {
        "makefile",
        "gnumakefile",
        "gruntfile.js",
        "gulpfile.js",
        "rakefile",
        "taskfile.yml",
        "taskfile.yaml",
        "justfile",
        "dockerfile",
        "dockerfile.dev",
    }
    return bool(parts.intersection(build_dirs) or filename in build_files)


def is_framework_code(file_path: str) -> bool:
    """Classify vendored/installed framework code, not arbitrary project directories.

    A repository is allowed to have application directories named ``django``,
    ``flask``, etc.  Those names alone must never downgrade or suppress findings.
    """
    normalized = Path(file_path).as_posix().lower()
    markers = (
        "/site-packages/",
        "/dist-packages/",
        "/vendor/",
        "/vendors/",
        "/node_modules/",
        "/third_party/",
        "/third-party/",
        "/lib/python",
    )
    wrapped = f"/{normalized.lstrip('/')}"
    return any(marker in wrapped for marker in markers)


def is_example_file(file_path: str) -> bool:
    path_lower = file_path.lower().replace("\\", "/")
    example_indicators = (
        "/example/",
        "/examples/",
        "/demo/",
        "/demos/",
        "/sample/",
        "/samples/",
        "/playground/",
        "/playgrounds/",
        "/how-to/",
        "/howto/",
        "/recipes/",
    )
    return any(ind in f"/{path_lower.lstrip('/')}" for ind in example_indicators)


def is_documentation_file(file_path: str) -> bool:
    path = Path(file_path)
    path_lower = file_path.lower().replace("\\", "/")
    doc_dirs = (
        "/docs/",
        "/doc/",
        "/documentation/",
        "/guides/",
        "/tutorials/",
        "/website/",
        "/www/",
        "/blog/",
        "/docs-site/",
    )
    if any(ind in f"/{path_lower.lstrip('/')}" for ind in doc_dirs):
        return True
    return path.suffix.lower() in {".md", ".mdx", ".rst", ".adoc", ".asciidoc", ".txt"}


def is_generated_file(file_path: str) -> bool:
    path_lower = file_path.lower().replace("\\", "/")
    generated_segments = (
        "/generated/",
        "/codegen/",
        "/code-gen/",
        "/code_generation/",
        "/auto_generated/",
    )
    generated_suffixes = (
        ".pb.go",
        "_grpc.pb.go",
        "_generated.py",
        "_generated.go",
        "_generated.rs",
        "_generated.java",
        ".generated.ts",
        ".generated.tsx",
        ".generated.js",
        ".generated.jsx",
        ".generated.kt",
        ".generated.swift",
        "_pb2.py",
        "_pb2_grpc.py",
        "_grpc.py",
        ".d.ts",
        "_mock.py",
        "_mock.rs",
        "_test.rs",
    )
    normalized = f"/{path_lower.lstrip('/')}"
    return any(seg in normalized for seg in generated_segments) or path_lower.endswith(
        generated_suffixes
    )


def get_file_context(file_path: str) -> str:
    """Return the security-gate context used by Finding.

    The order is intentional: tests/examples/docs/generated content must be
    recognized before broad build/framework heuristics so a high/critical
    finding in non-production content cannot leak into the production gate.
    """
    if is_test_file(file_path):
        return "test"
    if is_example_file(file_path):
        return "example"
    if is_documentation_file(file_path):
        return "documentation"
    if is_generated_file(file_path):
        return "generated"
    if is_build_script(file_path):
        return "build"
    if is_framework_code(file_path):
        return "framework"
    return "production"


# ═══════════════════════════════════════════════════════════════════════════════
#  BLAST RADIUS — Computed by CausalEngine, surfaced here
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BlastRadius:
    """Static impact assessment for a finding.

    Scores are normalized to ``0..100`` and describe *static structural
    exposure / estimated reduction if the finding is remediated*.  They are
    not probabilities and are not claims of measured business loss.

    ``provenance`` is explicit:
      * ``MEASURED`` — backed by an external measurement/telemetry source.
      * ``INFERRED`` — backed by concrete repository-derived evidence.
      * ``ESTIMATED`` — heuristic estimate without sufficient structural proof.
      * ``ASSERTED_ASSESSED`` — explicitly supplied by an external caller/test.
      * ``UNKNOWN`` — no defensible assessment available.
    """

    affected_resources: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    data_at_risk: list[str] = field(default_factory=list)
    api_endpoints: list[str] = field(default_factory=list)
    blast_radius_score: float = 0.0
    reduction_if_fixed: float = 0.0
    is_assessed: bool = False
    causal_path: list[str] = field(default_factory=list)
    provenance: str = "UNKNOWN"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    assessment_method: str = ""
    caveats: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.blast_radius_score = max(0.0, min(100.0, _finite_float(self.blast_radius_score)))
        self.reduction_if_fixed = max(0.0, min(100.0, _finite_float(self.reduction_if_fixed)))
        self.provenance = str(
            self.provenance or ("ASSERTED_ASSESSED" if self.is_assessed else "UNKNOWN")
        ).upper()
        self.evidence = _dedupe_json_records(self.evidence)
        valid_assessed_provenance = {"MEASURED", "INFERRED", "ASSERTED_ASSESSED"}
        if self.provenance not in {
            "MEASURED",
            "INFERRED",
            "ASSERTED_ASSESSED",
            "ESTIMATED",
            "UNKNOWN",
        }:
            self.provenance = "ESTIMATED"
            self.is_assessed = False
            self.caveats = [*self.caveats, "unknown provenance normalized to ESTIMATED"]
        elif self.is_assessed and (
            self.provenance not in valid_assessed_provenance or not self.evidence
        ):
            self.is_assessed = False
            self.provenance = "ESTIMATED"
            self.caveats = [
                *self.caveats,
                "assessed impact requires valid provenance and non-empty evidence",
            ]
        elif self.provenance in {"UNKNOWN", "ESTIMATED"}:
            self.is_assessed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "affected_resources": list(self.affected_resources),
            "affected_services": list(self.affected_services),
            "data_at_risk": list(self.data_at_risk),
            "api_endpoints": list(self.api_endpoints),
            "blast_radius_score": round(self.blast_radius_score, 4),
            "reduction_if_fixed": round(self.reduction_if_fixed, 4),
            "is_assessed": bool(self.is_assessed),
            "causal_path": list(self.causal_path),
            "provenance": self.provenance,
            "evidence": list(self.evidence),
            "assessment_method": self.assessment_method,
            "caveats": list(dict.fromkeys(self.caveats)),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  FINDING — The bridge between flat scanners and the Ontology
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Finding:
    """A Finding is the *perceptual* output of Layer 1 (Scanner Swarm).
    It carries enough information for Layer 2 (Cognition) to:
      1. Create OntologyObjects + OntologyLinks
      2. Run Conformal prediction
      3. Run structural-impact prioritization
      4. Route to the correct Action engine
    """

    # ── Required core fields ──
    scanner: str
    category: Category
    severity: Severity
    confidence: float
    file: str
    line: int
    title: str
    description: str

    # ── Optional / scanner-specific fields ──
    id: str = ""
    rule_id: str = ""
    rule_name: str = ""
    message: str = ""
    column: int = 0
    evidence: str = ""
    context: str = ""  # Code snippet / surrounding context
    value: str = ""  # Secret value or matched content
    secret_value: str = ""  # Alias for value (backward compat)
    _raw_secret: str = ""  # Internal storage for raw secret value (used by fixer)
    variable_name: str = ""
    tags: list[str] = field(default_factory=list)
    path: str = ""  # Alias for file (backward compat)
    source_file: str = ""  # Alias for file (backward compat)

    # ── Intelligence / analysis fields (populated by Layer 2) ──
    blast_radius: BlastRadius | None = None
    conformal_lower: float | None = None
    conformal_upper: float | None = None
    conformal_confidence: float | None = None
    conformal_set: list[str] | None = None
    causal_rank: int | None = None  # Deterministic structural-impact priority rank
    suppression_score: float | None = None  # Suppression/triage score from learned state
    dedup_cluster_id: str | None = None  # Semantic cluster, not hash

    # ── Fix / remediation fields (consumed by Layer 3) ──
    fix_available: bool = False
    fix_command: str | None = None
    fix_description: str | None = None
    remediation: str = ""  # SARIF / external format compat
    fix_patch: str | None = None  # Actual diff patch
    fix_engine: str = ""  # Which fix engine generated it

    # ── Vulnerability-specific fields ──
    cve: str | None = None
    cvss_score: float | None = None
    package_name: str = ""  # SBOM scanner
    fixed_version: str = ""  # SBOM scanner
    affected_files: list[str] = field(default_factory=list)  # SARIF compat

    # ── Ontological fields (v2.0) ──
    ontology_object_id: str = ""  # Link to the ontology graph node
    ontology_link_ids: list[str] = field(default_factory=list)
    semantic_signature: str = ""  # For semantic dedup (graph clustering)

    # ── Deduplication fields (legacy + v2.0) ──
    locations: list[dict[str, Any]] = field(default_factory=list)
    location_count: int = 1

    # ── Metadata / state ──
    metadata: dict[str, Any] = field(default_factory=dict)
    is_suppressed: bool = False
    suppression_reason: str | None = None
    file_context: str = ""
    effective_severity: Severity | None = None  # Override computed by suppression engine

    def __post_init__(self) -> None:
        # Auto-compute id if not provided (legacy hash-based, replaced by semantic dedup in v2.0)
        if not self.id:
            raw = f"{self.scanner}:{self.file}:{self.line}:{self.title}"
            self.id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

        # Backward compat: path / source_file mirror file
        if not self.path:
            self.path = self.file
        if not self.source_file:
            self.source_file = self.file

        # Backward compat: value / secret_value mirror each other
        if self.value and not self.secret_value:
            self.secret_value = self.value
        if self.secret_value and not self.value:
            self.value = self.secret_value

        # Normalize compatible string enum inputs at the model boundary.
        if isinstance(self.category, str):
            try:
                self.category = Category(self.category.lower())
            except ValueError:
                pass
        if isinstance(self.severity, str):
            try:
                self.severity = Severity(self.severity.lower())
            except ValueError:
                pass

        # Auto-populate rule_id from metadata if empty
        if not self.rule_id:
            self.rule_id = self.metadata.get("rule_id", self.id)

        # Auto-populate message from description if empty
        if not self.message:
            self.message = self.description

        # Auto-populate rule_name from metadata if empty
        if not self.rule_name:
            self.rule_name = self.metadata.get("rule_name", "")

        # Auto-detect file context
        if not self.file_context:
            self.file_context = get_file_context(self.file)

        # Compute semantic signature for v2.0 dedup (if not already set)
        if not self.semantic_signature:
            self.semantic_signature = self._compute_semantic_signature()

    def _compute_semantic_signature(self) -> str:
        """Return a deterministic, scanner-independent semantic signature.

        The signature deliberately excludes scanner name and volatile finding
        IDs so equivalent observations from independent engines can be merged.
        """
        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        cwe = self.cwe or ""
        rule_id = str(self.rule_id or metadata.get("rule_id", "")).strip().lower()
        rule_name = (
            str(self.rule_name or metadata.get("rule_name", "") or self.title).strip().lower()
        )
        sink = str(metadata.get("sink", metadata.get("sink_function", ""))).strip().lower()
        source = str(metadata.get("source", metadata.get("source_function", ""))).strip().lower()
        suffix = Path(self.file).suffix.lower()
        category = getattr(self.category, "value", self.category)
        parts = [
            str(category).lower(),
            cwe,
            rule_id,
            rule_name,
            sink,
            source,
            suffix,
            self.file_context,
        ]
        return "|".join(_normalize_signature_part(p) for p in parts)

    # ── Properties ──

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}"

    @property
    def is_in_test(self) -> bool:
        return self.file_context == "test"

    @property
    def is_in_build_script(self) -> bool:
        return self.file_context == "build"

    @property
    def is_in_framework(self) -> bool:
        return self.file_context == "framework"

    @property
    def is_production_code(self) -> bool:
        return self.file_context == "production"

    @property
    def computed_effective_severity(self) -> Severity:
        """Compute effective severity based on file context + suppression."""
        if self.effective_severity is not None:
            return self.effective_severity
        if self.file_context in {"test", "example", "documentation", "generated"}:
            return (
                Severity.INFO
                if self.severity in (Severity.CRITICAL, Severity.HIGH)
                else self.severity
            )
        if self.file_context == "framework":
            if self.severity == Severity.CRITICAL:
                return Severity.MEDIUM
            if self.severity == Severity.HIGH:
                return Severity.LOW
            return self.severity
        if self.file_context == "build":
            return Severity.HIGH if self.severity == Severity.CRITICAL else self.severity
        return self.severity

    @property
    def cwe(self) -> str | None:
        """Primary CWE identifier, normalized from scanner metadata."""
        value = self.metadata.get("cwe")
        if value is None:
            return None
        text = str(value).strip().upper()
        return text or None

    @property
    def cwe_aliases(self) -> list[str]:
        """Secondary CWE identifiers preserved for external taxonomy mappings."""
        value = self.metadata.get("cwe_aliases", [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple, set)):
            return []
        return sorted({str(item).strip().upper() for item in value if str(item).strip()})

    # ── Ontology bridge methods (v2.0) ──

    def to_ontology_object(self) -> OntologyObject:
        """Convert this Finding into a secret-safe ontology object."""
        obj_type = OntologyType.FINDING
        secret_values = [self.value, self.secret_value, self._raw_secret]
        return OntologyObject(
            id=self.ontology_object_id
            or "finding:"
            + hashlib.sha256(
                f"{self.id}|{self.file}|{self.line}|{self.column}".encode()
            ).hexdigest()[:24],
            type=obj_type,
            name=_redact_string(self.title, secret_values),
            path=self.file,
            line=self.line,
            column=self.column,
            properties={
                "severity": self.severity.value,
                "effective_severity": self.computed_effective_severity.value,
                "confidence": self.confidence,
                "description": _redact_string(self.description, secret_values),
                "evidence": _redact_value(self.evidence, secret_values),
                "secret_present": bool(self.value or self.secret_value or self._raw_secret),
                "variable_name": _redact_string(self.variable_name, secret_values),
                "rule_id": _redact_string(self.rule_id, secret_values),
                "rule_name": _redact_string(self.rule_name, secret_values),
                "cve": _redact_string(self.cve, secret_values),
                "cvss_score": self.cvss_score,
                "package_name": _redact_string(self.package_name, secret_values),
                "fixed_version": _redact_string(self.fixed_version, secret_values),
                "is_suppressed": self.is_suppressed,
                "suppression_reason": _redact_string(self.suppression_reason or "", secret_values),
                "semantic_signature": self.semantic_signature,
            },
            scanner=_redact_string(self.scanner, secret_values),
            confidence=self.confidence,
            conformal_lower=self.conformal_lower,
            conformal_upper=self.conformal_upper,
        )

    def _category_to_ontology_type(self) -> OntologyType:
        mapping = {
            Category.SECRET: OntologyType.SECRET,
            Category.VULNERABILITY: OntologyType.VULNERABILITY,
            Category.POLICY: OntologyType.POLICY_VIOLATION,
            Category.PATTERN: OntologyType.VULNERABILITY,
            Category.IAC: OntologyType.CONFIG,
            Category.CONTAINER: OntologyType.CONTAINER_LAYER,
        }
        return mapping.get(self.category, OntologyType.FILE)

    def to_ontology_links(self, file_object_id: str) -> list[OntologyLink]:
        """Generate ontology links from this finding to its containing file."""
        if not self.ontology_object_id:
            self.ontology_object_id = (
                "finding:"
                + hashlib.sha256(
                    f"{self.id}|{self.file}|{self.line}|{self.column}".encode()
                ).hexdigest()[:24]
            )
        return [
            OntologyLink(
                source_id=file_object_id,
                target_id=self.ontology_object_id,
                type=LinkType.CONTAINS,
                weight=self.confidence,
                properties={"line": self.line, "column": self.column},
                scanner=self.scanner,
            )
        ]

    def to_ontology_action(self) -> OntologyAction | None:
        """Generate a kinetic action if a fix is available."""
        if not self.fix_available:
            return None
        return OntologyAction(
            object_id=self.ontology_object_id or str(uuid.uuid4())[:12],
            action_type=ActionType.FIX,
            payload={
                "fix_command": self.fix_command,
                "fix_description": self.fix_description,
                "fix_patch": self.fix_patch,
                "remediation": self.remediation,
            },
            created_by=self.fix_engine or self.scanner,
        )

    def to_dict(self) -> dict[str, Any]:
        # All serialized finding content is secret-safe; raw secret fields are
        # deliberately never exposed, including when copied into metadata.
        secret_values = [self.value, self.secret_value, self._raw_secret]
        # Safely extract enum values to prevent AttributeError if they are passed as strings
        cat_val = self.category.value if hasattr(self.category, "value") else str(self.category)
        sev_val = self.severity.value if hasattr(self.severity, "value") else str(self.severity)

        eff_sev_obj = self.computed_effective_severity
        eff_sev_val = eff_sev_obj.value if hasattr(eff_sev_obj, "value") else str(eff_sev_obj)

        # Explicitly type as dict | None to satisfy mypy when self.blast_radius is None.
        br_val: dict[str, Any] | None = (
            _redact_value(self.blast_radius.to_dict(), secret_values)
            if isinstance(self.blast_radius, BlastRadius)
            else _redact_value(self.blast_radius, secret_values)
        )

        return {
            "id": self.id,
            "scanner": self.scanner,
            "category": cat_val,
            "severity": sev_val,
            "effective_severity": eff_sev_val,
            "confidence": self.confidence,
            "file": self.file,
            "path": self.path,
            "source_file": self.source_file,
            "line": self.line,
            "column": self.column,
            "title": _redact_string(self.title, secret_values),
            "description": _redact_string(self.description, secret_values),
            "evidence": _redact_value(self.evidence, secret_values),
            "context": _redact_string(self.context, secret_values),
            # FIX: Removed 'value' and 'secret_value' to prevent leaking sensitive private fields
            "variable_name": _redact_string(self.variable_name, secret_values),
            "rule_id": _redact_string(self.rule_id, secret_values),
            "rule_name": _redact_string(self.rule_name, secret_values),
            "message": _redact_string(self.message, secret_values),
            "tags": _redact_value(self.tags, secret_values),
            "file_context": self.file_context,
            "blast_radius": br_val,
            "causal_rank": self.causal_rank,
            "dedup_cluster_id": self.dedup_cluster_id,
            "fix_available": self.fix_available,
            "fix_command": _redact_string(self.fix_command or "", secret_values),
            "fix_description": _redact_string(self.fix_description or "", secret_values),
            "fix_patch": _redact_value(self.fix_patch, secret_values),
            "fix_engine": _redact_string(self.fix_engine or "", secret_values),
            "remediation": _redact_string(self.remediation or "", secret_values),
            "cve": _redact_string(self.cve, secret_values),
            "cvss_score": self.cvss_score,
            "package_name": _redact_string(self.package_name, secret_values),
            "fixed_version": _redact_string(self.fixed_version, secret_values),
            "conformal_lower": self.conformal_lower,
            "conformal_upper": self.conformal_upper,
            "conformal_confidence": self.conformal_confidence,
            "conformal_set": self.conformal_set,
            "suppression_score": self.suppression_score,
            "semantic_signature": self.semantic_signature,
            "ontology_object_id": self.ontology_object_id,
            "ontology_link_ids": self.ontology_link_ids,
            "is_suppressed": self.is_suppressed,
            "suppression_reason": _redact_string(self.suppression_reason or "", secret_values),
            "locations": _redact_value(self.locations, secret_values),
            "location_count": self.location_count,
            "affected_files": self.affected_files,
            "cwe": self.cwe,
            "cwe_aliases": self.cwe_aliases,
            "metadata": _redact_value(self.metadata, secret_values),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  SCAN CONTEXT — Carries the ontology reference through the pipeline
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ScanContext:
    path: str
    is_git_repo: bool = False
    changed_files: list[str] | None = None
    config: Any | None = None
    profile: Any | None = None
    ontology: Any | None = None  # v2.0: Reference to the live ontology graph
    metadata: dict[str, Any] = field(default_factory=dict)
    scan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    @property
    def resolved_path(self) -> Path:
        return Path(self.path).resolve()


# ═══════════════════════════════════════════════════════════════════════════════
#  SCANNER ABC — Every agent in the swarm implements this
# ═══════════════════════════════════════════════════════════════════════════════


class Scanner(ABC):
    """Abstract base for all Layer 1 (Perception) agents.

    v2.0 contract:
      1. scan() produces Findings.
      2. is_applicable() gates execution.
      3. ontological_view() declares what OntologyObjects + Links this scanner emits.
      4. No scanner talks to another scanner. All communication via ontology.
    """

    name: str = "BaseScanner"
    version: str = "2.0.0"
    categories: ClassVar[list[Category]] = []

    @abstractmethod
    async def scan(self, context: ScanContext) -> list[Finding]: ...

    @abstractmethod
    def is_applicable(self, context: ScanContext) -> bool: ...

    def ontological_view(self) -> dict[str, list[OntologyType | LinkType]]:
        """Declare what this scanner contributes to the ontology.
        Used by the scheduler to build the graph schema before scanning.
        """
        return {
            "objects": [OntologyType.FILE],
            "links": [LinkType.CONTAINS],
        }

    def should_scan_file(self, file_path: Path) -> bool:
        if ".min." in file_path.name:
            return False
        try:
            if file_path.stat().st_size > 1_000_000:
                return False
        except OSError:
            return False
        return True

    @override
    def __repr__(self) -> str:
        return f"<{self.name} v{self.version}>"


_SENSITIVE_KEYS = {
    "value",
    "secret_value",
    "_raw_secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "secret_key",
    "credentials",
    "credential",
    "secret",
}


def _redact_string(value: Any, secret_values: list[str]) -> str:
    text = "" if value is None else str(value)
    for secret in secret_values:
        if secret:
            text = text.replace(str(secret), "[REDACTED]")
    return text


def _redact_value(value: Any, secret_values: list[str]) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                result[str(key)] = "[REDACTED]"
            else:
                result[key] = _redact_value(item, secret_values)
        return result
    if isinstance(value, list):
        return [_redact_value(item, secret_values) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item, secret_values) for item in value]
    if isinstance(value, set):
        return sorted(_redact_string(item, secret_values) for item in value)
    if isinstance(value, str):
        return _redact_string(value, secret_values)
    return value


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _normalize_signature_part(value: Any) -> str:
    text = str(value or "").strip().lower().replace("\\", "/")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9._:/-]+", "_", text)
    return text[:240]


def _dedupe_json_records(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            key = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            key = repr(sorted((str(k), str(v)) for k, v in record.items()))
        if key not in seen:
            seen.add(key)
            result.append(dict(record))
    return result
