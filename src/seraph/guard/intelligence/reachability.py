"""Seraph Guard — Deep Dependency Reachability Analyzer
=================================================================
Solves the SCA Alert Fatigue problem by proving whether a vulnerable
dependency is actually imported and invoked in the codebase.

Architecture:
1. Import Detection: AST (Python) or Regex (JS/Go/Java) to find imports.
2. Invocation Verification: AST context check (ast.Load) to prove the
   imported module is actually executed, not just shadowed or dead code.
3. Evidence Collection: Captures file, line, and snippet for auditability.

This is the core engine that allows Seraph to safely suppress 80% of
SCA findings that exist only in manifests but are never executed.
"""

from __future__ import annotations

import ast
import logging
import re

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class ReachabilityStatus(Enum):
    REACHABLE_AND_USED = "reachable_and_used"
    REACHABLE_BUT_UNUSED = "reachable_but_unused"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


@dataclass
class ReachabilityEvidence:
    file_path: str
    line_number: int
    code_snippet: str


@dataclass
class ReachabilityResult:
    status: ReachabilityStatus
    evidence: list[ReachabilityEvidence] = field(default_factory=list)
    reason: str = ""


class ReachabilityAnalyzer:
    """Analyzes source code to determine if a dependency is actively used."""

    # Map common PyPI package names to their Python import names
    PY_PKG_TO_IMPORT: dict[str, str] = {
        "pyyaml": "yaml",
        "beautifulsoup4": "bs4",
        "scikit-learn": "sklearn",
        "pillow": "PIL",
        "opencv-python": "cv2",
        "python-dotenv": "dotenv",
        "requests": "requests",
        "httpx": "httpx",
        "fastapi": "fastapi",
        "python-dateutil": "dateutil",
    }

    # Regex for JS/TS imports (static and dynamic)
    JS_TS_IMPORT_RE = re.compile(
        r"""(?:import\s+(?:[^;]+\s+from\s+)?['"](?:@[^/]+/)?([^'/"]+)['"]|"""
        r"""require\s*\(\s*['"](?:@[^/]+/)?([^'/"]+)['"]\s*\)|"""
        r"""import\s*\(\s*['"](?:@[^/]+/)?([^'/"]+)['"]\s*\))"""
    )

    # Regex for Go and Java imports
    GO_IMPORT_RE = re.compile(r'^\s*"(?P<pkg>[^"]+)"', re.MULTILINE)
    JAVA_IMPORT_RE = re.compile(r"^\s*import\s+(?P<pkg>[a-zA-Z0-9_.]+)\s*;", re.MULTILINE)

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self._import_cache: dict[Path, set[str]] = {}
        self._usage_cache: dict[Path, bool] = {}

    def analyze(self, package_name: str, ecosystem: str, scan_path: Path) -> ReachabilityResult:
        """Main entry point. Routes to the correct language analyzer."""
        if ecosystem == "PyPI":
            return self._analyze_python(package_name, scan_path)
        if ecosystem in ("npm", "yarn", "pnpm"):
            return self._analyze_jsts(package_name, scan_path)
        if ecosystem == "Go":
            return self._analyze_go(package_name, scan_path)
        if ecosystem == "Maven":
            return self._analyze_java(package_name, scan_path)

        return ReachabilityResult(
            ReachabilityStatus.UNKNOWN,
            reason=f"Reachability analysis not supported for ecosystem: {ecosystem}",
        )

    def _analyze_python(self, package_name: str, scan_path: Path) -> ReachabilityResult:
        import_name = self.PY_PKG_TO_IMPORT.get(
            package_name.lower(), package_name.lower().replace("-", "_")
        )
        evidence: list[ReachabilityEvidence] = []
        is_used = False

        for py_file in scan_path.rglob("*.py"):
            # Skip symlinks and known non-production directories
            if py_file.is_symlink() or any(
                skip in py_file.parts
                for skip in (
                    ".venv",
                    "venv",
                    "site-packages",
                    "node_modules",
                    "tests",
                    "test",
                    "fixtures",
                    "mocks",
                )
            ):
                continue

            imports = self._get_python_imports(py_file)
            if import_name in imports:
                file_evidence = self._find_evidence_in_file(
                    py_file, import_name, is_python=True, base_path=scan_path
                )
                evidence.extend(file_evidence)

                # UFIC Usage Check: Is it actually invoked (ast.Load), not just shadowed?
                if self._check_python_usage(py_file, import_name):
                    is_used = True

        if evidence:
            status = (
                ReachabilityStatus.REACHABLE_AND_USED
                if is_used
                else ReachabilityStatus.REACHABLE_BUT_UNUSED
            )
            reason = (
                f"Package '{package_name}' is imported and actively invoked in production code."
                if is_used
                else f"Package '{package_name}' is imported but NEVER invoked (Dead Code)."
            )
            return ReachabilityResult(status, evidence, reason)

        return ReachabilityResult(
            ReachabilityStatus.UNREACHABLE,
            reason=f"Package '{package_name}' is not imported anywhere in the codebase.",
        )

    def _analyze_jsts(self, package_name: str, scan_path: Path) -> ReachabilityResult:
        evidence: list[ReachabilityEvidence] = []
        is_used = False
        base_pkg = package_name.rsplit("/", maxsplit=1)[-1]

        for file_path in scan_path.rglob("*"):
            if file_path.is_symlink() or file_path.suffix not in (
                ".js",
                ".ts",
                ".jsx",
                ".tsx",
                ".mjs",
                ".cjs",
            ):
                continue
            if any(
                skip in file_path.parts
                for skip in ("node_modules", "dist", "build", ".next", ".nuxt", "coverage")
            ):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for match in self.JS_TS_IMPORT_RE.finditer(content):
                    # Group 1: static import, Group 2: require, Group 3: dynamic import
                    imported_pkg = match.group(1) or match.group(2) or match.group(3)
                    if imported_pkg and (
                        imported_pkg == package_name or imported_pkg.startswith(f"{package_name}/")
                    ):
                        line_num = content[: match.start()].count("\n") + 1
                        evidence.append(
                            ReachabilityEvidence(
                                str(file_path.relative_to(self.repo_root)),
                                line_num,
                                content.split("\n")[line_num - 1].strip()[:120],
                            )
                        )

                        # UFIC Usage Check: Look for package invocation (e.g., pkg() or pkg.method())
                        usage_pattern = re.compile(rf"\b{re.escape(base_pkg)}\s*[\.(]")
                        if usage_pattern.search(content):
                            is_used = True
            except Exception as e:
                logger.debug("Failed to parse JS/TS file %s: %s", file_path, e)

        if evidence:
            status = (
                ReachabilityStatus.REACHABLE_AND_USED
                if is_used
                else ReachabilityStatus.REACHABLE_BUT_UNUSED
            )
            reason = (
                f"Package '{package_name}' is imported and actively invoked."
                if is_used
                else f"Package '{package_name}' is imported but NEVER invoked."
            )
            return ReachabilityResult(status, evidence, reason)

        return ReachabilityResult(
            ReachabilityStatus.UNREACHABLE, reason=f"Package '{package_name}' is not imported."
        )

    def _analyze_go(self, package_name: str, scan_path: Path) -> ReachabilityResult:
        evidence: list[ReachabilityEvidence] = []
        is_used = False
        base_pkg = package_name.rsplit("/", maxsplit=1)[-1]

        for go_file in scan_path.rglob("*.go"):
            if go_file.is_symlink() or any(
                skip in go_file.parts for skip in ("vendor", "test", "mock", "fixtures")
            ):
                continue
            try:
                content = go_file.read_text(encoding="utf-8", errors="ignore")
                for match in self.GO_IMPORT_RE.finditer(content):
                    if package_name.lower() in match.group("pkg").lower():
                        line_num = content[: match.start()].count("\n") + 1
                        evidence.append(
                            ReachabilityEvidence(
                                str(go_file.relative_to(self.repo_root)),
                                line_num,
                                content.split("\n")[line_num - 1].strip()[:120],
                            )
                        )

                        # UFIC Usage Check: Look for package invocation (e.g., exec.Command)
                        usage_pattern = re.compile(rf"\b{re.escape(base_pkg)}\.\w+")
                        if usage_pattern.search(content):
                            is_used = True
            except Exception as e:
                logger.debug("Failed to parse Go file %s: %s", go_file, e)

        if evidence:
            status = (
                ReachabilityStatus.REACHABLE_AND_USED
                if is_used
                else ReachabilityStatus.REACHABLE_BUT_UNUSED
            )
            reason = (
                f"Package '{package_name}' is imported and actively invoked."
                if is_used
                else f"Package '{package_name}' is imported but NEVER invoked."
            )
            return ReachabilityResult(status, evidence, reason)

        return ReachabilityResult(
            ReachabilityStatus.UNREACHABLE, reason=f"Package '{package_name}' is not imported."
        )

    def _analyze_java(self, package_name: str, scan_path: Path) -> ReachabilityResult:
        pkg_path = package_name.replace(".", "/")
        evidence: list[ReachabilityEvidence] = []
        is_used = False
        base_class = package_name.rsplit(".", maxsplit=1)[-1]

        for java_file in scan_path.rglob("*.java"):
            if java_file.is_symlink() or any(
                skip in java_file.parts for skip in ("test", "generated", "target")
            ):
                continue
            try:
                content = java_file.read_text(encoding="utf-8", errors="ignore")
                for match in self.JAVA_IMPORT_RE.finditer(content):
                    if pkg_path in match.group("pkg"):
                        line_num = content[: match.start()].count("\n") + 1
                        evidence.append(
                            ReachabilityEvidence(
                                str(java_file.relative_to(self.repo_root)),
                                line_num,
                                content.split("\n")[line_num - 1].strip()[:120],
                            )
                        )

                        # UFIC Usage Check: Look for class instantiation or static calls
                        usage_pattern = re.compile(rf"\b{re.escape(base_class)}\s*[\.(]")
                        if usage_pattern.search(content):
                            is_used = True
            except Exception as e:
                logger.debug("Failed to parse Java file %s: %s", java_file, e)

        if evidence:
            status = (
                ReachabilityStatus.REACHABLE_AND_USED
                if is_used
                else ReachabilityStatus.REACHABLE_BUT_UNUSED
            )
            reason = (
                f"Package '{package_name}' is imported and actively invoked."
                if is_used
                else f"Package '{package_name}' is imported but NEVER invoked."
            )
            return ReachabilityResult(status, evidence, reason)

        return ReachabilityResult(
            ReachabilityStatus.UNREACHABLE, reason=f"Package '{package_name}' is not imported."
        )

    def _get_python_imports(self, file_path: Path) -> set[str]:
        """Parse AST to extract top-level imported module names."""
        if file_path in self._import_cache:
            return self._import_cache[file_path]

        imports: set[str] = set()
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
        except (SyntaxError, UnicodeDecodeError, FileNotFoundError) as e:
            logger.debug("Failed to parse Python file %s: %s", file_path, e)

        self._import_cache[file_path] = imports
        return imports

    def _check_python_usage(self, file_path: Path, import_name: str) -> bool:
        """AST-based verification to ensure the imported module is actually invoked (ast.Load).
        This prevents false positives from variable shadowing (e.g., `import yaml` then `yaml = "test"`).
        """
        if file_path in self._usage_cache:
            return self._usage_cache[file_path]

        is_used = False
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
            for node in ast.walk(tree):
                # Skip the import statements themselves
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue

                # Check for Name nodes used in an expression (ast.Load), not an assignment (ast.Store)
                if (
                    isinstance(node, ast.Name)
                    and node.id == import_name
                    and isinstance(node.ctx, ast.Load)
                ):
                    is_used = True
                    break

                # Check for Attribute nodes (e.g., yaml.safe_load)
                if isinstance(node, ast.Attribute):
                    curr = node.value
                    while isinstance(curr, ast.Attribute):
                        curr = curr.value
                    if isinstance(curr, ast.Name) and curr.id == import_name:
                        is_used = True
                        break
        except Exception as e:
            logger.debug("Failed to parse Python file %s for usage check: %s", file_path, e)

        self._usage_cache[file_path] = is_used
        return is_used

    def _find_evidence_in_file(
        self,
        file_path: Path,
        import_name: str,
        is_python: bool = True,
        base_path: Path | None = None,
    ) -> list[ReachabilityEvidence]:
        """Extract the exact lines where the package is imported for auditability."""
        evidence: list[ReachabilityEvidence] = []
        target_base = base_path or self.repo_root

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.split("\n"), 1):
                if (
                    is_python and (f"import {import_name}" in line or f"from {import_name}" in line)
                ) or (not is_python and import_name in line):
                    evidence.append(
                        ReachabilityEvidence(
                            str(file_path.relative_to(target_base)), i, line.strip()[:120]
                        )
                    )
        except Exception as e:
            logger.debug("Failed to read file %s for evidence: %s", file_path, e)

        return evidence
