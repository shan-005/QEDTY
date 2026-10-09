from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from qedty.sources.base import SourceAdapter, SourceContext
from qedty.sources.repository_security.adapter import RepositorySecurityAdapter
from qedty.sources.repository_security.normalize import normalize
from qedty.sources.space.ccsds import parse_omm_kvn


def test_context_allowlist() -> None:
    c = SourceContext("x", "public", "0" * 64, allowed_hosts=("example.com",))
    assert c.permits("https://example.com/data")
    assert not c.permits("https://evil.example/data")


def test_security_observation_redacts() -> None:
    p = Path("/tmp/qedty-source-test.txt")
    p.write_text("api_key = supersecret\n", encoding="utf-8")
    try:
        obs = RepositorySecurityAdapter().inspect_text(p)
        assert obs and "supersecret" not in obs[0].evidence_excerpt
        assert normalize(obs[0]).line_number == 1
    finally:
        p.unlink(missing_ok=True)


def test_ccsds_parse() -> None:
    text = "\n".join(
        [
            "OBJECT_ID = 1",
            "EPOCH = 2026-01-01T00:00:00Z",
            "X = 1",
            "Y = 2",
            "Z = 3",
            "X_DOT = 0",
            "Y_DOT = 0",
            "Z_DOT = 0",
        ]
    )
    r = parse_omm_kvn(text)
    assert r.object_id == "1"


def test_fetch_enforces_max_bytes_while_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    consumed: list[bytes] = []

    class FakeResponse:
        status_code = 200
        headers: ClassVar[dict[str, str]] = {
            "ETag": "fixture-etag",
            "Last-Modified": "Thu, 01 Jan 2026 00:00:00 GMT",
        }

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(
            self, exc_type: object, exc_value: object, traceback: object
        ) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self):
            for chunk in (b"123", b"456", b"must-not-be-read"):
                consumed.append(chunk)
                yield chunk

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(
            self, exc_type: object, exc_value: object, traceback: object
        ) -> None:
            return None

        def stream(self, method: str, url: str) -> FakeResponse:
            assert method == "GET"
            assert url == "https://example.com/data"
            return FakeResponse()

    class TestAdapter(SourceAdapter):
        def discover(self, context: SourceContext) -> tuple[object, ...]:
            return ()

    monkeypatch.setattr("qedty.sources.base.httpx.Client", FakeClient)
    context = SourceContext(
        "test",
        "public",
        "0" * 64,
        allowed_hosts=("example.com",),
        max_bytes=5,
    )

    with pytest.raises(ValueError, match="max_bytes"):
        TestAdapter().fetch("https://example.com/data", context)

    assert consumed == [b"123", b"456"]
