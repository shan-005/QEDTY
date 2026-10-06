# Contributing to SERAPH-PCI-X

SERAPH-PCI-X is a domain model first. New functionality should enter through canonical contracts, preserve deterministic identity and carry evidence/provenance where applicable.

Before opening a change:

```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

Do not introduce new scanner-centric abstractions into the platform core. Security-specific integrations belong under `seraph.sources.repository_security` or `seraph.integrations.security`.
