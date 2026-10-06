from seraph.sources.repository_security.adapter import RepositorySecurityAdapter


def test_security_isolated(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("api_key = secret", encoding="utf-8")
    assert RepositorySecurityAdapter().inspect_text(p)[0].category == "credential-exposure"
