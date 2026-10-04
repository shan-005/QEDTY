"""Seraph Guard Language Server Protocol (LSP) Backend."""

from __future__ import annotations

import json
import logging
import re
import signal
import sys
import threading

from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from urllib.request import url2pathname


if TYPE_CHECKING:
    from lsprotocol.types import (
        DidChangeTextDocumentParams,
        DidOpenTextDocumentParams,
        DidSaveTextDocumentParams,
        InitializeParams,
    )

# ── Runtime LSP Imports ──────────────────────────────────────────────────────
from lsprotocol.types import (
    INITIALIZE,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    Diagnostic,
    DiagnosticSeverity,
    Position,
    Range,
)


try:
    from pygls.lsp.server import LanguageServer
except ImportError:
    from pygls.server import LanguageServer  # type: ignore[attr-defined,no-redef]

# ── Seraph Imports ───────────────────────────────────────────────────────────
from seraph.guard import __version__
from seraph.guard.config import SeraphConfig
from seraph.guard.intelligence.learning import AdaptiveLearningEngine
from seraph.guard.scanners.base import Severity
from seraph.guard.scanners.pattern import PatternScanner
from seraph.guard.scanners.secret import SECRET_PATTERNS
from seraph.guard.suppression.engine import SuppressionEngine


logger = logging.getLogger(__name__)

# LSP Severity Mappings
LSP_ERROR = DiagnosticSeverity.Error
LSP_WARNING = DiagnosticSeverity.Warning
LSP_INFO = DiagnosticSeverity.Information
LSP_HINT = DiagnosticSeverity.Hint


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════
def _severity_to_lsp(severity_str: str) -> Any:
    """Convert a Seraph severity string to an LSP DiagnosticSeverity."""
    return {
        "critical": LSP_ERROR,
        "high": LSP_ERROR,
        "medium": LSP_WARNING,
        "low": LSP_INFO,
        "info": LSP_HINT,
    }.get(severity_str.lower(), LSP_INFO)


def _uri_to_path(uri: str) -> str:
    """Convert file:///home/user/file.py → /home/user/file.py"""
    parsed = urlparse(uri)
    return url2pathname(parsed.path)


def _load_cached_findings(workspace_root: str) -> dict[str, list[dict[str, Any]]]:
    """Load findings from scan_results.json so the LSP can show full-scan
    results instantly without re-scanning the whole repo on every keystroke.
    """
    findings_map: dict[str, list[dict[str, Any]]] = {}
    root = Path(workspace_root)

    candidates: list[Path] = [
        root / "scan_results.json",
        root / ".seraph-cache" / "scan_results.json",
    ]
    for p in root.glob("**/scan_results.json"):
        if ".seraph-cache" not in str(p):
            candidates.append(p)

    for json_path in candidates:
        if not json_path.exists():
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            raw = data.get("findings", [])
            if not raw:
                continue
            for f in raw:
                fp = f.get("file", "")
                if not fp:
                    continue
                abs_path = str((root / fp).resolve())
                findings_map.setdefault(abs_path, []).append(f)
            logger.info("LSP: loaded %d findings from %s", len(raw), json_path.name)
            break
        except (json.JSONDecodeError, OSError):
            continue

    return findings_map


# ═══════════════════════════════════════════════════════════════════════════
#  Core analysis (no LSP dependency)
# ═══════════════════════════════════════════════════════════════════════════
def _analyze_document(
    uri: str,
    text: str,
    compiled_patterns: dict[str, tuple[re.Pattern[str], Severity]],
    suppression: SuppressionEngine | None,
    cached_findings: dict[str, list[dict[str, Any]]],
    learning: AdaptiveLearningEngine | None = None,
    ufic: Any | None = None,
    config: SeraphConfig | None = None,
) -> list[Any]:
    """Analyze a document and return a list of Diagnostic objects."""
    file_path = Path(_uri_to_path(uri))
    abs_path = str(file_path.resolve())
    diagnostics: list[Any] = []

    # BUG #5 FIX: UFIC Integration
    if ufic:
        try:
            if ufic.evaluate_file(str(file_path)):
                return []  # UFIC says suppress this file
        except Exception as e:
            logger.debug("UFIC evaluate_file failed: %s", e)

    if suppression:
        should_scan, _ = suppression.should_scan_file(str(file_path))
        if not should_scan:
            return diagnostics

    for f in cached_findings.get(abs_path, []):
        rule_id = f.get("rule_id", f.get("title", "unknown"))

        # BUG #4 FIX: Learning Engine Integration
        if learning and hasattr(learning, "should_suppress_diagnostic"):
            try:
                if learning.should_suppress_diagnostic(rule_id, str(file_path)):
                    continue
            except Exception as e:
                logger.debug("Learning engine suppress check failed: %s", e)

        sev_str = str(f.get("severity", "info"))
        line = max(f.get("line", 1) - 1, 0)
        col = f.get("column", 0) or 0
        message = f.get("message", rule_id)

        blast = f.get("blast_radius")
        if isinstance(blast, dict):
            score = blast.get("blast_radius_score")
            if score is not None:
                message += f"  [Blast: {score:.0f}%]"

        cl = f.get("conformal_lower")
        if cl is not None:
            message += f"  [Confidence: {cl:.0%}+]"

        diagnostics.append(
            Diagnostic(
                range=Range(
                    start=Position(line=line, character=col),
                    end=Position(line=line, character=col + 40),
                ),
                message=f"[Seraph:{rule_id}] {message}",
                severity=_severity_to_lsp(sev_str),
                source="seraph-guard",
                code=rule_id,
            )
        )

    lines = text.splitlines()
    for i, line_text in enumerate(lines):
        for rule_name, pattern in SECRET_PATTERNS.items():
            m = pattern.search(line_text)
            if not m:
                continue
            is_critical = any(
                kw in rule_name.lower() for kw in ("aws", "github", "google", "stripe")
            )
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=i, character=m.start()),
                        end=Position(line=i, character=m.end()),
                    ),
                    message=f"[Seraph:secret] Potential {rule_name.replace('_', ' ')} detected",
                    severity=LSP_ERROR if is_critical else LSP_WARNING,
                    source="seraph-guard",
                    code=rule_name,
                )
            )

    for i, line_text in enumerate(lines):
        stripped = line_text.strip()
        if stripped.startswith(("//", "#", "/*", "*", "<!--")):
            continue
        for p_str, (regex, sev) in compiled_patterns.items():
            m = regex.search(line_text)
            if not m:
                continue
            sev_val = sev.value if hasattr(sev, "value") else str(sev)
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=i, character=m.start()),
                        end=Position(line=i, character=m.end()),
                    ),
                    message=f"[Seraph:pattern] Dangerous pattern: {p_str}",
                    severity=_severity_to_lsp(sev_val),
                    source="seraph-guard",
                    code="pattern",
                )
            )

    # BUG #3 FIX: Correct Deduplication
    seen: set[str] = set()
    deduped: list[Any] = []
    for d in diagnostics:
        key = f"{d.range.start.line}:{d.code}:{d.message[:50]}"
        if key not in seen:
            seen.add(key)
            deduped.append(d)

    # BUG #7 FIX: Truncation Warning
    max_diags = getattr(config, "lsp_max_diagnostics", 100) if config else 100
    if len(deduped) > max_diags:
        extra = len(deduped) - max_diags
        logger.warning("LSP: truncated %d diagnostics to %d", extra, max_diags)
        deduped = deduped[:max_diags]
        deduped.append(
            Diagnostic(
                range=Range(
                    start=Position(line=len(lines) - 1, character=0),
                    end=Position(line=len(lines) - 1, character=1),
                ),
                message=f"[Seraph] {extra} more findings suppressed (max {max_diags} shown)",
                severity=LSP_HINT,
                source="seraph-guard",
                code="truncated",
            )
        )

    return deduped


# ═══════════════════════════════════════════════════════════════════════════
#  Server class
# ═══════════════════════════════════════════════════════════════════════════
class SeraphLanguageServer(LanguageServer):
    """Lightweight LSP server for real-time IDE squiggles."""

    def __init__(self) -> None:
        super().__init__("seraph-guard", __version__)
        self.config: SeraphConfig | None = None
        self.suppression: SuppressionEngine | None = None
        self.learning: AdaptiveLearningEngine | None = None
        self.ufic: Any = None
        self._compiled_patterns: dict[str, tuple[re.Pattern[str], Severity]] = {}
        self._initialized = False

        # Instance-level state to avoid global variables (PLW0603)
        self._cached_findings: dict[str, list[dict[str, Any]]] = {}
        self._workspace_root: str = ""
        self._workspace_lock = threading.Lock()

    def _init_workspace(self, workspace_path: str) -> None:
        """One-time workspace initialisation (cached results, patterns, etc.)."""
        if self._initialized:
            return

        path = Path(workspace_path)
        self.config = SeraphConfig.from_cli_args(path=str(path))
        self.suppression = SuppressionEngine(str(path))
        self.learning = AdaptiveLearningEngine(cache_dir=path / ".seraph-learn")

        # BUG #5 FIX: UFIC Initialization
        self.ufic = None
        try:
            from seraph.ufic.classifier import UFICClassifier

            self.ufic = UFICClassifier(topology={})
        except ImportError:
            pass

        # BUG #6 FIX: Log Invalid Regex Patterns
        for p_str, sev in PatternScanner.DANGEROUS_PATTERNS.items():
            try:
                self._compiled_patterns[p_str] = (re.compile(p_str), sev)
            except re.error as e:
                logger.warning("Invalid pattern '%s': %s", p_str, e)

        self._workspace_root = workspace_path
        with self._workspace_lock:
            self._cached_findings = _load_cached_findings(workspace_path)

        self._initialized = True
        logger.info(
            "Seraph LSP initialised: workspace=%s  cached=%d  patterns=%d",
            workspace_path,
            len(self._cached_findings),
            len(self._compiled_patterns),
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Handler registration
# ═══════════════════════════════════════════════════════════════════════════
def _register_handlers(srv: SeraphLanguageServer) -> None:
    """Wire up all LSP protocol handlers on *srv*."""

    @srv.feature(INITIALIZE)
    async def _on_initialize(params: InitializeParams) -> dict[str, Any]:
        root_uri = params.root_uri or ""
        workspace = _uri_to_path(root_uri) if root_uri.startswith("file://") else str(Path.cwd())
        srv._init_workspace(workspace)
        return {
            "capabilities": {
                "textDocumentSync": 1,
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "workspaceDiagnostics": False,
                },
            },
            "serverInfo": {"name": "seraph-guard", "version": __version__},
        }

    @srv.feature(TEXT_DOCUMENT_DID_OPEN)
    async def _on_did_open(params: DidOpenTextDocumentParams) -> None:
        _publish(srv, params.text_document.uri, params.text_document.text)

    @srv.feature(TEXT_DOCUMENT_DID_SAVE)
    async def _on_did_save(params: DidSaveTextDocumentParams) -> None:
        fp = Path(_uri_to_path(params.text_document.uri))
        text = fp.read_text(encoding="utf-8", errors="ignore") if fp.exists() else ""
        if text:
            _publish(srv, params.text_document.uri, text)

    @srv.feature(TEXT_DOCUMENT_DID_CHANGE)
    async def _on_did_change(params: DidChangeTextDocumentParams) -> None:
        if params.content_changes:
            _publish(srv, params.text_document.uri, params.content_changes[-1].text)


def _publish(srv: SeraphLanguageServer, uri: str, text: str) -> None:
    """Run analysis and push diagnostics to the editor."""
    if not srv._initialized:
        fp = Path(_uri_to_path(uri))
        for parent in fp.parents:
            if (parent / ".seraph-guard.yaml").exists() or (parent / ".git").exists():
                srv._init_workspace(str(parent))
                break
        else:
            srv._init_workspace(str(fp.parent))

    # BUG #2 FIX: Read snapshot under lock to prevent race conditions
    with srv._workspace_lock:
        cached = srv._cached_findings

    diags = _analyze_document(
        uri=uri,
        text=text,
        compiled_patterns=srv._compiled_patterns,
        suppression=srv.suppression,
        cached_findings=cached,
        learning=srv.learning,
        ufic=srv.ufic,
        config=srv.config,
    )

    # pygls >= 1.0 uses publish_diagnostics.
    # Fallback to text_document_publish_diagnostics for older versions if needed.
    publish = getattr(srv, "publish_diagnostics", None) or getattr(
        srv, "text_document_publish_diagnostics", None
    )
    if publish:
        try:
            publish(uri, diags)
        except TypeError:
            # Fallback for older pygls versions requiring PublishDiagnosticsParams
            try:
                from lsprotocol.types import PublishDiagnosticsParams

                publish(PublishDiagnosticsParams(uri=uri, diagnostics=diags))
            except ImportError:
                pass


# ═══════════════════════════════════════════════════════════════════════════
#  Entry points
# ═══════════════════════════════════════════════════════════════════════════
def start_lsp() -> None:
    """Start the LSP server on stdio. Blocks until stdin closes."""
    srv = SeraphLanguageServer()
    _register_handlers(srv)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
    )

    # BUG #1 FIX: Signal Handlers for Clean Shutdown
    def _shutdown(_signum: int, _frame: Any) -> None:
        try:
            if hasattr(srv, "stop"):
                srv.stop()
            elif hasattr(srv, "shutdown"):
                srv.shutdown()  # type: ignore[no-untyped-call]
        except Exception as e:
            logger.debug("Error during LSP shutdown: %s", e)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    srv.start_io()


def validate_lsp() -> int:
    """Self-test: verify the LSP server can instantiate and register handlers."""
    try:
        srv = SeraphLanguageServer()
        _register_handlers(srv)
        print("OK: LSP server instantiated, handlers registered", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"BROKEN: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    start_lsp()
