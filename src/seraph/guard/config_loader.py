"""Configuration loader for Seraph Guard."""

import json
import re

from pathlib import Path
from typing import Any


try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
    yaml = None  # type: ignore[assignment]


class ConfigLoader:
    """Loads and merges configuration from YAML files, native tool baselines, and CISO Global Baselines."""

    @staticmethod
    def load(repo_path: str, config_path: str | None = None) -> dict[str, Any]:
        """Load configuration from .seraph-guard.yaml, .gitleaks.toml, .secrets.baseline, and .seraph-baseline.yaml."""
        config: dict[str, Any] = {}

        default_path = Path(repo_path) / ".seraph-guard.yaml"
        target_path = Path(config_path) if config_path else default_path

        if target_path.exists():
            if not _HAS_YAML or yaml is None:
                msg = "PyYAML is required to load config files. Install with: pip install pyyaml"
                raise ImportError(msg)
            try:
                with open(target_path, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Failed to load config from {target_path}: {e}")

        # Initialize secret allowlist
        allowlist_data: dict[str, Any] = {"paths": [], "regexes": [], "ignored_lines": {}}

        # Initialize Global Baseline Enforcement (CISO Override)
        global_baseline: dict[str, Any] = {
            "enforcement_enabled": False,
            "must_fix_rules": [],
            "must_fix_categories": [],
            "must_fix_severities": [],
        }

        # ── 1. Parse .gitleaks.toml ─────────────────────────────────────────────
        gitleaks_path = Path(repo_path) / ".gitleaks.toml"
        if gitleaks_path.exists():
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore[no-redef]
                except ImportError:
                    tomllib = None  # type: ignore[assignment]

            if tomllib is not None:
                try:
                    with open(gitleaks_path, "rb") as f:
                        gitleaks_data = tomllib.load(f)
                    al = gitleaks_data.get("allowlist", {})
                    allowlist_data["paths"] = [re.compile(p) for p in al.get("paths", []) if p]
                    allowlist_data["regexes"] = [re.compile(r) for r in al.get("regexes", []) if r]
                except Exception as e:
                    print(f"Warning: Failed to parse .gitleaks.toml: {e}")

        # ── 2. Parse .secrets.baseline (detect-secrets) ─────────────────────────
        baseline_path = Path(repo_path) / ".secrets.baseline"
        if baseline_path.exists():
            try:
                with open(baseline_path, encoding="utf-8") as f:
                    baseline_data = json.load(f)
                for filename, secrets in baseline_data.get("results", {}).items():
                    for secret in secrets:
                        allowlist_data["ignored_lines"].setdefault(filename, set()).add(
                            secret.get("line_number", 0)
                        )
                allowlist_data["ignored_lines"] = {
                    k: list(v) for k, v in allowlist_data["ignored_lines"].items()
                }
            except Exception as e:
                print(f"Warning: Failed to parse .secrets.baseline: {e}")

        # ── 3. Parse Global Baseline Enforcement (CISO Override) ────────────────
        # Can be defined in .seraph-baseline.yaml or under `global_baseline` in .seraph-guard.yaml

        # Check main config first
        if "global_baseline" in config and isinstance(config["global_baseline"], dict):
            gb = config["global_baseline"]
            global_baseline["enforcement_enabled"] = True
            global_baseline["must_fix_rules"].extend(
                [str(r).lower() for r in gb.get("must_fix_rules", [])]
            )
            global_baseline["must_fix_categories"].extend(
                [str(c).lower() for c in gb.get("must_fix_categories", [])]
            )
            global_baseline["must_fix_severities"].extend(
                [str(s).lower() for s in gb.get("must_fix_severities", [])]
            )

        # Check dedicated CISO baseline file
        ciso_baseline_path = Path(repo_path) / ".seraph-baseline.yaml"
        if ciso_baseline_path.exists() and _HAS_YAML and yaml is not None:
            try:
                with open(ciso_baseline_path, encoding="utf-8") as f:
                    ciso_data = yaml.safe_load(f) or {}

                # Support both root-level keys and nested `enforcement:` block safely
                enforcement_raw = ciso_data.get("enforcement")
                enforcement = enforcement_raw if isinstance(enforcement_raw, dict) else ciso_data

                if isinstance(enforcement, dict):
                    global_baseline["enforcement_enabled"] = True
                    global_baseline["must_fix_rules"].extend(
                        [str(r).lower() for r in enforcement.get("must_fix_rules", [])]
                    )
                    global_baseline["must_fix_categories"].extend(
                        [str(c).lower() for c in enforcement.get("must_fix_categories", [])]
                    )
                    global_baseline["must_fix_severities"].extend(
                        [str(s).lower() for s in enforcement.get("must_fix_severities", [])]
                    )
            except Exception as e:
                print(f"Warning: Failed to parse .seraph-baseline.yaml: {e}")

        config["secret_allowlist"] = allowlist_data
        config["global_baseline"] = global_baseline

        return config
