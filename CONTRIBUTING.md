# Contributing to QEDTY

Thank you for considering a contribution. QEDTY is a contract-driven modelling and
intelligence platform. Contributions should preserve semantic consistency, deterministic
behaviour, evidence provenance, and compatibility across the implementations that are
actually supported.

This guide describes the contribution workflow. The [documentation standards](docs/DOCUMENTATION_STANDARDS.md)
define how project documentation is written. The [architecture](docs/ARCHITECTURE.md)
describes component responsibilities and implementation boundaries.

## Before starting

1. Read the [README](README.md) and the documentation for the affected domain.
2. Search existing issues and pull requests for related work.
3. For a significant feature or semantic change, open an issue or design discussion before
   implementation.
4. Identify the authoritative contract, implementation, tests, and downstream consumers.
5. Keep the change focused. Split unrelated refactoring from behavior changes.

Do not begin by adding a second representation of an existing concept. First determine
whether the canonical model or contract should be extended.

## Development environment

QEDTY currently targets Python `>=3.12,<3.14` and has a Rust workspace. Use the toolchain
versions and dependency constraints declared in the repository.

```bash
git clone https://github.com/shan-005/QEDTY.git
cd QEDTY
uv sync
```

For Rust changes, install the repository's supported Rust toolchain and use the committed
Cargo lockfile.

## Change workflow

1. Create a focused branch from an up-to-date `main`.
2. Write or update the contract before changing implementations when semantics change.
3. Add tests for expected behavior, edge cases, invalid input, and regression cases.
4. Update Python and Rust implementations where the contract requires both.
5. Update golden vectors and differential fixtures when shared deterministic behavior changes.
6. Update documentation, examples, schemas, generated artifacts, and migration notes as needed.
7. Run the relevant focused checks, then the repository verification gates.
8. Review the complete diff, including generated files and lockfile/manifest changes.
9. Open a pull request with exact verification evidence and known limitations.

Do not force-push shared branches, rewrite protected history, or discard another contributor's
work. Do not commit secrets, private datasets, credentials, or machine-specific artifacts.

## Semantic and contract requirements

A semantic change should identify:

- the concept and its canonical owner;
- input and output types;
- invariants and boundary conditions;
- identity and canonicalization behavior;
- temporal and spatial semantics, where applicable;
- epistemic state and evidence/provenance requirements;
- error and failure behavior;
- versioning and compatibility implications;
- conformance fixtures and validation strategy.

Do not silently change the meaning of identifiers, quantities, intervals, coordinate
references, epistemic states, evidence links, propagation rules, or result fields.

A model output must not be represented as an observation. A counterfactual or simulation
must retain its assumptions and model scope. Graph propagation alone does not establish
empirical causation.

## Python and Rust boundaries

Python is the current semantic/reference and application implementation. Rust provides the
shipped deterministic native core for its explicitly implemented operation set. Do not
assume that the Rust core is a complete port of the Python domain model.

For cross-language behavior:

- use an independent reference oracle where practical;
- compare canonical outputs, not incidental implementation details;
- cover malformed input and numerical boundaries;
- make generated cases deterministic and replayable;
- record exact operation scope and unsupported cases;
- do not claim parity beyond the operations and fixtures that passed.

Go, C/C++/CUDA, TypeScript/React, SQL service infrastructure, and WIT/WASM are future
execution targets unless corresponding implementation and verification are present in the
repository.

## Data, sources, and licensing

- Record source identity, acquisition context, and provenance where applicable.
- Check licensing, redistribution rights, terms of use, and privacy constraints before
  adding external datasets or fixtures.
- Keep raw or sensitive evidence out of Git unless explicitly approved and legally suitable.
- Prefer small, synthetic, or appropriately licensed fixtures.
- Do not add credentials, API keys, personal data, or confidential operational information.

## Code quality and validation

Run the checks relevant to the changed surface. For Python changes, the standard local
checks are:

```bash
uv run pytest -q --cov-fail-under=60
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

For security-sensitive or dependency changes, also run:

```bash
uv run bandit -r src -ll
uv run pip-audit
```

For Rust changes:

```bash
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
```

Run the repository gate when practical:

```bash
./scripts/verify.sh
```

Commands may evolve; the CI workflows and scripts on the pull request's exact head commit
are authoritative. Report failures honestly. Do not describe a local test run as a hosted
check or a focused test as full-suite verification.

## Documentation requirements

Documentation changes are expected when a contribution changes public behavior, contracts,
commands, supported environments, configuration, limitations, or architecture.

Use the appropriate document type. Keep the root README concise and navigational; put
detailed architecture, research, contracts, operations, and engineering history in their
authoritative documents. Distinguish implemented, tested, validated, planned, proposed,
deferred, and unsupported work.

## Pull requests

A pull request should explain:

1. the problem and motivation;
2. the design and scope of the change;
3. affected contracts, packages, and interfaces;
4. compatibility or migration impact;
5. tests and commands run, including exact outcomes;
6. hosted checks on the exact head SHA;
7. known limitations and follow-up work.

Use the repository pull request template. Link related issues and decisions. Include a
benchmark only when the workload, hardware, runtime, baseline, and method are documented.

## Review and merge

Review the complete diff, not only the summary. Verify that required checks correspond to
the exact proposed head commit. Contract, security, provenance, release, and dependency
changes require particular care.

A maintainer's self-review is not independent approval. Do not claim independent review
unless another qualified reviewer has actually approved the change. Merge only after the
repository's active branch protection and required checks are satisfied.

## Scope boundaries

QEDTY is an engineering and research platform. A passing test suite does not establish
production certification, universal data quality, causal identification, calibrated
uncertainty for every domain, or planetary-scale performance. Contributions and examples
must preserve these boundaries.

## Questions

For reproducible defects and feature proposals, use GitHub Issues. For suspected security
vulnerabilities, do not open a public issue; follow [SECURITY.md](SECURITY.md).
For general support, see [SUPPORT.md](SUPPORT.md).
