# Contributing to QEDTY

QEDTY is a domain model first. New functionality should enter through canonical contracts, preserve deterministic identity and carry evidence/provenance where applicable.

Before opening a change:

```bash
uv run pytest -q --cov-fail-under=26
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

Do not introduce new scanner-centric abstractions into the platform core. Security-specific integrations belong under `qedty.sources.repository_security` or `qedty.integrations.security`.
