import asyncio
import json
import logging
import os
import re
import sqlite3
import tempfile
import time

from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any, ClassVar, NoReturn, cast, override
from urllib.parse import quote, unquote

import httpx

from cvss import CVSS3, CVSS4
from packaging.version import InvalidVersion, Version

from seraph.guard.intelligence.reachability import (
    ReachabilityAnalyzer,
    ReachabilityResult,
    ReachabilityStatus,
)
from seraph.guard.scanners.base import (
    BlastRadius,
    Category,
    Finding,
    ScanContext,
    Scanner,
    Severity,
)


logger = logging.getLogger(__name__)
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_CACHE_SCHEMA = 2

_OSV_PAGINATION_RESPONSE_FIELD = "next_page_token"
_OSV_PAGINATION_REQUEST_FIELD = "page_token"

_MSG_OSV_BATCH_NOT_OBJECT = "OSV batch response must be a JSON object"
_MSG_OSV_BATCH_RESULTS_NOT_LIST = "OSV batch response contained a non-list 'results' field"
_MSG_OSV_BATCH_RESULT_NOT_OBJECT = "OSV batch response contains a non-object result"
_MSG_OSV_BATCH_RETRIES_EXHAUSTED = "OSV batch request exhausted retries"
_MSG_OSV_BATCH_VULNS_NOT_LIST = "OSV batch result contained a non-list 'vulns' field"
_MSG_OSV_EMPTY_NEXT_PAGE_CURSOR = "OSV returned an empty next_page_token"


def _parse_osv_timestamp(value: Any) -> datetime | None:
    """Parse an OSV RFC3339 UTC timestamp without losing security semantics.

    Python ``datetime`` stores microsecond precision. OSV responses are valid
    RFC3339 timestamps and may contain more than six fractional digits. Parsing
    through ``datetime.fromisoformat`` therefore intentionally normalizes
    sub-microsecond precision instead of comparing timestamp strings
    lexicographically.

    Invalid or timezone-less timestamps return ``None`` so callers can fail
    closed rather than treating unverifiable freshness data as trusted.
    """
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        return None

    return parsed.astimezone(UTC)


def _osv_timestamp_at_least(actual: Any, expected: Any) -> bool:
    """Return whether an OSV timestamp is at least as fresh as another."""
    actual_dt = _parse_osv_timestamp(actual)
    expected_dt = _parse_osv_timestamp(expected)
    if actual_dt is None or expected_dt is None:
        return False
    return actual_dt >= expected_dt


def _coerce_int(
    value: Any,
    default: int,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    """Coerce configuration values without allowing mixed-type comparisons."""
    if isinstance(value, bool):
        result = default
    elif isinstance(value, int):
        result = value
    elif isinstance(value, float) and value.is_integer():
        result = int(value)
    elif isinstance(value, str):
        raw = value.strip()
        try:
            result = int(raw, 10)
        except ValueError:
            result = default
    else:
        result = default

    result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _coerce_optional_int(
    value: Any,
    default: int | None,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return default
    return _coerce_int(
        value, default if default is not None else minimum, minimum=minimum, maximum=maximum
    )


def _coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerce YAML/CLI boolean scalars safely."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


def _valid_osv_scalar(value: Any, *, field_name: str) -> tuple[str | None, str | None]:
    """Validate an OSV API scalar before it can poison a batch request."""
    if not isinstance(value, str):
        return None, f"{field_name} must be a string"
    value = value.strip()
    if not value:
        return None, f"{field_name} is empty"
    if len(value) > 4096:
        return None, f"{field_name} exceeds 4096 characters"
    if any(ord(char) < 32 for char in value):
        return None, f"{field_name} contains control characters"
    return value, None


def _build_osv_query(package: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Build one OSV query using the endpoint's mutually-exclusive identity rules.

    OSV accepts either a package name+ecosystem with a top-level version, or a
    package URL. A version must never be supplied twice.
    """
    raw_package = package.get("package")
    if not isinstance(raw_package, dict):
        return None, "package identity is not an object"

    version_value = package.get("version")
    if version_value in (None, "", "latest"):
        return None, "version is missing or unresolved"

    version, error = _valid_osv_scalar(version_value, field_name="version")
    if error is not None or version is None:
        return None, error or "version is missing"

    # Dependency parsers normally produce exact versions. Ranges and wildcards
    # cannot identify one installed artifact and should be reported as partial
    # coverage rather than guessed into a concrete version.
    if any(marker in version for marker in ("^", "~", "<", ">", "=", "|", "*", " ", ",")):
        return None, f"version is not a concrete version: {version!r}"

    raw_purl = raw_package.get("purl")
    if raw_purl:
        purl, error = _valid_osv_scalar(raw_purl, field_name="package.purl")
        if error is not None or purl is None:
            return None, error or "package.purl is missing"
        last_at = purl.rfind("@")
        last_slash = purl.rfind("/")
        purl_is_versioned = last_at > last_slash
        if purl_is_versioned:
            return (
                None,
                "package.purl already contains a version; top-level version would duplicate it",
            )
        return {"package": {"purl": purl}, "version": version}, None

    name, error = _valid_osv_scalar(raw_package.get("name"), field_name="package.name")
    if error is not None or name is None:
        return None, error or "package.name is missing"

    ecosystem, error = _valid_osv_scalar(
        raw_package.get("ecosystem"), field_name="package.ecosystem"
    )
    if error is not None or ecosystem is None:
        return None, error or "package.ecosystem is missing"

    return {
        "package": {"name": name, "ecosystem": ecosystem},
        "version": version,
    }, None


# CycloneDX JSON is a first-class SBOM input. Conventional names are
# recognized explicitly, while *.cdx.json and *.cyclonedx.json are also accepted.
_CYCLONEDX_JSON_NAMES: frozenset[str] = frozenset(
    {
        "bom.json",
        "bom.cdx.json",
        "cyclonedx.json",
    }
)

_CYCLONEDX_PURL_ECOSYSTEMS: dict[str, str] = {
    "npm": "npm",
    "pypi": "PyPI",
    "golang": "Go",
    "maven": "Maven",
    "cargo": "crates.io",
    "gem": "RubyGems",
    "composer": "Packagist",
    "nuget": "NuGet",
    "pub": "Pub",
    "hex": "Hex",
    "cran": "CRAN",
}


def _is_cyclonedx_json_name(filename: str) -> bool:
    """Return whether a filename should be treated as CycloneDX JSON."""
    normalized = filename.strip().lower()
    return normalized in _CYCLONEDX_JSON_NAMES or normalized.endswith(
        (".cdx.json", ".cyclonedx.json")
    )


def _parse_cyclonedx_purl(purl: str) -> dict[str, str] | None:
    """Parse OSV-queryable package identity from a PURL."""
    raw = str(purl).strip()
    if not raw.lower().startswith("pkg:"):
        return None

    body = raw[4:]
    slash = body.find("/")
    if slash <= 0:
        return None

    purl_type = body[:slash].strip().lower()
    path_part = re.split(r"[?#]", body[slash + 1 :], maxsplit=1)[0]
    if not path_part:
        return None

    version = ""
    last_at = path_part.rfind("@")
    last_slash = path_part.rfind("/")
    if last_at > last_slash:
        version = unquote(path_part[last_at + 1 :]).strip()
        path_part = path_part[:last_at]

    decoded_path = unquote(path_part).strip("/")
    if not decoded_path:
        return None

    if purl_type == "maven" and "/" in decoded_path:
        namespace, artifact = decoded_path.split("/", 1)
        name = f"{namespace}:{artifact}".strip(":")
    else:
        name = decoded_path

    ecosystem = _CYCLONEDX_PURL_ECOSYSTEMS.get(purl_type, "")
    if not ecosystem or not name:
        return None

    identity = {"ecosystem": ecosystem, "name": name}
    if version:
        identity["version"] = version
    return identity


def _cyclonedx_bool_property(component: dict[str, Any], names: set[str]) -> bool:
    """Read a conservative boolean development-dependency property."""
    properties = component.get("properties", [])
    if not isinstance(properties, list):
        return False
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = str(prop.get("name", "")).strip().lower()
        value = str(prop.get("value", "")).strip().lower()
        if name in names and value in {"1", "true", "yes", "on"}:
            return True
    return False


MANIFEST_PARSERS: dict[str, str] = {
    "package-lock.json": "parse_npm_lock",
    "yarn.lock": "parse_yarn_lock",
    "pnpm-lock.yaml": "parse_pnpm_lock",
    "package.json": "parse_package_json",
    "poetry.lock": "parse_poetry_lock",
    "Pipfile.lock": "parse_pipfile_lock",
    "requirements.txt": "parse_requirements_txt",
    "requirements-dev.txt": "parse_requirements_txt",
    "pyproject.toml": "parse_pyproject_toml",
    "go.mod": "parse_go_mod",
    "go.sum": "parse_go_sum",
    "pom.xml": "parse_pom_xml",
    "build.gradle": "parse_gradle",
    "build.gradle.kts": "parse_gradle_kts",
    "Cargo.lock": "parse_cargo_lock",
    "Gemfile.lock": "parse_gemfile_lock",
    "composer.lock": "parse_composer_lock",
    "pubspec.lock": "parse_pubspec_lock",
    "packages.lock.json": "parse_packages_lock_json",
    "uv.lock": "parse_uv_lock",
    "bom.json": "parse_cyclonedx_json",
    "bom.cdx.json": "parse_cyclonedx_json",
    "cyclonedx.json": "parse_cyclonedx_json",
}

_PARSER_FILES: set[str] = set(MANIFEST_PARSERS.keys())

_LOCKFILE_NAMES: set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "go.sum",
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
    "pubspec.lock",
    "packages.lock.json",
    "uv.lock",
}

ECOSYSTEM_MAP: dict[str, str] = {
    "package-lock.json": "npm",
    "yarn.lock": "npm",
    "pnpm-lock.yaml": "npm",
    "package.json": "npm",
    "poetry.lock": "PyPI",
    "Pipfile.lock": "PyPI",
    "requirements.txt": "PyPI",
    "requirements-dev.txt": "PyPI",
    "pyproject.toml": "PyPI",
    "go.mod": "Go",
    "go.sum": "Go",
    "pom.xml": "Maven",
    "build.gradle": "Maven",
    "build.gradle.kts": "Maven",
    "Cargo.lock": "crates.io",
    "Gemfile.lock": "RubyGems",
    "composer.lock": "Packagist",
    "pubspec.lock": "Pub",
    "packages.lock.json": "NuGet",
    "uv.lock": "PyPI",
}

_WALK_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".eggs",
        ".seraph-cache",
        ".seraph-learn",
        "site-packages",
        ".idea",
        ".vscode",
        "vendor",
        "vendors",
        "third_party",
        "third-party",
        "bower_components",
        ".next",
        ".nuxt",
        ".turbo",
        "coverage",
        ".cache",
        "__snapshots__",
        "out",
        "target",
        "playground",
        "playgrounds",
        ".storybook",
        ".docusaurus",
    }
)


def _toml_loads(text: str) -> dict[str, Any]:
    try:
        import tomllib

        return tomllib.loads(text)
    except ImportError:
        try:
            import tomli

            return tomli.loads(text)
        except ImportError:
            return {}


class OSVCache:
    def __init__(self, cache_dir: Path | None = None):
        if cache_dir is None:
            cache_dir = Path(tempfile.gettempdir()) / ".seraph-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_dir / "osv_cache.db"
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS osv_vulns (
                    id TEXT PRIMARY KEY,
                    schema_version INTEGER,
                    modified TEXT,
                    record TEXT,
                    created_at INTEGER
                )
            """)
            # Cache full records for 7 days
            conn.execute(
                "DELETE FROM osv_vulns WHERE created_at < ?", (int(time.time()) - 7 * 86400,)
            )

    def get_vuln(self, vuln_id: str, expected_modified: str = "") -> dict[str, Any] | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT schema_version, modified, record FROM osv_vulns WHERE id = ?", (vuln_id,)
            ).fetchone()
            if row:
                schema_version, modified, record_str = row
                if schema_version == OSV_CACHE_SCHEMA:
                    # Freshness is a timestamp comparison, not a string comparison.
                    # OSV uses RFC3339 UTC timestamps and may include fractional
                    # seconds beyond Python datetime's microsecond precision.
                    if expected_modified and not _osv_timestamp_at_least(
                        modified, expected_modified
                    ):
                        return None
                    return cast("dict[str, Any]", json.loads(record_str))
        return None

    def set_vuln(self, vuln_id: str, record: dict[str, Any]) -> None:
        modified = record.get("modified", "")
        parsed_modified = _parse_osv_timestamp(modified)
        normalized_modified = (
            parsed_modified.isoformat(timespec="microseconds").replace("+00:00", "Z")
            if parsed_modified is not None
            else str(modified or "").strip()
        )
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO osv_vulns
                   (id, schema_version, modified, record, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    vuln_id,
                    OSV_CACHE_SCHEMA,
                    normalized_modified,
                    json.dumps(record),
                    int(time.time()),
                ),
            )


class SBOMScanner(Scanner):
    name = "SBOMScanner"
    version = "4.3.2"
    categories: ClassVar[list[Category]] = [Category.VULNERABILITY]

    def __init__(
        self,
        timeout: int = 60,
        cache_dir: Path | None = None,
        chunk_size: int = 50,
        max_dependencies: int | None = None,
        quick_mode: bool = False,
    ):
        self.timeout = _coerce_int(timeout, 60, minimum=1, maximum=3600)
        self.chunk_size = _coerce_int(chunk_size, 50, minimum=1, maximum=500)
        self.max_dependencies = _coerce_optional_int(
            max_dependencies,
            None,
            minimum=10,
            maximum=1_000_000,
        )
        self.quick_mode = _coerce_bool(quick_mode, False)
        self.osv_cache = OSVCache(cache_dir)
        self._pkg_graph: dict[str, set[str]] = {}
        self._hydration_concurrency = 64
        self.last_scan_stats: dict[str, Any] = {}

    @override
    def is_applicable(self, context: ScanContext) -> bool:
        return True

    @override
    async def scan(self, context: ScanContext) -> list[Finding]:
        findings: list[Finding] = []
        self._pkg_graph.clear()
        scan_path = context.resolved_path
        packages_to_query: list[dict[str, Any]] = []

        stats: dict[str, Any] = {
            "coverage_status": "complete",
            "manifests_discovered": 0,
            "manifests_parsed": 0,
            "parse_errors": 0,
            "dependencies_discovered": 0,
            "dependencies_filtered": 0,
            "dependencies_unique": 0,
            "dependencies_queryable": 0,
            "dependencies_skipped": 0,
            "dependencies_skipped_cap": 0,
            "invalid_osv_queries": 0,
            "cyclonedx_components": 0,
            "osv_batches": 0,
            "osv_pages": 0,
            "osv_vulnerability_references": 0,
            "osv_unique_vulnerabilities": 0,
            "osv_cache_hits": 0,
            "osv_hydrated": 0,
            "partial_reasons": [],
        }

        include_dev = False
        chunk_size = self.chunk_size
        quick_mode = self.quick_mode
        max_deps: int | None = self.max_dependencies

        if context.config is not None:
            sbom_cfg = getattr(context.config, "sbom", None)
            if sbom_cfg is not None:
                include_dev = _coerce_bool(
                    getattr(sbom_cfg, "include_dev_dependencies", False),
                    False,
                )
                chunk_size = _coerce_int(
                    getattr(sbom_cfg, "chunk_size", self.chunk_size),
                    self.chunk_size,
                    minimum=1,
                    maximum=500,
                )
                quick_mode = _coerce_bool(
                    getattr(sbom_cfg, "quick_mode", self.quick_mode),
                    self.quick_mode,
                )
                max_deps = _coerce_optional_int(
                    getattr(sbom_cfg, "max_dependencies", self.max_dependencies),
                    self.max_dependencies,
                    minimum=10,
                    maximum=1_000_000,
                )

        discovered_files: list[Path] = []
        try:
            for dirpath, dirnames, filenames in os.walk(
                scan_path, followlinks=False, onerror=lambda _: None
            ):
                dirnames[:] = sorted(d for d in dirnames if d not in _WALK_SKIP_DIRS)
                for filename in sorted(filenames):
                    if filename in _PARSER_FILES or _is_cyclonedx_json_name(filename):
                        path = Path(dirpath) / filename
                        if path.is_file():
                            discovered_files.append(path)
        except (PermissionError, OSError) as e:
            logger.warning("SBOM manifest walk error: %s", e)
            stats["partial_reasons"].append("manifest_walk_error")

        discovered_files.sort()
        stats["manifests_discovered"] = len(discovered_files)

        if not discovered_files:
            stats["coverage_status"] = "no_manifests"
            self.last_scan_stats = stats
            context.metadata.setdefault("scanners", {})[self.name] = dict(stats)
            logger.info("SBOMScanner: no manifest files found in %s", scan_path)
            return findings

        cyclonedx_files = [f for f in discovered_files if _is_cyclonedx_json_name(f.name)]

        if quick_mode:
            files_to_parse = [
                f for f in discovered_files if f.name not in _LOCKFILE_NAMES or f in cyclonedx_files
            ]
        else:
            lockfiles = [f for f in discovered_files if f.name in _LOCKFILE_NAMES]
            lockfile_parents = {str(f.parent) for f in lockfiles}
            orphan_manifests = [
                f
                for f in discovered_files
                if f.name not in _LOCKFILE_NAMES
                and not _is_cyclonedx_json_name(f.name)
                and str(f.parent) not in lockfile_parents
            ]
            # A CycloneDX SBOM is an independent authoritative dependency
            # representation and must not be hidden by a sibling lockfile.
            files_to_parse = lockfiles + orphan_manifests + cyclonedx_files

        files_to_parse = list(dict.fromkeys(sorted(files_to_parse)))

        total_parsed = 0
        for file_path in files_to_parse:
            parser_name = MANIFEST_PARSERS.get(file_path.name)
            if parser_name is None and _is_cyclonedx_json_name(file_path.name):
                parser_name = "parse_cyclonedx_json"
            parser = getattr(self, parser_name or "parse_generic", self.parse_generic)
            try:
                parsed_deps = parser(file_path)
                if not isinstance(parsed_deps, list):
                    stats["parse_errors"] += 1
                    stats["partial_reasons"].append(f"parser_return:{file_path.name}")
                    continue
                total_parsed += len(parsed_deps)
                stats["manifests_parsed"] += 1
                if _is_cyclonedx_json_name(file_path.name):
                    stats["cyclonedx_components"] += len(parsed_deps)

                default_ecosystem = ECOSYSTEM_MAP.get(file_path.name, "")
                for dep in parsed_deps:
                    stats["dependencies_discovered"] += 1
                    if not isinstance(dep, dict):
                        stats["dependencies_filtered"] += 1
                        continue
                    raw_name = dep.get("name")
                    raw_version = dep.get("version")
                    if not isinstance(raw_name, str) or not raw_name.strip():
                        stats["dependencies_filtered"] += 1
                        continue
                    if raw_version in (None, "", "latest"):
                        stats["dependencies_filtered"] += 1
                        continue
                    if dep.get("is_dev") and not include_dev:
                        stats["dependencies_filtered"] += 1
                        continue
                    if quick_mode and dep.get("transitive"):
                        stats["dependencies_filtered"] += 1
                        continue

                    name = raw_name.strip()
                    version = str(raw_version).strip()
                    ecosystem = str(dep.get("ecosystem") or default_ecosystem).strip()
                    if not ecosystem:
                        stats["dependencies_filtered"] += 1
                        stats["partial_reasons"].append(f"unknown_ecosystem:{file_path.name}")
                        continue

                    rel_file = str(file_path.relative_to(scan_path))
                    packages_to_query.append(
                        {
                            "package": {"name": name, "ecosystem": ecosystem},
                            "version": version,
                            "file": rel_file,
                            "is_dev": _coerce_bool(dep.get("is_dev", False), False),
                            "transitive": _coerce_bool(dep.get("transitive", False), False),
                            "children": dep.get("children", []),
                            "bom_ref": str(dep.get("bom_ref", "")),
                            "purl": str(dep.get("purl", "")),
                            "sbom_format": str(dep.get("sbom_format", "")),
                            "sbom_spec_version": str(dep.get("sbom_spec_version", "")),
                        }
                    )
                    children = dep.get("children", [])
                    if isinstance(children, (list, tuple, set, frozenset)):
                        self._pkg_graph.setdefault(name, set()).update(
                            str(child) for child in children if isinstance(child, (str, int))
                        )
            except Exception as e:
                stats["parse_errors"] += 1
                stats["partial_reasons"].append(f"parse_error:{file_path.name}")
                logger.debug("Failed to parse %s: %s", file_path, e)

        stats["dependencies_parsed"] = total_parsed

        if not packages_to_query:
            stats["coverage_status"] = "partial" if stats["parse_errors"] else "complete"
            self.last_scan_stats = stats
            context.metadata.setdefault("scanners", {})[self.name] = dict(stats)
            logger.info("SBOMScanner: no dependencies to query after parsing")
            return findings

        # Collapse duplicate package/version identities while preserving production
        # priority. A dependency referenced by both dev and production manifests is
        # production-impacting and must not inherit the first (possibly dev) context.
        by_identity: dict[tuple[str, str, str], dict[str, Any]] = {}
        for package in packages_to_query:
            p = package["package"]
            key = (str(p["ecosystem"]), str(p["name"]), str(package["version"]))
            existing = by_identity.get(key)
            if existing is None:
                by_identity[key] = dict(package)
            else:
                existing["is_dev"] = bool(
                    existing.get("is_dev", False) and package.get("is_dev", False)
                )
                existing["transitive"] = bool(
                    existing.get("transitive", False) and package.get("transitive", False)
                )
                # Prefer a lockfile origin over a loose manifest where possible.
                existing_file = str(existing.get("file", ""))
                candidate_file = str(package.get("file", ""))
                if (candidate_file and not existing_file) or (
                    candidate_file.endswith(tuple(_LOCKFILE_NAMES))
                    and not existing_file.endswith(tuple(_LOCKFILE_NAMES))
                ):
                    existing["file"] = candidate_file

        unique_packages = sorted(
            by_identity.values(),
            key=lambda p: (
                bool(p.get("transitive", False)),
                bool(p.get("is_dev", False)),
                str(p["package"]["ecosystem"]),
                str(p["package"]["name"]).lower(),
                str(p["version"]),
                str(p.get("file", "")),
            ),
        )
        stats["dependencies_unique"] = len(unique_packages)

        if max_deps is not None and len(unique_packages) > max_deps:
            stats["dependencies_skipped_cap"] = len(unique_packages) - max_deps
            stats["partial_reasons"].append("max_dependencies_cap")
            logger.warning(
                "SBOM: %d dependencies found, only %d checked",
                len(unique_packages),
                max_deps,
            )
            unique_packages = unique_packages[:max_deps]

        stats["dependencies_queryable"] = len(unique_packages)
        stats["dependencies_skipped"] = (
            stats["dependencies_filtered"] + stats["dependencies_skipped_cap"]
        )

        vulnerabilities = await self._query_osv_cached(
            unique_packages,
            chunk_size,
            context=context,
        )
        stats.update({k: v for k, v in self.last_scan_stats.items() if k.startswith("osv_")})
        if self.last_scan_stats.get("invalid_osv_queries", 0):
            stats["invalid_osv_queries"] = self.last_scan_stats["invalid_osv_queries"]
            stats["dependencies_skipped"] += self.last_scan_stats["invalid_osv_queries"]
            stats["partial_reasons"].append("invalid_osv_queries")
        if self.last_scan_stats.get("partial_reasons"):
            stats["partial_reasons"].extend(
                reason
                for reason in self.last_scan_stats["partial_reasons"]
                if reason not in stats["partial_reasons"]
            )

        raw_findings: list[dict[str, Any]] = []
        for vuln in vulnerabilities:
            raw_findings.append(
                {
                    "package": vuln["package_name"],
                    "ecosystem": vuln.get("ecosystem", "PyPI"),
                    "cve_id": vuln["id"],
                    "vulnerability_id": vuln["id"],
                    "aliases": vuln.get("aliases", []),
                    "version": vuln["version"],
                    "severity": vuln.get("severity", "UNKNOWN").upper(),
                    "source_severity": vuln.get("source_severity", "UNKNOWN"),
                    "severity_source": vuln.get("severity_source", "none"),
                    "advisory_type": vuln.get("advisory_type", "vulnerability"),
                    "cvss_score": vuln.get("cvss_score"),
                    "cvss_vector": vuln.get("cvss_vector", ""),
                    "cvss_version": vuln.get("cvss_version", ""),
                    "file": vuln["file"],
                    "title": vuln.get("summary", f"Vulnerability in {vuln['package_name']}"),
                    "description": vuln.get("details", "No details provided by OSV.")[:800],
                    "fixed_version": vuln.get("fixed_version", ""),
                    "fixed_versions": vuln.get("fixed_versions", []),
                    "is_dev": vuln.get("is_dev", False),
                }
            )

        deduped = self._deduplicate_and_rank(raw_findings, str(scan_path))

        reachability_analyzer = ReachabilityAnalyzer(scan_path)
        reachability_cache: dict[tuple[str, str], ReachabilityResult] = {}

        for entry in deduped:
            severity_str = str(entry.get("severity", "MEDIUM")).lower()
            raw_entry_cvss = entry.get("cvss_score")
            cvss = (
                float(raw_entry_cvss)
                if isinstance(raw_entry_cvss, (int, float)) and not isinstance(raw_entry_cvss, bool)
                else 0.0
            )
            severity = self._map_severity(severity_str, cvss)
            fix_available = bool(entry.get("fixed_version"))
            fix_cmd = (
                f"Upgrade {entry.get('package')} to >= {entry.get('fixed_version')}"
                if fix_available
                else None
            )
            pkg = entry.get("package", "")
            children = self._pkg_graph.get(pkg, set())
            blast_score = float(severity.weight) + (len(children) * 0.5)
            reduction = (
                80.0
                if severity == Severity.CRITICAL
                else (60.0 if severity == Severity.HIGH else 30.0)
            )
            if entry.get("is_dev"):
                reduction *= 0.3

            if cvss > 0:
                conformal_lower = max(0.0, (cvss / 10.0) - 0.15)
                conformal_upper = min(1.0, (cvss / 10.0) + 0.10)
                confidence = cvss / 10.0
            else:
                conformal_lower = 0.50
                conformal_upper = 0.90
                confidence = 0.70

            pkg_name = entry.get("package", "")
            ecosystem = entry.get("ecosystem", "PyPI")
            cache_key = (pkg_name, ecosystem)
            if cache_key not in reachability_cache:
                try:
                    reachability_cache[cache_key] = reachability_analyzer.analyze(
                        pkg_name, ecosystem, scan_path
                    )
                except Exception as e:
                    logger.debug("Reachability analysis failed for %s: %s", pkg_name, e)
                    reachability_cache[cache_key] = ReachabilityResult(
                        status=ReachabilityStatus.UNKNOWN, reason=str(e)
                    )

            reach_result = reachability_cache[cache_key]
            reach_status = reach_result.status.value

            finding = Finding(
                scanner=self.name,
                category=Category.VULNERABILITY,
                severity=severity,
                confidence=confidence,
                file=entry.get("file", ""),
                line=0,
                title=f"{entry.get('cve_id', 'OSV')} in {entry.get('package', 'unknown')}@{entry.get('version', '')}",
                description=entry.get("description", ""),
                evidence=(
                    f"{entry.get('package', '')} @ {entry.get('version', '')} "
                    f"(CVSS: {cvss if cvss is not None else 'N/A'})"
                ),
                blast_radius=BlastRadius(
                    affected_resources=entry.get("affected_manifests", []),
                    blast_radius_score=min(blast_score, 10.0),
                    reduction_if_fixed=reduction,
                ),
                fix_available=fix_available,
                fix_command=fix_cmd,
                fix_description=f"Upgrade to {entry.get('fixed_version')}"
                if fix_available
                else None,
                cve=entry.get("cve_id"),
                cvss_score=cvss,
                package_name=entry.get("package", ""),
                fixed_version=entry.get("fixed_version", ""),
                metadata={
                    "package": entry.get("package"),
                    "version": entry.get("version"),
                    "vulnerability_id": entry.get("vulnerability_id", entry.get("cve_id")),
                    "aliases": entry.get("aliases", []),
                    "advisory_type": entry.get("advisory_type", "vulnerability"),
                    "source_severity": entry.get("source_severity", "UNKNOWN"),
                    "severity_source": entry.get("severity_source", "none"),
                    "cvss_score": cvss,
                    "cvss_vector": entry.get("cvss_vector", ""),
                    "cvss_version": entry.get("cvss_version", ""),
                    "fixed_version": entry.get("fixed_version", ""),
                    "fixed_versions": entry.get("fixed_versions", []),
                    "affected_manifests": entry.get("affected_manifests", []),
                    "manifest_count": entry.get("manifest_count", 0),
                    "is_dev_dependency": entry.get("is_dev_dependency", False),
                    "transitive": entry.get("transitive", False),
                    "reachability": reach_status,
                },
            )

            if reach_status == ReachabilityStatus.UNREACHABLE.value:
                if severity == Severity.CRITICAL:
                    eff_sev = Severity.HIGH
                elif severity == Severity.HIGH:
                    eff_sev = Severity.MEDIUM
                elif severity == Severity.MEDIUM:
                    eff_sev = Severity.LOW
                elif severity == Severity.LOW:
                    eff_sev = Severity.INFO
                else:
                    eff_sev = severity
            else:
                eff_sev = severity

            try:
                finding.effective_severity = eff_sev
            except (AttributeError, TypeError):
                object.__setattr__(finding, "effective_severity", eff_sev)

            try:
                finding.conformal_lower = conformal_lower
                finding.conformal_upper = conformal_upper
                finding.causal_rank = None
            except (AttributeError, TypeError):
                object.__setattr__(finding, "conformal_lower", conformal_lower)
                object.__setattr__(finding, "conformal_upper", conformal_upper)
                object.__setattr__(finding, "causal_rank", None)

            findings.append(finding)

        stats["coverage_status"] = (
            "partial"
            if stats["partial_reasons"]
            or stats["invalid_osv_queries"]
            or stats["dependencies_skipped_cap"]
            else "complete"
        )
        stats["partial_reasons"] = list(dict.fromkeys(stats["partial_reasons"]))
        self.last_scan_stats = stats
        context.metadata.setdefault("scanners", {})[self.name] = dict(stats)
        if stats["coverage_status"] == "partial":
            context.metadata.setdefault("warnings", []).append(
                "SBOM dependency coverage is partial; see scan_metadata.scanners.SBOMScanner for exact counts."
            )

        logger.info("SBOMScanner found %d vulnerabilities", len(findings))
        return findings

    async def _query_osv_cached(
        self,
        packages: list[dict[str, Any]],
        chunk_size: int | None = None,
        *,
        context: ScanContext | None = None,
    ) -> list[dict[str, Any]]:
        """Query OSV safely, deterministically, and with per-query fault isolation.

        OSV querybatch is ordered, supports per-query pagination, and requires the
        version to be specified exactly once. A malformed item must not poison all
        valid dependencies in the same batch, so 400/413/422 responses are split
        deterministically until an offending single query is isolated. Transient
        transport/server failures are retried and remain fatal after exhaustion.
        """
        chunk_size = _coerce_int(
            self.chunk_size if chunk_size is None else chunk_size,
            self.chunk_size,
            minimum=1,
            maximum=500,
        )

        stats: dict[str, Any] = {
            "osv_batches": 0,
            "osv_pages": 0,
            "osv_vulnerability_references": 0,
            "osv_unique_vulnerabilities": 0,
            "osv_cache_hits": 0,
            "osv_hydrated": 0,
            "invalid_osv_queries": 0,
            "partial_reasons": [],
        }

        def package_key(pkg: dict[str, Any]) -> tuple[str, str, str, str]:
            package = pkg.get("package", {})
            file_path = str(pkg.get("file") or (pkg.get("files") or [""])[0])
            return (
                str(package.get("ecosystem", "")),
                str(package.get("name", "")),
                str(pkg.get("version", "")),
                file_path,
            )

        def package_file(pkg: dict[str, Any]) -> str:
            return str(pkg.get("file") or (pkg.get("files") or [""])[0])

        pending: list[dict[str, Any]] = []
        for pkg in packages:
            query, reason = _build_osv_query(pkg)
            if query is None:
                stats["invalid_osv_queries"] += 1
                stats["partial_reasons"].append(f"invalid_query:{reason or 'unknown'}")
                continue
            pending.append(
                {
                    "query": query,
                    "pkg": pkg,
                    "key": package_key(pkg),
                    "page_cursor": None,
                }
            )

        stats["dependencies_queryable"] = len(pending)

        if not pending:
            self.last_scan_stats = stats
            if context is not None:
                context.metadata.setdefault("scanners", {})[self.name] = {
                    **context.metadata.get("scanners", {}).get(self.name, {}),
                    **stats,
                }
            return []

        # Keep vulnerability references attached to exact package identities.
        pkg_vuln_map: dict[tuple[str, str, str, str], list[tuple[str, str]]] = {}
        pkg_vuln_seen: dict[tuple[str, str, str, str], set[tuple[str, str]]] = {}

        class _BadBatchRequestError(RuntimeError):
            def __init__(self, status_code: int, detail: str) -> None:
                super().__init__(detail)
                self.status_code = status_code

        def _raise_bad_batch_request(status_code: int, detail: str) -> NoReturn:
            message = f"OSV rejected batch ({status_code}): {detail or 'no detail'}"
            raise _BadBatchRequestError(status_code, message)

        def _validate_osv_response(payload: Any, batch_len: int) -> list[dict[str, Any]]:
            if not isinstance(payload, dict):
                raise TypeError(_MSG_OSV_BATCH_NOT_OBJECT)
            results = payload.get("results")
            if not isinstance(results, list):
                raise TypeError(_MSG_OSV_BATCH_RESULTS_NOT_LIST)
            if len(results) != batch_len:
                message = (
                    f"OSV batch response length mismatch: sent {batch_len} queries, "
                    f"received {len(results)} results"
                )
                raise ValueError(message)
            if any(not isinstance(result, dict) for result in results):
                raise TypeError(_MSG_OSV_BATCH_RESULT_NOT_OBJECT)
            return cast("list[dict[str, Any]]", results)

        try:
            http2_enabled = find_spec("h2") is not None
        except (ImportError, ValueError):
            http2_enabled = False

        if not http2_enabled:
            logger.warning(
                "HTTP/2 support is unavailable; install the 'h2' dependency for efficient large OSV queries."
            )

        timeout = httpx.Timeout(
            connect=10.0,
            read=float(self.timeout),
            write=20.0,
            pool=30.0,
        )
        limits = httpx.Limits(
            max_connections=self._hydration_concurrency,
            max_keepalive_connections=min(self._hydration_concurrency, 32),
        )

        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=http2_enabled,
            headers={"Accept": "application/json"},
        ) as client:

            async def post_batch(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
                queries: list[dict[str, Any]] = []
                for q_info in batch:
                    query = dict(q_info["query"])
                    cursor = q_info.get("page_cursor")
                    if cursor:
                        query[_OSV_PAGINATION_REQUEST_FIELD] = str(cursor)
                    queries.append(query)

                transient_statuses = {429, 500, 502, 503, 504}
                for attempt in range(4):
                    try:
                        response = await client.post(OSV_BATCH_URL, json={"queries": queries})
                        status = response.status_code
                        if status in {400, 413, 422}:
                            detail = response.text.strip().replace("\n", " ")[:300]
                            _raise_bad_batch_request(status, detail)
                        if status in transient_statuses:
                            if attempt >= 3:
                                response.raise_for_status()
                            await self._sleep(0.5 * (2**attempt))
                            continue
                        response.raise_for_status()
                        return _validate_osv_response(response.json(), len(batch))
                    except _BadBatchRequestError:
                        raise
                    except (httpx.TimeoutException, httpx.NetworkError) as exc:
                        if attempt >= 3:
                            message = f"OSV batch transport failed after retries: {exc}"
                            raise RuntimeError(message) from exc
                        await self._sleep(0.5 * (2**attempt))
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        if status in transient_statuses and attempt < 3:
                            await self._sleep(0.5 * (2**attempt))
                            continue
                        message = f"OSV batch query failed: {exc}"
                        raise RuntimeError(message) from exc
                    except ValueError as exc:
                        message = f"OSV batch response was invalid: {exc}"
                        raise RuntimeError(message) from exc
                raise RuntimeError(_MSG_OSV_BATCH_RETRIES_EXHAUSTED)

            # Each queue element is a list. Splitting a rejected batch isolates
            # malformed dependencies without discarding valid package queries.
            batch_queue: list[list[dict[str, Any]]] = [
                pending[index : index + chunk_size] for index in range(0, len(pending), chunk_size)
            ]

            while batch_queue:
                batch = batch_queue.pop(0)
                try:
                    results = await post_batch(batch)
                except _BadBatchRequestError as exc:
                    if len(batch) > 1:
                        midpoint = len(batch) // 2
                        # Preserve deterministic left-before-right order.
                        batch_queue.insert(0, batch[midpoint:])
                        batch_queue.insert(0, batch[:midpoint])
                        continue

                    only = batch[0]
                    stats["invalid_osv_queries"] += 1
                    stats["partial_reasons"].append(
                        f"rejected_query:{exc.status_code}:{only['pkg'].get('file', '')}"
                    )
                    logger.warning(
                        "Skipping one invalid OSV dependency query from %s: %s",
                        only["pkg"].get("file", ""),
                        exc,
                    )
                    continue

                stats["osv_batches"] += 1
                for q_info, result in zip(batch, results, strict=True):
                    key = q_info["key"]
                    vulns = result.get("vulns", [])
                    if vulns is None:
                        vulns = []
                    if not isinstance(vulns, list):
                        raise TypeError(_MSG_OSV_BATCH_VULNS_NOT_LIST)

                    refs = pkg_vuln_map.setdefault(key, [])
                    seen = pkg_vuln_seen.setdefault(key, set())

                    for vuln in vulns:
                        if not isinstance(vuln, dict):
                            continue
                        vuln_id = vuln.get("id")
                        if not isinstance(vuln_id, str) or not vuln_id.strip():
                            continue
                        modified_raw = vuln.get("modified", "")
                        modified = str(modified_raw).strip()
                        ref = (vuln_id.strip(), modified)
                        if ref not in seen:
                            seen.add(ref)
                            refs.append(ref)
                            stats["osv_vulnerability_references"] += 1

                    next_page_cursor_raw = result.get(_OSV_PAGINATION_RESPONSE_FIELD)
                    if next_page_cursor_raw:
                        cursor = str(next_page_cursor_raw).strip()
                        if not cursor:
                            raise RuntimeError(_MSG_OSV_EMPTY_NEXT_PAGE_CURSOR)
                        next_item = dict(q_info)
                        next_item["page_cursor"] = cursor
                        batch_queue.append([next_item])
                        stats["osv_pages"] += 1

            all_vuln_ids = {
                vuln_id for refs in pkg_vuln_map.values() for vuln_id, _modified in refs
            }
            stats["osv_unique_vulnerabilities"] = len(all_vuln_ids)

            expected_modified: dict[str, str] = {}
            for refs in pkg_vuln_map.values():
                for vuln_id, modified in refs:
                    if not modified:
                        continue
                    modified_dt = _parse_osv_timestamp(modified)
                    if modified_dt is None:
                        message = (
                            f"OSV discovery returned an invalid modified timestamp for "
                            f"{vuln_id}: {modified}"
                        )
                        raise ValueError(message)
                    previous = expected_modified.get(vuln_id)
                    if previous is None:
                        expected_modified[vuln_id] = modified
                        continue
                    previous_dt = _parse_osv_timestamp(previous)
                    if previous_dt is None or modified_dt > previous_dt:
                        expected_modified[vuln_id] = modified

            vuln_records: dict[str, dict[str, Any]] = {}
            semaphore = asyncio.Semaphore(self._hydration_concurrency)

            async def fetch_vuln(vuln_id: str) -> None:
                expected = expected_modified.get(vuln_id, "")
                cached = self.osv_cache.get_vuln(vuln_id, expected_modified=expected)
                if cached:
                    vuln_records[vuln_id] = cached
                    stats["osv_cache_hits"] += 1
                    return

                url = f"https://api.osv.dev/v1/vulns/{quote(vuln_id, safe='')}"
                record: Any = None
                async with semaphore:
                    for attempt in range(4):
                        try:
                            response = await client.get(url)
                            status = response.status_code
                            if status in {429, 500, 502, 503, 504} and attempt < 3:
                                await self._sleep(0.5 * (2**attempt))
                                continue
                            response.raise_for_status()
                            record = response.json()
                            break
                        except (httpx.TimeoutException, httpx.NetworkError) as exc:
                            if attempt >= 3:
                                message = (
                                    f"Failed to fetch OSV vulnerability {vuln_id} "
                                    f"after retries: {exc}"
                                )
                                raise RuntimeError(message) from exc
                            await self._sleep(0.5 * (2**attempt))
                        except httpx.HTTPStatusError as exc:
                            status = exc.response.status_code
                            if status in {429, 500, 502, 503, 504} and attempt < 3:
                                await self._sleep(0.5 * (2**attempt))
                                continue
                            message = f"Failed to fetch OSV vulnerability {vuln_id}: {exc}"
                            raise RuntimeError(message) from exc
                        except ValueError as exc:
                            message = f"OSV vulnerability {vuln_id} returned invalid JSON: {exc}"
                            raise RuntimeError(message) from exc

                if not isinstance(record, dict):
                    message = f"OSV vulnerability {vuln_id} returned a non-object record"
                    raise TypeError(message)

                record_id = str(record.get("id", "")).strip()
                if record_id and record_id != vuln_id:
                    message = (
                        f"OSV vulnerability ID mismatch: requested {vuln_id}, received {record_id}"
                    )
                    raise ValueError(message)

                record_modified = str(record.get("modified", "")).strip()
                if expected:
                    if not record_modified:
                        message = (
                            f"OSV vulnerability {vuln_id} omitted its modified timestamp; "
                            "freshness could not be verified"
                        )
                        raise ValueError(message)
                    if _parse_osv_timestamp(record_modified) is None:
                        message = (
                            f"OSV returned an invalid modified timestamp for {vuln_id}: "
                            f"{record_modified}"
                        )
                        raise ValueError(message)
                    if not _osv_timestamp_at_least(record_modified, expected):
                        message = (
                            f"OSV returned a stale vulnerability record for {vuln_id}: "
                            f"expected >= {expected}, received {record_modified}"
                        )
                        raise ValueError(message)

                self.osv_cache.set_vuln(vuln_id, record)
                vuln_records[vuln_id] = record
                stats["osv_hydrated"] += 1

            await asyncio.gather(*(fetch_vuln(vuln_id) for vuln_id in sorted(all_vuln_ids)))

            vulnerabilities: list[dict[str, Any]] = []
            for pkg in packages:
                key = package_key(pkg)
                refs = pkg_vuln_map.get(key, [])
                for vuln_id, _modified in refs:
                    record = vuln_records.get(vuln_id)
                    if not record:
                        message = f"OSV vulnerability record unavailable: {vuln_id}"
                        raise RuntimeError(message)

                    sev, cvss, cvss_vector, cvss_version, source_severity, severity_source = (
                        self._extract_severity(record)
                    )
                    fixed_version, fixed_versions = self._extract_fixed_version(
                        record,
                        str(pkg["version"]),
                        str(pkg["package"]["ecosystem"]),
                    )
                    advisory_type = self._extract_advisory_type(record)
                    aliases = [
                        str(alias)
                        for alias in record.get("aliases", [])
                        if isinstance(alias, str) and alias
                    ]

                    vulnerabilities.append(
                        {
                            "id": str(record.get("id", vuln_id)),
                            "package_name": str(pkg["package"]["name"]),
                            "ecosystem": str(pkg["package"]["ecosystem"]),
                            "version": str(pkg["version"]),
                            "severity": sev,
                            "source_severity": source_severity,
                            "severity_source": severity_source,
                            "cvss_score": cvss,
                            "cvss_vector": cvss_vector,
                            "cvss_version": cvss_version,
                            "summary": record.get("summary", record.get("id", vuln_id)),
                            "details": str(record.get("details", ""))[:800],
                            "fixed_version": fixed_version,
                            "fixed_versions": fixed_versions,
                            "advisory_type": advisory_type,
                            "aliases": aliases,
                            "file": package_file(pkg),
                            "is_dev": _coerce_bool(pkg.get("is_dev", False), False),
                            "children": pkg.get("children", []),
                            "bom_ref": str(pkg.get("bom_ref", "")),
                            "purl": str(pkg.get("purl", "")),
                            "sbom_format": str(pkg.get("sbom_format", "")),
                            "sbom_spec_version": str(pkg.get("sbom_spec_version", "")),
                        }
                    )

        self.last_scan_stats = stats
        if context is not None:
            context.metadata.setdefault("scanners", {})[self.name] = {
                **context.metadata.get("scanners", {}).get(self.name, {}),
                **stats,
            }
        return vulnerabilities

    @staticmethod
    async def _sleep(seconds: float) -> None:
        await asyncio.sleep(seconds)

    @staticmethod
    def _score_cvss_vector(vector: str, metric_type: str = "") -> tuple[float | None, str, str]:
        """Return ``(score, severity, normalized_version)`` for a CVSS vector.
        OSV's ``severity[].score`` field normally contains the complete CVSS
        vector, not the numeric score.  The CVSS version prefix (for example
        ``4.0`` in ``CVSS:4.0/...``) is never itself a vulnerability score.
        CVSS3/CVSS4 are used here so the result follows the published CVSS
        calculation rather than a regex approximation.
        """
        vector = vector.strip()
        if not vector:
            return None, "UNKNOWN", ""
        try:
            if vector.startswith("CVSS:4.0/"):
                calculator = CVSS4(vector)
                score = float(calculator.scores()[0])
                severity = str(calculator.severities()[0]).upper()
                return score, severity, "4.0"
            if vector.startswith(("CVSS:3.1/", "CVSS:3.0/")):
                calculator = CVSS3(vector)
                score = float(calculator.scores()[0])
                severity = str(calculator.severities()[0]).upper()
                return score, severity, vector.split("/", 1)[0].split(":", 1)[1]
            # Some producers omit the CVSS prefix.  Reconstruct it from the
            # OSV type when the metric payload is otherwise valid.
            if vector.startswith("AV:") and metric_type == "CVSS_V4":
                calculator = CVSS4("CVSS:4.0/" + vector)
                score = float(calculator.scores()[0])
                severity = str(calculator.severities()[0]).upper()
                return score, severity, "4.0"
            if vector.startswith("AV:") and metric_type == "CVSS_V3":
                calculator = CVSS3("CVSS:3.1/" + vector)
                score = float(calculator.scores()[0])
                severity = str(calculator.severities()[0]).upper()
                return score, severity, "3.1"
        except Exception as exc:
            logger.debug("Failed to calculate CVSS vector %r: %s", vector, exc)
        return None, "UNKNOWN", ""

    @staticmethod
    def _extract_severity(
        vuln: dict[str, Any],
    ) -> tuple[str, float | None, str, str, str, str]:
        """Extract authoritative CVSS/database severity from an OSV record.
        Returns ``(severity, score, vector, cvss_version, source_severity,
        severity_source)``.  Vector strings are calculated with the CVSS
        reference-compatible Python implementation; the ``3.1``/``4.0``
        prefix is never mistaken for the score.
        """
        best_score: float | None = None
        best_severity = "UNKNOWN"
        best_vector = ""
        best_version = ""
        best_source = "none"
        severity_items = vuln.get("severity", [])
        if isinstance(severity_items, list):
            for item in severity_items:
                if not isinstance(item, dict):
                    continue
                raw_score = item.get("score")
                metric_type = str(item.get("type", ""))
                numeric_score: float | None = None
                vector_value = ""
                if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
                    value = float(raw_score)
                    if 0.0 <= value <= 10.0:
                        numeric_score = value
                elif isinstance(raw_score, str):
                    stripped = raw_score.strip()
                    if re.fullmatch(r"(?:10(?:\.0+)?|[0-9](?:\.[0-9]+)?)", stripped):
                        try:
                            value = float(stripped)
                            if 0.0 <= value <= 10.0:
                                numeric_score = value
                        except ValueError:
                            numeric_score = None
                    elif stripped.startswith(("CVSS:", "AV:")):
                        vector_value = stripped
                if vector_value:
                    calculated_score, calculated_severity, calculated_version = (
                        SBOMScanner._score_cvss_vector(vector_value, metric_type)
                    )
                    if calculated_score is not None:
                        numeric_score = calculated_score
                        if calculated_score > (best_score if best_score is not None else -1.0):
                            best_score = calculated_score
                            best_severity = calculated_severity
                            best_vector = vector_value
                            best_version = calculated_version
                            best_source = metric_type or "CVSS"
                        continue
                if numeric_score is not None and numeric_score > (
                    best_score if best_score is not None else -1.0
                ):
                    best_score = numeric_score
                    best_severity = SBOMScanner._cvss_severity(numeric_score)
                    best_vector = ""
                    best_version = ""
                    best_source = metric_type or "CVSS_SCORE"
        # OSV database-specific severity is useful when a record has no CVSS
        # vector.  It must never override a stronger calculated CVSS result.
        db_specific = vuln.get("database_specific", {})
        db_severity = ""
        if isinstance(db_specific, dict):
            db_severity = str(db_specific.get("severity", "")).strip().upper()
            if db_severity == "MODERATE":
                db_severity = "MEDIUM"
        if best_score is None and db_severity in {
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW",
            "INFO",
            "NONE",
        }:
            best_severity = db_severity
            best_source = "database_specific"
        source_severity = best_severity if best_severity != "UNKNOWN" else "UNKNOWN"
        return (
            best_severity,
            best_score,
            best_vector,
            best_version,
            source_severity,
            best_source,
        )

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {
            "NONE": 0,
            "INFO": 0,
            "UNKNOWN": -1,
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
        }.get(str(severity).upper(), -1)

    @staticmethod
    def _cvss_severity(score: float) -> str:
        if score <= 0.0:
            return "NONE"
        if score <= 3.9:
            return "LOW"
        if score <= 6.9:
            return "MEDIUM"
        if score <= 8.9:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def _extract_advisory_type(vuln: dict[str, Any]) -> str:
        """Classify informational RustSec/OSV advisories without inventing risk."""
        db_specific = vuln.get("database_specific", {})
        informational = ""
        if isinstance(db_specific, dict):
            informational = str(db_specific.get("informational", "")).strip().lower()
        if informational in {"unmaintained", "unsound", "malicious", "withdrawn", "yanked"}:
            return informational
        advisory_id = str(vuln.get("id", "")).upper()
        summary = str(vuln.get("summary", "")).lower()
        if advisory_id.startswith("RUSTSEC-"):
            if "unmaintained" in summary:
                return "unmaintained"
            if "unsound" in summary:
                return "unsound"
        return "vulnerability"

    @staticmethod
    def _version_parts(
        version: str,
    ) -> tuple[int, int, int, tuple[int, tuple[tuple[int, tuple[int, ...]], ...]]] | None:
        """Return a SemVer precedence key whose comparable values are integers only.

        The previous representation mixed integers and strings inside nested tuples.
        Python's tuple ordering can then raise ``TypeError`` on malformed or unusual
        prerelease structures. Encoding non-numeric identifiers as Unicode codepoint
        tuples keeps every comparison homogeneous and deterministic.
        """
        value = str(version).strip().removeprefix("v")
        if value == "0":
            return (0, 0, 0, (0, ()))

        match = re.fullmatch(
            r"(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?",
            value,
        )
        if not match:
            return None

        major, minor, patch = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3) or 0),
        )
        prerelease = match.group(4)
        if prerelease is None:
            # Stable releases sort after prereleases.
            return (major, minor, patch, (1, ()))

        encoded: list[tuple[int, tuple[int, ...]]] = []
        for part in prerelease.split("."):
            if not part:
                return None
            if part.isdigit():
                # SemVer numeric identifiers must not contain leading zeroes.
                if len(part) > 1 and part.startswith("0"):
                    return None
                encoded.append((0, (int(part),)))
            else:
                encoded.append((1, tuple(ord(char) for char in part)))
        return (major, minor, patch, (0, tuple(encoded)))

    @staticmethod
    def _compare_versions(a: str, b: str, range_type: str, ecosystem: str) -> int | None:
        if a == b:
            return 0
        if a == "0":
            return -1 if b != "0" else 0
        if b == "0":
            return 1
        semver_ecosystems = {"npm", "crates.io", "cargo", "Go"}
        if range_type.upper() == "SEMVER" or ecosystem in semver_ecosystems:
            pa = SBOMScanner._version_parts(a)
            pb = SBOMScanner._version_parts(b)
            if pa is not None and pb is not None:
                return -1 if pa < pb else 1
        try:
            va = Version(str(a).lstrip("v"))
            vb = Version(str(b).lstrip("v"))
            return -1 if va < vb else 1
        except InvalidVersion:
            return None

    @classmethod
    def _in_version_interval(
        cls,
        target: str,
        introduced: str | None,
        fixed: str | None,
        last_affected: str | None,
        limit: str | None,
        range_type: str,
        ecosystem: str,
    ) -> bool:
        if introduced is not None:
            cmp_intro = cls._compare_versions(target, introduced, range_type, ecosystem)
            if cmp_intro is None or cmp_intro < 0:
                return False
        if fixed is not None:
            cmp_fixed = cls._compare_versions(target, fixed, range_type, ecosystem)
            return cmp_fixed is not None and cmp_fixed < 0
        if last_affected is not None:
            cmp_last = cls._compare_versions(target, last_affected, range_type, ecosystem)
            return cmp_last is not None and cmp_last <= 0
        if limit is not None and limit != "*":
            cmp_limit = cls._compare_versions(target, limit, range_type, ecosystem)
            return cmp_limit is not None and cmp_limit < 0
        return True

    @classmethod
    def _extract_fixed_version(
        cls,
        vuln: dict[str, Any],
        installed_version: str,
        ecosystem: str,
    ) -> tuple[str, list[str]]:
        """Select the fix that belongs to the affected branch containing the installed version."""
        candidates: list[str] = []
        all_fixed: list[str] = []
        for affected in vuln.get("affected", []):
            for rng in affected.get("ranges", []):
                if not isinstance(rng, dict):
                    continue
                range_type = str(rng.get("type", "")).upper()
                events = rng.get("events", [])
                if not isinstance(events, list):
                    continue
                introduced: str | None = None
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    if "introduced" in event:
                        introduced = str(event["introduced"])
                        continue
                    if "fixed" in event:
                        fixed = str(event["fixed"])
                        all_fixed.append(fixed)
                        if cls._in_version_interval(
                            installed_version,
                            introduced,
                            fixed,
                            None,
                            None,
                            range_type,
                            ecosystem,
                        ):
                            candidates.append(fixed)
                        introduced = None
                        continue
                    if "last_affected" in event:
                        last = str(event["last_affected"])
                        if cls._in_version_interval(
                            installed_version,
                            introduced,
                            None,
                            last,
                            None,
                            range_type,
                            ecosystem,
                        ):
                            # Explicitly vulnerable but no known fixed version.
                            pass
                        introduced = None
                        continue
                    if "limit" in event:
                        limit = str(event["limit"])
                        if cls._in_version_interval(
                            installed_version,
                            introduced,
                            None,
                            None,
                            limit,
                            range_type,
                            ecosystem,
                        ):
                            pass
                        introduced = None
        # Preserve unique fixed versions in metadata even when the branch cannot
        # be compared safely. Never invent a branch-specific fix.
        unique_all = sorted(set(all_fixed))
        if not candidates:
            return "", unique_all
        # Prefer the smallest applicable fixed version strictly above the
        # installed version. If versions cannot be safely compared, retain the
        # first candidate only when it is the sole applicable candidate.
        comparable: list[str] = []
        for candidate in candidates:
            cmp_value = cls._compare_versions(installed_version, candidate, "SEMVER", ecosystem)
            if cmp_value is not None and cmp_value < 0:
                comparable.append(candidate)
        if comparable:
            comparable.sort(key=lambda value: cls._version_sort_key(value, ecosystem))
            return comparable[0], unique_all
        if len(set(candidates)) == 1:
            return candidates[0], unique_all
        return "", unique_all

    @staticmethod
    def _version_sort_key(version: str, ecosystem: str) -> Any:
        semver_ecosystems = {"npm", "crates.io", "cargo", "Go"}
        if ecosystem in semver_ecosystems:
            parsed = SBOMScanner._version_parts(version)
            if parsed is not None:
                return (0, parsed)
        try:
            return (1, Version(str(version).lstrip("v")))
        except InvalidVersion:
            return (2, str(version))

    def parse_npm_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            lockfile_version = data.get("lockfileVersion", 1)
            if lockfile_version >= 2:
                packages = data.get("packages", {})
                for pkg_path, info in packages.items():
                    if pkg_path == "":
                        continue
                    name = info.get("name", pkg_path.split("node_modules/")[-1]).lower()
                    version = info.get("version", "latest")
                    is_dev = info.get("dev", False)
                    deps.append(
                        {"name": name, "version": version, "is_dev": is_dev, "transitive": True}
                    )
            if not deps:

                def _walk_v1(node: dict[str, Any], is_dev: bool = False) -> None:
                    for name, info in node.items():
                        ver = info.get("version", "latest")
                        child_dev = info.get("dev", False) or is_dev
                        deps.append(
                            {
                                "name": name.lower(),
                                "version": ver,
                                "is_dev": child_dev,
                                "transitive": True,
                            }
                        )
                        children = info.get("dependencies", {})
                        if children:
                            _walk_v1(children, child_dev)

                v1_deps = data.get("dependencies", {})
                _walk_v1(v1_deps)
        except Exception as e:
            logger.debug("Failed to parse package-lock.json: %s", e)
        return deps

    def parse_pyproject_toml(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = _toml_loads(file_path.read_text(encoding="utf-8"))
            for dep in data.get("project", {}).get("dependencies", []):
                match = re.match(r"^([a-zA-Z0-9_-]+)", dep)
                if match:
                    deps.append(
                        {"name": match.group(1).lower(), "version": "latest", "is_dev": False}
                    )
            poetry = data.get("tool", {}).get("poetry", {})
            for name in poetry.get("dependencies", {}):
                if name.lower() != "python":
                    deps.append({"name": name.lower(), "version": "latest", "is_dev": False})
            for name in poetry.get("dev-dependencies", {}):
                deps.append({"name": name.lower(), "version": "latest", "is_dev": True})
        except Exception as e:
            logger.debug("Failed to parse pyproject.toml: %s", e)
        return deps

    def parse_requirements_txt(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        is_dev = "dev" in file_path.name.lower()
        for raw_line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                match = re.match(
                    r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*==\s*([0-9A-Za-z][0-9A-Za-z.+-]*)",
                    line,
                )
                if match:
                    deps.append(
                        {
                            "name": match.group(1).lower(),
                            "version": match.group(2),
                            "is_dev": is_dev,
                        }
                    )
                else:
                    match = re.match(r"^([a-zA-Z0-9_.-]+)", line)
                    if match:
                        deps.append(
                            {
                                "name": match.group(1).lower(),
                                "version": "latest",
                                "is_dev": is_dev,
                            }
                        )
        return deps

    def parse_pipfile_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            for section, is_dev in (("default", False), ("develop", True)):
                for name, info in data.get(section, {}).items():
                    ver = info.get("version", "latest").removeprefix("==")
                    deps.append({"name": name.lower(), "version": ver, "is_dev": is_dev})
        except Exception as e:
            logger.debug("Failed to parse Pipfile.lock: %s", e)
        return deps

    def parse_package_json(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))

            def _npm_version(value: Any) -> str:
                raw = str(value).strip()
                match = re.search(r"(?<!\d)(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)", raw)
                return match.group(1) if match else "latest"

            for pkg, ver in data.get("dependencies", {}).items():
                deps.append(
                    {"name": str(pkg).lower(), "version": _npm_version(ver), "is_dev": False}
                )
            for pkg, ver in data.get("devDependencies", {}).items():
                deps.append(
                    {"name": str(pkg).lower(), "version": _npm_version(ver), "is_dev": True}
                )
        except Exception as e:
            logger.debug("Failed to parse package.json: %s", e)
        return deps

    def parse_yarn_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(
            r'^"?([^"\n]+)"?:\s*[\s\S]*?^\s*version\s+"([^"]+)"', content, re.MULTILINE
        ):
            name = match.group(1).split("@")[0].strip().lower()
            version = match.group(2)
            deps.append({"name": name, "version": version, "is_dev": False, "transitive": True})
        return deps

    def parse_pnpm_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            import yaml

            data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
            packages = data.get("packages", {})
            if not isinstance(packages, dict):
                return deps
            for spec, info in packages.items():
                if not isinstance(info, dict):
                    continue
                raw_spec = str(spec).lstrip("/")
                version = str(info.get("version", "")).strip()
                # pnpm v6/v7/v8 keys can look like:
                #   foo@1.2.3
                #   @scope/foo@1.2.3
                #   foo@1.2.3(peer@...)
                name = raw_spec
                split_at = raw_spec.find("@", 1) if raw_spec.startswith("@") else raw_spec.find("@")
                if split_at > 0:
                    name = raw_spec[:split_at]
                if not version:
                    suffix = raw_spec[split_at + 1 :] if split_at > 0 else ""
                    version_match = re.match(r"(\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?)", suffix)
                    version = version_match.group(1) if version_match else "latest"
                if name:
                    deps.append(
                        {
                            "name": name.lower(),
                            "version": version,
                            "is_dev": False,
                            "transitive": True,
                        }
                    )
        except Exception as e:
            logger.debug("Failed to parse pnpm-lock.yaml: %s", e)
        return deps

    def parse_poetry_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = _toml_loads(file_path.read_text(encoding="utf-8"))
            for pkg in data.get("package", []):
                name = pkg.get("name", "").lower()
                version = pkg.get("version", "latest")
                is_dev = pkg.get("category", "") == "dev"
                deps.append({"name": name, "version": version, "is_dev": is_dev})
        except Exception as e:
            logger.debug("Failed to parse poetry.lock: %s", e)
        return deps

    def parse_go_mod(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        in_require = False
        for raw_line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if line.startswith("require ("):
                in_require = True
                continue
            if in_require and line == ")":
                in_require = False
                continue
            if in_require or line.startswith("require "):
                parts = line.replace("require ", "").split()
                if len(parts) >= 2:
                    deps.append(
                        {
                            "name": parts[0].lower(),
                            "version": parts[1].lstrip("v"),
                            "is_dev": False,
                        }
                    )
        return deps

    def parse_go_sum(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        for line in file_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) >= 2 and not parts[1].startswith("go.mod") and "/go.mod" not in parts[1]:
                deps.append(
                    {
                        "name": parts[0].lower(),
                        "version": parts[1].lstrip("v"),
                        "is_dev": False,
                        "transitive": True,
                    }
                )
        return deps

    def parse_pom_xml(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            import defusedxml.ElementTree as ET  # noqa: N817

            root = ET.fromstring(file_path.read_text(encoding="utf-8"))
            ns = {"m": "http://maven.apache.org/POM/4.0.0"}

            def _find(parent: Any, local_name: str) -> Any:
                node = parent.find(f"m:{local_name}", ns)
                if node is None:
                    node = parent.find(local_name)
                return node

            for dep in root.findall(".//m:dependency", ns) or root.findall(".//dependency"):
                group = _find(dep, "groupId")
                artifact = _find(dep, "artifactId")
                version = _find(dep, "version")
                if group is None or artifact is None:
                    continue
                group_text = (group.text or "").strip()
                artifact_text = (artifact.text or "").strip()
                if not group_text or not artifact_text:
                    continue
                name = f"{group_text}:{artifact_text}".lower()
                ver = (version.text or "").strip() if version is not None else "latest"
                deps.append({"name": name, "version": ver or "latest", "is_dev": False})
        except Exception as e:
            logger.debug("Failed to parse pom.xml: %s", e)
        return deps

    def parse_gradle(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(
            r"""(?:implementation|compile|api|testImplementation|androidTestImplementation)\s*['"]([^'"]+)['"]""",
            content,
        ):
            spec = match.group(1)
            parts = spec.split(":")
            if len(parts) >= 2:
                name = f"{parts[0]}:{parts[1]}".lower()
                ver = parts[2] if len(parts) >= 3 else "latest"
                is_dev = "test" in match.group(0).lower() or "androidTest" in match.group(0)
                deps.append({"name": name, "version": ver, "is_dev": is_dev})
        return deps

    def parse_gradle_kts(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(
            r"""(?:implementation|compile|api|testImplementation|androidTestImplementation)\s*\(\s*['"]([^'"]+)['"]\s*\)""",
            content,
        ):
            spec = match.group(1)
            parts = spec.split(":")
            if len(parts) >= 2:
                name = f"{parts[0]}:{parts[1]}".lower()
                ver = parts[2] if len(parts) >= 3 else "latest"
                is_dev = "test" in match.group(0).lower() or "androidTest" in match.group(0)
                deps.append({"name": name, "version": ver, "is_dev": is_dev})
        return deps

    def parse_cargo_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = _toml_loads(file_path.read_text(encoding="utf-8"))
            for pkg in data.get("package", []):
                name = pkg.get("name", "").lower()
                version = pkg.get("version", "latest")
                deps.append({"name": name, "version": version, "is_dev": False, "transitive": True})
        except Exception as e:
            logger.debug("Failed to parse Cargo.lock: %s", e)
        return deps

    def parse_gemfile_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        in_specs = False
        for line in content.splitlines():
            if line.strip() == "GEM":
                in_specs = True
                continue
            if in_specs and line.strip() == "specs:":
                continue
            if in_specs and line.strip() == "":
                in_specs = False
                continue
            if in_specs:
                match = re.match(r"^\s+([a-zA-Z0-9_-]+)\s*\(([^)]+)\)", line)
                if match:
                    deps.append(
                        {
                            "name": match.group(1).lower(),
                            "version": match.group(2),
                            "is_dev": False,
                            "transitive": True,
                        }
                    )
        return deps

    def parse_composer_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            for section, is_dev in (("packages", False), ("packages-dev", True)):
                for pkg in data.get(section, []):
                    name = pkg.get("name", "").lower()
                    version = pkg.get("version", "latest").lstrip("v")
                    deps.append(
                        {"name": name, "version": version, "is_dev": is_dev, "transitive": True}
                    )
        except Exception as e:
            logger.debug("Failed to parse composer.lock: %s", e)
        return deps

    def parse_pubspec_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            import yaml

            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            for name, info in data.get("packages", {}).items():
                version = info.get("version", "latest")
                deps.append(
                    {"name": name.lower(), "version": version, "is_dev": False, "transitive": True}
                )
        except Exception as e:
            logger.debug("Failed to parse pubspec.lock: %s", e)
        return deps

    def parse_packages_lock_json(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            for dep in data.get("dependencies", {}).values():
                name = dep.get("id", "").lower() or dep.get("resolved", "").lower()
                version = dep.get("resolved", "latest").split("/")[-1].replace(".nupkg", "")
                if name:
                    deps.append(
                        {"name": name, "version": version, "is_dev": False, "transitive": True}
                    )
        except Exception as e:
            logger.debug("Failed to parse packages.lock.json: %s", e)
        return deps

    def parse_uv_lock(self, file_path: Path) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        try:
            data = _toml_loads(file_path.read_text(encoding="utf-8"))
            for pkg in data.get("package", []):
                source = pkg.get("source", {})
                if isinstance(source, dict) and ("editable" in source or "virtual" in source):
                    continue  # skip the project itself
                name = str(pkg.get("name", "")).lower()
                ver = pkg.get("version")
                if name and ver:
                    deps.append(
                        {"name": name, "version": str(ver), "is_dev": False, "transitive": True}
                    )
        except Exception as e:
            logger.debug("Failed to parse uv.lock: %s", e)
        return deps

    def parse_cyclonedx_json(self, file_path: Path) -> list[dict[str, Any]]:
        """Parse CycloneDX JSON components into Seraph dependency identities.

        Standard component ``name``/``version`` fields are preferred. A PURL
        supplies missing identity fields and the recognized PURL ecosystem is
        passed into the existing OSV query pipeline.
        """
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            message = f"invalid CycloneDX JSON: {exc}"
            raise ValueError(message) from exc

        if not isinstance(data, dict):
            message = "CycloneDX document root must be an object"
            raise TypeError(message)

        if str(data.get("bomFormat", "")).strip().lower() != "cyclonedx":
            return []

        spec_version = str(data.get("specVersion", "")).strip()
        if not spec_version:
            message = "CycloneDX specVersion is missing"
            raise ValueError(message)

        components = data.get("components", [])
        if components is None:
            return []
        if not isinstance(components, list):
            message = "CycloneDX components must be a list"
            raise TypeError(message)

        parsed: list[dict[str, Any]] = []
        identity_map: dict[str, dict[str, Any]] = {}

        for component in components:
            if not isinstance(component, dict):
                continue

            component_type = str(component.get("type", "")).strip().lower()
            if component_type and component_type not in {
                "library",
                "framework",
                "application",
            }:
                continue

            purl = str(component.get("purl", "")).strip()
            purl_info = _parse_cyclonedx_purl(purl) if purl else None

            raw_name = str(component.get("name", "")).strip()
            raw_version = str(component.get("version", "")).strip()
            group = str(component.get("group", "")).strip()

            ecosystem = purl_info.get("ecosystem", "") if purl_info else ""
            name = purl_info.get("name", "") if purl_info else ""
            version = purl_info.get("version", "") if purl_info else ""

            if not name:
                if ecosystem == "Maven" and group and raw_name:
                    name = f"{group}:{raw_name}"
                else:
                    name = raw_name
            if not version:
                version = raw_version

            if str(component.get("scope", "")).strip().lower() == "excluded":
                continue

            if not name or not version or not ecosystem:
                # The scan's existing dependency-skipping accounting reports
                # unsupported/unresolved components as partial coverage.
                continue

            dependency: dict[str, Any] = {
                "name": name,
                "version": version,
                "ecosystem": ecosystem,
                "is_dev": _cyclonedx_bool_property(
                    component,
                    {
                        "cdx:dev",
                        "seraph:dev",
                        "is_dev",
                        "development",
                        "dev_dependency",
                    },
                ),
                "transitive": False,
                "children": [],
                "bom_ref": str(component.get("bom-ref", "")).strip(),
                "purl": purl,
                "sbom_format": "CycloneDX",
                "sbom_spec_version": spec_version,
            }
            parsed.append(dependency)

            for identity in (
                dependency["bom_ref"],
                dependency["purl"],
                f"{dependency['name']}@{dependency['version']}",
            ):
                if identity:
                    identity_map[identity] = dependency

        # Project CycloneDX dependency relationships into Seraph's existing
        # package graph so blast-radius scoring remains meaningful.
        relationships = data.get("dependencies", [])
        if isinstance(relationships, list):
            for relationship in relationships:
                if not isinstance(relationship, dict):
                    continue
                parent = identity_map.get(str(relationship.get("ref", "")).strip())
                if parent is None:
                    continue

                depends_on = relationship.get("dependsOn", [])
                if not isinstance(depends_on, list):
                    continue

                children: list[str] = []
                for child_raw in depends_on:
                    child = identity_map.get(str(child_raw).strip())
                    if child is None:
                        continue
                    child_name = str(child.get("name", "")).strip()
                    if child_name and child_name != parent.get("name"):
                        children.append(child_name)
                    child["transitive"] = True

                parent["children"] = sorted(set(children))

        logger.debug(
            "CycloneDX parser: %s -> %d queryable components (spec %s)",
            file_path,
            len(parsed),
            spec_version,
        )
        return parsed

    def parse_generic(self, file_path: Path) -> list[dict[str, Any]]:
        logger.debug("Using generic fallback for %s", file_path.name)
        return []

    def _deduplicate_and_rank(
        self, raw_findings: list[dict[str, Any]], repo_root: str
    ) -> list[dict[str, Any]]:
        dedup: dict[str, dict[str, Any]] = {}
        for finding in raw_findings:
            pkg_name = finding.get("package", "").lower()
            cve = finding.get("cve_id", "UNKNOWN")
            version = finding.get("version", "")
            severity = finding.get("severity", "MEDIUM").upper()
            file_path = finding.get("file", "")
            is_dev = finding.get("is_dev", False)
            raw_cvss = finding.get("cvss_score")
            cvss = (
                float(raw_cvss)
                if isinstance(raw_cvss, (int, float)) and not isinstance(raw_cvss, bool)
                else 0.0
            )
            dedup_key = f"{cve}::{pkg_name}@{version}"
            if dedup_key not in dedup:
                dedup[dedup_key] = {
                    **finding,
                    "_manifests": set(),
                    "is_dev_dependency": is_dev,
                    "max_cvss": cvss if cvss > 0.0 else None,
                }
            entry = dedup[dedup_key]
            entry["_manifests"].add(file_path)
            if cvss > 0.0:
                current_cvss = entry.get("max_cvss")
                if not isinstance(current_cvss, (int, float)) or cvss > float(current_cvss):
                    entry["max_cvss"] = cvss
            entry["is_dev_dependency"] = bool(entry.get("is_dev_dependency", False) and is_dev)
            severity_rank = {
                "CRITICAL": 4,
                "HIGH": 3,
                "MEDIUM": 2,
                "LOW": 1,
                "INFO": 0,
                "UNKNOWN": -1,
            }
            current_max = severity_rank.get(entry.get("severity", "UNKNOWN"), -1)
            new_sev = severity_rank.get(severity, -1)
            if new_sev > current_max:
                entry["severity"] = severity
        results: list[dict[str, Any]] = []
        for entry in dedup.values():
            manifests = sorted(entry.pop("_manifests"))
            primary_manifest = manifests[0]
            for m in manifests:
                if m.endswith(
                    (
                        "package.json",
                        "go.mod",
                        "requirements.txt",
                        "pyproject.toml",
                        "Pipfile",
                        "uv.lock",
                    )
                ):
                    primary_manifest = m
                    break
            entry["file"] = primary_manifest
            entry["affected_manifests"] = manifests
            entry["manifest_count"] = len(manifests)
            entry["cvss_score"] = entry.pop("max_cvss", None)
            # v2.0.1 FIX: Do NOT downgrade severity for dev dependencies.
            # Instead, flag them so suppression engine can decide.
            # Severity should reflect actual risk; dev flag handles context.
            results.append(entry)

        def sort_key(f: dict[str, Any]) -> tuple[int, int, float]:
            sev_rank = {
                "CRITICAL": 4,
                "HIGH": 3,
                "MEDIUM": 2,
                "LOW": 1,
                "INFO": 0,
                "UNKNOWN": -1,
            }
            is_prod = 0 if f.get("is_dev_dependency") else 1
            raw_cvss = f.get("cvss_score")
            sort_cvss = (
                float(raw_cvss)
                if isinstance(raw_cvss, (int, float)) and not isinstance(raw_cvss, bool)
                else 0.0
            )
            return (is_prod, sev_rank.get(f.get("severity", "UNKNOWN"), -1), sort_cvss)

        results.sort(key=sort_key, reverse=True)
        return results

    @staticmethod
    def _map_severity(severity_str: str, cvss_score: float | None) -> Severity:
        if cvss_score is not None:
            if cvss_score >= 9.0:
                return Severity.CRITICAL
            if cvss_score >= 7.0:
                return Severity.HIGH
            if cvss_score >= 4.0:
                return Severity.MEDIUM
        mapping = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "unknown": Severity.INFO,
            "info": Severity.INFO,
        }
        return mapping.get(severity_str.lower(), Severity.MEDIUM)
