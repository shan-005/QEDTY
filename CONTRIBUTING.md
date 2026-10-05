# Contributing

Contributions should preserve deterministic behavior, explicit provenance and strict validation.

Before opening a pull request:

```bash
uv sync --all-groups
pytest -q
ruff check src tests
ruff format --check src tests
mypy src
```

Changes that alter model semantics should include regression tests and an explicit description of assumptions and limitations.
