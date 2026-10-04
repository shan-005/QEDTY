# Contributing to Seraph Guard

Thank you for contributing to Seraph Guard.

Seraph is a security-sensitive project. Contributions should preserve correctness, reproducibility, security boundaries, deterministic behavior where required, and compatibility of documented interfaces.

## Before you start

Please read:

- `README.md`
- `SECURITY.md`
- `SUPPORT.md`
- the relevant documentation under `docs/`

Do not submit:

- credentials;
- API keys;
- private keys;
- proprietary source code;
- customer data;
- private repository contents;
- undisclosed vulnerabilities;
- sensitive benchmark data.

If you discover a security vulnerability, do not open a public issue. Follow `SECURITY.md`.

## Development environment

Seraph Guard currently targets Python 3.12 through 3.14.

The repository uses `uv` for reproducible dependency management.

Create the development environment with:

```bash
uv sync --group dev
```

Verify the environment:

```bash
python --version
seraph-guard --version
```

## Running tests

Start with:

```bash
pytest -q
```

Run the relevant narrower suites when changing a specific subsystem.

Examples:

```bash
pytest -q tests/test_core.py
pytest -q tests/test_scanners.py
pytest -q tests/test_intelligence.py
pytest -q tests/test_outputs.py
pytest -q tests/test_cli_matrix.py
pytest -q tests/test_lsp.py
```

Do not weaken or remove a regression test merely to make a change pass.

## Testing requirements by subsystem

### Scanner changes

Changes under scanner implementations should include detection/regression coverage.

At minimum verify:

- expected positive findings;
- expected negative cases;
- severity/category behavior;
- finding normalization;
- stable identifiers where applicable;
- output serialization where affected.

### Intelligence changes

Changes to:

```text
guard/intelligence/
guard/ontology.py
guard/orchestration/
guard/deduplication.py
guard/explanation/
```

should include tests for:

- evidence preservation;
- deterministic behavior;
- provenance;
- relationship construction;
- impact behavior;
- priority behavior;
- explanation contracts;
- regression cases.

Do not describe heuristic or inferred information as independently measured evidence.

### Output changes

Changes to output modules should preserve the relevant schema and integration contracts.

Where applicable, test:

- JSON;
- SARIF;
- JUnit;
- GitHub output.

### CLI changes

CLI changes should include command, option, exit-code, and error-path coverage where applicable.

### Fixer changes

Auto-fix behavior is security-sensitive. Tests should demonstrate both safe application and refusal/handling of cases that cannot be fixed safely.

### Learning and suppression changes

Changes to adaptive learning or suppression must preserve isolation and must not silently turn uncertain findings into trusted findings.

## Code quality

Before opening a pull request, run the project's applicable checks.

At minimum:

```bash
git diff --check
python -m compileall -q src tests
pytest -q
```

Also run the repository's configured linting, type checking, dependency/security checks, and relevant integration validation when those checks apply to your change.

## Pull requests

A good pull request should explain:

1. What changed.
2. Why it changed.
3. Which security or product behavior is affected.
4. Which tests were added or updated.
5. Which commands were run.
6. Any known limitations or compatibility implications.

Keep pull requests focused.

Avoid combining unrelated refactors, formatting changes, feature work, and security-sensitive changes into one large pull request.

## Security-sensitive changes

Security-sensitive changes receive additional scrutiny.

Examples include:

- finding identity/deduplication;
- severity or priority;
- taint propagation;
- reachability;
- dependency interpretation;
- impact assessment;
- causal ranking;
- suppression;
- adaptive learning;
- secret handling;
- output serialization;
- CI/release workflows;
- authentication or external integrations.

Never introduce a security decision that depends on hidden or undocumented behavior.

If a change introduces a new heuristic, document:

- the input signals;
- the transformation;
- assumptions;
- limitations;
- provenance;
- deterministic behavior;
- validation method.

## Tests and fixtures

Use synthetic fixtures for security-sensitive examples whenever possible.

Synthetic secrets should be clearly non-secret.

Do not copy real credentials or proprietary repositories into tests.

## External repository testing

When using external repositories for validation:

- respect their licenses;
- respect their terms and usage limits;
- do not modify the external repository;
- do not upload private source or findings without authorization;
- keep raw/private results outside the public repository;
- publish only reproducible, sanitized evidence that is appropriate for public release.

## Commit messages

Use concise, meaningful commit messages.

Examples:

```text
feat: add dependency reachability evidence
fix: preserve finding provenance during deduplication
test: add regression for taint sink identity
docs: clarify impact provenance
ci: restrict workflow permissions
refactor: isolate repository graph construction
```

Avoid commit messages that hide security-sensitive changes.

## Pull request checklist

Before requesting review:

- [ ] Tests pass.
- [ ] `git diff --check` passes.
- [ ] No secrets or private data are included.
- [ ] Documentation is updated where behavior changed.
- [ ] Security-sensitive behavior has regression coverage.
- [ ] Public claims match actual implementation.
- [ ] New dependencies are justified.
- [ ] Generated artifacts are not accidentally committed.
- [ ] Compatibility impact is documented.

## Review standard

A contribution is not considered complete merely because the code executes.

For security-sensitive functionality, review should consider:

```text
correctness
determinism
security impact
provenance
failure behavior
backward compatibility
test coverage
operational behavior
documentation
```

The goal is to make Seraph Guard more reliable, inspectable, and useful—not merely larger.
