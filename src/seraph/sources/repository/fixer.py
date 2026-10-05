"""Seraph Guard — Automated Fixer Engine.
Applies deterministic, safe codemods to fix findings.
"""

import ast
import logging
import re
import shutil
import time

from pathlib import Path
from typing import Any

from seraph.sources.repository.scanners.base import Category, Finding


logger = logging.getLogger(__name__)


class FixResult:
    """Result of a fix attempt."""

    def __init__(
        self, finding_id: str, success: bool, message: str, changes: list[str] | None = None
    ) -> None:
        self.finding_id = finding_id
        self.success = success
        self.message = message
        self.changes = changes or []


class BackupManager:
    """Safely backs up files before modification to prevent data loss."""

    def __init__(self, scan_path: Path) -> None:
        self.scan_path = scan_path
        self.backup_dir = scan_path / ".seraph-guard" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, file_path: Path) -> Path:
        if not file_path.exists():
            return file_path
        rel_path = file_path.relative_to(self.scan_path)
        backup_path = self.backup_dir / rel_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        return backup_path


def _import_line_index(content: str) -> int:
    """Calculate the correct 0-based list index to insert a standard Python import.
    Respects shebangs, module docstrings, and __future__ imports.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return 0

    idx = 0
    for i, node in enumerate(tree.body):
        is_doc = (
            i == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        is_future = isinstance(node, ast.ImportFrom) and node.module == "__future__"

        if is_doc or is_future:
            # FIX: Extract to temporary variable to satisfy Mypy's strict `int | None` narrowing
            end_line = getattr(node, "end_lineno", None)
            idx = end_line if end_line is not None else i + 1
        else:
            break

    # If no docstring or __future__ import, but there is a shebang, insert after it.
    if idx == 0 and content.startswith("#!"):
        idx = 1

    return idx


class Fixer:
    """Automatically fixes findings using deterministic, safe codemods."""

    def __init__(self, scan_path: Path, learning_engine: Any | None = None) -> None:
        self.scan_path = scan_path.resolve()
        self.learning = learning_engine
        self.results: list[FixResult] = []
        self.backup_manager = BackupManager(self.scan_path)

    def fix_all(self, findings: list[Finding], dry_run: bool = False) -> list[FixResult]:
        """Fix all findings that have automated fixes available."""
        self.results = []
        fixable = [
            f
            for f in findings
            if getattr(f, "fix_available", False)
            and not getattr(f, "is_suppressed", False)
            # Guard clause: Do not treat IaC findings as fixable unless they carry a
            # concrete, tested fix_command. Vague remediation text is not enough.
            and not (
                getattr(f, "scanner", "").lower() == "iac" and not getattr(f, "fix_command", "")
            )
        ]
        if not fixable:
            logger.info("No fixable findings found.")
            return self.results

        for finding in fixable:
            # Route through fix_one to correctly wire the learning callback
            result = self.fix_one(finding, dry_run)
            self.results.append(result)
        return self.results

    def fix_one(self, finding: Finding, dry_run: bool = False) -> FixResult:
        """Fix a single finding."""
        start_time = time.time()
        result = self._apply_deterministic_fix(finding, dry_run)
        if self.learning and not dry_run:
            duration = (time.time() - start_time) / 3600
            self.learning.record_fix(finding, duration)
        return result

    def _apply_deterministic_fix(self, finding: Finding, dry_run: bool) -> FixResult:
        """Route finding to the appropriate deterministic fix handler."""
        metadata = getattr(finding, "metadata", {}) or {}
        rule_id = str(metadata.get("rule_id", "")).lower()
        file_path = self.scan_path / finding.file

        if "missing" in rule_id or "require-" in rule_id or "Missing" in finding.title:
            return self._fix_policy(finding, file_path, rule_id, dry_run)

        if "forbidden file" in finding.title.lower() or "no-ds_store" in rule_id:
            return self._fix_policy(finding, file_path, rule_id, dry_run)

        # Guard clause: skip IaC-scanner findings that do not carry a
        # concrete, machine-parseable fix_command. Prevents false "fix_available" positives.
        scanner = getattr(finding, "scanner", "").lower()
        if scanner == "iac" and not getattr(finding, "fix_command", ""):
            return FixResult(
                finding.id,
                False,
                "IaC fix not yet implemented — no concrete fix command provided.",
            )

        if finding.fix_command and finding.category == Category.POLICY:
            return self._fix_iac(finding, file_path, dry_run)

        if file_path.suffix == ".py" and finding.category == Category.PATTERN:
            return self._fix_python_pattern(finding, file_path, rule_id, dry_run)

        if finding.category == Category.SECRET:
            return self._fix_secret(finding, file_path, dry_run)

        if finding.category == Category.VULNERABILITY:
            return self._fix_dependency(finding, file_path, dry_run)

        return FixResult(finding.id, False, "No deterministic fix available for this pattern.")

    def _fix_iac(self, finding: Finding, file_path: Path, dry_run: bool) -> FixResult:
        r"""Apply a fix_command from a policy finding (e.g., 'Set acl = "private"')."""
        if not file_path.exists():
            return FixResult(finding.id, False, f"File not found: {finding.file}")

        fix_cmd = finding.fix_command
        if not fix_cmd or "Remove" in fix_cmd or "Create" in fix_cmd:
            return FixResult(finding.id, False, "IaC fix requires manual intervention.")

        try:
            content = file_path.read_text(encoding="utf-8")
            original = content
            evidence = getattr(finding, "evidence", "") or ""

            if evidence.strip() in content:
                set_match = re.search(r'Set\s+(\w+)\s*=\s*["\']?([^"\']+)["\']?', fix_cmd)
                if set_match:
                    new_attr, new_val = set_match.groups()
                    content = content.replace(evidence.strip(), f"{new_attr} = {new_val}")

            if content == original:
                return FixResult(
                    finding.id, False, "Could not locate the IaC attribute to replace in the file."
                )

            if dry_run:
                return FixResult(
                    finding.id,
                    True,
                    f"Dry run: Would modify {finding.file}",
                    [f"Evidence: {evidence[:100]}", f"Fix: {fix_cmd}"],
                )

            self.backup_manager.backup(file_path)
            file_path.write_text(content, encoding="utf-8")
            return FixResult(
                finding.id,
                True,
                f"Applied IaC fix: {fix_cmd}",
                [f"File: {finding.file}", f"Fix: {fix_cmd}"],
            )
        except Exception as e:
            return FixResult(finding.id, False, f"IaC fix error: {e}")

    def _fix_python_pattern(
        self, finding: Finding, file_path: Path, rule_id: str, dry_run: bool
    ) -> FixResult:
        try:
            if not file_path.exists():
                return FixResult(finding.id, False, f"File not found: {finding.file}")

            original_content = file_path.read_text(encoding="utf-8")
            new_lines = original_content.splitlines()

            target_line = finding.line - 1
            if target_line < 0 or target_line >= len(new_lines):
                return FixResult(finding.id, False, "Line number out of range.")

            original_line = new_lines[target_line]
            new_line = original_line
            metadata = getattr(finding, "metadata", {}) or {}
            pattern_str = str(metadata.get("pattern", ""))

            # Safe YAML fix
            if (
                (
                    "yaml" in rule_id
                    or "yaml" in pattern_str
                    or "unsafe yaml" in finding.title.lower()
                )
                and "yaml.load(" in original_line
                and "safe_load" not in original_line
            ):
                new_line = re.sub(r"(\byaml\s*\.\s*)load\s*\(", r"\1safe_load(", original_line)

            # NOTE: pickle.loads to json.loads branch DELETED.
            # It changes serialization behavior and breaks data structures.

            if new_line == original_line:
                return FixResult(
                    finding.id,
                    False,
                    "Pattern recognized but no safe automated AST/regex replacement found. Manual review required.",
                )

            if dry_run:
                return FixResult(
                    finding.id,
                    True,
                    f"Dry run: Would modify line {finding.line}",
                    [f"Old: {original_line.strip()}", f"New: {new_line.strip()}"],
                )

            self.backup_manager.backup(file_path)
            new_lines[target_line] = new_line
            file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

            return FixResult(
                finding.id,
                True,
                "Successfully applied deterministic codemod.",
                [f"Old: {original_line.strip()}", f"New: {new_line.strip()}"],
            )
        except SyntaxError:
            return FixResult(
                finding.id, False, "File contains syntax errors, cannot safely apply AST fix."
            )
        except Exception as e:
            return FixResult(finding.id, False, f"Error applying fix: {e}")

    def _fix_secret(self, finding: Finding, file_path: Path, dry_run: bool) -> FixResult:
        # Strictly rely on the internal _raw_secret for safe, accurate replacement
        raw_secret = getattr(finding, "_raw_secret", "")
        if not raw_secret:
            return FixResult(
                finding.id, False, "Raw secret value not available for safe redaction."
            )

        target_file = file_path

        if file_path.name == ".env" or file_path.suffix == ".env":
            return self._fix_env_secret(finding, file_path, dry_run)

        if not target_file.exists():
            return FixResult(finding.id, False, f"File not found: {finding.file}")

        try:
            content = target_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            target_line = finding.line - 1

            if target_line < 0 or target_line >= len(lines):
                return FixResult(finding.id, False, "Line number out of range.")

            original_line = lines[target_line]
            ext = target_file.suffix.lower()
            new_line = original_line
            import_stmt = ""

            # Go, Ruby, YAML substitutions produce invalid code. Make them manual.
            if ext in (".go", ".rb", ".yaml", ".yml"):
                return FixResult(finding.id, False, "Manual change required for this file type.")

            if ext == ".py":
                var_match = re.search(r"(\w+)\s*=\s*", original_line)
                var_name = var_match.group(1).upper() if var_match else "SECRET_KEY"
                new_line = original_line.replace(raw_secret, f'os.environ.get("{var_name}")')
                import_stmt = "import os"
            elif ext in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"):
                var_match = re.search(r"(?:const|let|var)\s+(\w+)\s*=\s*", original_line)
                var_name = var_match.group(1).upper() if var_match else "SECRET_KEY"
                new_line = original_line.replace(raw_secret, f"process.env.{var_name}")
            elif ext in (".tf", ".tfvars"):
                var_match = re.search(r'(\w+)\s*=\s*["\']', original_line)
                var_name = var_match.group(1) if var_match else "secret_value"
                new_line = original_line.replace(raw_secret, f"var.{var_name}")
            else:
                new_line = original_line.replace(raw_secret, "REDACTED_BY_SERAPH")

            if new_line == original_line:
                return FixResult(
                    finding.id, False, "Could not safely identify variable assignment to replace."
                )

            if dry_run:
                return FixResult(
                    finding.id,
                    True,
                    f"Dry run: Would redact secret on line {finding.line}",
                    [f"Old: {original_line.strip()}", f"New: {new_line.strip()}"],
                )

            self.backup_manager.backup(target_file)

            if import_stmt and not re.search(
                rf"^{re.escape(import_stmt)}\s*$", content, re.MULTILINE
            ):
                # Use AST-aware index to respect shebangs, docstrings, and __future__ imports
                insert_idx = _import_line_index(content)
                lines.insert(insert_idx, import_stmt)
                if insert_idx <= target_line:
                    target_line += 1

            lines[target_line] = new_line
            target_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

            return FixResult(
                finding.id,
                True,
                "Fixed — credential replaced with environment variable lookup.",
                [f"Old: {original_line.strip()}", f"New: {new_line.strip()}"],
            )
        except Exception as e:
            return FixResult(finding.id, False, f"Error applying secret fix: {e}")

    def _fix_env_secret(self, finding: Finding, file_path: Path, dry_run: bool) -> FixResult:
        try:
            if not file_path.exists():
                return FixResult(finding.id, False, f".env file not found: {finding.file}")

            # Safely do nothing when the raw value isn't available
            raw_secret = getattr(finding, "_raw_secret", "")
            if not raw_secret:
                return FixResult(
                    finding.id, False, "Raw secret value not available for safe redaction."
                )

            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            original_line = ""
            new_line = ""
            modified = False

            for i, line in enumerate(lines):
                if not line.strip() or line.strip().startswith("#"):
                    continue

                # If the raw secret is in this line, we redact it
                if raw_secret in line:
                    original_line = line
                    # Preserve the key, redact the value
                    if "=" in line:
                        key_part = line.split("=", 1)[0]
                        new_line = f"{key_part}=REDACTED_BY_SERAPH"
                    else:
                        new_line = "REDACTED_BY_SERAPH"

                    lines[i] = new_line
                    modified = True
                    break

            if not modified:
                return FixResult(finding.id, False, "Could not locate the secret in .env file.")

            if dry_run:
                return FixResult(
                    finding.id,
                    True,
                    "Dry run: Would redact secret in .env",
                    [f"Old: {original_line.strip()}", f"New: {new_line.strip()}"],
                )

            self.backup_manager.backup(file_path)
            file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            return FixResult(
                finding.id,
                True,
                "Fixed — secret redacted in .env file.",
                [f"Old: {original_line.strip()}", f"New: {new_line.strip()}"],
            )
        except Exception as e:
            return FixResult(finding.id, False, f"Error fixing .env secret: {e}")

    def _fix_policy(
        self, finding: Finding, file_path: Path, rule_id: str, dry_run: bool
    ) -> FixResult:
        changes: list[str] = []

        if "require-" in rule_id or "Missing" in finding.title:
            file_to_create = self._get_file_to_create(rule_id)
            if file_to_create:
                target_path = self.scan_path / file_to_create
                if dry_run:
                    return FixResult(
                        finding.id,
                        True,
                        f"Dry run: Would create {target_path}",
                        [f"Create {target_path}"],
                    )

                self.backup_manager.backup(target_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                content = self._get_template_content(rule_id)
                target_path.write_text(content, encoding="utf-8")
                return FixResult(
                    finding.id, True, f"Created {target_path}", [f"Created {target_path}"]
                )

        if "Forbidden file" in finding.title or "no-ds_store" in rule_id:
            gitignore_path = self.scan_path / ".gitignore"
            pattern = finding.file.split("/")[-1]
            if dry_run:
                return FixResult(
                    finding.id,
                    True,
                    f"Dry run: Would add '{pattern}' to .gitignore",
                    [f"Add '{pattern}' to .gitignore"],
                )

            self.backup_manager.backup(gitignore_path)
            if gitignore_path.exists():
                content = gitignore_path.read_text(encoding="utf-8")
                if pattern not in content:
                    with gitignore_path.open("a", encoding="utf-8") as f:
                        f.write(f"\n{pattern}\n")
                    changes.append(f"Added '{pattern}' to .gitignore")
            else:
                gitignore_path.write_text(f"{pattern}\n", encoding="utf-8")
                changes.append(f"Created .gitignore with '{pattern}'")
            return FixResult(finding.id, True, "Fixed policy violation", changes)

        return FixResult(finding.id, False, "No automated fix for this policy rule")

    def _fix_dependency(self, finding: Finding, file_path: Path, dry_run: bool) -> FixResult:
        metadata = getattr(finding, "metadata", {}) or {}
        pkg = str(metadata.get("package") or metadata.get("pkg_name") or "")
        fixed_version = str(
            metadata.get("fixed_version") or ""
        ) or self._extract_version_from_message(finding.message, "fixed")
        current_version = str(metadata.get("version") or "") or self._extract_version_from_message(
            finding.message, "current"
        )
        cve = str(metadata.get("cve", "") or getattr(finding, "cve", ""))

        if not pkg or not fixed_version:
            pkg_from_msg, ver_from_msg = self._parse_dependency_from_text(
                finding.description or finding.message or ""
            )
            if not pkg:
                pkg = pkg_from_msg
            if not fixed_version:
                fixed_version = ver_from_msg

        if not pkg or not fixed_version:
            return FixResult(
                finding.id,
                False,
                f"Missing package name or fixed version for dependency fix. "
                f"Needed: package={pkg or '?'}, fixed_version={fixed_version or '?'}. "
                f"Message was: {(finding.message or '')[:100]}",
            )

        affected_manifests = metadata.get("affected_manifests", [])
        supported_manifests = {
            "package.json",
            "package-lock.json",
            "requirements.txt",
            "requirements-dev.txt",
            "requirements.in",
            "go.mod",
            "pyproject.toml",
            "Pipfile",
            "Cargo.toml",
            "Gemfile",
            "composer.json",
        }

        target_manifests = [
            f
            for f in affected_manifests
            if f in supported_manifests or Path(f).name in supported_manifests
        ]

        if not target_manifests and file_path.name in supported_manifests:
            target_manifests = [str(file_path.relative_to(self.scan_path))]

        if not target_manifests:
            for manifest_name in supported_manifests:
                candidate = self.scan_path / manifest_name
                if candidate.exists():
                    target_manifests = [manifest_name]
                    break

        if not target_manifests:
            return FixResult(
                finding.id,
                False,
                f"No supported manifest file found to edit for {pkg}. Supported: {', '.join(sorted(supported_manifests))}",
            )

        target_rel_path = target_manifests[0]
        target_file_path = self.scan_path / target_rel_path

        if not target_file_path.exists():
            return FixResult(finding.id, False, f"Manifest file not found: {target_file_path}")

        try:
            content = target_file_path.read_text(encoding="utf-8")
            file_name = target_file_path.name
            pkg_escaped = re.escape(pkg)
            count = 0

            if file_name in ("package.json", "package-lock.json"):
                pattern = re.compile(rf'("{pkg_escaped}"\s*:\s*")([^"]+)(")', re.IGNORECASE)

                def replacer(m: re.Match[str]) -> str:
                    prefix = m.group(2)
                    match_prefix = re.match(r"^([^\d\s]*)", prefix)
                    ver_prefix = match_prefix.group(1) if match_prefix else "^"
                    return f"{m.group(1)}{ver_prefix}{fixed_version}{m.group(3)}"

                content, count = pattern.subn(replacer, content)

            elif file_name in ("requirements.txt", "requirements-dev.txt", "requirements.in"):
                pattern = re.compile(
                    rf"^(\s*{pkg_escaped}(?:\[[^\]]+\])?\s*)([=<>!~]+)([^\s#,]+)",
                    re.IGNORECASE | re.MULTILINE,
                )

                def replacer(m: re.Match[str]) -> str:
                    return f"{m.group(1)}>={fixed_version}"

                content, count = pattern.subn(replacer, content)

            elif file_name == "go.mod":
                v_fixed = fixed_version if fixed_version.startswith("v") else f"v{fixed_version}"
                pattern = re.compile(
                    rf"^(\s*{pkg_escaped}\s+)(v?[^\s]+)", re.IGNORECASE | re.MULTILINE
                )

                def replacer(m: re.Match[str]) -> str:
                    return f"{m.group(1)}{v_fixed}"

                content, count = pattern.subn(replacer, content)

            elif file_name == "pyproject.toml":
                pattern = re.compile(
                    rf'(^\s*["\']?{pkg_escaped}["\']?\s*=\s*["\'])([^"\']+)(["\'])',
                    re.IGNORECASE | re.MULTILINE,
                )

                def replacer(m: re.Match[str]) -> str:
                    prefix = m.group(2)
                    match_prefix = re.match(r"^([^\d\s]*)", prefix)
                    ver_prefix = match_prefix.group(1) if match_prefix else ">="
                    return f"{m.group(1)}{ver_prefix}{fixed_version}{m.group(3)}"

                content, count = pattern.subn(replacer, content)

            elif file_name == "Pipfile":
                pattern = re.compile(
                    rf'(^\s*{pkg_escaped}\s*=\s*["\'])([^"\']+)(["\'])',
                    re.IGNORECASE | re.MULTILINE,
                )

                def replacer(m: re.Match[str]) -> str:
                    return f"{m.group(1)}>={fixed_version}{m.group(3)}"

                content, count = pattern.subn(replacer, content)

            elif file_name == "Cargo.toml":
                pattern = re.compile(
                    rf'(^\s*{pkg_escaped}\s*=\s*["\'])([^"\']+)(["\'])',
                    re.IGNORECASE | re.MULTILINE,
                )

                def replacer(m: re.Match[str]) -> str:
                    return f"{m.group(1)}{fixed_version}{m.group(3)}"

                content, count = pattern.subn(replacer, content)

            elif file_name == "Gemfile":
                pattern = re.compile(
                    rf'(gem\s+["\']{pkg_escaped}["\'](?:\s*,\s*["\']~>?\s*)([^"\']+)(["\'])',
                    re.IGNORECASE | re.MULTILINE,
                )

                def replacer(m: re.Match[str]) -> str:
                    return f"{m.group(1)}{fixed_version}{m.group(3)}"

                content, count = pattern.subn(replacer, content)

            elif file_name == "composer.json":
                pattern = re.compile(rf'("{pkg_escaped}"\s*:\s*")([^"]+)(")', re.IGNORECASE)

                def replacer(m: re.Match[str]) -> str:
                    return f"{m.group(1)}^{fixed_version}{m.group(3)}"

                content, count = pattern.subn(replacer, content)

            else:
                return FixResult(
                    finding.id, False, f"Direct manifest editing not supported for: {file_name}."
                )

            if count == 0:
                return FixResult(
                    finding.id,
                    False,
                    f"Could not find '{pkg}' in {file_name} to bump version. The package may use a different name in this manifest.",
                )

            if dry_run:
                return FixResult(
                    finding.id,
                    True,
                    f"Dry run: Would bump {pkg} to {fixed_version} in {file_name}",
                    [
                        f"File: {file_name}",
                        f"Package: {pkg}",
                        f"Old Version: {current_version or 'unknown'}",
                        f"New Version: {fixed_version}",
                        f"CVE: {cve or 'N/A'}",
                    ],
                )

            self.backup_manager.backup(target_file_path)
            target_file_path.write_text(content, encoding="utf-8")

            return FixResult(
                finding.id,
                True,
                f"Successfully bumped {pkg} to {fixed_version} in {file_name}.",
                [
                    f"File: {file_name}",
                    f"Package: {pkg}",
                    f"Old Version: {current_version or 'unknown'}",
                    f"New Version: {fixed_version}",
                    f"CVE: {cve or 'N/A'}",
                ],
            )
        except Exception as e:
            return FixResult(finding.id, False, f"Error applying dependency fix: {e}")

    @staticmethod
    def _extract_version_from_message(message: str, which: str) -> str:
        if not message:
            return ""

        if which == "fixed":
            patterns = [
                r"[Ff]ixed\s+in\s+v?(\d+\.\d+\.\d+[^\s,)]*)",
                r"[Uu]pgrade\s+to\s+v?(\d+\.\d+\.\d+[^\s,)]*)",
                r"[Pp]atch\s+v?(\d+\.\d+\.\d+[^\s,)]*)",
                r"[Rr]esolve\s+by\s+upgrading\s+to\s+v?(\d+\.\d+\.\d+[^\s,)]*)",
            ]
        else:
            patterns = [
                r"[Vv]ersion\s+v?(\d+\.\d+\.\d+[^\s,)]*)",
                r"(?:in|using)\s+v?(\d+\.\d+\.\d+[^\s,)]*)",
            ]

        for pat in patterns:
            try:
                m = re.search(pat, message)
                if m:
                    return m.group(1).strip()
            except Exception:
                logger.debug("Regex match failed", exc_info=True)
                continue
        return ""

    @staticmethod
    def _parse_dependency_from_text(text: str) -> tuple[str, str]:
        if not text:
            return "", ""

        pkg = ""
        fixed_ver = ""

        m = re.search(r"in\s+([a-zA-Z0-9_.-]+)@(\d+\.\d+\.\d+)", text)
        if m:
            pkg = m.group(1)
            fixed_m = re.search(r"[Ff]ixed\s+in\s+v?(\d+\.\d+\.\d+)", text[m.end() :])
            if fixed_m:
                fixed_ver = fixed_m.group(1)
            else:
                all_versions = re.findall(r"\d+\.\d+\.\d+[^\s,)]*", text)
                if len(all_versions) >= 2:
                    fixed_ver = all_versions[-1]
            return pkg, fixed_ver

        m = re.search(r"([a-zA-Z0-9_.-]+?)\s+v?(\d+\.\d+\.\d+)", text)
        if m:
            pkg = m.group(1)
            if pkg.lower() in ("version", "affected", "fixed", "using", "in"):
                pkg = ""
            else:
                all_versions = re.findall(r"\d+\.\d+\.\d+[^\s,)]*", text)
                if len(all_versions) >= 2:
                    fixed_ver = all_versions[-1]

        return pkg, fixed_ver

    def _get_file_to_create(self, rule_id: str) -> str | None:
        mapping = {
            "require-readme": "README.md",
            "require-license": "LICENSE",
            "require-gitignore": ".gitignore",
            "require-codeowners": ".github/CODEOWNERS",
            "require-security-policy": "SECURITY.md",
            "require-pr-template": ".github/PULL_REQUEST_TEMPLATE.md",
            "require-dependabot": ".github/dependabot.yml",
        }
        return mapping.get(rule_id)

    def _get_template_content(self, rule_id: str) -> str:
        templates = {
            "require-readme": "# Project Name\n\nBrief description.\n\n## Usage\n\n```\n```\n",
            "require-license": 'MIT License\n\nCopyright (c) 2024\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n',
            "require-gitignore": "__pycache__/\n*.pyc\n.env\n.env.local\n.venv/\nvenv/\nnode_modules/\n*.egg-info/\ndist/\nbuild/\n.seraph-learn/\n.seraph-cache/\n.DS_Store\nThumbs.db\n",
            "require-codeowners": "# Default: security team reviews everything\n* @security-team\n\n# Docs can be reviewed by docs team\n/docs/ @docs-team\n",
            "require-security-policy": "# Security Policy\n\n## Supported Versions\n\n| Version | Supported |\n| ------- | -------------- |\n| Latest  | ✅ |\n\n## Reporting a Vulnerability\n\nPlease report security vulnerabilities by emailing security@example.com.\n\nWe will acknowledge receipt within 24 hours and aim to provide a resolution within 7 days.\n",
            "require-dependabot": "version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n    schedule:\n      interval: weekly\n    open-pull-requests-limit: 10\n\n  - package-ecosystem: npm\n    directory: /\n    schedule:\n      interval: weekly\n    open-pull-requests-limit: 10\n\n  - package-ecosystem: gomod\n    directory: /\n    schedule:\n      interval: weekly\n    open-pull-requests-limit: 10\n",
        }
        return templates.get(rule_id, "# Auto-generated by Seraph Guard\n")

    def get_summary(self) -> dict[str, Any]:
        total = len(self.results)
        fixed = sum(1 for r in self.results if r.success)
        return {
            "total": total,
            "fixed": fixed,
            "failed": total - fixed,
            "success_rate": round((fixed / total * 100), 2) if total > 0 else 0.0,
            "results": [
                {
                    "finding_id": r.finding_id,
                    "success": r.success,
                    "message": r.message,
                    "changes": r.changes,
                }
                for r in self.results
            ],
        }
