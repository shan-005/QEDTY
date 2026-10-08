# Support

QEDTY is an engineering and research platform. Support requests are most useful when they are reproducible and identify the exact environment involved.

## Before opening an issue

Check:

- [`README.md`](README.md)
- the relevant domain documentation under [`docs/`](docs/)
- existing issues and discussions;
- the verification script: [`scripts/verify.sh`](scripts/verify.sh)

Run:

```bash
python --version
uv --version
python -m qedty validate
python -m qedty demo
./scripts/verify.sh
```

Include the results relevant to your problem.

## Bug reports

A strong bug report includes:

- QEDTY version or commit;
- operating system and architecture;
- Python and Rust versions when relevant;
- installation method;
- smallest reproducible input;
- expected behavior;
- actual behavior;
- complete error message or traceback;
- relevant contract/schema version;
- whether the issue is deterministic.

For data- or model-related problems, include the smallest non-sensitive fixture that reproduces the problem.

## Semantic or model questions

For questions about the meaning of a result, specify:

- the epistemic state;
- the evidence/source set;
- the temporal context;
- the spatial reference;
- the scenario/intervention;
- assumptions;
- uncertainty configuration;
- model or contract version.

Without this context, a numerical result may be impossible to interpret correctly.

## Feature requests

A good feature request describes:

1. the problem or operational need;
2. why the existing semantic model cannot express it;
3. the proposed behavior;
4. contract/API implications;
5. provenance and audit implications;
6. performance or operational implications;
7. alternatives considered.

Features that merely add another implementation of an existing semantic layer should normally be evaluated against the project's polyglot architecture first.

## Security

Do not report security vulnerabilities publicly.

Follow [`SECURITY.md`](SECURITY.md).

## Data and privacy

Do not attach:

- credentials;
- API keys;
- secrets;
- private production datasets;
- personal data;
- confidential infrastructure details.

Redact sensitive values while preserving the structure needed for reproduction.

## Performance issues

For performance reports, provide:

- workload size;
- relevant graph/temporal/spatial dimensions;
- hardware;
- Python/Rust/runtime version;
- baseline and observed timings;
- whether the result is cold-cache or warm-cache;
- reproducibility information.

Prefer benchmark fixtures that can be shared publicly.

## Intended support boundary

QEDTY documentation and project support do not constitute:

- operational guarantees;
- safety certification;
- regulatory advice;
- financial advice;
- authoritative physical-world forecasts;
- deployment-specific security certification.

Domain operators remain responsible for validating models and assumptions for their deployment.

## Escalation

Issues that affect contracts, provenance, security, or cross-language compatibility should be treated as higher priority than cosmetic or documentation-only defects.

When a problem crosses multiple domains, include the minimal complete reproduction rather than opening a separate issue for every symptom.

