import ast
import logging
import re

from pathlib import Path
from typing import Any, ClassVar, cast, override

import yaml


try:
    import hcl2

    HAS_HCL2 = True
except ImportError:
    HAS_HCL2 = False

from seraph.guard.scanners.base import (
    BlastRadius,
    Category,
    Finding,
    ScanContext,
    Scanner,
    Severity,
)


logger = logging.getLogger(__name__)


class PolicyScanner(Scanner):
    name = "PolicyScanner"
    version = "0.5.0"
    categories: ClassVar[list[Category]] = [Category.POLICY]

    IGNORE_DIRS: ClassVar[set[str]] = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
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
        "coverage",
    }

    NON_PROD_SEGMENTS: ClassVar[set[str]] = {
        "test",
        "tests",
        "spec",
        "specs",
        "e2e",
        "__tests__",
        "__mocks__",
        "mock",
        "mocks",
        "fixture",
        "fixtures",
        "testdata",
        "test_data",
        "testcluster",
        "testhelpers",
        "testutil",
        "testutils",
        "testing",
        "cypress",
        "playwright",
        "__testfixtures__",
        "example",
        "examples",
        "demo",
        "demos",
        "playground",
        "playgrounds",
        "docs",
        "doc",
        "documentation",
        "website",
        "www",
        "bench",
        "benchmark",
        "benchmarks",
        "perf",
        "performance",
        "build",
        "dist",
        "out",
        "target",
        "compiled",
        ".next",
        ".nuxt",
        "devenv",
        "dev-env",
        "evals",
        "eval",
        "app-dir",
        "development",
        "apps",
        "codemod",
        "codemods",
        "eslint-plugin",
        "eslint-plugin-next",
    }

    BUILD_TOOL_FILES: ClassVar[set[str]] = {
        "taskfile.js",
        "taskfile.ts",
        "gulpfile.js",
        "gruntfile.js",
        "webpack.config.js",
        "webpack.config.ts",
        "vite.config.ts",
        "vite.config.js",
        "rollup.config.js",
        "rollup.config.ts",
        "jest.config.js",
        "jest.config.ts",
        "cypress.config.ts",
        "cypress.config.js",
        "playwright.config.ts",
        "playwright.config.js",
        "vitest.config.ts",
        "vitest.config.js",
        "next.config.js",
        "next.config.ts",
        "babel.config.js",
        "babel.config.ts",
        "esbuild.config.js",
        "tsup.config.ts",
        "gulpfile.ts",
        "gruntfile.ts",
    }

    LANG_EXT_MAP: ClassVar[dict[str, set[str]]] = {
        "python": {".py", ".pyx", ".pyd"},
        "javascript": {".js", ".jsx", ".mjs", ".cjs"},
        "typescript": {".ts", ".tsx"},
        "go": {".go"},
        "java": {".java", ".kt", ".scala"},
        "ruby": {".rb", ".erb"},
        "php": {".php"},
        "csharp": {".cs"},
        "shell": {".sh", ".bash", ".zsh"},
        "rust": {".rs"},
        "terraform": {".tf", ".tfvars", ".hcl"},
    }

    def __init__(self, policies_dir: Path | None = None):
        self.policies_dir = policies_dir or Path("policies/builtin")
        self.auto_policies_dir = Path("policies/auto-generated")
        self.rules: list[dict[str, Any]] = []
        self._repo_languages: set[str] = set()
        self._builtin_iac_rules_loaded: bool = False
        self._repo_file_count: int = -1

    @override
    def is_applicable(self, context: ScanContext) -> bool:
        return self.policies_dir.exists() or self.auto_policies_dir.exists()

    @override
    async def scan(self, context: ScanContext) -> list[Finding]:
        findings: list[Finding] = []
        self._detect_repo_languages(context)
        self._load_rules()
        self._ensure_iac_rules()
        if not self.rules:
            logger.warning("No policy rules loaded")
            return findings
        scan_path = context.resolved_path
        for rule in self.rules:
            findings.extend(self._check_rule(rule, scan_path))
        logger.info("PolicyScanner found %d violations", len(findings))
        return findings

    def _ensure_iac_rules(self) -> None:
        if self._builtin_iac_rules_loaded:
            return
        self._builtin_iac_rules_loaded = True
        existing_ids = {r.get("id", "") for r in self.rules}
        iac_rules = self._get_builtin_iac_rules()
        for rule in iac_rules:
            if rule["id"] not in existing_ids and self._rule_applies_to_repo(rule):
                self.rules.append(rule)

    @staticmethod
    def _get_builtin_iac_rules() -> list[dict[str, Any]]:
        return [
            {
                "id": "tf-s3-no-public-acl",
                "name": "S3 Bucket Public ACL",
                "type": "hcl_attribute_value",
                "resource_type": "aws_s3_bucket",
                "attribute": "acl",
                "forbidden_values": ["public-read", "public-read-write", "authenticated-read"],
                "paths": ["**/*.tf"],
                "severity": "high",
                "message": "S3 bucket must not have a public ACL. Use 'private' or omit the attribute.",
                "fix": 'Set acl = "private" or remove the acl attribute entirely.',
                "languages": ["terraform"],
            },
            {
                "id": "tf-s3-no-versioning",
                "name": "S3 Bucket Versioning Disabled",
                "type": "hcl_attribute_value",
                "resource_type": "aws_s3_bucket_versioning",
                "attribute": "enabled",
                "required_value": True,
                "paths": ["**/*.tf"],
                "severity": "medium",
                "message": "S3 bucket should have versioning enabled for data protection.",
                "fix": "Set versioning { enabled = true }",
                "languages": ["terraform"],
            },
            {
                "id": "tf-sg-open-ingress",
                "name": "Security Group Open Ingress",
                "type": "hcl_attribute_value",
                "resource_type": "aws_security_group_rule",
                "attribute": "cidr_blocks",
                "forbidden_values": ["0.0.0.0/0"],
                "paths": ["**/*.tf"],
                "severity": "high",
                "message": "Security group rule must not allow ingress from 0.0.0.0/0 (entire internet).",
                "fix": "Restrict cidr_blocks to known IP ranges.",
                "languages": ["terraform"],
            },
            {
                "id": "tf-ebs-no-encryption",
                "name": "EBS Volume Unencrypted",
                "type": "hcl_attribute_value",
                "resource_type": "aws_ebs_volume",
                "attribute": "encrypted",
                "required_value": True,
                "paths": ["**/*.tf"],
                "severity": "high",
                "message": "EBS volumes must be encrypted at rest.",
                "fix": "Set encrypted = true",
                "languages": ["terraform"],
            },
            {
                "id": "tf-rds-no-encryption",
                "name": "RDS Instance Unencrypted",
                "type": "hcl_attribute_value",
                "resource_type": "aws_db_instance",
                "attribute": "storage_encrypted",
                "required_value": True,
                "paths": ["**/*.tf"],
                "severity": "high",
                "message": "RDS instances must have storage encryption enabled.",
                "fix": "Set storage_encrypted = true",
                "languages": ["terraform"],
            },
            {
                "id": "tf-s3-bucket-no-encryption",
                "name": "S3 Bucket Default Encryption Missing",
                "type": "hcl_attribute_value",
                "resource_type": "aws_s3_bucket_server_side_encryption_configuration",
                "attribute": "apply_server_side_encryption_by_default",
                "paths": ["**/*.tf"],
                "severity": "medium",
                "message": "S3 bucket should have default server-side encryption configured.",
                "fix": "Add aws_s3_bucket_server_side_encryption_configuration resource.",
                "languages": ["terraform"],
            },
            {
                "id": "tf-iam-admin-policy",
                "name": "IAM Policy Admin Access",
                "type": "content_not_contains",
                "pattern": r"""Action\s*=\s*['"]\*['"]""",
                "paths": ["**/*.tf"],
                "severity": "high",
                "message": 'IAM policy must not use Action = "*" (full admin access). Use least-privilege permissions.',
                "fix": 'Replace Action = "*" with specific allowed actions.',
                "languages": ["terraform"],
            },
            {
                "id": "tf-s3-no-logging",
                "name": "S3 Bucket Access Logging Disabled",
                "type": "content_not_contains",
                "pattern": "aws_s3_bucket_logging",
                "paths": ["**/*.tf"],
                "severity": "low",
                "message": "S3 buckets should have access logging enabled for audit compliance.",
                "fix": "Add an aws_s3_bucket_logging resource targeting this bucket.",
                "languages": ["terraform"],
            },
            {
                "id": "tf-no-resource-tags",
                "name": "Missing Resource Tags",
                "type": "content_not_contains",
                "pattern": r"tags\s*=\s*\{",
                "paths": ["**/*.tf"],
                "severity": "low",
                "message": "Terraform resources should have tags for cost allocation and compliance.",
                "fix": "Add a tags = { Name = ..., Environment = ... } block.",
                "languages": ["terraform"],
            },
            {
                "id": "k8s-privileged-container",
                "name": "Privileged Container",
                "type": "yaml_attribute_value",
                "attribute_path": "securityContext.privileged",
                "forbidden_values": [True],
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "high",
                "message": "Containers must not run as privileged. This grants full host access.",
                "fix": "Set privileged: false or remove the securityContext.privileged field.",
                "languages": ["go"],
            },
            {
                "id": "k8s-run-as-root",
                "name": "Container Runs as Root",
                "type": "yaml_attribute_value",
                "attribute_path": "securityContext.runAsNonRoot",
                "required_value": True,
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "medium",
                "message": "Containers should set runAsNonRoot: true to prevent running as root.",
                "fix": "Add securityContext: runAsNonRoot: true",
                "languages": ["go"],
            },
            {
                "id": "k8s-host-network",
                "name": "Host Network Enabled",
                "type": "yaml_attribute_value",
                "attribute_path": "hostNetwork",
                "forbidden_values": [True],
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "high",
                "message": "hostNetwork should not be enabled. It bypasses network isolation.",
                "fix": "Remove hostNetwork: true or set it to false.",
                "languages": ["go"],
            },
            {
                "id": "k8s-host-pid",
                "name": "Host PID Enabled",
                "type": "yaml_attribute_value",
                "attribute_path": "hostPID",
                "forbidden_values": [True],
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "high",
                "message": "hostPID should not be enabled. It allows visibility into all host processes.",
                "fix": "Remove hostPID: true or set it to false.",
                "languages": ["go"],
            },
            {
                "id": "k8s-host-ipc",
                "name": "Host IPC Enabled",
                "type": "yaml_attribute_value",
                "attribute_path": "hostIPC",
                "forbidden_values": [True],
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "high",
                "message": "hostIPC should not be enabled. It allows IPC namespace access on the host.",
                "fix": "Remove hostIPC: true or set it to false.",
                "languages": ["go"],
            },
            {
                "id": "k8s-secret-env-var",
                "name": "Secret in Environment Variable",
                "type": "content_not_contains",
                "pattern": r"valueFrom:\s*\n\s*secretKeyRef:",
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "info",
                "message": "Environment variables reference secrets. Ensure secrets are encrypted at rest.",
                "fix": "Consider using external secrets manager (Vault, AWS Secrets Manager).",
                "languages": ["go"],
            },
            {
                "id": "k8s-no-resource-limits",
                "name": "Missing Resource Limits",
                "type": "content_not_contains",
                "pattern": r"limits:\s*\n",
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "medium",
                "message": "Containers should define resource limits to prevent resource exhaustion.",
                "fix": "Add resources: limits: { cpu: ..., memory: ... }",
                "languages": ["go"],
            },
            {
                "id": "k8s-add-capabilities",
                "name": "Additional Linux Capabilities",
                "type": "yaml_attribute_value",
                "attribute_path": "securityContext.capabilities.add",
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "medium",
                "message": "Adding Linux capabilities increases container privilege. Review necessity.",
                "fix": "Remove capabilities.add or use capabilities.drop: [ALL]",
                "languages": ["go"],
            },
            {
                "id": "k8s-latest-tag",
                "name": "Container Image Using :latest Tag",
                "type": "content_not_contains",
                "pattern": "image:.*:latest",
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "medium",
                "message": "Container images should not use :latest tag. It makes deployments non-reproducible.",
                "fix": "Pin image to a specific digest or version tag.",
                "languages": ["go"],
            },
            {
                "id": "k8s-default-service-account",
                "name": "Using Default Service Account",
                "type": "yaml_attribute_value",
                "attribute_path": "serviceAccountName",
                "required_value": "default",
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "low",
                "message": "Pods should use a dedicated service account, not the default one.",
                "fix": "Create a minimal service account and set serviceAccountName.",
                "languages": ["go"],
            },
            {
                "id": "k8s-default-namespace",
                "name": "Resource in Default Namespace",
                "type": "content_not_contains",
                "pattern": r"namespace:\s*default",
                "paths": ["**/*.yaml", "**/*.yml"],
                "severity": "low",
                "message": "Resources should be deployed to a dedicated namespace, not 'default'.",
                "fix": "Set namespace to a project-specific namespace.",
                "languages": ["go"],
            },
            {
                "id": "docker-root-user",
                "name": "Dockerfile Runs as Root",
                "type": "content_not_contains",
                "pattern": r"^\s*USER\s+\d",
                "paths": ["**/Dockerfile*", "**/*.dockerfile"],
                "severity": "medium",
                "message": "Dockerfile should specify a non-root USER directive.",
                "fix": "Add USER <non-root-uid> before the CMD/ENTRYPOINT.",
                "languages": [],
            },
            {
                "id": "docker-add-apt-key-deprecated",
                "name": "Deprecated apt-key in Dockerfile",
                "type": "content_contains",
                "pattern": r"apt-key\s+add",
                "paths": ["**/Dockerfile*", "**/*.dockerfile"],
                "severity": "low",
                "message": "apt-key is deprecated. Use /usr/share/keyrings/ instead.",
                "fix": "Replace apt-key add with a keyring file in /usr/share/keyrings/.",
                "languages": [],
            },
        ]

    def _detect_repo_languages(self, context: ScanContext) -> None:
        self._repo_languages = set()
        self._repo_file_count = -1
        scan_path = context.resolved_path
        profile = getattr(context, "profile", None)
        if profile:
            if hasattr(profile, "languages") and profile.languages:
                self._repo_languages = {lang.lower() for lang in profile.languages}
            if hasattr(profile, "file_count"):
                self._repo_file_count = profile.file_count
            if self._repo_languages and self._repo_file_count >= 0:
                return
        ext_counts: dict[str, int] = {}
        sample_limit = 500
        file_count_limit = 2000
        sample_count = 0
        self._repo_file_count = 0
        for file_path in scan_path.rglob("*"):
            if not file_path.is_file():
                continue
            self._repo_file_count += 1
            if self._repo_file_count >= file_count_limit:
                break
            if sample_count >= sample_limit:
                continue
            ext = file_path.suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                sample_count += 1
        for lang, exts in self.LANG_EXT_MAP.items():
            for ext in exts:
                if ext_counts.get(ext, 0) > 3:
                    self._repo_languages.add(lang)
                    break
        if list(scan_path.glob("**/*.tf")):
            self._repo_languages.add("terraform")
        if list(scan_path.glob("**/Chart.yaml")):
            self._repo_languages.add("helm")
        if list(scan_path.glob("**/Dockerfile*")):
            self._repo_languages.add("docker")

    def _rule_applies_to_repo(self, rule: dict[str, Any]) -> bool:
        if self._repo_languages:
            rule_langs = rule.get("languages", [])
            if rule_langs:
                rule_lang_set = {lang.lower() for lang in rule_langs}
                if rule_lang_set.isdisjoint(self._repo_languages):
                    return False
        min_files = rule.get("min_file_count")
        return not (
            min_files is not None
            and self._repo_file_count >= 0
            and self._repo_file_count < min_files
        )

    def _load_rules(self) -> None:
        for directory in [self.policies_dir, self.auto_policies_dir]:
            if not directory.exists():
                continue
            for extension in ("*.yml", "*.yaml"):
                for yaml_file in directory.glob(extension):
                    try:
                        content = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                        if content and "rules" in content:
                            for rule in content["rules"]:
                                if self._rule_applies_to_repo(rule):
                                    self.rules.append(rule)
                    except (yaml.YAMLError, OSError) as e:
                        logger.warning("Failed to load policy %s: %s", yaml_file, e)

    def _is_non_production_path(self, rel_path: str) -> bool:
        parts = Path(rel_path).parts
        return any(part.lower() in self.NON_PROD_SEGMENTS for part in parts)

    def _is_policy_definition_path(self, rel_path: str, scan_path: Path | None = None) -> bool:
        """Return True only for Seraph policy control-plane files."""
        normalized = Path(rel_path).as_posix().lstrip("./").rstrip("/")
        roots: set[str] = {"policies/builtin", "policies/auto-generated"}

        for directory in (self.policies_dir, self.auto_policies_dir):
            root_path = Path(directory)

            if root_path.is_absolute() and scan_path is not None:
                try:
                    root_path = root_path.resolve().relative_to(scan_path.resolve())
                except ValueError:
                    continue

            root = root_path.as_posix().lstrip("./").rstrip("/")
            if root:
                roots.add(root)

        return any(normalized == root or normalized.startswith(root + "/") for root in roots)

    def _is_build_tool(self, rel_path: str) -> bool:
        return Path(rel_path).name.lower() in self.BUILD_TOOL_FILES

    @staticmethod
    def _python_qualified_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = PolicyScanner._python_qualified_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    @staticmethod
    def _python_source_line(source: str, line_number: int) -> str:
        lines = source.splitlines()
        return lines[line_number - 1].strip()[:200] if 0 < line_number <= len(lines) else ""

    @staticmethod
    def _python_hash_is_non_security(node: ast.Call) -> bool:
        return any(
            keyword.arg == "usedforsecurity"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is False
            for keyword in node.keywords
        )

    @staticmethod
    def _python_sql_expression_is_unsafe(node: ast.AST) -> bool:
        if isinstance(node, ast.JoinedStr):
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"
        ):
            receiver = node.func.value
            if isinstance(receiver, ast.Constant) and isinstance(receiver.value, str):
                text = receiver.value.upper()
                return any(
                    token in text
                    for token in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "FROM ", "WHERE ")
                )
        return any(
            PolicyScanner._python_sql_expression_is_unsafe(child)
            for child in ast.iter_child_nodes(node)
        )

    @classmethod
    def _python_semantic_matches(
        cls, rule: dict[str, Any], content: str
    ) -> list[tuple[int, str]] | None:
        """Use Python AST semantics for rules where lexical matching is unsafe."""
        rule_id = str(rule.get("id", ""))
        supported = {
            "no-eval-in-production",
            "no-runtime-compile",
            "no-pickle-loads-untrusted",
            "no-unsafe-pickle-in-ml-pipeline",
            "no-yaml-unsafe-load",
            "no-weak-hash-md5-sha1",
            "no-orm-raw-sql-with-format",
            "no-hardcoded-passwords-source",
        }
        if rule_id not in supported:
            return None
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        matches: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if rule_id == "no-hardcoded-passwords-source":
                if isinstance(node, ast.Assign):
                    targets = [target for target in node.targets if isinstance(target, ast.Name)]
                    value = node.value
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    targets = [node.target]
                    if node.value is None:
                        continue
                    value = node.value
                else:
                    continue
                if (
                    not isinstance(value, ast.Constant)
                    or not isinstance(value.value, str)
                    or not value.value.strip()
                ):
                    continue
                for target in targets:
                    if re.search(
                        r"(password|passwd|pwd|passphrase|secret|api[_-]?key|token|auth)",
                        target.id,
                        re.IGNORECASE,
                    ):
                        normalized = re.sub(r"[^a-z0-9]+", "_", value.value.lower()).strip("_")
                        if normalized in {
                            "password",
                            "passwd",
                            "pwd",
                            "passphrase",
                            "secret",
                            "api_key",
                            "apikey",
                            "token",
                            "auth",
                            "basic_auth",
                            "credential",
                            "credentials",
                            "jwt_secret",
                            "secret_key",
                        } or normalized == re.sub(r"[^a-z0-9]+", "_", target.id.lower()).strip("_"):
                            continue
                        matches.append((node.lineno, cls._python_source_line(content, node.lineno)))
                continue

            if not isinstance(node, ast.Call):
                continue
            qname = cls._python_qualified_name(node.func)
            line = node.lineno

            if (
                (
                    rule_id == "no-eval-in-production"
                    and qname in {"eval", "exec", "builtins.eval", "builtins.exec"}
                )
                or (rule_id == "no-runtime-compile" and qname == "compile")
                or (
                    rule_id
                    in {
                        "no-pickle-loads-untrusted",
                        "no-unsafe-pickle-in-ml-pipeline",
                    }
                    and qname in {"pickle.load", "pickle.loads"}
                )
            ):
                matches.append((line, cls._python_source_line(content, line)))
            elif rule_id == "no-yaml-unsafe-load" and qname == "yaml.load":
                loader = next((kw.value for kw in node.keywords if kw.arg == "Loader"), None)
                if loader is None or cls._python_qualified_name(loader) not in {
                    "SafeLoader",
                    "yaml.SafeLoader",
                }:
                    matches.append((line, cls._python_source_line(content, line)))
            elif rule_id == "no-weak-hash-md5-sha1" and qname in {
                "hashlib.md5",
                "hashlib.sha1",
                "md5",
                "sha1",
            }:
                if not cls._python_hash_is_non_security(node):
                    matches.append((line, cls._python_source_line(content, line)))
            elif rule_id == "no-orm-raw-sql-with-format":
                terminal = qname.rsplit(".", 1)[-1] if qname else ""
                if (
                    (qname in {"session.execute", "db.execute", "text"} or terminal == "raw")
                    and node.args
                    and cls._python_sql_expression_is_unsafe(node.args[0])
                ):
                    matches.append((line, cls._python_source_line(content, line)))

        return matches

    def _check_rule(self, rule: dict[str, Any], scan_path: Path) -> list[Finding]:
        findings: list[Finding] = []
        rule_type = rule.get("type", "file_exists")
        try:
            severity = Severity(rule.get("severity", "medium").lower())
        except ValueError:
            severity = Severity.MEDIUM
        if rule_type == "file_exists":
            findings = self._check_file_exists(rule, scan_path, severity)
        elif rule_type == "file_not_exists":
            findings = self._check_file_not_exists(rule, scan_path, severity)
        elif rule_type == "content_not_contains":
            findings = self._check_content_not_contains(rule, scan_path, severity)
        elif rule_type == "content_contains":
            findings = self._check_content_contains(rule, scan_path, severity)
        elif rule_type == "hcl_attribute_value":
            findings = self._check_hcl_attribute_value(rule, scan_path, severity)
        elif rule_type == "yaml_attribute_value":
            findings = self._check_yaml_attribute_value(rule, scan_path, severity)
        return findings

    def _parse_hcl(self, file_path: Path) -> dict[str, Any] | None:
        if not HAS_HCL2:
            return None
        try:
            with file_path.open("r", encoding="utf-8") as f:
                return cast("dict[str, Any]", hcl2.load(f))
        except Exception as e:
            logger.debug("Failed to parse HCL file %s: %s", file_path, e)
            return None

    def _parse_yaml_all(self, file_path: Path) -> list[Any]:
        try:
            return list(yaml.safe_load_all(file_path.read_text(encoding="utf-8")))
        except Exception:
            return []

    def _find_yaml_values(self, obj: Any, key: str) -> list[Any]:
        values: list[Any] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == key:
                    values.append(v)
                values.extend(self._find_yaml_values(v, key))
        elif isinstance(obj, list):
            for item in obj:
                values.extend(self._find_yaml_values(item, key))
        return values

    def _get_hcl_attribute(self, body: dict[str, Any], attribute: str) -> Any:
        if attribute in body:
            val = body[attribute]
            if isinstance(val, list) and len(val) == 1:
                return val[0]
            return val
        for val in body.values():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and attribute in item:
                        attr_val = item[attribute]
                        if isinstance(attr_val, list) and len(attr_val) == 1:
                            return attr_val[0]
                        return attr_val
        return None

    def _check_hcl_attribute_value(
        self, rule: dict[str, Any], scan_path: Path, severity: Severity
    ) -> list[Finding]:
        if not HAS_HCL2:
            logger.warning(
                "python-hcl2 not installed — skipping HCL rules. Install with: pip install python-hcl2"
            )
            return []
        findings: list[Finding] = []
        resource_type = rule.get("resource_type", "")
        attribute = rule.get("attribute", "")
        forbidden_values = rule.get("forbidden_values", [])
        required_value = rule.get("required_value")
        paths = rule.get("paths", ["**/*.tf"])
        for path_pattern in paths:
            for file_path in scan_path.glob(path_pattern):
                if not file_path.is_file() or not self.should_scan_file(file_path):
                    continue
                try:
                    rel = str(file_path.relative_to(scan_path))
                except ValueError:
                    continue
                if self._is_non_production_path(rel) or self._is_policy_definition_path(rel):
                    continue
                hcl_dict = self._parse_hcl(file_path)
                if not hcl_dict:
                    continue
                resources = hcl_dict.get("resource", [])
                if not isinstance(resources, list):
                    continue
                for res_list in resources:
                    if not isinstance(res_list, dict):
                        continue
                    for res_type, res_instances in res_list.items():
                        if resource_type and res_type != resource_type:
                            continue
                        if not isinstance(res_instances, list):
                            continue
                        for res_instance in res_instances:
                            if not isinstance(res_instance, dict):
                                continue
                            for res_name, res_body in res_instance.items():
                                if not isinstance(res_body, dict):
                                    continue
                                attr_val = self._get_hcl_attribute(res_body, attribute)
                                if attr_val is None:
                                    continue
                                is_violation = False
                                if forbidden_values:
                                    check_val = attr_val
                                    if isinstance(check_val, list):
                                        is_violation = any(v in forbidden_values for v in check_val)
                                    else:
                                        is_violation = check_val in forbidden_values
                                if required_value is not None and attr_val != required_value:
                                    is_violation = True
                                if is_violation:
                                    findings.append(
                                        Finding(
                                            scanner=self.name,
                                            category=Category.POLICY,
                                            severity=severity,
                                            confidence=0.95,
                                            file=rel,
                                            line=0,
                                            title=f"IaC Violation: {rule.get('name', rule.get('id'))}",
                                            description=rule.get("message", ""),
                                            evidence=f"{res_type}.{res_name}.{attribute} = {attr_val}",
                                            fix_available=True,
                                            fix_command=rule.get("fix", ""),
                                            metadata={
                                                "rule_id": rule.get("id"),
                                                "iac_type": "terraform",
                                            },
                                        )
                                    )
        return findings

    def _check_yaml_attribute_value(
        self, rule: dict[str, Any], scan_path: Path, severity: Severity
    ) -> list[Finding]:
        findings: list[Finding] = []
        attribute_path = rule.get("attribute_path", "")
        forbidden_values = rule.get("forbidden_values", [])
        required_value = rule.get("required_value")
        paths = rule.get("paths", ["**/*.yaml", "**/*.yml"])
        leaf_key = attribute_path.split(".")[-1] if attribute_path else ""
        if not leaf_key:
            return findings
        for path_pattern in paths:
            for file_path in scan_path.glob(path_pattern):
                if not file_path.is_file() or not self.should_scan_file(file_path):
                    continue
                try:
                    rel = str(file_path.relative_to(scan_path))
                except ValueError:
                    continue
                if self._is_non_production_path(rel) or self._is_policy_definition_path(rel):
                    continue
                docs = self._parse_yaml_all(file_path)
                if not docs:
                    continue
                for doc in docs:
                    if not isinstance(doc, dict):
                        continue
                    matches = self._find_yaml_values(doc, leaf_key)
                    for val in matches:
                        is_violation = False
                        if forbidden_values and val in forbidden_values:
                            is_violation = True
                        if required_value is not None and val != required_value:
                            is_violation = True
                        if is_violation:
                            findings.append(
                                Finding(
                                    scanner=self.name,
                                    category=Category.POLICY,
                                    severity=severity,
                                    confidence=0.95,
                                    file=rel,
                                    line=0,
                                    title=f"IaC Violation: {rule.get('name', rule.get('id'))}",
                                    description=rule.get("message", ""),
                                    evidence=f"{leaf_key}: {val}",
                                    fix_available=True,
                                    fix_command=rule.get("fix", ""),
                                    metadata={"rule_id": rule.get("id"), "iac_type": "kubernetes"},
                                )
                            )
                            break
        return findings

    def _check_file_exists(
        self, rule: dict[str, Any], scan_path: Path, severity: Severity
    ) -> list[Finding]:
        paths = rule.get("paths", rule.get("files", []))
        if not paths:
            return []
        rule_langs = {lang.lower() for lang in rule.get("languages", [])}
        if rule_langs and self._repo_languages and rule_langs.isdisjoint(self._repo_languages):
            return []
        for pattern in paths:
            if list(scan_path.glob(pattern)):
                return []
        return [
            Finding(
                scanner=self.name,
                category=Category.POLICY,
                severity=Severity.INFO,
                confidence=1.0,
                file=paths[0] if paths else "(unknown)",
                line=0,
                title="Missing: " + rule.get("name", rule.get("id", "unknown")),
                description=rule.get("message", "Required file not found"),
                evidence="",
                fix_available=True,
                fix_command=rule.get("fix", "Create the required file"),
                blast_radius=BlastRadius(
                    blast_radius_score=severity.weight * 0.5,
                    reduction_if_fixed=severity.weight * 0.4,
                    is_assessed=True,
                ),
                metadata={"rule_id": rule.get("id"), "policy_name": rule.get("name")},
            )
        ]

    def _check_file_not_exists(
        self, rule: dict[str, Any], scan_path: Path, severity: Severity
    ) -> list[Finding]:
        findings: list[Finding] = []
        forbidden = rule.get("files", rule.get("paths", []))
        for pattern in forbidden:
            for match in scan_path.glob(pattern):
                try:
                    rel_parts = match.relative_to(scan_path).parts
                except ValueError:
                    rel_parts = match.parts
                if any(part in self.IGNORE_DIRS for part in rel_parts):
                    continue
                try:
                    rel = str(match.relative_to(scan_path))
                except ValueError:
                    rel = str(match)
                if self._is_non_production_path(rel):
                    continue
                findings.append(
                    Finding(
                        scanner=self.name,
                        category=Category.POLICY,
                        severity=severity,
                        confidence=1.0,
                        file=rel,
                        line=0,
                        title="Forbidden file: " + match.name,
                        description=rule.get("message", "File violates policy"),
                        evidence=str(match),
                        fix_available=True,
                        fix_command="Remove: " + rel,
                        metadata={"rule_id": rule.get("id")},
                    )
                )
        return findings

    def _check_content_not_contains(
        self, rule: dict[str, Any], scan_path: Path, severity: Severity
    ) -> list[Finding]:
        findings: list[Finding] = []
        pattern = rule.get("pattern", "")
        paths = rule.get("paths", ["**/*.py", "**/*.js", "**/*.ts"])
        if not pattern:
            return findings
        try:
            regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        except re.error:
            return findings
        for path_pattern in paths:
            for file_path in scan_path.glob(path_pattern):
                if not file_path.is_file() or not self.should_scan_file(file_path):
                    continue
                try:
                    rel_parts = file_path.relative_to(scan_path).parts
                except ValueError:
                    continue
                if any(part in self.IGNORE_DIRS for part in rel_parts):
                    continue
                try:
                    rel = str(file_path.relative_to(scan_path))
                except ValueError:
                    rel = str(file_path)
                if (
                    self._is_non_production_path(rel)
                    or self._is_build_tool(rel)
                    or self._is_policy_definition_path(rel, scan_path)
                ):
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except (OSError, UnicodeDecodeError):
                    continue

                if file_path.suffix.lower() == ".py":
                    semantic_matches = self._python_semantic_matches(rule, content)
                    if semantic_matches is not None:
                        if not semantic_matches:
                            continue
                        match_line_num, line_text = semantic_matches[0]
                        findings.append(
                            Finding(
                                scanner=self.name,
                                category=Category.POLICY,
                                severity=severity,
                                confidence=float(rule.get("confidence", 0.95)),
                                file=rel,
                                line=match_line_num,
                                title="Policy violation: " + rule.get("name", rule.get("id", "")),
                                description=rule.get("message", "Pattern matched"),
                                evidence=line_text,
                                fix_available=True,
                                fix_command=rule.get("fix", "Remove the matched pattern"),
                                metadata={
                                    "rule_id": rule.get("id"),
                                    "pattern": pattern,
                                    "match_engine": "python-ast",
                                },
                            )
                        )
                        break

                if regex.search(content):
                    match_line_num = 1
                    line_text = content.splitlines()[0] if content.splitlines() else ""
                    for idx, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            line_text = line
                            match_line_num = idx
                            break
                    line_stripped = line_text.strip().lower()
                    if line_stripped.startswith(("//", "#", "/*", "*", "'", '"', "`")):
                        continue
                    findings.append(
                        Finding(
                            scanner=self.name,
                            category=Category.POLICY,
                            severity=severity,
                            confidence=0.95,
                            file=rel,
                            line=match_line_num,
                            title="Policy violation: " + rule.get("name", rule.get("id", "")),
                            description=rule.get("message", "Pattern matched"),
                            evidence=line_text.strip()[:200],
                            fix_available=True,
                            fix_command=rule.get("fix", "Remove the matched pattern"),
                            metadata={"rule_id": rule.get("id"), "pattern": pattern},
                        )
                    )
                    break
        return findings

    def _check_content_contains(
        self, rule: dict[str, Any], scan_path: Path, severity: Severity
    ) -> list[Finding]:
        pattern = rule.get("pattern", "")
        paths = rule.get("paths", ["**/*"])
        if not pattern:
            return []
        try:
            regex = re.compile(pattern)
        except re.error:
            return []
        relevant_files_exist = any(list(scan_path.glob(path_pattern)) for path_pattern in paths)
        if not relevant_files_exist:
            return []
        for path_pattern in paths:
            for file_path in scan_path.glob(path_pattern):
                if not file_path.is_file():
                    continue
                try:
                    rel_parts = file_path.relative_to(scan_path).parts
                    if any(part in self.IGNORE_DIRS for part in rel_parts):
                        continue
                    rel = str(file_path.relative_to(scan_path))
                    if self._is_non_production_path(rel) or self._is_policy_definition_path(rel):
                        continue
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if regex.search(content):
                        return []
                except (OSError, UnicodeDecodeError, ValueError):
                    continue
        return [
            Finding(
                scanner=self.name,
                category=Category.POLICY,
                severity=Severity.INFO,
                confidence=0.9,
                file="(repository)",
                line=0,
                title="Missing: " + rule.get("name", rule.get("id", "")),
                description=rule.get("message", "Required pattern not found"),
                evidence="",
                metadata={"rule_id": rule.get("id")},
            )
        ]
