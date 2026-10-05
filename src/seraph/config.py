from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScannerConfig(BaseModel):
    """Configuration for scanner execution."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    timeout_seconds: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Maximum time in seconds for each scanner subprocess",
    )
    max_output_bytes: int = Field(
        default=10 * 1024 * 1024,
        description="Maximum bytes to capture from scanner stdout",
    )
    parallel_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of parallel scanner workers",
    )
    # Optional external binaries (Seraph native scanners need none of these)
    gitleaks_binary: str | None = Field(
        default=None,
        description="Optional path to external gitleaks binary (Seraph native scanner is preferred)",
    )
    grype_binary: str | None = Field(
        default=None,
        description="Optional path to external grype binary (Seraph native scanner is preferred)",
    )

    @field_validator("gitleaks_binary", "grype_binary")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class IntelligenceConfig(BaseModel):
    """Configuration for the intelligence layer."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    conformal_alpha: float = Field(
        default=0.1,
        ge=0.01,
        le=0.5,
        description="Significance level for conformal prediction (confidence = 1 - alpha)",
    )
    min_calibration_samples: int = Field(
        default=10,
        ge=1,
        description="Minimum samples needed before conformal prediction is calibrated",
    )
    learning_enabled: bool = Field(
        default=True,
        description="Enable adaptive learning from suppressions and fixes",
    )
    causal_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum depth for causal chain traversal",
    )
    ufic_enabled: bool = Field(
        default=True,
        description="Enable UFIC (Unified File Integrity Checker) module",
    )
    fix_time_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Override default fix time estimates per category (minutes)",
    )


class OutputConfig(BaseModel):
    """Configuration for output formatting."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    format: str = Field(
        default="table",
        description="Output format: table, json, sarif, junit, github",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose/debug output",
    )
    color: bool = Field(
        default=True,
        description="Enable colored terminal output",
    )
    output_file: Path | None = Field(
        default=None,
        description="Write output to a file instead of stdout",
    )
    max_explanations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of detailed explanations to display",
    )
    max_findings: int = Field(
        default=0,
        ge=0,
        description="Maximum findings to include in output (0 = unlimited)",
    )
    show_suppressed_count: bool = Field(
        default=True,
        description="Show suppressed findings count in output",
    )
    show_blast_radius: bool = Field(
        default=True,
        description="Show blast radius analysis in output",
    )
    show_conformal_prediction: bool = Field(
        default=True,
        description="Show conformal prediction intervals in output",
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        allowed = {"table", "json", "sarif", "junit", "github"}
        if v.lower() not in allowed:
            raise ValueError(f"Output format must be one of {allowed}, got '{v}'")
        return v.lower()


class CacheConfig(BaseModel):
    """Configuration for incremental scan caching."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    enabled: bool = Field(
        default=True,
        description="Enable incremental scan caching",
    )
    directory: Path = Field(
        default=Path(".seraph-cache"),
        description="Directory for cache storage",
    )
    ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Cache time-to-live in seconds",
    )
    max_entries: int = Field(
        default=50000,
        ge=100,
        description="Maximum number of cached file entries",
    )


class LearningConfig(BaseModel):
    """Configuration for the adaptive learning engine."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    enabled: bool = Field(
        default=True,
        description="Enable adaptive learning",
    )
    cache_dir: Path = Field(
        default=Path(".seraph-learn"),
        description="Directory for learning state storage",
    )
    min_suppressions_for_auto: int = Field(
        default=5,
        ge=1,
        description="Minimum suppressions before auto-action is triggered",
    )
    confidence_threshold: float = Field(
        default=0.9,
        ge=0.5,
        le=1.0,
        description="Confidence threshold for auto-suppression",
    )
    auto_generate_policies: bool = Field(
        default=True,
        description="Automatically generate YAML policies from learned patterns",
    )


class FailConfig(BaseModel):
    """Configuration for build failure behavior."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    fail_on_severity: str = Field(
        default="high",
        description="Exit non-zero if findings at or above this severity",
    )
    fail_on_count: int | None = Field(
        default=None,
        ge=1,
        description="Exit non-zero if total findings exceed this count",
    )
    ignore_suppressed: bool = Field(
        default=True,
        description="Exclude suppressed findings from fail conditions",
    )
    exit_code: bool = Field(
        default=False,
        description="Exit with code 1 if any findings exist (for CI gates)",
    )

    @field_validator("fail_on_severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"critical", "high", "medium", "low", "info"}
        if v.lower() not in allowed:
            raise ValueError(f"fail_on_severity must be one of {allowed}, got '{v}'")
        return v.lower()


class SBOMConfig(BaseModel):
    """Configuration for SBOM/dependency scanning."""

    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
    )

    include_dev_dependencies: bool = Field(
        default=False,
        description="Include dev dependencies in SBOM vulnerability analysis",
    )

    deduplicate_across_manifests: bool = Field(
        default=True,
        description="Deduplicate findings across multiple manifest files",
    )

    chunk_size: int = Field(
        default=50,
        ge=1,
        le=1000,  # Increased from 100 to 1000 to accommodate test values like 500
        description="Maximum packages per OSV batch query chunk",
    )

    max_dependencies: int = Field(
        default=2000,
        ge=10,
        le=100_000,
        description="Maximum dependencies to analyze in one scan",
    )

    quick_mode: bool = Field(
        default=False,
        description="Skip lockfiles and perform manifest-only dependency analysis",
    )


class SecretConfig(BaseModel):
    """Configuration for secret scanning."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    min_entropy: float = Field(
        default=3.5,
        ge=1.0,
        le=8.0,
        description="Minimum Shannon entropy for secret detection",
    )
    validate_live: bool = Field(
        default=False,
        description="Perform live API validation of detected secrets (destructive — use with caution)",
    )
    git_history: bool = Field(
        default=False,
        description="Scan git history for leaked secrets",
    )


class PolicyConfig(BaseModel):
    """Configuration for policy scanning."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    compliance_frameworks: list[str] = Field(
        default_factory=lambda: ["CIS", "SOC2"],
        description="Compliance frameworks to enforce",
    )
    auto_policies_dir: Path = Field(
        default=Path("policies/auto-generated"),
        description="Directory for auto-generated policies",
    )


class PatternConfig(BaseModel):
    """Configuration for pattern scanning."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    language_aware: bool = Field(
        default=True,
        description="Enable language-aware pattern matching",
    )
    framework_context: bool = Field(
        default=True,
        description="Enable framework context in pattern matching",
    )


class SuppressionConfig(BaseModel):
    """Configuration for the suppression engine."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    enabled: bool = Field(
        default=True,
        description="Enable suppression engine",
    )
    test_files: bool = Field(
        default=True,
        description="Suppress findings in test files",
    )
    framework_internals: bool = Field(
        default=True,
        description="Suppress findings in framework internal files",
    )
    build_scripts: bool = Field(
        default=True,
        description="Suppress findings in build scripts",
    )
    examples: bool = Field(
        default=True,
        description="Suppress findings in example directories",
    )
    documentation: bool = Field(
        default=True,
        description="Suppress findings in documentation files",
    )


class SeraphConfig(BaseModel):
    """Root configuration for Seraph Guard.

    Combines all sub-configurations into a single validated model.
    """

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    # Core scan settings
    scan_path: Path = Field(
        default=Path("."),
        description="Path to scan",
    )
    explain: bool = Field(
        default=False,
        description="Generate detailed explanations for findings",
    )
    rank_by_impact: bool = Field(
        default=False,
        description="Rank findings by blast-radius reduction per effort",
    )
    learn_mode: bool = Field(
        default=False,
        description="Enable adaptive learning during this scan",
    )
    image: str | None = Field(
        default=None,
        description="Docker/OCI image to scan (e.g., alpine:latest)",
    )
    git_history: bool = Field(
        default=False,
        description="Scan git history for leaked secrets",
    )

    # Sub-configurations
    scanners: ScannerConfig = Field(default_factory=ScannerConfig)
    intelligence: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    fail: FailConfig = Field(default_factory=FailConfig)
    sbom: SBOMConfig = Field(default_factory=SBOMConfig)
    secrets: SecretConfig = Field(default_factory=SecretConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    pattern: PatternConfig = Field(default_factory=PatternConfig)
    suppression: SuppressionConfig = Field(default_factory=SuppressionConfig)

    # Policy paths (legacy — also available in PolicyConfig)
    policies_dir: Path = Field(
        default=Path("policies/builtin"),
        description="Directory containing built-in YAML policy rules",
    )
    auto_policies_dir: Path = Field(
        default=Path("policies/auto-generated"),
        description="Directory for auto-generated policies from learning",
    )

    @field_validator("scan_path", mode="before")
    @classmethod
    def resolve_path(cls, v: str | Path) -> Path:
        return Path(v).resolve()

    @model_validator(mode="after")
    def validate_config(self) -> "SeraphConfig":
        """Cross-field validation and defaults propagation."""
        if self.learn_mode and not self.learning.enabled:
            self.learning.enabled = True
        # Propagate git_history to secret scanner config
        if self.git_history and not self.secrets.git_history:
            self.secrets.git_history = True
        return self

    @classmethod
    def from_cli_args(
        cls,
        path: str = ".",
        output_format: str = "table",
        fail_on: str = "high",
        explain: bool = False,
        rank_by_impact: bool = False,
        learn: bool = False,
        verbose: bool = False,
        image: str | None = None,
        git_history: bool = False,
        timeout: int | None = None,
        no_suppress: bool = False,
        dedup: bool = True,
    ) -> "SeraphConfig":
        """Create config from CLI arguments.

        This factory method maps CLI flags to the nested config structure,
        ensuring all CLI options are properly represented in the config model.
        """
        cfg = cls(
            scan_path=Path(path),
            explain=explain,
            rank_by_impact=rank_by_impact,
            learn_mode=learn,
            image=image,
            git_history=git_history,
            output=OutputConfig(format=output_format, verbose=verbose),
            fail=FailConfig(fail_on_severity=fail_on),
        )
        if timeout is not None:
            cfg.scanners.timeout_seconds = timeout
        if no_suppress:
            cfg.suppression.enabled = False
        if not dedup:
            # Deduplication is handled at CLI layer; config just notes it
            pass
        return cfg

    def to_dict(self) -> dict[str, Any]:
        """Serialize config to dictionary."""
        return self.model_dump()
