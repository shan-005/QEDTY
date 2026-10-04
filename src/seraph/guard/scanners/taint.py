"""Seraph Guard taint scanner (production edition).

This scanner performs conservative Python source-to-sink analysis.  It is
intentionally independent from PatternScanner: PatternScanner reports high
signal security sinks; this module attempts to establish attacker-controlled
provenance reaching those sinks.

The implementation is:
* AST based and syntax-error tolerant;
* flow-sensitive within statements and common control-flow constructs;
* bounded interprocedural and cross-file for repository-local functions;
* alias aware for imports such as ``import subprocess as sp``;
* route-parameter aware for common Python web frameworks; and
* deterministic in findings, traces, and ordering.

It deliberately does not execute project code, import the target application,
or inspect network responses.  Dynamic Python features that cannot be proven
statically are left unresolved instead of guessed.
"""

from __future__ import annotations

import ast
import asyncio
import fnmatch
import hashlib
import logging
import os
import time

from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, ClassVar, override

from seraph.guard.scanners.base import (
    Category,
    Finding,
    ScanContext,
    Scanner,
    Severity,
)


logger = logging.getLogger("seraph.guard.scanners.taint")

_PARAM = "<parameter>"
_MAX_TRACE = 16


@dataclass
class TaintInfo:
    """Provenance and path for a tainted value."""

    source: str
    path: list[dict[str, Any]] = field(default_factory=list)
    sanitizers: list[str] = field(default_factory=list)

    def extend(self, step: dict[str, Any]) -> TaintInfo:
        path = [*self.path, step]
        if len(path) > _MAX_TRACE:
            path = [path[0], *path[-(_MAX_TRACE - 1) :]]
        return TaintInfo(self.source, path, list(self.sanitizers))


@dataclass
class Hit:
    """A proven or bounded source-to-sink flow."""

    sink: str
    file: str
    line: int
    col: int
    func_id: str
    source: str
    path: list[dict[str, Any]]
    severity: Severity
    depth: int = 0
    cross_file: bool = False


@dataclass
class FuncResult:
    """Summary of one function under one parameter-taint assumption."""

    hits: list[Hit] = field(default_factory=list)
    returns: TaintInfo | None = None


@dataclass(frozen=True)
class _Ctx:
    file_key: str
    func_id: str
    remaining: int
    parameter: str | None = None


class _TaintTimeoutError(Exception):
    """Internal deadline control flow."""


@dataclass
class TaintFinding(Finding):
    """Finding carrying the complete taint trace."""

    taint_path: list[dict[str, Any]] = field(default_factory=list)
    source_function: str = ""
    sink_function: str = ""
    sanitizers_hit: list[str] = field(default_factory=list)
    call_depth: int = 0
    cross_file: bool = False


class TaintScanner(Scanner):
    """Bounded Python taint analysis for attacker-controlled data."""

    name = "taint"
    version = "4.0.1"
    categories: ClassVar[list[Category]] = [Category.VULNERABILITY]

    DEFAULT_SOURCES: ClassVar[set[str]] = {
        # Flask / Werkzeug style
        "request.args.get",
        "request.args.getlist",
        "request.form.get",
        "request.form.getlist",
        "request.json.get",
        "request.headers.get",
        "request.cookies.get",
        "request.values.get",
        "request.files.get",
        "request.get_json",
        "request.get_data",
        "request.stream.read",
        # Django / DRF style
        "request.GET.get",
        "request.POST.get",
        "request.body.decode",
        # Generic program input
        "input",
        "sys.stdin.read",
        "sys.stdin.readline",
        "socket.recv",
        "socket.recvfrom",
        # Common HTTP libraries exposing request data through wrappers
        "urllib.parse.parse_qs",
        "urllib.parse.parse_qsl",
    }

    DEFAULT_SOURCE_ATTRS: ClassVar[set[str]] = {
        "request.args",
        "request.form",
        "request.json",
        "request.cookies",
        "request.headers",
        "request.values",
        "request.data",
        "request.files",
        "request.GET",
        "request.POST",
        "request.body",
        "request.META",
        "request.query_params",
        "request.path_params",
        "request.scope",
        "sys.argv",
    }

    DEFAULT_SINKS: ClassVar[set[str]] = {
        # Dynamic code
        "eval",
        "exec",
        "compile",
        "__import__",
        "builtins.eval",
        "builtins.exec",
        "builtins.compile",
        # Command execution
        "os.system",
        "os.popen",
        "os.spawnv",
        "os.spawnve",
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.check_output",
        "subprocess.check_call",
        "subprocess.getoutput",
        "subprocess.getstatusoutput",
        # SQL
        "cursor.execute",
        "cursor.executemany",
        "cursor.executescript",
        "connection.execute",
        "connection.executemany",
        "connection.executescript",
        # Deserialization
        "pickle.loads",
        "pickle.load",
        "yaml.unsafe_load",
        "yaml.load",
        "yaml.full_load",
        "marshal.loads",
        "marshal.load",
        # Template execution
        "render_template_string",
        "jinja2.Template",
        "jinja2.Environment.from_string",
        # Filesystem
        "open",
        "pathlib.Path.open",
        "pathlib.Path.read_text",
        "pathlib.Path.write_text",
        "pathlib.Path.read_bytes",
        "pathlib.Path.write_bytes",
        "os.open",
        # Network / SSRF
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "requests.request",
        "httpx.get",
        "httpx.post",
        "httpx.put",
        "httpx.delete",
        "httpx.request",
        "urllib.request.urlopen",
        "urllib.request.Request",
    }

    DEFAULT_SANITIZERS: ClassVar[set[str]] = {
        # Security-oriented transformations. Ordinary type coercions such as
        # str(), int(), float(), bool(), and bytes() are deliberately excluded:
        # they preserve attacker control and therefore must not erase taint.
        "ast.literal_eval",
        "os.path.basename",
        "pathlib.PurePath.name",
        "html.escape",
        "markupsafe.escape",
        "bleach.clean",
        "shlex.quote",
        "validators.url",
        "validators.email",
        "re.fullmatch",
    }

    _CRITICAL_SINKS: ClassVar[set[str]] = {
        "eval",
        "exec",
        "compile",
        "builtins.eval",
        "builtins.exec",
        "builtins.compile",
        "os.system",
        "os.popen",
        "pickle.loads",
        "pickle.load",
        "yaml.unsafe_load",
        "yaml.load",
        "yaml.full_load",
        "marshal.loads",
        "marshal.load",
        "render_template_string",
    }

    _HIGH_SINKS: ClassVar[set[str]] = {
        "__import__",
        "os.spawnv",
        "os.spawnve",
        "subprocess.call",
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.check_output",
        "subprocess.check_call",
        "subprocess.getoutput",
        "subprocess.getstatusoutput",
        "cursor.execute",
        "cursor.executemany",
        "cursor.executescript",
        "connection.execute",
        "connection.executemany",
        "connection.executescript",
        "jinja2.Template",
        "jinja2.Environment.from_string",
    }

    _SINK_POSITIONS: ClassVar[dict[str, tuple[int, ...]]] = {
        "eval": (0,),
        "exec": (0,),
        "compile": (0,),
        "builtins.eval": (0,),
        "builtins.exec": (0,),
        "builtins.compile": (0,),
        "__import__": (0,),
        "os.system": (0,),
        "os.popen": (0,),
        "os.spawnv": (0, 1),
        "os.spawnve": (0, 1),
        "subprocess.call": (0,),
        "subprocess.run": (0,),
        "subprocess.Popen": (0,),
        "subprocess.check_output": (0,),
        "subprocess.check_call": (0,),
        "subprocess.getoutput": (0,),
        "subprocess.getstatusoutput": (0,),
        "cursor.execute": (0,),
        "cursor.executemany": (0,),
        "cursor.executescript": (0,),
        "connection.execute": (0,),
        "connection.executemany": (0,),
        "connection.executescript": (0,),
        "pickle.loads": (0,),
        "pickle.load": (0,),
        "yaml.unsafe_load": (0,),
        "yaml.load": (0,),
        "yaml.full_load": (0,),
        "marshal.loads": (0,),
        "marshal.load": (0,),
        "render_template_string": (0,),
        "jinja2.Template": (0,),
        "jinja2.Environment.from_string": (0,),
        "open": (0,),
        "pathlib.Path.open": (0,),
        "pathlib.Path.read_text": (),
        "pathlib.Path.write_text": (0,),
        "pathlib.Path.read_bytes": (),
        "pathlib.Path.write_bytes": (0,),
        "os.open": (0,),
        "requests.get": (0,),
        "requests.post": (0,),
        "requests.put": (0,),
        "requests.delete": (0,),
        "requests.request": (0,),
        "httpx.get": (0,),
        "httpx.post": (0,),
        "httpx.put": (0,),
        "httpx.delete": (0,),
        "httpx.request": (0,),
        "urllib.request.urlopen": (0,),
        "urllib.request.Request": (0,),
    }

    _SINK_MAIN_KWARGS: ClassVar[set[str]] = {
        "query",
        "sql",
        "operation",
        "command",
        "cmd",
        "args",
        "url",
        "file",
        "filename",
        "path",
        "name",
        "source",
        "code",
        "expression",
        "template",
        "template_string",
        "string",
        "data",
    }

    _SAFE_KWARGS: ClassVar[set[str]] = {
        "params",
        "parameters",
        "timeout",
        "shell",
        "cwd",
        "env",
        "mode",
        "encoding",
        "errors",
        "headers",
        "verify",
        "stdin",
        "stdout",
        "stderr",
        "check",
        "text",
        "capture_output",
        "stream",
    }

    _ROUTE_DECORATORS: ClassVar[set[str]] = {
        "route",
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "head",
        "options",
        "websocket",
        "api_view",
        "action",
    }

    _ROUTE_SKIP_PARAMS: ClassVar[set[str]] = {
        "self",
        "cls",
        "request",
        "req",
        "response",
        "res",
        "db",
        "session",
        "current_user",
    }

    SKIP_DIRS: ClassVar[set[str]] = {
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
        "site-packages",
        "dist-packages",
        "vendor",
        "third_party",
        "third-party",
        "htmlcov",
    }

    _SINK_ADVICE: ClassVar[dict[str, tuple[str, str]]] = {
        "code": (
            "CWE-95",
            "Avoid dynamic evaluation; use a data format or ast.literal_eval() for literals.",
        ),
        "command": (
            "CWE-78",
            "Avoid shell interpretation, pass a fixed executable and explicit arguments, and validate untrusted input.",
        ),
        "sql": ("CWE-89", "Use parameterized queries and keep untrusted data out of SQL syntax."),
        "deserialize": (
            "CWE-502",
            "Do not deserialize untrusted data with pickle, marshal, or unsafe YAML loaders.",
        ),
        "template": (
            "CWE-1336",
            "Do not compile attacker-controlled template source; use trusted templates with autoescaping.",
        ),
        "path": (
            "CWE-22",
            "Constrain paths to an intended root after canonicalization and reject traversal/symlink escapes.",
        ),
        "ssrf": (
            "CWE-918",
            "Allow-list destinations and prevent access to private, loopback, link-local, and metadata networks.",
        ),
        "generic": (
            "CWE-20",
            "Validate untrusted input before it reaches the security-sensitive operation.",
        ),
    }

    def __init__(
        self,
        sources: set[str] | None = None,
        sinks: set[str] | None = None,
        sanitizers: set[str] | None = None,
        max_call_depth: int = 3,
        max_file_size_mb: float = 1,
        timeout: int = 300,
        max_findings: int = 1000,
        source_attrs: set[str] | None = None,
    ) -> None:
        self.sources = set(sources) if sources is not None else set(self.DEFAULT_SOURCES)
        self.sinks = set(sinks) if sinks is not None else set(self.DEFAULT_SINKS)
        self.sanitizers = (
            set(sanitizers) if sanitizers is not None else set(self.DEFAULT_SANITIZERS)
        )
        self.source_attrs = (
            set(source_attrs) if source_attrs is not None else set(self.DEFAULT_SOURCE_ATTRS)
        )
        self.max_call_depth = max(0, min(int(max_call_depth), 5))
        self.max_file_size = max(1, int(float(max_file_size_mb) * 1_000_000))
        self.timeout = max(1, int(timeout))
        self.max_findings = max(1, int(max_findings))
        self._reset()

    def _reset(self) -> None:
        self._root = Path(".")
        self._function_defs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self._imports: dict[str, dict[str, str]] = {}
        self._module_index: dict[str, list[str]] = defaultdict(list)
        self._summary_cache: dict[tuple[str, str | None, int], FuncResult] = {}
        self._stack: set[tuple[str, str | None, int]] = set()
        self._lines_cache: dict[str, list[str]] = {}
        self._deadline = float("inf")
        self._ticks = 0
        self._active_hits: dict[tuple[str, str | None], list[Hit]] = {}

    @override
    def is_applicable(self, context: ScanContext) -> bool:
        root = context.resolved_path
        if root.is_file():
            return root.suffix.lower() == ".py"
        try:
            for _dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                dirnames[:] = [d for d in dirnames if d not in self.SKIP_DIRS]
                if any(name.endswith(".py") for name in filenames):
                    return True
        except OSError:
            return False
        return False

    @override
    async def scan(self, context: ScanContext) -> list[Finding]:
        return await asyncio.to_thread(self._scan_sync, context)

    def _scan_sync(self, context: ScanContext) -> list[Finding]:
        self._reset()
        self._root = context.resolved_path
        self._deadline = time.monotonic() + self.timeout
        files = self._iter_py_files(self._root, context)
        if not files:
            return []

        logger.info("TaintScanner: indexing %d files", len(files))
        for path in files:
            self._index_file(path)

        hits: list[Hit] = []
        try:
            for func_id in sorted(self._function_defs):
                self._tick()
                result = self._summary(func_id, None, self.max_call_depth)
                hits.extend(result.hits)
                if len(hits) >= self.max_findings * 4:
                    break
        except _TaintTimeoutError:
            logger.warning(
                "TaintScanner: timeout after %ss; returning deterministic partial results",
                self.timeout,
            )

        findings = self._hits_to_findings(hits)
        logger.info(
            "TaintScanner: %d functions, %d findings", len(self._function_defs), len(findings)
        )
        return findings

    def _tick(self) -> None:
        self._ticks += 1
        if self._ticks & 0xFF == 0 and time.monotonic() > self._deadline:
            raise _TaintTimeoutError

    def _iter_py_files(self, root: Path, context: ScanContext) -> list[Path]:
        ignore = list(getattr(getattr(context, "config", None), "ignore", []) or [])
        if root.is_file():
            return (
                [root]
                if root.suffix.lower() == ".py" and self._file_allowed(root, root.parent, ignore)
                else []
            )

        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames if d not in self.SKIP_DIRS and not d.endswith(".egg-info")
            )
            for name in sorted(filenames):
                if not name.endswith(".py"):
                    continue
                path = Path(dirpath) / name
                if path.is_symlink() or not self._file_allowed(path, root, ignore):
                    continue
                files.append(path)
        return files

    def _file_allowed(self, path: Path, root: Path, ignore: list[str]) -> bool:
        try:
            if path.stat().st_size > self.max_file_size:
                return False
            rel = path.relative_to(root).as_posix()
        except (OSError, ValueError):
            return False
        for pattern in ignore:
            try:
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(f"/{rel}", pattern):
                    return False
            except (TypeError, ValueError):
                if pattern in rel:
                    return False
        return True

    def _index_file(self, path: Path) -> None:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, ValueError, RecursionError, MemoryError) as exc:
            logger.debug("TaintScanner: cannot parse %s: %s", path, exc)
            return

        key = str(path)
        self._imports[key] = self._collect_imports(tree)
        self._index_functions(tree.body, key, "")
        self._register_module(path, key)

        # Module-level executable code is represented as a pseudo function.
        top = [
            node
            for node in tree.body
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        if top:
            pseudo = ast.FunctionDef(
                name="<module>",
                args=ast.arguments(
                    posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
                ),
                body=top,
                decorator_list=[],
                returns=None,
                type_comment=None,
                type_params=[],
                lineno=1,
                col_offset=0,
                end_lineno=getattr(top[-1], "end_lineno", 1) or 1,
                end_col_offset=getattr(top[-1], "end_col_offset", 0) or 0,
            )
            self._function_defs[f"{key}::<module>"] = pseudo

    def _index_functions(
        self,
        body: list[ast.stmt],
        file_key: str,
        prefix: str,
    ) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._function_defs[f"{file_key}::{prefix}{node.name}"] = node
            elif isinstance(node, ast.ClassDef):
                self._index_functions(node.body, file_key, f"{prefix}{node.name}.")
            elif isinstance(
                node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)
            ):
                for attr in ("body", "orelse", "finalbody"):
                    self._index_functions(getattr(node, attr, []), file_key, prefix)
                for handler in getattr(node, "handlers", []):
                    self._index_functions(handler.body, file_key, prefix)
            elif isinstance(node, ast.Match):
                for case in node.cases:
                    self._index_functions(case.body, file_key, prefix)

    def _register_module(self, path: Path, key: str) -> None:
        try:
            parts = list(path.relative_to(self._root).with_suffix("").parts)
        except ValueError:
            return
        if parts and parts[-1] == "__init__":
            parts.pop()
        if not parts:
            return
        for i in range(len(parts)):
            module = ".".join(parts[i:])
            self._module_index[module].append(key)

    @staticmethod
    def _collect_imports(tree: ast.Module) -> dict[str, str]:
        imports: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split(".")[0]] = alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    imports[alias.asname or alias.name] = (
                        f"{module}.{alias.name}" if module else alias.name
                    )
        return imports

    def _dotted(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = self._dotted(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return None

    def _resolved_dotted(self, node: ast.AST, file_key: str) -> str | None:
        dotted = self._dotted(node)
        if not dotted:
            return None
        first, dot, rest = dotted.partition(".")
        real = self._imports.get(file_key, {}).get(first)
        return f"{real}{dot}{rest}" if real else dotted

    def _get_call_name(self, call: ast.Call, file_key: str) -> str | None:
        return self._resolved_dotted(call.func, file_key)

    @staticmethod
    def _matches(name: str, rules: set[str]) -> bool:
        return any(name == rule or ("." in rule and name.endswith("." + rule)) for rule in rules)

    @staticmethod
    def _match_rule(name: str, rules: set[str]) -> str | None:
        for rule in sorted(rules, key=len, reverse=True):
            if name == rule or ("." in rule and name.endswith("." + rule)):
                return rule
        return None

    def _is_source(self, name: str) -> bool:
        return self._matches(name, self.sources)

    def _is_sink(self, name: str) -> bool:
        return self._matches(name, self.sinks)

    def _is_sanitizer(self, name: str) -> bool:
        return self._matches(name, self.sanitizers)

    def _lookup_in_module(self, module: str, name: str) -> str | None:
        files = self._module_index.get(module.lstrip("."), [])
        candidates = [
            f"{file_key}::{name}"
            for file_key in files
            if f"{file_key}::{name}" in self._function_defs
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _resolve_call(self, call: ast.Call, ctx: _Ctx) -> tuple[str, int] | None:
        func = call.func
        file_key = ctx.file_key
        defs = self._function_defs
        if isinstance(func, ast.Name):
            local = f"{file_key}::{func.id}"
            if local in defs:
                return local, 0
            local_method = f"{file_key}::{func.id}.__call__"
            if local_method in defs:
                return local_method, 0
            real = self._imports.get(file_key, {}).get(func.id)
            if real and "." in real:
                module, _, fn = real.rpartition(".")
                hit = self._lookup_in_module(module, fn)
                if hit:
                    return hit, 0
        elif isinstance(func, ast.Attribute):
            chain = self._attr_chain(func)
            if chain:
                if len(chain) == 2 and chain[0] in {"self", "cls"}:
                    qual = ctx.func_id.split("::", 1)[1]
                    if "." in qual:
                        cls = qual.rsplit(".", 1)[0]
                        cid = f"{file_key}::{cls}.{chain[1]}"
                        if cid in defs:
                            return cid, 1
                if len(chain) == 2:
                    cid = f"{file_key}::{chain[0]}.{chain[1]}"
                    if cid in defs:
                        return cid, 0
            dotted = self._resolved_dotted(func, file_key)
            if dotted and "." in dotted:
                module, _, fn = dotted.rpartition(".")
                hit = self._lookup_in_module(module, fn)
                if hit:
                    return hit, 0
                if "." in module:
                    module2, _, cls = module.rpartition(".")
                    hit = self._lookup_in_module(module2, f"{cls}.{fn}")
                    if hit:
                        return hit, 0
        return None

    @staticmethod
    def _attr_chain(node: ast.Attribute) -> list[str] | None:
        parts: list[str] = []
        current: ast.AST = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return list(reversed(parts))
        return None

    def _param_pairs(self, call: ast.Call, callee: str, shift: int) -> list[tuple[str, ast.expr]]:
        fn = self._function_defs[callee]
        positional = [arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args)][shift:]
        valid = {arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs)}
        pairs: list[tuple[str, ast.expr]] = []
        for index, arg in enumerate(call.args):
            if isinstance(arg, ast.Starred):
                break
            if index < len(positional):
                pairs.append((positional[index], arg))
        for keyword in call.keywords:
            if keyword.arg and keyword.arg in valid:
                pairs.append((keyword.arg, keyword.value))
        return pairs

    def _summary(self, func_id: str, parameter: str | None, remaining: int) -> FuncResult:
        key = (func_id, parameter, remaining)
        cached = self._summary_cache.get(key)
        if cached is not None:
            return cached
        guard = (func_id, parameter, remaining)
        if guard in self._stack:
            return FuncResult()
        self._stack.add(guard)
        try:
            result = self._analyze_function(func_id, parameter, remaining)
        finally:
            self._stack.discard(guard)
        self._summary_cache[key] = result
        return result

    def _analyze_function(self, func_id: str, parameter: str | None, remaining: int) -> FuncResult:
        fn = self._function_defs[func_id]
        file_key = func_id.split("::", 1)[0]
        qualified = func_id.split("::", 1)[1]
        ctx = _Ctx(file_key, func_id, remaining, parameter)
        env: dict[str, TaintInfo] = {}

        if parameter is None:
            env.update(self._route_taint(fn, file_key, qualified))
        else:
            env[parameter] = TaintInfo(
                _PARAM,
                [
                    self._step(
                        file_key,
                        getattr(fn, "lineno", 1),
                        f"PARAMETER `{parameter}` of {qualified}",
                    )
                ],
            )

        hits: list[Hit] = []
        returns: list[TaintInfo] = []
        try:
            env_out, block_returns = self._analyze_block(fn.body, env, ctx)
            del env_out
            returns.extend(block_returns)
        except _TaintTimeoutError:
            raise
        except (RecursionError, MemoryError):
            logger.debug("TaintScanner: analysis guard triggered for %s", func_id, exc_info=True)
        # Hits are accumulated through an instance scratch list to avoid threading state.
        hits = (
            getattr(self, "_active_hits", {}).pop((func_id, parameter), [])
            if hasattr(self, "_active_hits")
            else []
        )
        return FuncResult(self._dedupe_hits(hits), self._merge_returns(returns))

    def _analyze_block(
        self,
        statements: list[ast.stmt],
        env: dict[str, TaintInfo],
        ctx: _Ctx,
    ) -> tuple[dict[str, TaintInfo], list[TaintInfo]]:
        current = dict(env)
        returns: list[TaintInfo] = []
        for statement in statements:
            self._tick()
            current, statement_returns = self._analyze_statement(statement, current, ctx)
            returns.extend(statement_returns)
        return current, returns

    def _record_hit(self, ctx: _Ctx, hit: Hit) -> None:
        active = getattr(self, "_active_hits", None)
        if active is None:
            active = {}
            self._active_hits = active
        active.setdefault((ctx.func_id, ctx.parameter), []).append(hit)

    def _analyze_statement(
        self,
        statement: ast.stmt,
        env: dict[str, TaintInfo],
        ctx: _Ctx,
    ) -> tuple[dict[str, TaintInfo], list[TaintInfo]]:
        current = dict(env)
        returns: list[TaintInfo] = []

        if isinstance(statement, ast.Assign):
            info = self._eval_expr(statement.value, current, ctx)
            for target in statement.targets:
                self._bind_target(target, info, current, statement.value, ctx)
            return current, returns

        if isinstance(statement, ast.AnnAssign):
            info = self._eval_expr(statement.value, current, ctx) if statement.value else None
            self._bind_target(statement.target, info, current, statement.value, ctx)
            return current, returns

        if isinstance(statement, ast.AugAssign):
            left_info = self._target_taint(statement.target, current)
            right_info = self._eval_expr(statement.value, current, ctx)
            info = left_info or right_info
            if left_info and right_info and left_info.source != right_info.source:
                info = left_info
            self._bind_target(statement.target, info, current, statement.value, ctx)
            return current, returns

        if isinstance(statement, ast.NamedExpr):
            info = self._eval_expr(statement.value, current, ctx)
            self._bind_target(statement.target, info, current, statement.value, ctx)
            return current, returns

        if isinstance(statement, ast.Expr):
            self._eval_expr(statement.value, current, ctx)
            return current, returns

        if isinstance(statement, ast.Return):
            if statement.value is not None:
                info = self._eval_expr(statement.value, current, ctx)
                if info:
                    returns.append(
                        info.extend(self._step(ctx.file_key, statement.lineno, "RETURN"))
                    )
            return current, returns

        if isinstance(statement, ast.If):
            self._eval_expr(statement.test, current, ctx)
            left, left_returns = self._analyze_block(statement.body, dict(current), ctx)
            right, right_returns = self._analyze_block(statement.orelse, dict(current), ctx)
            return self._merge_env(left, right), [*left_returns, *right_returns]

        if isinstance(statement, (ast.For, ast.AsyncFor)):
            iter_info = self._eval_expr(statement.iter, current, ctx)
            loop_env = dict(current)
            self._bind_target(statement.target, iter_info, loop_env, statement.iter, ctx)
            loop_out, loop_returns = self._analyze_block(statement.body, loop_env, ctx)
            else_out, else_returns = self._analyze_block(statement.orelse, dict(current), ctx)
            merged = self._merge_env(current, self._merge_env(loop_out, else_out))
            return merged, [*loop_returns, *else_returns]

        if isinstance(statement, ast.While):
            self._eval_expr(statement.test, current, ctx)
            loop_out, loop_returns = self._analyze_block(statement.body, dict(current), ctx)
            else_out, else_returns = self._analyze_block(statement.orelse, dict(current), ctx)
            return self._merge_env(current, self._merge_env(loop_out, else_out)), [
                *loop_returns,
                *else_returns,
            ]

        if isinstance(statement, (ast.With, ast.AsyncWith)):
            out = dict(current)
            for item in statement.items:
                info = self._eval_expr(item.context_expr, out, ctx)
                if item.optional_vars:
                    self._bind_target(item.optional_vars, info, out, item.context_expr, ctx)
            return self._analyze_block(statement.body, out, ctx)

        if isinstance(statement, ast.Try):
            branches: list[tuple[dict[str, TaintInfo], list[TaintInfo]]] = []
            branches.append(self._analyze_block(statement.body, dict(current), ctx))
            for handler in statement.handlers:
                branches.append(self._analyze_block(handler.body, dict(current), ctx))
            if statement.orelse:
                branches.append(self._analyze_block(statement.orelse, dict(current), ctx))
            merged = dict(current)
            branch_returns: list[TaintInfo] = []
            for branch_env, branch_ret in branches:
                merged = self._merge_env(merged, branch_env)
                branch_returns.extend(branch_ret)
            if statement.finalbody:
                merged, final_returns = self._analyze_block(statement.finalbody, merged, ctx)
                branch_returns.extend(final_returns)
            return merged, branch_returns

        if isinstance(statement, ast.Match):
            self._eval_expr(statement.subject, current, ctx)
            match_branches: list[tuple[dict[str, TaintInfo], list[TaintInfo]]] = [
                self._analyze_block(case.body, dict(current), ctx) for case in statement.cases
            ]
            merged = dict(current)
            match_returns: list[TaintInfo] = []
            for branch_env, branch_ret in match_branches:
                merged = self._merge_env(merged, branch_env)
                match_returns.extend(branch_ret)
            return merged, match_returns

        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Definitions are indexed separately; decorators/defaults are still
            # executable, so inspect them for tainted calls.
            for node in ast.walk(statement):
                if isinstance(node, ast.Call):
                    self._inspect_call(node, current, ctx)
            return current, returns

        # Conservative generic handling: inspect all calls and assignments in a
        # statement while avoiding mutation of names we cannot safely bind.
        for node in ast.walk(statement):
            if isinstance(node, ast.Call):
                self._inspect_call(node, current, ctx)
        return current, returns

    def _bind_target(
        self,
        target: ast.AST,
        info: TaintInfo | None,
        env: dict[str, TaintInfo],
        value: ast.AST | None,
        ctx: _Ctx,
    ) -> None:
        names = self._target_names(target)
        if info:
            step = self._step(
                ctx.file_key,
                getattr(value, "lineno", getattr(target, "lineno", 1)),
                f"ASSIGN: {', '.join(names) if names else self._safe_source(target)}",
            )
            for name in names:
                env[name] = info.extend(step)
        else:
            for name in names:
                env.pop(name, None)

    @staticmethod
    def _target_names(target: ast.AST) -> list[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Starred):
            return TaintScanner._target_names(target.value)
        if isinstance(target, (ast.Tuple, ast.List)):
            result: list[str] = []
            for elt in target.elts:
                result.extend(TaintScanner._target_names(elt))
            return result
        return []

    @staticmethod
    def _target_taint(target: ast.AST, env: dict[str, TaintInfo]) -> TaintInfo | None:
        if isinstance(target, ast.Name):
            return env.get(target.id)
        return None

    def _eval_expr(
        self, node: ast.AST | None, env: dict[str, TaintInfo], ctx: _Ctx
    ) -> TaintInfo | None:
        if node is None:
            return None
        self._tick()
        if isinstance(node, ast.Constant):
            return None
        if isinstance(node, ast.Name):
            return env.get(node.id)
        if isinstance(node, ast.Attribute):
            dotted = self._resolved_dotted(node, ctx.file_key)
            if dotted and self._matches(dotted, self.source_attrs):
                return TaintInfo(
                    dotted, [self._step(ctx.file_key, node.lineno, f"SOURCE: {dotted}")]
                )
            return self._eval_expr(node.value, env, ctx)
        if isinstance(node, ast.Call):
            # Inspect the call before deciding whether its result propagates
            # taint. An outer expression must never hide a nested security sink,
            # e.g. str(subprocess.run(command, shell=True).returncode).
            self._inspect_call(node, env, ctx)

            name = self._get_call_name(node, ctx.file_key)
            if name:
                if self._is_source(name):
                    return TaintInfo(
                        name,
                        [self._step(ctx.file_key, node.lineno, f"SOURCE: {name}")],
                    )

                if self._is_sanitizer(name):
                    # Sanitizers stop taint propagation through their result,
                    # but every child still needs inspection so nested sinks are
                    # not suppressed by the outer sanitizer.
                    for child in ast.iter_child_nodes(node):
                        self._eval_expr(child, env, ctx)
                    return None

                if ctx.remaining > 0:
                    resolved = self._resolve_call(node, ctx)
                    if resolved:
                        return self._call_result_taint(node, resolved, env, ctx)

            result: TaintInfo | None = None
            for child in ast.iter_child_nodes(node):
                child_info = self._eval_expr(child, env, ctx)
                if child_info:
                    result = child_info
                    break
            return result
        if isinstance(node, ast.FormattedValue):
            return self._eval_expr(node.value, env, ctx)
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                info = self._eval_expr(value, env, ctx)
                if info:
                    return info
            return None
        if isinstance(node, ast.Lambda):
            return None
        for child in ast.iter_child_nodes(node):
            info = self._eval_expr(child, env, ctx)
            if info:
                return info
        return None

    def _inspect_call(self, call: ast.Call, env: dict[str, TaintInfo], ctx: _Ctx) -> None:
        name = self._get_call_name(call, ctx.file_key)
        if not name:
            return
        rule = self._match_rule(name, self.sinks)
        if rule:
            # YAML SafeLoader is not an unsafe sink.
            if rule in {"yaml.load", "yaml.full_load"} and self._yaml_call_safe(call, ctx.file_key):
                pass
            else:
                info = self._tainted_sink_arg(call, rule, env, ctx)
                if info:
                    path = [*info.path, self._step(ctx.file_key, call.lineno, f"SINK: {name}")]
                    self._record_hit(
                        ctx,
                        Hit(
                            sink=name,
                            file=ctx.file_key,
                            line=call.lineno,
                            col=call.col_offset,
                            func_id=ctx.func_id,
                            source=info.source,
                            path=path,
                            severity=self._sink_severity(name, call),
                            depth=self.max_call_depth - ctx.remaining,
                            cross_file=False,
                        ),
                    )

        if ctx.remaining <= 0:
            return
        resolved = self._resolve_call(call, ctx)
        if not resolved:
            return
        callee, shift = resolved
        for parameter, argument in self._param_pairs(call, callee, shift):
            info = self._eval_expr(argument, env, ctx)
            if not info:
                continue
            summary = self._summary(callee, parameter, ctx.remaining - 1)
            call_step = self._step(
                ctx.file_key, call.lineno, f"CALL: {callee.split('::', 1)[1]}({parameter}=...)"
            )
            for hit in summary.hits:
                self._record_hit(
                    ctx,
                    replace(
                        hit,
                        source=info.source,
                        path=[*info.path, call_step, *hit.path],
                        depth=hit.depth + 1,
                        cross_file=hit.cross_file or hit.file != ctx.file_key,
                    ),
                )

    def _tainted_sink_arg(
        self,
        call: ast.Call,
        rule: str,
        env: dict[str, TaintInfo],
        ctx: _Ctx,
    ) -> TaintInfo | None:
        # Subprocess deserves special treatment: shell=True is an explicit shell
        # boundary; argv-style shell=False calls only propagate sink taint through
        # the executable position. This prevents later argv data from being treated
        # as shell code.
        if rule.startswith("subprocess."):
            shell_true = any(
                kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in call.keywords
            )
            first = call.args[0] if call.args else None
            if shell_true:
                # With shell=True the complete first argument is interpreted by a
                # shell, so taint on that command string is directly security
                # relevant.
                return self._eval_expr(first, env, ctx) if first is not None else None

            if isinstance(first, (ast.List, ast.Tuple)):
                # shell=False with argv-style arguments does not interpret later
                # argv elements as shell source. Only a tainted executable/path
                # position is relevant to this sink rule. Critically, return here
                # even when the first element is a constant; otherwise the generic
                # sink walk below would incorrectly traverse every argv element and
                # re-flag a harmless list such as ["echo", user_input].
                if not first.elts:
                    return None
                return self._eval_expr(first.elts[0], env, ctx)

            if first is not None and isinstance(first, ast.Name):
                # A dynamic command value supplied without shell=True is not
                # classical shell injection, but a tainted executable/command name
                # is still relevant for direct process-spawn APIs.
                return self._eval_expr(first, env, ctx)

            # Constants, attributes and other non-name expressions are not treated
            # as shell-injection sinks under shell=False. Do not fall through into
            # generic argument traversal for subprocess calls.
            return None

        positions = self._SINK_POSITIONS.get(rule)
        for index, arg in enumerate(call.args):
            if positions is not None and index not in positions:
                continue
            expression = arg.value if isinstance(arg, ast.Starred) else arg
            info = self._eval_expr(expression, env, ctx)
            if info:
                return info
        for keyword in call.keywords:
            if keyword.arg is None or keyword.arg in self._SAFE_KWARGS:
                continue
            if positions is not None and keyword.arg not in self._SINK_MAIN_KWARGS:
                continue
            info = self._eval_expr(keyword.value, env, ctx)
            if info:
                return info
        return None

    def _call_result_taint(
        self,
        call: ast.Call,
        resolved: tuple[str, int],
        env: dict[str, TaintInfo],
        ctx: _Ctx,
    ) -> TaintInfo | None:
        callee, shift = resolved
        if ctx.remaining <= 0:
            return None
        sub = ctx.remaining - 1
        base = self._summary(callee, None, sub)
        if base.returns:
            return base.returns.extend(
                self._step(ctx.file_key, call.lineno, f"RETURN from {callee.split('::', 1)[1]}")
            )
        for parameter, argument in self._param_pairs(call, callee, shift):
            info = self._eval_expr(argument, env, ctx)
            if not info:
                continue
            summary = self._summary(callee, parameter, sub)
            if summary.returns:
                return info.extend(
                    self._step(
                        ctx.file_key,
                        call.lineno,
                        f"CALL: {callee.split('::', 1)[1]}({parameter}=...) returns it",
                    )
                )
        return None

    def _route_taint(
        self,
        fn: ast.FunctionDef | ast.AsyncFunctionDef,
        file_key: str,
        qualified: str,
    ) -> dict[str, TaintInfo]:
        if not self._is_route_handler(fn):
            return {}
        result: dict[str, TaintInfo] = {}
        positional = (*fn.args.posonlyargs, *fn.args.args)
        defaults: list[ast.expr | None] = [None] * (len(positional) - len(fn.args.defaults)) + list(
            fn.args.defaults
        )
        for arg, default in [
            *zip(positional, defaults, strict=True),
            *zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True),
        ]:
            if arg.arg in self._ROUTE_SKIP_PARAMS:
                continue
            if isinstance(default, ast.Call) and (self._dotted(default.func) or "").rsplit(".", 1)[
                -1
            ] in {"Depends", "Security"}:
                continue
            label = f"route parameter `{arg.arg}`"
            result[arg.arg] = TaintInfo(
                label, [self._step(file_key, fn.lineno, f"SOURCE: {label} of {qualified}")]
            )
        return result

    def _is_route_handler(self, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for decorator in fn.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            dotted = self._dotted(target)
            if not dotted:
                continue
            last = dotted.rsplit(".", 1)[-1]
            if last in self._ROUTE_DECORATORS and ("." in dotted or last == "api_view"):
                return True
        return False

    @staticmethod
    def _merge_env(left: dict[str, TaintInfo], right: dict[str, TaintInfo]) -> dict[str, TaintInfo]:
        merged = dict(left)
        for name, info in right.items():
            if name not in merged:
                merged[name] = info
            elif merged[name].source != info.source:
                merged[name] = merged[name]
        return merged

    @staticmethod
    def _merge_returns(values: list[TaintInfo]) -> TaintInfo | None:
        if not values:
            return None
        first = values[0]
        for value in values[1:]:
            if value.source == first.source:
                return first if len(first.path) <= len(value.path) else value
        return first

    @staticmethod
    def _dedupe_hits(hits: list[Hit]) -> list[Hit]:
        seen: set[tuple[str, int, int, str, str]] = set()
        out: list[Hit] = []
        for hit in hits:
            key = (hit.file, hit.line, hit.col, hit.sink, hit.source)
            if key not in seen:
                seen.add(key)
                out.append(hit)
        return out

    @staticmethod
    def _sink_kind(name: str) -> str:
        if TaintScanner._matches(
            name,
            {
                "eval",
                "exec",
                "compile",
                "__import__",
                "builtins.eval",
                "builtins.exec",
                "builtins.compile",
            },
        ):
            return "code"
        if TaintScanner._matches(
            name, {"os.system", "os.popen", "os.spawnv", "os.spawnve"}
        ) or name.startswith("subprocess."):
            return "command"
        if TaintScanner._matches(
            name,
            {
                "cursor.execute",
                "cursor.executemany",
                "cursor.executescript",
                "connection.execute",
                "connection.executemany",
                "connection.executescript",
            },
        ):
            return "sql"
        if TaintScanner._matches(
            name,
            {
                "pickle.loads",
                "pickle.load",
                "marshal.loads",
                "marshal.load",
                "yaml.load",
                "yaml.full_load",
                "yaml.unsafe_load",
            },
        ):
            return "deserialize"
        if TaintScanner._matches(
            name, {"render_template_string", "jinja2.Template", "jinja2.Environment.from_string"}
        ):
            return "template"
        if TaintScanner._matches(
            name,
            {
                "open",
                "pathlib.Path.open",
                "pathlib.Path.write_text",
                "pathlib.Path.write_bytes",
                "os.open",
            },
        ):
            return "path"
        if TaintScanner._matches(
            name,
            {
                "requests.get",
                "requests.post",
                "requests.put",
                "requests.delete",
                "requests.request",
                "httpx.get",
                "httpx.post",
                "httpx.put",
                "httpx.delete",
                "httpx.request",
                "urllib.request.urlopen",
                "urllib.request.Request",
            },
        ):
            return "ssrf"
        return "generic"

    def _sink_severity(self, name: str, call: ast.Call) -> Severity:
        if self._matches(name, self._CRITICAL_SINKS):
            return Severity.CRITICAL
        if self._matches(name, self._HIGH_SINKS):
            if name.startswith("subprocess."):
                shell_true = any(
                    kw.arg == "shell"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                    for kw in call.keywords
                )
                first = call.args[0] if call.args else None
                if not shell_true and isinstance(first, (ast.List, ast.Tuple)):
                    return Severity.MEDIUM
            return Severity.HIGH
        return Severity.MEDIUM

    def _rel(self, file_key: str) -> str:
        try:
            return Path(file_key).relative_to(self._root).as_posix()
        except ValueError:
            return Path(file_key).as_posix()

    def _step(self, file_key: str, line: int, action: str) -> dict[str, Any]:
        return {"file": self._rel(file_key), "line": int(line), "action": action}

    def _line_text(self, file_key: str, line: int) -> str:
        lines = self._lines_cache.get(file_key)
        if lines is None:
            try:
                lines = Path(file_key).read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                lines = []
            self._lines_cache[file_key] = lines
        return lines[line - 1].strip()[:300] if 0 < line <= len(lines) else ""

    def _context(self, file_key: str, line: int, radius: int = 2) -> str:
        lines = self._lines_cache.get(file_key)
        if lines is None:
            self._line_text(file_key, line)
            lines = self._lines_cache.get(file_key, [])
        start = max(0, line - 1 - radius)
        end = min(len(lines), line + radius)
        return "\n".join(lines[start:end])

    def _hits_to_findings(self, hits: list[Hit]) -> list[Finding]:
        best: dict[tuple[str, int, int, str], Hit] = {}
        for hit in hits:
            # Parameter-only summaries are internal evidence unless that
            # parameter is a route source in the concrete entry function.
            if hit.source == _PARAM:
                continue
            key = (hit.file, hit.line, hit.col, hit.sink)
            current = best.get(key)
            if current is None or (hit.depth, len(hit.path)) < (current.depth, len(current.path)):
                best[key] = hit

        ordered = sorted(
            best.values(),
            key=lambda hit: (
                -hit.severity.weight,
                hit.depth,
                self._rel(hit.file),
                hit.line,
                hit.sink,
            ),
        )[: self.max_findings]
        return [self._hit_to_finding(hit) for hit in ordered]

    def _hit_to_finding(self, hit: Hit) -> Finding:
        rel = self._rel(hit.file)
        kind = self._sink_kind(hit.sink)
        cwe, advice = self._SINK_ADVICE[kind]
        interprocedural = hit.depth > 0
        rule_id = "taint-flow-interprocedural" if interprocedural else "taint-flow"
        digest = hashlib.sha1(
            f"{rel}:{hit.line}:{hit.sink}:{hit.source}".encode(), usedforsecurity=False
        ).hexdigest()[:10]
        trace = [
            f"Source: `{hit.source}` → sink: `{hit.sink}` ({rel}:{hit.line})",
            "",
            "Taint trace:",
        ]
        for step in hit.path:
            trace.append(
                f"  {step.get('file', rel)}:{step.get('line', 0)}  {step.get('action', '')}"
            )
        trace.extend(["", f"Fix: {advice}"])
        return TaintFinding(
            scanner=self.name,
            category=Category.VULNERABILITY,
            severity=hit.severity,
            confidence=0.72 if interprocedural else 0.82,
            file=rel,
            line=hit.line,
            title=f"Tainted data reaches {hit.sink}",
            description="\n".join(trace),
            id=f"TAINT-{digest}",
            rule_id=rule_id,
            rule_name=f"Tainted data reaches {hit.sink}",
            message=f"Untrusted data from `{hit.source}` reaches `{hit.sink}` without a recognized sanitizer.",
            column=hit.col,
            evidence=self._line_text(hit.file, hit.line),
            context=self._context(hit.file, hit.line),
            tags=["taint", cwe.lower()],
            fix_available=False,
            fix_description=advice,
            metadata={
                "rule_id": rule_id,
                "language": "python",
                "cwe": cwe,
                "source": hit.source,
                "sink": hit.sink,
                "sink_kind": kind,
                "call_depth": hit.depth,
                "cross_file": hit.cross_file,
                "analysis_layer": "source-to-sink",
                "precision": "flow-proven",
            },
            taint_path=hit.path,
            source_function=hit.source,
            sink_function=hit.sink,
            call_depth=hit.depth,
            cross_file=hit.cross_file,
        )

    @staticmethod
    def _yaml_call_safe(call: ast.Call, file_key: str) -> bool:
        del file_key
        for keyword in call.keywords:
            if keyword.arg == "Loader":
                name = TaintScanner._static_name(keyword.value)
                return name.rsplit(".", 1)[-1] in {"SafeLoader", "BaseLoader"}
        return False

    @staticmethod
    def _static_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = TaintScanner._static_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    @staticmethod
    def _safe_source(node: ast.AST) -> str:
        try:
            return ast.unparse(node)[:120]
        except Exception:
            return type(node).__name__


__all__ = ["TaintFinding", "TaintScanner"]
