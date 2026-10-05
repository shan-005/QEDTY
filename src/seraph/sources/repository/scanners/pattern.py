"""Seraph Guard pattern scanner.

The scanner is intentionally repository-agnostic.  It detects concrete,
security-sensitive operations (sinks and dangerous APIs) while leaving
source-to-sink reachability to :mod:`seraph.sources.repository.scanners.taint` and policy
reasoning to the Scheduler's cognition layer.

Design goals
------------
* Python uses the stdlib ``ast`` parser, with import/alias resolution.
* Other supported languages use Tree-sitter when available and a conservative
  lexical fallback when it is not.
* Test/example/build/framework code is scanned; Seraph's Scheduler decides
  production severity/suppression from ``Finding.file_context``.
* Learning state is read-only here. PatternScanner never writes suppressions.
* CWE metadata is explicit when the API maps cleanly to a CWE.
* No blanket keyword rules for libraries such as ``ldap``, ``random``, XML, or
  SQL are used: importing a library is not itself a vulnerability.

This is a sink detector, not a substitute for data-flow analysis.  A finding
such as ``pickle.loads(data)`` means that an unsafe deserialization sink exists;
TaintScanner is responsible for proving that untrusted data reaches it.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import importlib
import json
import logging
import os
import re

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar, override

from seraph.sources.repository.scanners.base import Category, Finding, ScanContext, Scanner, Severity


_STAR_IMPORT = "*"


_pack_module: Any | None = None
try:
    _pack_module = importlib.import_module("tree_sitter_language_pack")
except ImportError:
    _pack_module = None

_pack_get_parser: Callable[[str], Any] | None = (
    getattr(_pack_module, "get_parser", None) if _pack_module is not None else None
)
_pack_has_parser: Callable[[str], bool] | None = (
    getattr(_pack_module, "has_parser", None) if _pack_module is not None else None
)
_HAS_TS_PACK = callable(_pack_get_parser) and callable(_pack_has_parser)


tree_sitter_languages: Any | None = None
try:
    tree_sitter_languages = importlib.import_module("tree_sitter_languages")
except ImportError:
    tree_sitter_languages = None

_HAS_TS_LEGACY = tree_sitter_languages is not None and callable(
    getattr(tree_sitter_languages, "get_parser", None)
)

_HAS_TREE_SITTER = _HAS_TS_PACK or _HAS_TS_LEGACY

logger = logging.getLogger(__name__)


# ============================================================================
# File discovery
# ============================================================================

ALLOWED_EXTENSIONS: set[str] = {
    ".py",
    ".pyi",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".mjs",
    ".cjs",
    ".mts",
    ".cts",
    ".vue",
    ".svelte",
    ".astro",
    ".rb",
    ".go",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".groovy",
    ".gradle",
    ".dart",
    ".cs",
    ".cshtml",
    ".vb",
    ".vbs",
    ".php",
    ".sh",
    ".bash",
    ".zsh",
    ".csh",
    ".ksh",
    ".ps1",
    ".psm1",
    ".c",
    ".cc",
    ".cp",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".m",
    ".mm",
    ".rs",
    ".swift",
    ".r",
    ".pl",
    ".pm",
    ".lua",
    ".fs",
    ".fsx",
    ".ex",
    ".exs",
    ".erl",
    ".hrl",
    ".zig",
    ".nim",
    ".v",
    ".sol",
    ".sql",
    ".graphql",
    ".gql",
}

# Dependency/cache/artifact directories.  Do NOT put test/example/benchmark
# directories here; those are legitimate analysis targets and are suppressed
# later by the Scheduler according to file_context.
SKIP_DIRS: set[str] = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".nox",
    ".eggs",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".seraph-cache",
    ".seraph-learn",
    "node_modules",
    "bower_components",
    "vendor",
    "vendors",
    "third_party",
    "third-party",
    "site-packages",
    "dist-packages",
    "dist",
    "out",
    "target",
    ".next",
    ".nuxt",
    ".turbo",
    ".parcel-cache",
    ".cache",
    "coverage",
    "htmlcov",
    ".idea",
    ".vscode",
}

SKIP_EXTENSIONS: set[str] = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    ".sqlite",
    ".db",
    ".lock",
    ".sum",
    ".map",
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".whl",
    ".egg",
    ".o",
    ".a",
    ".rlib",
}

GENERATED_CODE_PATTERNS: set[str] = {
    "*.pb.go",
    "*_gen.go",
    "zz_generated*.go",
    "deepcopy*.go",
    "*.gen.go",
    "*_generated.go",
    "*.pb.cc",
    "*.pb.h",
    "*.grpc.pb.go",
    "*_pb2.py",
    "*_pb2_grpc.py",
    "*_pb2.pyi",
    "*.generated.ts",
    "*.generated.tsx",
    "*.generated.js",
    "*.generated.jsx",
    "*.generated.rs",
    "*_generated.tsx",
    "*.generated.kt",
    "*.generated.swift",
}

# Compatibility constants retained for existing tests/callers.  These are
# contextual signals, not broad suppression lists.
NON_PROD_SEGMENTS: set[str] = {
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
    "testing",
    "example",
    "examples",
    "demo",
    "demos",
    "benchmark",
    "benchmarks",
    "perf",
    "performance",
    "docs",
    "doc",
    "documentation",
    "build",
    "dist",
    "out",
    "target",
    "compiled",
}

NON_PROD_FILENAME_PREFIXES = (
    "run-tests.",
    "run-test.",
    "run-evals.",
    "run-eval.",
    "test-runner.",
    "test-helper.",
)

NON_PROD_FILENAME_PATTERNS = (".test.", ".spec.", "_test.", "_spec.")

BUILD_CONFIG_ALLOWLIST = {
    "webpack.config.js",
    "vite.config.ts",
    "rollup.config.js",
    "rollup.config.ts",
    "babel.config.js",
    "jest.config.js",
    "next.config.js",
    "next.config.ts",
    "tsup.config.ts",
    "esbuild.config.js",
    "gulpfile.js",
    "gruntfile.js",
    "vitest.config.ts",
    "playwright.config.ts",
    "cypress.config.ts",
    "tailwind.config.js",
    "postcss.config.js",
    "taskfile.js",
    "taskfile.ts",
}

AUTOTOOLS_ALLOWLIST = {
    "ltmain.sh",
    "configure",
    "config.sub",
    "config.guess",
    "aclocal.m4",
    "compile",
    "depcomp",
    "install-sh",
    "missing",
    "ylwrap",
    "test-driver",
    "ar-lib",
    "mkinstalldirs",
}

# This set is used only to tell the fixer that security patterns are not safe
# for automatic rewriting.
UNFIXABLE_PATTERN_FRAGMENTS = {
    "eval",
    "exec",
    "system",
    "subprocess",
    "os.system",
    "os.popen",
    "exec.command",
    "pickle",
    "marshal",
    "yaml.",
    "child_process",
    "innerhtml",
    "outerhtml",
    "document.write",
    "dangerouslysetinnerhtml",
    "shell_exec",
    "passthru",
    "instance_eval",
    "runtime.getruntime",
    "objectinputstream",
    "unserialize",
    "tempfile.mktemp",
    "gets(",
    "strcpy(",
    "strcat(",
    "sprintf(",
    "vsprintf(",
}


# ============================================================================
# Python rule helpers
# ============================================================================

PY_EVAL = r"\beval\s*\("
PY_EXEC = r"\bexec\s*\("
PY_COMPILE = r"\bcompile\s*\("
PY_IMPORT = r"\b__import__\s*\("
PY_OS_SYSTEM = r"\bos\.system\s*\("
PY_OS_POPEN = r"\bos\.popen\s*\("
PY_SUBPROCESS = (
    r"\bsubprocess\.(?:call|Popen|run|check_call|check_output|getoutput|getstatusoutput)\s*\("
)
PY_PICKLE = r"\bpickle\.(?:load|loads|Unpickler)\s*\("
PY_MARSHAL = r"\bmarshal\.(?:load|loads)\s*\("
PY_YAML = r"\byaml\.(?:load|unsafe_load|full_load)\s*\("
PY_MKTEMP = r"\btempfile\.mktemp\s*\("
PY_TEMPLATE = r"\brender_template_string\s*\("
PY_JINJA_TEMPLATE = r"\b(?:jinja2\.)?Template\s*\("
PY_JINJA_FROM_STRING = r"\b(?:jinja2\.)?Environment\s*\.\s*from_string\s*\("


class _PythonAnalyzer:
    """AST sink detector with scope-aware import resolution."""

    BUILTIN_CALLS: ClassVar[set[str]] = {"eval", "exec", "compile", "__import__"}

    def __init__(self, source: str) -> None:
        self.source = source
        self.tree: ast.Module | None = None
        try:
            self.tree = ast.parse(source)
        except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
            self.tree = None
        self.matches: list[tuple[str, int, str, str]] = []
        self._scope_stack: list[dict[str, str | None]] = []

    def analyze(self) -> list[tuple[str, int, str, str]]:
        tree = self.tree
        if tree is None:
            return []
        self._visit_module(tree)
        return self._dedupe(self.matches)

    def _visit_module(self, node: ast.Module) -> None:
        symbols = self._collect_scope_symbols(node.body, is_module=True, parameters=())
        self._scope_stack.append(symbols)
        try:
            for child in node.body:
                self._visit_node(child)
        finally:
            self._scope_stack.pop()

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        params = tuple(
            arg.arg
            for arg in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            )
        )
        symbols = self._collect_scope_symbols(node.body, is_module=False, parameters=params)
        self._scope_stack.append(symbols)
        try:
            for decorator in node.decorator_list:
                self._visit_node(decorator)
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self._visit_node(default)
            if node.returns is not None:
                self._visit_node(node.returns)
            for child in node.body:
                self._visit_node(child)
        finally:
            self._scope_stack.pop()

    def _visit_class(self, node: ast.ClassDef) -> None:
        symbols = self._collect_scope_symbols(node.body, is_module=False, parameters=())
        self._scope_stack.append(symbols)
        try:
            for decorator in node.decorator_list:
                self._visit_node(decorator)
            for base in node.bases:
                self._visit_node(base)
            for keyword in node.keywords:
                self._visit_node(keyword.value)
            for child in node.body:
                self._visit_node(child)
        finally:
            self._scope_stack.pop()

    def _visit_node(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._visit_function(node)
            return
        if isinstance(node, ast.ClassDef):
            self._visit_class(node)
            return
        if isinstance(node, ast.Call):
            self._inspect_call(node)
        for child in ast.iter_child_nodes(node):
            self._visit_node(child)

    def _inspect_call(self, node: ast.Call) -> None:
        resolved = self._resolve(node.func)
        if not resolved:
            return
        text = _ast_source(node, self.source)
        line = int(getattr(node, "lineno", 1) or 1)

        if resolved in {"eval", "builtins.eval"}:
            if node.args and not _python_is_constant(node.args[0]):
                self.matches.append((PY_EVAL, line, text, resolved))
            return

        if resolved in {"exec", "builtins.exec"}:
            if node.args and not _python_is_constant(node.args[0]):
                self.matches.append((PY_EXEC, line, text, resolved))
            return

        if resolved in {"compile", "builtins.compile"}:
            if node.args and not _python_is_constant(node.args[0]):
                self.matches.append((PY_COMPILE, line, text, resolved))
            return

        if resolved in {"__import__", "builtins.__import__"}:
            if node.args and not _python_is_constant(node.args[0]):
                self.matches.append((PY_IMPORT, line, text, resolved))
            return

        if resolved in {"os.system", "os.popen"}:
            pattern = PY_OS_SYSTEM if resolved == "os.system" else PY_OS_POPEN
            self.matches.append((pattern, line, text, resolved))
            return

        if resolved.startswith("subprocess."):
            method = resolved.rsplit(".", 1)[-1]
            if method in {
                "call",
                "Popen",
                "run",
                "check_call",
                "check_output",
                "getoutput",
                "getstatusoutput",
            } and _python_shell_is_enabled(node):
                self.matches.append((PY_SUBPROCESS, line, text, resolved))
            return

        if resolved in {
            "asyncio.create_subprocess_shell",
            "asyncio.subprocess.create_subprocess_shell",
        }:
            self.matches.append(
                (r"\basyncio\.(?:subprocess\.)?create_subprocess_shell\s*\(", line, text, resolved)
            )
            return

        if resolved.startswith("pickle.") and resolved.rsplit(".", 1)[-1] in {
            "load",
            "loads",
            "Unpickler",
        }:
            self.matches.append((PY_PICKLE, line, text, resolved))
            return

        if resolved in {"marshal.load", "marshal.loads"}:
            self.matches.append((PY_MARSHAL, line, text, resolved))
            return

        if resolved.startswith("yaml.") and resolved.rsplit(".", 1)[-1] in {
            "load",
            "unsafe_load",
            "full_load",
        }:
            if _python_yaml_call_is_safe(node, self._scope_aliases()):
                return
            self.matches.append((PY_YAML, line, text, resolved))
            return

        if resolved == "tempfile.mktemp":
            self.matches.append((PY_MKTEMP, line, text, resolved))
            return

        if resolved.endswith(".render_template_string"):
            self.matches.append((PY_TEMPLATE, line, text, resolved))
            return

        if resolved in {"jinja2.Template", "Template"}:
            if node.args and not _python_is_constant(node.args[0]):
                self.matches.append((PY_JINJA_TEMPLATE, line, text, resolved))
            return

        if (
            resolved in {"jinja2.Environment.from_string", "Environment.from_string"}
            and node.args
            and not _python_is_constant(node.args[0])
        ):
            self.matches.append((PY_JINJA_FROM_STRING, line, text, resolved))

    def _resolve(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self._resolve_name(node.id)
        if isinstance(node, ast.Attribute):
            prefix = self._resolve(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return ""

    def _resolve_name(self, name: str) -> str:
        for scope in reversed(self._scope_stack):
            if name in scope:
                target = scope[name]
                # A local/module binding with no import target shadows a
                # builtin. Returning an empty string prevents a user-defined
                # function named ``eval``/``exec`` from being misclassified as
                # the Python builtin sink.
                return target or ""
        if name in self.BUILTIN_CALLS:
            return f"builtins.{name}"
        return name

    def _scope_aliases(self) -> dict[str, str]:
        return {
            name: target for scope in self._scope_stack for name, target in scope.items() if target
        }

    @classmethod
    def _collect_scope_symbols(
        cls,
        body: list[ast.stmt],
        *,
        is_module: bool,
        parameters: tuple[str, ...],
    ) -> dict[str, str | None]:
        symbols: dict[str, str | None] = dict.fromkeys(parameters)

        def bind_target(target: ast.AST) -> None:
            if isinstance(target, ast.Name):
                symbols.setdefault(target.id, None)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    bind_target(elt)
            elif isinstance(target, ast.Starred):
                bind_target(target.value)

        def walk_statements(statements: list[ast.stmt]) -> None:
            for statement in statements:
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.setdefault(statement.name, None)
                    continue
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    if isinstance(statement, ast.Import):
                        for alias in statement.names:
                            bound = alias.asname or alias.name.split(".", 1)[0]
                            symbols[bound] = alias.name
                    else:
                        module = statement.module or ""
                        for alias in statement.names:
                            if alias.name == _STAR_IMPORT:
                                continue
                            bound = alias.asname or alias.name
                            symbols[bound] = f"{module}.{alias.name}" if module else alias.name
                    continue
                if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    if isinstance(statement, ast.Assign):
                        for target in statement.targets:
                            bind_target(target)
                    else:
                        bind_target(statement.target)
                elif isinstance(statement, (ast.For, ast.AsyncFor)):
                    bind_target(statement.target)
                    walk_statements(statement.body)
                    walk_statements(statement.orelse)
                elif isinstance(statement, (ast.While, ast.If)):
                    walk_statements(statement.body)
                    walk_statements(statement.orelse)
                elif isinstance(statement, ast.Try):
                    walk_statements(statement.body)
                    walk_statements(statement.orelse)
                    walk_statements(statement.finalbody)
                    for handler in statement.handlers:
                        if handler.name:
                            symbols.setdefault(handler.name, None)
                        walk_statements(handler.body)
                elif isinstance(statement, (ast.With, ast.AsyncWith)):
                    for item in statement.items:
                        if item.optional_vars is not None:
                            bind_target(item.optional_vars)
                    walk_statements(statement.body)
                elif isinstance(statement, ast.Match):
                    for case in statement.cases:
                        walk_statements(case.body)

        walk_statements(body)
        if not is_module:
            # Parameters take precedence over imports/assignments in their scope.
            for name in parameters:
                symbols[name] = None
        return symbols

    @staticmethod
    def _dedupe(
        matches: list[tuple[str, int, str, str]],
    ) -> list[tuple[str, int, str, str]]:
        seen: set[tuple[str, int, str]] = set()
        result: list[tuple[str, int, str, str]] = []
        for match in matches:
            key = (match[0], match[1], match[3])
            if key not in seen:
                seen.add(key)
                result.append(match)
        return result


# ============================================================================
# Tree-sitter adapter for non-Python languages
# ============================================================================


class TreeSitterAnalyzer:
    """AST-based matching adapter for languages supported by Tree-sitter."""

    LANG_MAP: ClassVar[dict[str, str]] = {
        "javascript": "javascript",
        "typescript": "typescript",
        "go": "go",
        "ruby": "ruby",
        "php": "php",
        "java": "java",
        "kotlin": "kotlin",
        "scala": "scala",
        "groovy": "groovy",
        "dart": "dart",
        "csharp": "c_sharp",
        "visualbasic": "visual_basic",
        "shell": "bash",
        "powershell": "powershell",
        "c": "c",
        "cpp": "cpp",
        "rust": "rust",
        "swift": "swift",
        "fsharp": "fsharp",
        "r": "r",
        "perl": "perl",
        "lua": "lua",
        "elixir": "elixir",
        "erlang": "erlang",
        "zig": "zig",
        "nim": "nim",
        "solidity": "solidity",
        "sql": "sql",
        "graphql": "graphql",
    }

    def __init__(self) -> None:
        self.available = _HAS_TREE_SITTER
        if _HAS_TS_PACK:
            logger.debug("Tree-sitter language pack available")
        elif _HAS_TS_LEGACY:
            logger.debug("Legacy tree-sitter-languages available")
        else:
            logger.info("No Tree-sitter backend installed; using lexical fallback")

    def parse(self, content: bytes, lang: str) -> Any:
        if not self.available:
            return None
        ts_lang = self.LANG_MAP.get(lang)
        if not ts_lang:
            return None
        if _HAS_TS_PACK and _pack_get_parser is not None and _pack_has_parser is not None:
            try:
                # ``has_parser`` is checked first so a scan never implicitly
                # downloads a grammar from the network.
                if _pack_has_parser(ts_lang):
                    parser = _pack_get_parser(ts_lang)
                    return parser.parse(content)
            except Exception:
                logger.debug(
                    "Tree-sitter language-pack parser unavailable for %s", lang, exc_info=True
                )
        if _HAS_TS_LEGACY and tree_sitter_languages is not None:
            try:
                parser = tree_sitter_languages.get_parser(ts_lang)
                return parser.parse(content)
            except Exception:
                logger.debug("Legacy Tree-sitter parser unavailable for %s", lang, exc_info=True)
        return None

    def find_dangerous_calls(
        self,
        tree: Any,
        lang: str,
        source: str = "",
    ) -> list[tuple[str, int, str, str]]:
        if not tree:
            return []
        aliases = self._collect_aliases(source, lang) if source else {}
        results: list[tuple[str, int, str, str]] = []

        def node_text(node: Any) -> str:
            try:
                raw = node.text
                return raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
            except Exception:
                return ""

        def visit(node: Any) -> None:
            node_type = getattr(node, "type", "")
            text = node_text(node)

            if node_type in {
                "call",
                "call_expression",
                "method_invocation",
                "invocation_expression",
                "function_call_expression",
                "new_expression",
                "command",
            }:
                func_name = self._get_func_name(node, lang)
                if func_name:
                    resolved = self._resolve_alias_text(func_name, aliases)
                    match = self._match_call(resolved, text, lang)
                    pattern = match[0]
                    if pattern is not None and not self._contextual_safe(pattern, text, lang):
                        results.append(
                            (
                                pattern,
                                int(getattr(node, "start_point", (0, 0))[0]) + 1,
                                text.replace("\n", " ").strip()[:500],
                                resolved,
                            )
                        )

            if lang in {"javascript", "typescript"}:
                if node_type in {"assignment_expression", "assignment_pattern"}:
                    left = getattr(node, "child_by_field_name", lambda _name: None)("left")
                    left_text = node_text(left).strip() if left is not None else ""
                    if re.search(r"(?:^|\.)(?:innerHTML|outerHTML)$", left_text):
                        pattern = r"\b(?:innerHTML|outerHTML)\s*="
                        if not self._js_html_is_safe(text):
                            results.append(
                                (
                                    pattern,
                                    int(getattr(node, "start_point", (0, 0))[0]) + 1,
                                    text.replace("\n", " ").strip()[:500],
                                    left_text,
                                )
                            )

                if node_type == "jsx_attribute":
                    attr_name = getattr(node, "child_by_field_name", lambda _name: None)("name")
                    name = node_text(attr_name).strip() if attr_name is not None else ""
                    if name == "dangerouslySetInnerHTML" and not re.search(
                        r"(?:DOMPurify\.sanitize|sanitizeHtml|escapeHtml)",
                        text,
                        re.IGNORECASE,
                    ):
                        results.append(
                            (
                                r"\bdangerouslySetInnerHTML\b",
                                int(getattr(node, "start_point", (0, 0))[0]) + 1,
                                text.replace("\n", " ").strip()[:500],
                                name,
                            )
                        )

            for child in getattr(node, "children", []):
                visit(child)

        visit(getattr(tree, "root_node", None))
        return self._dedupe(results)

    def _get_func_name(self, node: Any, lang: str) -> str:
        try:
            if lang in {"javascript", "typescript", "go"}:
                fn = node.child_by_field_name("function")
                if fn is not None:
                    return self._node_text(fn)
            if lang == "ruby":
                method = node.child_by_field_name("method")
                if method is not None:
                    return self._node_text(method)
            if lang == "php":
                fn = node.child_by_field_name("function")
                if fn is not None:
                    return self._node_text(fn)
            if lang == "java":
                name = node.child_by_field_name("name")
                obj = node.child_by_field_name("object")
                if name is not None:
                    name_text = self._node_text(name)
                    obj_text = self._node_text(obj) if obj is not None else ""
                    return f"{obj_text}.{name_text}" if obj_text else name_text
            if lang in {"c", "cpp", "rust", "swift", "csharp"}:
                fn = node.child_by_field_name("function")
                if fn is not None:
                    return self._node_text(fn)
                fn = node.child_by_field_name("name")
                if fn is not None:
                    return self._node_text(fn)
            if lang == "shell" and getattr(node, "children", None):
                return self._node_text(node.children[0])
        except Exception:
            logger.debug("Tree-sitter function-name extraction failed", exc_info=True)
        return ""

    def _match_call(
        self,
        func_name: str,
        text: str,
        lang: str,
    ) -> tuple[str | None, Severity | None]:
        f = func_name.strip()

        if lang in {"javascript", "typescript"}:
            if f in {"eval", "globalThis.eval", "window.eval"}:
                return PY_EVAL, Severity.HIGH
            if f in {"Function", "window.Function", "globalThis.Function"}:
                return r"\bFunction\s*\(", Severity.HIGH
            if f in {
                "child_process.exec",
                "child_process.execSync",
                "child_process.execFile",
                "child_process.execFileSync",
            }:
                return (
                    r"\bchild_process\.(?:exec|execSync|execFile|execFileSync)\s*\(",
                    Severity.HIGH,
                )
            if f in {"child_process.spawn", "child_process.spawnSync"}:
                if re.search(r"\bshell\s*:\s*true\b", text, re.IGNORECASE):
                    return r"\bchild_process\.(?:spawn|spawnSync)\s*\(", Severity.HIGH
                return None, None
            if f == "document.write":
                return r"\bdocument\.write\s*\(", Severity.MEDIUM
            if f in {"setTimeout", "setInterval"} and re.search(
                r"^\s*\(?\s*['\"]", text.split("(", 1)[1] if "(" in text else "", re.DOTALL
            ):
                return r"\b(?:setTimeout|setInterval)\s*\(\s*['\"]", Severity.HIGH
            if f in {"vm.runInNewContext", "vm.runInThisContext"}:
                return r"\bvm\.runIn(?:NewContext|ThisContext)\s*\(", Severity.HIGH
            if f in {"vm.Script", "new vm.Script"}:
                return r"\bvm\.Script\s*\(", Severity.HIGH
            if f == "insertAdjacentHTML":
                return r"\binsertAdjacentHTML\s*\(", Severity.MEDIUM

        elif lang == "go":
            if f in {"exec.Command", "exec.CommandContext"}:
                if re.search(
                    r"\b(?:sh|bash|zsh|cmd|powershell)(?:\.exe)?['\"]?\s*,\s*['\"]?-c\b",
                    text,
                    re.IGNORECASE,
                ):
                    return r"\bexec\.Command(?:Context)?\s*\(", Severity.HIGH
                # Normal exec.Command is not itself shell injection; don't make
                # every ordinary process launch a vulnerability finding.
                return None, None
            if f == "syscall.Exec":
                return r"\bsyscall\.Exec(?:ve|v)?\s*\(", Severity.MEDIUM
            if f == "os.StartProcess":
                return r"\bos\.StartProcess\s*\(", Severity.MEDIUM

        elif lang == "ruby":
            if f == "eval":
                return PY_EVAL, Severity.HIGH
            if f in {"instance_eval", "class_eval", "module_eval"}:
                return r"\b(?:instance_eval|class_eval|module_eval)\s*\(", Severity.HIGH
            if f in {"system", "Kernel.system", "exec", "Kernel.exec", "spawn", "Kernel.spawn"}:
                return r"\b(?:system|exec|spawn)(?:\.[a-z]+)?\s*\(", Severity.HIGH

        elif lang == "php":
            if f == "eval":
                return PY_EVAL, Severity.HIGH
            if f in {"system", "exec", "passthru", "shell_exec", "popen", "proc_open"}:
                return r"\b(?:system|exec|passthru|shell_exec|popen|proc_open)\s*\(", Severity.HIGH
            if f == "unserialize":
                return r"\bunserialize\s*\(", Severity.HIGH

        elif lang == "java":
            dotted = f.replace(" ", "")
            if "Runtime.getRuntime().exec" in dotted or "getRuntime().exec" in dotted:
                return r"\bRuntime\.getRuntime\(\)\.exec\s*\(", Severity.HIGH
            if dotted.endswith("ProcessBuilder") or f.endswith("ProcessBuilder"):
                return r"\b(?:new\s+)?ProcessBuilder\s*\(", Severity.MEDIUM
            if f.endswith("ScriptEngine.eval") or f == "ScriptEngine.eval":
                return r"\bScriptEngine\b.*\.eval\s*\(", Severity.HIGH
            if f.endswith("readObject") and "ObjectInputStream" in text:
                return r"\bObjectInputStream\b.*\.readObject\s*\(", Severity.MEDIUM

        elif lang == "csharp":
            if f.endswith("Process.Start"):
                return r"\bProcess\.Start\s*\(", Severity.MEDIUM
            if f.endswith("Microsoft.VisualBasic.Interaction.Shell"):
                return r"\b(?:Interaction\.)?Shell\s*\(", Severity.HIGH

        elif lang == "shell":
            if re.search(r"^eval\s+", text.strip()):
                return r"\beval\s+", Severity.HIGH
            if re.search(r"(?:^|\s)(?:bash|sh|zsh|ksh)\s+-c\s+", text):
                return r"\b(?:bash|sh|zsh|ksh)\s+-c\s+", Severity.HIGH

        elif lang in {"c", "cpp"}:
            if f in {"system", "::system"}:
                return r"\bsystem\s*\(", Severity.HIGH
            if f in {"popen", "_popen", "_wpopen"}:
                return r"\b(?:popen|_popen|_wpopen)\s*\(", Severity.HIGH
            if f == "gets":
                return r"\bgets\s*\(", Severity.HIGH
            if f in {"strcpy", "strcat", "sprintf", "vsprintf", "gets"}:
                return r"\b(?:strcpy|strcat|sprintf|vsprintf|gets)\s*\(", Severity.MEDIUM

        return None, None

    def _match_ast_pattern(
        self,
        func_name: str,
        node: Any,
        lang: str,
    ) -> tuple[str | None, Severity | None]:
        """Backward-compatible Tree-sitter matcher entry point.

        Older tests/callers used ``_match_ast_pattern`` directly. Keep that
        surface while using the stricter language-aware matcher internally.
        """
        return self._match_call(func_name, self._node_text(node), lang)

    @staticmethod
    def _node_text(node: Any) -> str:
        try:
            raw = node.text
            return raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
        except Exception:
            return ""

    @staticmethod
    def _contextual_safe(pattern: str, text: str, lang: str) -> bool:
        lower = text.lower()
        if lang in {"javascript", "typescript"}:
            if pattern in {
                r"\bdocument\.write\s*\(",
                r"\binsertAdjacentHTML\s*\(",
                r"\b(?:innerHTML|outerHTML)\s*=",
            }:
                if any(
                    marker in lower
                    for marker in (
                        "dompurify.sanitize",
                        "sanitizehtml",
                        "escapehtml",
                        "textcontent",
                    )
                ):
                    return True
                if re.search(r"(?:\(|=)\s*['\"`]", text):
                    return True
            if pattern == r"\bdangerouslySetInnerHTML\b" and any(
                marker in lower for marker in ("dompurify.sanitize", "sanitizehtml", "escapehtml")
            ):
                return True
        return False

    @staticmethod
    def _js_html_is_safe(text: str) -> bool:
        lower = text.lower()
        return any(
            marker in lower
            for marker in ("dompurify.sanitize", "sanitizehtml", "escapehtml", "textcontent")
        ) or bool(re.search(r"=\s*['\"`]", text))

    @staticmethod
    def _collect_aliases(source: str, lang: str) -> dict[str, str]:
        aliases: dict[str, str] = {}
        if not source:
            return aliases

        if lang in {"javascript", "typescript"}:
            # import * as cp from "child_process"
            for match in re.finditer(
                r"import\s+\*\s+as\s+(?P<alias>[A-Za-z_$][\w$]*)\s+from\s+[\'\"](?:node:)?child_process[\'\"]",
                source,
            ):
                aliases[match.group("alias")] = "child_process"
            # import {exec as run, spawn} from "child_process"
            for match in re.finditer(
                r"import\s*\{(?P<body>[^}]+)\}\s*from\s*[\'\"](?:node:)?child_process[\'\"]",
                source,
            ):
                for item in match.group("body").split(","):
                    parts = re.split(r"\s+as\s+", item.strip())
                    original = parts[0].strip()
                    alias = parts[-1].strip()
                    if original:
                        aliases[alias] = f"child_process.{original}"
            # const cp = require("child_process")
            for match in re.finditer(
                r"(?:const|let|var)\s+(?P<alias>[A-Za-z_$][\w$]*)\s*=\s*require\s*\(\s*[\'\"](?:node:)?child_process[\'\"]\s*\)",
                source,
            ):
                aliases[match.group("alias")] = "child_process"
            # const { exec: run } = require("child_process")
            for match in re.finditer(
                r"(?:const|let|var)\s*\{(?P<body>[^}]+)\}\s*=\s*require\s*\(\s*[\'\"](?:node:)?child_process[\'\"]\s*\)",
                source,
            ):
                for item in match.group("body").split(","):
                    parts = re.split(r"\s*:\s*", item.strip())
                    original = parts[0].strip()
                    alias = parts[-1].strip()
                    if original:
                        aliases[alias] = f"child_process.{original}"

            for match in re.finditer(
                r"import\s+(?P<alias>[A-Za-z_$][\w$]*)\s+from\s+[\'\"](?:vm|node:vm)[\'\"]",
                source,
            ):
                aliases[match.group("alias")] = "vm"

        elif lang == "go":
            # Go imports: cp "os/exec", exec "os/exec"
            for match in re.finditer(
                r'(?m)^\s*(?:[A-Za-z_][\w]*\s+)?(?:"os/exec"|`os/exec`)', source
            ):
                alias_match = re.search(r"\b([A-Za-z_][\w]*)\s+['\"]os/exec['\"]", match.group(0))
                if alias_match:
                    aliases[alias_match.group(1)] = "exec"
            for match in re.finditer(r"\b([A-Za-z_][\w]*)\s+\"os/exec\"", source):
                aliases[match.group(1)] = "exec"

        return aliases

    @staticmethod
    def _resolve_alias_text(func_name: str, aliases: dict[str, str]) -> str:
        if not func_name:
            return func_name
        first, dot, rest = func_name.partition(".")
        resolved = aliases.get(first)
        if resolved:
            return f"{resolved}.{rest}" if dot and rest else resolved
        return func_name

    @staticmethod
    def _dedupe(
        matches: list[tuple[str, int, str, str]],
    ) -> list[tuple[str, int, str, str]]:
        seen: set[tuple[str, int, str]] = set()
        out: list[tuple[str, int, str, str]] = []
        for item in matches:
            key = (item[0], item[1], item[3])
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out


# ============================================================================
# Main scanner
# ============================================================================


class PatternScanner(Scanner):
    """High-signal security-pattern/sink scanner."""

    name = "PatternScanner"
    version = "7.2.0"
    categories: ClassVar[list[Category]] = [Category.PATTERN]

    # These patterns are used by the lexical fallback and for rule metadata.
    # Language-specific AST logic determines when they are actually emitted.
    DANGEROUS_PATTERNS: ClassVar[dict[str, Severity]] = {
        # Python
        PY_OS_SYSTEM: Severity.HIGH,
        PY_OS_POPEN: Severity.HIGH,
        PY_SUBPROCESS: Severity.HIGH,
        PY_EVAL: Severity.HIGH,
        PY_EXEC: Severity.HIGH,
        PY_COMPILE: Severity.HIGH,
        PY_IMPORT: Severity.MEDIUM,
        PY_PICKLE: Severity.MEDIUM,
        PY_MARSHAL: Severity.MEDIUM,
        PY_YAML: Severity.MEDIUM,
        PY_MKTEMP: Severity.MEDIUM,
        PY_TEMPLATE: Severity.MEDIUM,
        PY_JINJA_TEMPLATE: Severity.MEDIUM,
        PY_JINJA_FROM_STRING: Severity.MEDIUM,
        r"\basyncio\.(?:subprocess\.)?create_subprocess_shell\s*\(": Severity.HIGH,
        # JavaScript / TypeScript
        r"\bFunction\s*\(": Severity.HIGH,
        r"\bchild_process\.(?:exec|execSync|execFile|execFileSync)\s*\(": Severity.HIGH,
        r"\bchild_process\.(?:spawn|spawnSync)\s*\(": Severity.HIGH,
        r"\bdocument\.write\s*\(": Severity.MEDIUM,
        r"\b(?:setTimeout|setInterval)\s*\(\s*['\"]": Severity.HIGH,
        r"\bvm\.runIn(?:NewContext|ThisContext)\s*\(": Severity.HIGH,
        r"\bvm\.Script\s*\(": Severity.HIGH,
        r"\b(?:innerHTML|outerHTML)\s*=": Severity.MEDIUM,
        r"\binsertAdjacentHTML\s*\(": Severity.MEDIUM,
        r"\bdangerouslySetInnerHTML\b": Severity.MEDIUM,
        # Ruby / PHP
        r"\b(?:instance_eval|class_eval|module_eval)\s*\(": Severity.HIGH,
        r"\b(?:system|exec|spawn|passthru|shell_exec|popen|proc_open)\s*\(": Severity.HIGH,
        r"\bunserialize\s*\(": Severity.HIGH,
        # JVM / .NET
        r"\bRuntime\.getRuntime\(\)\.exec\s*\(": Severity.HIGH,
        r"\b(?:new\s+)?ProcessBuilder\s*\(": Severity.MEDIUM,
        r"\bObjectInputStream\b.*\.readObject\s*\(": Severity.MEDIUM,
        r"\bScriptEngine\b.*\.eval\s*\(": Severity.HIGH,
        r"\bProcess\.Start\s*\(": Severity.MEDIUM,
        # Go / native
        r"\bexec\.Command(?:Context)?\s*\(": Severity.HIGH,
        r"\bos\.StartProcess\s*\(": Severity.MEDIUM,
        r"\bsyscall\.Exec(?:ve|v)?\s*\(": Severity.MEDIUM,
        r"\bsystem\s*\(": Severity.HIGH,
        r"\b(?:popen|_popen|_wpopen)\s*\(": Severity.HIGH,
        r"\bgets\s*\(": Severity.HIGH,
        r"\b(?:strcpy|strcat|sprintf|vsprintf)\s*\(": Severity.MEDIUM,
        # PowerShell
        r"\bInvoke-Expression\s+": Severity.HIGH,
        r"\bIEX\s+": Severity.HIGH,
        # Language-neutral high-signal fallbacks.
        r"\b(?:unserialize)\s*\(": Severity.HIGH,
        r"\b(?:system|shell_exec|passthru|proc_open)\s*\(": Severity.HIGH,
    }

    # Stable, primary CWE mapping.  Context-dependent use remains a sink-level
    # finding; TaintScanner provides the source-to-sink proof.
    PATTERN_CWE: ClassVar[dict[str, str]] = {
        PY_OS_SYSTEM: "CWE-78",
        PY_OS_POPEN: "CWE-78",
        PY_SUBPROCESS: "CWE-78",
        PY_EVAL: "CWE-95",
        PY_EXEC: "CWE-95",
        PY_COMPILE: "CWE-95",
        PY_IMPORT: "CWE-94",
        PY_PICKLE: "CWE-502",
        PY_MARSHAL: "CWE-502",
        PY_YAML: "CWE-502",
        PY_MKTEMP: "CWE-377",
        PY_TEMPLATE: "CWE-1336",
        PY_JINJA_TEMPLATE: "CWE-1336",
        PY_JINJA_FROM_STRING: "CWE-1336",
        r"\basyncio\.(?:subprocess\.)?create_subprocess_shell\s*\(": "CWE-78",
        r"\bFunction\s*\(": "CWE-95",
        r"\bchild_process\.(?:exec|execSync|execFile|execFileSync)\s*\(": "CWE-78",
        r"\bchild_process\.(?:spawn|spawnSync)\s*\(": "CWE-78",
        r"\bdocument\.write\s*\(": "CWE-79",
        r"\b(?:setTimeout|setInterval)\s*\(\s*['\"]": "CWE-95",
        r"\bvm\.runIn(?:NewContext|ThisContext)\s*\(": "CWE-95",
        r"\bvm\.Script\s*\(": "CWE-95",
        r"\b(?:innerHTML|outerHTML)\s*=": "CWE-79",
        r"\binsertAdjacentHTML\s*\(": "CWE-79",
        r"\bdangerouslySetInnerHTML\b": "CWE-79",
        r"\b(?:instance_eval|class_eval|module_eval)\s*\(": "CWE-95",
        r"\b(?:system|exec|spawn|passthru|shell_exec|popen|proc_open)\s*\(": "CWE-78",
        r"\bunserialize\s*\(": "CWE-502",
        r"\bRuntime\.getRuntime\(\)\.exec\s*\(": "CWE-78",
        r"\b(?:new\s+)?ProcessBuilder\s*\(": "CWE-78",
        r"\bObjectInputStream\b.*\.readObject\s*\(": "CWE-502",
        r"\bScriptEngine\b.*\.eval\s*\(": "CWE-95",
        r"\bProcess\.Start\s*\(": "CWE-78",
        r"\bexec\.Command(?:Context)?\s*\(": "CWE-78",
        r"\bos\.StartProcess\s*\(": "CWE-78",
        r"\bsyscall\.Exec(?:ve|v)?\s*\(": "CWE-78",
        r"\bsystem\s*\(": "CWE-78",
        r"\b(?:popen|_popen|_wpopen)\s*\(": "CWE-78",
        r"\bgets\s*\(": "CWE-120",
        r"\b(?:strcpy|strcat|sprintf|vsprintf)\s*\(": "CWE-120",
        r"\bInvoke-Expression\s+": "CWE-95",
        r"\bIEX\s+": "CWE-95",
        r"\b(?:unserialize)\s*\(": "CWE-502",
        r"\b(?:system|shell_exec|passthru|proc_open)\s*\(": "CWE-78",
    }

    LANG_MAP: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".pyi": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".mts": "typescript",
        ".cts": "typescript",
        ".vue": "javascript",
        ".svelte": "javascript",
        ".astro": "javascript",
        ".rb": "ruby",
        ".go": "go",
        ".java": "java",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".scala": "scala",
        ".groovy": "groovy",
        ".gradle": "groovy",
        ".dart": "dart",
        ".cs": "csharp",
        ".cshtml": "csharp",
        ".vb": "visualbasic",
        ".vbs": "visualbasic",
        ".php": "php",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".csh": "shell",
        ".ksh": "shell",
        ".ps1": "powershell",
        ".psm1": "powershell",
        ".c": "c",
        ".cc": "cpp",
        ".cp": "cpp",
        ".cpp": "cpp",
        ".cxx": "cpp",
        ".h": "c",
        ".hh": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        ".m": "c",
        ".mm": "cpp",
        ".rs": "rust",
        ".swift": "swift",
        ".r": "r",
        ".pl": "perl",
        ".pm": "perl",
        ".lua": "lua",
        ".fs": "fsharp",
        ".fsx": "fsharp",
        ".ex": "elixir",
        ".exs": "elixir",
        ".erl": "erlang",
        ".hrl": "erlang",
        ".zig": "zig",
        ".nim": "nim",
        ".v": "v",
        ".sol": "solidity",
        ".sql": "sql",
        ".graphql": "graphql",
        ".gql": "graphql",
    }

    _LANG_PATTERNS: ClassVar[dict[str, set[str]]] = {
        "python": {
            PY_OS_SYSTEM,
            PY_OS_POPEN,
            PY_SUBPROCESS,
            PY_EVAL,
            PY_EXEC,
            PY_COMPILE,
            PY_IMPORT,
            PY_PICKLE,
            PY_MARSHAL,
            PY_YAML,
            PY_MKTEMP,
            PY_TEMPLATE,
            PY_JINJA_TEMPLATE,
            PY_JINJA_FROM_STRING,
            r"\basyncio\.(?:subprocess\.)?create_subprocess_shell\s*\(",
        },
        "javascript": {
            PY_EVAL,
            r"\bFunction\s*\(",
            r"\bchild_process\.(?:exec|execSync|execFile|execFileSync)\s*\(",
            r"\bchild_process\.(?:spawn|spawnSync)\s*\(",
            r"\bdocument\.write\s*\(",
            r"\b(?:setTimeout|setInterval)\s*\(\s*['\"]",
            r"\bvm\.runIn(?:NewContext|ThisContext)\s*\(",
            r"\bvm\.Script\s*\(",
            r"\b(?:innerHTML|outerHTML)\s*=",
            r"\binsertAdjacentHTML\s*\(",
            r"\bdangerouslySetInnerHTML\b",
        },
        "typescript": {
            PY_EVAL,
            r"\bFunction\s*\(",
            r"\bchild_process\.(?:exec|execSync|execFile|execFileSync)\s*\(",
            r"\bchild_process\.(?:spawn|spawnSync)\s*\(",
            r"\bdocument\.write\s*\(",
            r"\b(?:setTimeout|setInterval)\s*\(\s*['\"]",
            r"\bvm\.runIn(?:NewContext|ThisContext)\s*\(",
            r"\bvm\.Script\s*\(",
            r"\b(?:innerHTML|outerHTML)\s*=",
            r"\binsertAdjacentHTML\s*\(",
            r"\bdangerouslySetInnerHTML\b",
        },
        "ruby": {
            PY_EVAL,
            r"\b(?:instance_eval|class_eval|module_eval)\s*\(",
            r"\b(?:system|exec|spawn)\s*\(",
        },
        "php": {
            PY_EVAL,
            r"\b(?:system|exec|spawn|passthru|shell_exec|popen|proc_open)\s*\(",
            r"\bunserialize\s*\(",
        },
        "java": {
            r"\bRuntime\.getRuntime\(\)\.exec\s*\(",
            r"\b(?:new\s+)?ProcessBuilder\s*\(",
            r"\bObjectInputStream\b.*\.readObject\s*\(",
            r"\bScriptEngine\b.*\.eval\s*\(",
        },
        "csharp": {
            r"\bProcess\.Start\s*\(",
        },
        "go": {
            r"\bexec\.Command(?:Context)?\s*\(",
            r"\bos\.StartProcess\s*\(",
            r"\bsyscall\.Exec(?:ve|v)?\s*\(",
        },
        "c": {
            r"\bsystem\s*\(",
            r"\b(?:popen|_popen|_wpopen)\s*\(",
            r"\bgets\s*\(",
            r"\b(?:strcpy|strcat|sprintf|vsprintf)\s*\(",
        },
        "cpp": {
            r"\bsystem\s*\(",
            r"\b(?:popen|_popen|_wpopen)\s*\(",
            r"\bgets\s*\(",
            r"\b(?:strcpy|strcat|sprintf|vsprintf)\s*\(",
        },
        "shell": {r"\beval\s+", r"\b(?:bash|sh|zsh|ksh)\s+-c\s+"},
        "powershell": {r"\bInvoke-Expression\s+", r"\bIEX\s+"},
        # Conservative language-neutral rules used only when a language-specific
        # parser/rule set is unavailable.  Avoid generic ``execute``/``query``
        # rules because they create large false-positive populations.
        "generic": {
            PY_EVAL,
            r"\b(?:system|shell_exec|passthru|proc_open)\s*\(",
            r"\bunserialize\s*\(",
            r"\b(?:pickle\.(?:load|loads)|yaml\.(?:load|unsafe_load|full_load))\s*\(",
            r"\bRuntime\.getRuntime\(\)\.exec\s*\(",
            r"\bProcess\.Start\s*\(",
            r"\bchild_process\.(?:exec|execSync)\s*\(",
        },
    }

    def __init__(
        self,
        learning_cache_path: Path | None = None,
        *,
        max_findings: int = 5000,
    ) -> None:
        self.learning_cache_path = learning_cache_path or Path(".seraph-learn/cache.json")
        self.max_findings = max(1, int(max_findings))
        self.learned_patterns: dict[str, Any] = {}
        self._compiled_patterns: dict[str, re.Pattern[str]] = {}
        self._compile_patterns()
        self._load_learning_cache()
        self.ts_analyzer = TreeSitterAnalyzer()

    def _compile_patterns(self) -> None:
        for pattern in self.DANGEROUS_PATTERNS:
            try:
                self._compiled_patterns[pattern] = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                logger.warning("Failed to compile pattern %r: %s", pattern, exc)

    @override
    def is_applicable(self, context: ScanContext) -> bool:
        try:
            return any(
                self._candidate_file(path) for path in self._iter_files(context.resolved_path)
            )
        except Exception:
            return False

    @override
    async def scan(self, context: ScanContext) -> list[Finding]:
        findings: list[Finding] = []
        scan_path = context.resolved_path

        max_files_raw = os.getenv("SERAPH_PATTERN_MAX_FILES", "").strip()
        message = "SERAPH_PATTERN_MAX_FILES must be a non-negative integer"
        try:
            max_files = max(0, int(max_files_raw)) if max_files_raw else 0
        except ValueError:
            raise ValueError(message) from None

        candidate_paths: list[Path] | None = None
        if max_files:
            candidate_paths = list(self._iter_files(scan_path))
            total_candidates = len(candidate_paths)
            if total_candidates > max_files:
                candidate_paths.sort(
                    key=lambda path: hashlib.sha256(
                        self._relative_path(path, scan_path).encode("utf-8")
                    ).hexdigest()
                )
                candidate_paths = candidate_paths[:max_files]

            coverage: dict[str, Any] = {
                "candidate_files": total_candidates,
                "selected_files": len(candidate_paths),
                "analyzed_files": 0,
                "partial": total_candidates > len(candidate_paths),
                "max_files": max_files,
                "selection": "deterministic_sha256_path_sample",
            }
            context.metadata.setdefault("scanner_coverage", {})[self.name] = coverage
            file_iter: Iterator[Path] = iter(candidate_paths)
        else:
            coverage = {
                "candidate_files": None,
                "selected_files": None,
                "analyzed_files": 0,
                "partial": False,
                "max_files": None,
                "selection": "complete_walk",
            }
            context.metadata.setdefault("scanner_coverage", {})[self.name] = coverage
            file_iter = self._iter_files(scan_path)

        for file_path in file_iter:
            coverage["analyzed_files"] += 1
            if len(findings) >= self.max_findings:
                logger.warning("PatternScanner reached max_findings=%d", self.max_findings)
                break
            if not self.should_scan_file(file_path):
                continue

            rel_path = self._relative_path(file_path, scan_path)
            try:
                raw = file_path.read_bytes()
                content = raw.decode("utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue

            lang = self._detect_language(rel_path, content)
            if lang == "unknown":
                continue

            matches = self._find_matches(content, raw, rel_path, lang)
            for pattern, line, evidence, func_name, detection in matches:
                if self._is_safe_in_context(pattern, rel_path, lang, evidence, content, line):
                    continue
                if self._should_suppress_learned(pattern, rel_path):
                    continue
                severity = self._severity_for_match(pattern, evidence, lang)
                findings.append(
                    self._create_finding(
                        rel_path,
                        line,
                        evidence,
                        pattern,
                        severity,
                        lang,
                        func_name=func_name,
                        detection=detection,
                    )
                )
                if len(findings) >= self.max_findings:
                    break

        logger.info(
            "PatternScanner found %d pattern issues; analyzed_files=%s partial=%s",
            len(findings),
            coverage["analyzed_files"],
            coverage["partial"],
        )
        return self._dedupe_findings(findings)

    def _find_matches(
        self,
        content: str,
        raw: bytes,
        rel_path: str,
        lang: str,
    ) -> list[tuple[str, int, str, str, str]]:
        if lang == "python":
            analyzer = _PythonAnalyzer(content)
            matches = analyzer.analyze()
            if matches:
                return [(p, line, text, func, "ast-python") for p, line, text, func in matches]
            if self._python_parse_failed(content):
                return self._regex_fallback(content, rel_path, lang)
            return []

        if self.ts_analyzer.available and lang in self.ts_analyzer.LANG_MAP:
            tree = self.ts_analyzer.parse(raw, lang)
            if tree is not None:
                matches = self.ts_analyzer.find_dangerous_calls(tree, lang, content)
                if matches:
                    return [
                        (p, line, text, func, "ast-tree-sitter") for p, line, text, func in matches
                    ]
                # A successful parse does not mean our rule model understood every
                # security-sensitive construct. Fall back only when the AST produced
                # no finding, so we never combine duplicate AST + regex hits.

        return self._regex_fallback(content, rel_path, lang)

    @staticmethod
    def _python_parse_failed(content: str) -> bool:
        try:
            ast.parse(content)
            return False
        except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
            return True

    def _regex_fallback(
        self,
        content: str,
        rel_path: str,
        lang: str,
    ) -> list[tuple[str, int, str, str, str]]:
        del rel_path
        patterns = self._LANG_PATTERNS.get(lang) or self._LANG_PATTERNS["generic"]
        if not patterns:
            return []
        lines = content.splitlines()
        masked_lines = _mask_source_lines(content, lang)
        aliases = _fallback_aliases(content, lang)
        results: list[tuple[str, int, str, str, str]] = []
        for index, (source_line, search_line) in enumerate(
            zip(lines, masked_lines, strict=False), 1
        ):
            if not search_line.strip():
                continue
            canonical_line = _canonicalize_aliases(search_line, aliases)
            for pattern in patterns:
                regex = self._compiled_patterns.get(pattern)
                if regex is None or not regex.search(canonical_line):
                    continue
                if not self._regex_match_context_valid(pattern, source_line, content, lang, index):
                    continue
                results.append(
                    (
                        pattern,
                        index,
                        source_line.strip()[:500],
                        self._pattern_to_name(pattern),
                        "regex-fallback",
                    )
                )
        return self._dedupe_matches(results)

    @staticmethod
    def _regex_match_context_valid(
        pattern: str,
        line: str,
        content: str,
        lang: str,
        line_num: int,
    ) -> bool:
        del line_num
        compact = re.sub(r"\s+", "", line).lower()
        if lang == "python":
            if pattern == PY_SUBPROCESS:
                # Regex fallback cannot reliably reason across multiline calls.
                # Only emit when shell=True is visibly attached to this line or
                # the surrounding source contains a compact shell=True call.
                return "shell=true" in compact or bool(
                    re.search(
                        r"subprocess\.[\w]+\s*\([^\n]{0,500}\bshell\s*=\s*True\b",
                        content,
                        re.IGNORECASE,
                    )
                )
            if pattern == PY_YAML:
                if re.search(r"\byaml\.safe_load(?:_all)?\s*\(", line, re.IGNORECASE):
                    return False
                if re.search(r"\bLoader\s*=\s*(?:[\w.]+\.)?(?:SafeLoader|BaseLoader)\b", line):
                    return False
            if pattern == r"\basyncio\.(?:subprocess\.)?create_subprocess_shell\s*\(":
                return True
        if lang in {"javascript", "typescript"} and pattern.startswith(
            r"\bchild_process\.(?:spawn"
        ):
            return bool(re.search(r"\bshell\s*:\s*true\b", line, re.IGNORECASE))
        return True

    @staticmethod
    def _candidate_file(path: Path) -> bool:
        ext = path.suffix.lower()
        if ext in SKIP_EXTENSIONS:
            return False
        if ext in ALLOWED_EXTENSIONS or not ext:
            try:
                return path.is_file()
            except OSError:
                return False
        return False

    def _iter_files(self, scan_path: Path) -> Iterator[Path]:
        if scan_path.is_file():
            if self._candidate_file(scan_path):
                yield scan_path
            return

        try:
            for dirpath, dirnames, filenames in os.walk(scan_path, followlinks=False):
                dirnames[:] = [
                    directory
                    for directory in dirnames
                    if directory not in SKIP_DIRS and not directory.endswith(".egg-info")
                ]
                for filename in sorted(filenames):
                    path = Path(dirpath) / filename
                    if self._candidate_file(path):
                        yield path
        except (PermissionError, OSError) as exc:
            logger.debug("Permission error walking %s: %s", scan_path, exc)

    @staticmethod
    def _relative_path(file_path: Path, scan_path: Path) -> str:
        try:
            return file_path.relative_to(scan_path).as_posix()
        except ValueError:
            return file_path.as_posix()

    def _is_non_production_file(self, rel_path: str) -> bool:
        """Return only for generated/artifact content.

        Test/example/benchmark directories deliberately return False here. The
        Scheduler's ``Finding.file_context`` is the authoritative production
        classification.
        """
        file_name = Path(rel_path).name.lower()
        path_lower = rel_path.lower().replace("\\", "/")
        if any(fnmatch.fnmatchcase(file_name, pattern) for pattern in GENERATED_CODE_PATTERNS):
            return True
        generated_segments = (
            "/generated/",
            "/codegen/",
            "/code-gen/",
            "/auto_generated/",
        )
        if any(segment in f"/{path_lower.lstrip('/')}" for segment in generated_segments):
            return True
        return path_lower.endswith((".min.js", ".min.css", ".bundle.js", ".bundle.css"))

    def _detect_language(self, rel_path: str, content: str = "") -> str:
        ext = Path(rel_path).suffix.lower()
        if ext in self.LANG_MAP:
            return self.LANG_MAP[ext]
        first_line = content.splitlines()[0].lower() if content.splitlines() else ""
        if first_line.startswith("#!"):
            if "python" in first_line:
                return "python"
            if any(shell in first_line for shell in ("bash", "sh", "zsh", "ksh")):
                return "shell"
            if "pwsh" in first_line or "powershell" in first_line:
                return "powershell"
        filename = Path(rel_path).name.lower()
        if filename in AUTOTOOLS_ALLOWLIST or filename in {"configure.ac", "configure.in"}:
            return "shell"
        if filename in {"Dockerfile", "Containerfile", "Jenkinsfile"}:
            return "shell"
        return "unknown"

    def _is_safe_in_context(
        self,
        pattern: str,
        rel_path: str,
        lang: str,
        line: str,
        content: str,
        line_num: int,
    ) -> bool:
        del rel_path, content, line_num
        line_lower = line.lower()

        if lang == "python":
            if re.search(r"\bplatform\.system\s*\(", line_lower) and pattern == r"\bsystem\s*\(":
                return True
            if pattern == PY_YAML:
                if re.search(r"\byaml\.safe_load(?:_all)?\s*\(", line_lower):
                    return True
                if re.search(
                    r"\bLoader\s*=\s*(?:[\w.]+\.)?(?:SafeLoader|BaseLoader)\b",
                    line,
                ):
                    return True

            # A fully literal template cannot carry attacker-controlled template
            # source.  Dynamic templates remain findings and should be validated by
            # TaintScanner if input provenance matters.
            if pattern in {PY_JINJA_TEMPLATE, PY_JINJA_FROM_STRING, PY_TEMPLATE}:
                return bool(re.search(r"\(\s*['\"]", line))

        if lang in {"javascript", "typescript"} and pattern in {
            r"\bdocument\.write\s*\(",
            r"\binsertAdjacentHTML\s*\(",
            r"\b(?:innerHTML|outerHTML)\s*=",
            r"\bdangerouslySetInnerHTML\b",
        }:
            if any(
                marker in line_lower
                for marker in (
                    "dompurify.sanitize",
                    "sanitizehtml",
                    "escapehtml",
                    "textcontent",
                )
            ):
                return True
            if pattern != r"\bdangerouslySetInnerHTML\b" and re.search(r"(?:\(|=)\s*['\"`]", line):
                return True

        if lang == "powershell" and pattern in {r"\bInvoke-Expression\s+", r"\bIEX\s+"}:
            return False

        # Path names should never be treated as blanket security allowlists.
        # Context remains available to the scheduler's production classifier.
        return False

    def _severity_for_match(self, pattern: str, evidence: str, lang: str) -> Severity:
        severity = self.DANGEROUS_PATTERNS.get(pattern, Severity.MEDIUM)
        compact = re.sub(r"\s+", "", evidence).lower()
        if pattern == PY_SUBPROCESS:
            return Severity.HIGH if "shell=true" in compact else Severity.MEDIUM
        if pattern == r"\bchild_process\.(?:spawn|spawnSync)\s*\(":
            return Severity.HIGH if "shell:true" in compact else Severity.MEDIUM
        if lang == "go" and pattern == r"\bexec\.Command(?:Context)?\s*\(":
            return (
                Severity.HIGH
                if re.search(
                    r"(?:sh|bash|zsh|cmd|powershell)(?:\.exe)?['\"`]?\s*,\s*['\"`]?-[cC]",
                    evidence,
                    re.IGNORECASE,
                )
                else Severity.MEDIUM
            )
        return severity

    def _create_finding(
        self,
        rel_path: str,
        line_num: int,
        line_content: str,
        pattern_str: str,
        severity: Severity,
        lang: str,
        *,
        func_name: str = "",
        detection: str = "unknown",
    ) -> Finding:
        rule_name = self._pattern_to_name(pattern_str)
        finding_id = self._make_finding_id(pattern_str, rel_path, line_num)
        cwe = self.PATTERN_CWE.get(pattern_str)
        metadata: dict[str, Any] = {
            "rule_id": f"pattern-{hashlib.sha256(pattern_str.encode()).hexdigest()[:8]}",
            "pattern": pattern_str,
            "language": lang,
            "detection": detection,
            "api": func_name or rule_name,
            "analysis_layer": "sink",
            "precision": "high-signal-sink",
            "requires_dataflow_for_exploitability": True,
        }
        if cwe:
            metadata["cwe"] = cwe
        if cwe == "CWE-95":
            # Seraph's TaintScanner uses CWE-95 for dynamic-code sinks while
            # some external taxonomies score them under CWE-94. Preserve both
            # without changing Seraph's primary taxonomy.
            metadata["cwe_aliases"] = ["CWE-94"]

        description = (
            f"Security-sensitive operation '{rule_name}' detected at "
            f"{rel_path}:{line_num}. PatternScanner identifies the sink/API; "
            "it does not by itself establish that attacker-controlled data reaches "
            "the sink. Use TaintScanner/data-flow and application context to assess "
            "exploitability."
        )
        evidence = line_content.strip()[:500] if line_content else pattern_str
        finding = Finding(
            scanner=self.name,
            category=Category.PATTERN,
            severity=severity,
            confidence=self._confidence_for(pattern_str, detection),
            file=rel_path,
            line=line_num,
            title=rule_name,
            description=description,
            id=finding_id,
            rule_id=str(metadata["rule_id"]),
            rule_name=rule_name,
            message=f"Security-sensitive operation detected: {rule_name}",
            column=0,
            evidence=evidence,
            context=evidence,
            fix_available=False,
            metadata=metadata,
        )
        return finding

    @classmethod
    def _confidence_for(cls, pattern: str, detection: str) -> float:
        if detection.startswith("ast-"):
            if pattern in {PY_OS_SYSTEM, PY_OS_POPEN, PY_EVAL, PY_EXEC, PY_MKTEMP}:
                return 0.96
            return 0.92
        if pattern in {PY_OS_SYSTEM, PY_OS_POPEN, PY_EVAL, PY_EXEC}:
            return 0.89
        return 0.82

    @staticmethod
    def _dedupe_matches(
        matches: list[tuple[str, int, str, str, str]],
    ) -> list[tuple[str, int, str, str, str]]:
        seen: set[tuple[str, int, str]] = set()
        out: list[tuple[str, int, str, str, str]] = []
        for item in matches:
            key = (item[0], item[1], item[3])
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out

    @staticmethod
    def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
        seen: set[tuple[str, int, str]] = set()
        out: list[Finding] = []
        for finding in findings:
            key = (
                getattr(finding, "file", ""),
                int(getattr(finding, "line", 0) or 0),
                getattr(finding, "rule_id", ""),
            )
            if key not in seen:
                seen.add(key)
                out.append(finding)
        return out

    def _should_suppress_learned(self, pattern: str, rel_path: str) -> bool:
        if not self.learned_patterns:
            return False
        key = self._make_learning_key(pattern, rel_path)
        entry = self.learned_patterns.get(key)
        return isinstance(entry, dict) and entry.get("status") == "suppressed"

    @staticmethod
    def _make_learning_key(pattern: str, rel_path: str) -> str:
        return hashlib.sha256(f"{pattern}:{rel_path}".encode()).hexdigest()[:16]

    @staticmethod
    def _make_finding_id(pattern: str, rel_path: str, line_num: int) -> str:
        raw = f"{pattern}:{rel_path}:{line_num}"
        return "PAT-" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    @staticmethod
    def _is_pattern_fixable(_pattern: str, _rel_path: str, _line_content: str) -> bool:
        return False

    @staticmethod
    def _pattern_to_name(pattern_str: str) -> str:
        names = {
            PY_OS_SYSTEM: "os.system() call",
            PY_OS_POPEN: "os.popen() call",
            PY_SUBPROCESS: "subprocess process execution with shell",
            PY_EVAL: "dynamic eval() call",
            PY_EXEC: "dynamic exec() call",
            PY_COMPILE: "dynamic compile() call",
            PY_IMPORT: "dynamic __import__() call",
            PY_PICKLE: "pickle deserialization",
            PY_MARSHAL: "marshal deserialization",
            PY_YAML: "non-safe YAML deserialization",
            PY_MKTEMP: "insecure tempfile.mktemp()",
            PY_TEMPLATE: "Jinja template from dynamic string",
            PY_JINJA_TEMPLATE: "Jinja Template from dynamic string",
            PY_JINJA_FROM_STRING: "Jinja Environment.from_string() with dynamic template",
            r"\basyncio\.(?:subprocess\.)?create_subprocess_shell\s*\(": "asyncio shell process execution",
            r"\bFunction\s*\(": "Function() dynamic code constructor",
            r"\bchild_process\.(?:exec|execSync|execFile|execFileSync)\s*\(": "Node child_process execution",
            r"\bchild_process\.(?:spawn|spawnSync)\s*\(": "Node child_process spawn with shell option",
            r"\bdocument\.write\s*\(": "document.write() HTML sink",
            r"\b(?:setTimeout|setInterval)\s*\(\s*['\"]": "timer string-code execution",
            r"\bvm\.runIn(?:NewContext|ThisContext)\s*\(": "Node VM dynamic code execution",
            r"\bvm\.Script\s*\(": "Node VM Script construction",
            r"\b(?:innerHTML|outerHTML)\s*=": "DOM HTML assignment",
            r"\binsertAdjacentHTML\s*\(": "insertAdjacentHTML() HTML sink",
            r"\bdangerouslySetInnerHTML\b": "dangerouslySetInnerHTML HTML sink",
            r"\b(?:instance_eval|class_eval|module_eval)\s*\(": "Ruby dynamic evaluation",
            r"\b(?:system|exec|spawn|passthru|shell_exec|popen|proc_open)\s*\(": "shell/process execution",
            r"\bunserialize\s*\(": "PHP unserialize()",
            r"\bRuntime\.getRuntime\(\)\.exec\s*\(": "Java Runtime.exec()",
            r"\b(?:new\s+)?ProcessBuilder\s*\(": "Java ProcessBuilder",
            r"\bObjectInputStream\b.*\.readObject\s*\(": "Java object deserialization",
            r"\bScriptEngine\b.*\.eval\s*\(": "Java ScriptEngine evaluation",
            r"\bProcess\.Start\s*\(": ".NET Process.Start()",
            r"\bexec\.Command(?:Context)?\s*\(": "Go exec.Command() shell execution",
            r"\bos\.StartProcess\s*\(": "Go os.StartProcess()",
            r"\bsyscall\.Exec(?:ve|v)?\s*\(": "Go syscall.Exec()",
            r"\bsystem\s*\(": "system() shell execution",
            r"\b(?:popen|_popen|_wpopen)\s*\(": "popen() shell execution",
            r"\bgets\s*\(": "unsafe gets() buffer operation",
            r"\b(?:strcpy|strcat|sprintf|vsprintf)\s*\(": "unsafe native string operation",
            r"\bInvoke-Expression\s+": "PowerShell Invoke-Expression",
            r"\bIEX\s+": "PowerShell IEX dynamic execution",
            r"\b(?:unserialize)\s*\(": "unserialize() dangerous deserialization",
            r"\b(?:system|shell_exec|passthru|proc_open)\s*\(": "generic process/shell execution",
        }
        return names.get(pattern_str, f"Pattern: {pattern_str[:60]}")

    @staticmethod
    def _suggest_fix(rule_name: str, lang: str) -> str:
        del lang
        suggestions = {
            "os.system() call": "Prefer subprocess.run([...], shell=False) with an explicit argument list.",
            "os.popen() call": "Prefer subprocess.run([...], shell=False) with an explicit argument list.",
            "dynamic eval() call": "Remove dynamic evaluation or use a data parser such as ast.literal_eval() for literals.",
            "dynamic exec() call": "Remove dynamic execution and replace it with explicit dispatch or data parsing.",
            "pickle deserialization": "Use a data-only format such as JSON for untrusted data.",
            "marshal deserialization": "Use a data-only format such as JSON for untrusted data.",
            "non-safe YAML deserialization": "Use yaml.safe_load() or Loader=SafeLoader for untrusted YAML.",
            "insecure tempfile.mktemp()": "Use tempfile.mkstemp(), NamedTemporaryFile(), or TemporaryDirectory().",
        }
        return suggestions.get(
            rule_name, "Manual security review and context-specific remediation required."
        )

    def _load_learning_cache(self) -> None:
        try:
            if self.learning_cache_path.exists():
                data = json.loads(self.learning_cache_path.read_text(encoding="utf-8"))
                patterns = data.get("pattern_suppressions", {})
                self.learned_patterns = patterns if isinstance(patterns, dict) else {}
        except (OSError, UnicodeError, json.JSONDecodeError):
            self.learned_patterns = {}

    @staticmethod
    def _match_glob(filename: str, pattern: str) -> bool:
        return fnmatch.fnmatchcase(filename, pattern)

    @staticmethod
    def _is_user_controlled_html(line: str) -> bool:
        # Backward-compatible helper. The real DOM analysis is AST/Tree-sitter
        # based; this helper intentionally remains conservative for old callers.
        lower = line.lower()
        if "dangerouslysetinnerhtml" in lower and re.search(
            r"dangerouslysetinnerhtml\s*=\s*\{", lower
        ):
            return True
        return not ("__html" in lower and re.search(r"__html\s*:\s*['\"`]", line))


# ============================================================================
# Shared Python helpers
# ============================================================================


def _ast_source(node: ast.AST, source: str) -> str:
    try:
        value = ast.get_source_segment(source, node)
        return value.replace("\n", " ").strip()[:500] if value else ""
    except (AttributeError, TypeError, ValueError):
        return ""


def _python_is_constant(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_python_is_constant(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=False):
            if key is None:
                continue
            if not _python_is_constant(key) or not _python_is_constant(value):
                return False
        return True
    if isinstance(node, ast.UnaryOp):
        return _python_is_constant(node.operand)
    if isinstance(node, ast.BinOp):
        return _python_is_constant(node.left) and _python_is_constant(node.right)
    if isinstance(node, ast.JoinedStr):
        return False
    return False


def _python_shell_is_enabled(node: ast.Call) -> bool:
    """Return true only when shell execution is enabled or not statically disabled."""
    for keyword in node.keywords:
        if keyword.arg != "shell":
            continue
        if isinstance(keyword.value, ast.Constant):
            return keyword.value.value is not False
        return True
    return False


def _python_yaml_call_is_safe(node: ast.Call, aliases: dict[str, str]) -> bool:
    for keyword in node.keywords:
        if keyword.arg != "Loader":
            continue
        resolved = _resolve_python_name(keyword.value, aliases)
        tail = resolved.rsplit(".", 1)[-1]
        return tail in {"SafeLoader", "BaseLoader"}
    # Explicitly safe constructors used by some codebases.
    return False


def _resolve_python_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        prefix = _resolve_python_name(node.value, aliases)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


# ============================================================================
# Lexical fallback
# ============================================================================


def _fallback_aliases(source: str, lang: str) -> dict[str, str]:
    """Collect simple import aliases for parser-free fallback matching."""
    aliases: dict[str, str] = {}
    if lang == "python":
        for match in re.finditer(
            r"(?m)^\s*import\s+([A-Za-z_][\w.]*)\s+as\s+([A-Za-z_][\w]*)",
            source,
        ):
            aliases[match.group(2)] = match.group(1)
        for match in re.finditer(
            r"(?m)^\s*import\s+([A-Za-z_][\w.]*)\s*(?:#.*)?$",
            source,
        ):
            module = match.group(1)
            aliases.setdefault(module.split(".", 1)[0], module.split(".", 1)[0])
        for match in re.finditer(
            r"(?m)^\s*from\s+([A-Za-z_][\w.]*)\s+import\s+([^#\n]+)",
            source,
        ):
            module, names = match.groups()
            for item in names.split(","):
                raw_name = item.strip()
                if not raw_name or raw_name == _STAR_IMPORT:
                    continue
                parts = re.split(r"\s+as\s+", raw_name)
                original = parts[0].strip()
                alias = parts[-1].strip()
                if re.fullmatch(r"[A-Za-z_][\w]*", alias):
                    aliases[alias] = f"{module}.{original}"
    elif lang in {"javascript", "typescript"}:
        for match in re.finditer(
            r"import\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from\s+['\"](?:node:)?child_process['\"]",
            source,
        ):
            aliases[match.group(1)] = "child_process"
        for match in re.finditer(
            r"import\s*\{([^}]+)\}\s*from\s*['\"](?:node:)?child_process['\"]",
            source,
        ):
            for item in match.group(1).split(","):
                parts = re.split(r"\s+as\s+", item.strip())
                original = parts[0].strip()
                alias = parts[-1].strip()
                if original and re.fullmatch(r"[A-Za-z_$][\w$]*", alias):
                    aliases[alias] = f"child_process.{original}"
        for match in re.finditer(
            r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\s*\(\s*['\"](?:node:)?child_process['\"]\s*\)",
            source,
        ):
            aliases[match.group(1)] = "child_process"
        for match in re.finditer(
            r"(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\s*\(\s*['\"](?:node:)?child_process['\"]\s*\)",
            source,
        ):
            for item in match.group(1).split(","):
                parts = re.split(r"\s*:\s*", item.strip())
                original = parts[0].strip()
                alias = parts[-1].strip()
                if original and re.fullmatch(r"[A-Za-z_$][\w$]*", alias):
                    aliases[alias] = f"child_process.{original}"
        for match in re.finditer(
            r"import\s+(?:\{[^}]*\}|[A-Za-z_$][\w$]*)\s+from\s*['\"](?:node:)?vm['\"]",
            source,
        ):
            del match
    elif lang == "go":
        for match in re.finditer(r'(?m)^\s*([A-Za-z_][\w]*)\s+["\']os/exec["\']', source):
            aliases[match.group(1)] = "exec"
    return aliases


def _canonicalize_aliases(line: str, aliases: dict[str, str]) -> str:
    """Rewrite imported aliases to canonical API names for regex matching."""
    result = line
    for alias, target in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if alias == target:
            continue
        result = re.sub(rf"\b{re.escape(alias)}(?=\s*\.)", target, result)
        if "." in target:
            result = re.sub(rf"\b{re.escape(alias)}(?=\s*\()", target, result)
    return result


def _mask_source_lines(content: str, lang: str) -> list[str]:
    """Mask comments and quoted literals while preserving line/column layout."""
    lines = content.splitlines()
    masked: list[str] = []
    in_block_comment = False
    quote: str | None = None
    triple = False
    escape = False

    line_comment_tokens: tuple[str, ...]
    if lang in {"javascript", "typescript", "java", "go", "csharp", "c", "cpp", "rust", "swift"}:
        line_comment_tokens = ("//",)
    elif lang in {"python", "ruby", "shell", "powershell", "perl", "r", "lua"}:
        line_comment_tokens = ("#",)
    elif lang == "php":
        line_comment_tokens = ("//", "#")
    else:
        line_comment_tokens = ("#",)

    for source_line in lines:
        chars = list(source_line)
        i = 0
        while i < len(chars):
            two = "".join(chars[i : i + 2]) if i + 1 < len(chars) else ""
            three = "".join(chars[i : i + 3]) if i + 2 < len(chars) else ""

            if in_block_comment:
                if two == "*/":
                    chars[i] = " "
                    chars[i + 1] = " "
                    in_block_comment = False
                    i += 2
                else:
                    chars[i] = " "
                    i += 1
                continue

            if quote is not None:
                if triple and three == quote * 3:
                    for offset in range(3):
                        chars[i + offset] = " "
                    quote = None
                    triple = False
                    escape = False
                    i += 3
                    continue
                if not triple and chars[i] == quote and not escape:
                    chars[i] = " "
                    quote = None
                    escape = False
                    i += 1
                    continue
                was_escape = chars[i] == "\\"
                chars[i] = " "
                escape = not escape if was_escape and not triple else False
                i += 1
                continue

            if two == "/*":
                chars[i] = " "
                chars[i + 1] = " "
                in_block_comment = True
                i += 2
                continue

            if any("".join(chars[i : i + len(token)]) == token for token in line_comment_tokens):
                for offset in range(i, len(chars)):
                    chars[offset] = " "
                break

            if lang in {"python", "ruby", "shell", "powershell", "perl", "r"} and chars[i] in {
                "'",
                '"',
            }:
                quote = chars[i]
                triple = lang == "python" and three == quote * 3
                width = 3 if triple else 1
                for offset in range(width):
                    chars[i + offset] = " "
                i += width
                continue

            if lang in {"javascript", "typescript"} and chars[i] in {"'", '"', "`"}:
                quote = chars[i]
                triple = False
                chars[i] = " "
                i += 1
                continue

            if lang in {"java", "go", "csharp", "c", "cpp", "rust", "swift", "php"} and chars[
                i
            ] in {"'", '"'}:
                quote = chars[i]
                triple = False
                chars[i] = " "
                i += 1
                continue

            i += 1

        masked.append("".join(chars))

    return masked


__all__ = ["PatternScanner", "TreeSitterAnalyzer"]
