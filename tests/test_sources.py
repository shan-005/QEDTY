from pathlib import Path

from seraph.sources.base import SourceContext
from seraph.sources.repository_security.adapter import RepositorySecurityAdapter
from seraph.sources.repository_security.normalize import normalize
from seraph.sources.space.ccsds import parse_omm_kvn


def test_context_allowlist() -> None:
    c = SourceContext("x", "public", "0" * 64, allowed_hosts=("example.com",))
    assert c.permits("https://example.com/data")
    assert not c.permits("https://evil.example/data")


def test_security_observation_redacts() -> None:
    p = Path("/tmp/seraph-source-test.txt")
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
