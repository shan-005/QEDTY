"""Tests for Layer 3 Action: LSP Server & Real-time IDE Diagnostics."""

import pytest

from seraph.lsp.server import SeraphLanguageServer, _analyze_document, _uri_to_path


def test_uri_to_path_conversion():
    """Verify LSP file URI to local path resolution."""
    assert _uri_to_path("file:///home/user/file.py").replace("\\", "/") == "/home/user/file.py"


@pytest.mark.integration
@pytest.mark.security
def test_analyze_document_secret_detection():
    """Verify LSP pushes diagnostics for hardcoded secrets on keystroke."""
    uri = "file:///tmp/test.py"
    text = "AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'\n"

    diags = _analyze_document(
        uri=uri,
        text=text,
        compiled_patterns={},
        suppression=None,
        cached_findings={},
    )
    assert len(diags) > 0
    assert any("secret" in d.message.lower() or "AWS" in d.message for d in diags)


@pytest.mark.integration
def test_lsp_server_instantiation():
    """Verify LSP server initializes without crashing."""
    server = SeraphLanguageServer()
    assert server.name == "seraph-guard"
