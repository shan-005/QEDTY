# Security Policy

Seraph processes security-sensitive source material and may ingest externally supplied data. Treat the application, its inputs, credentials, caches and generated reports as security-sensitive.

## Reporting vulnerabilities

Do not disclose an undisclosed vulnerability through a public issue, pull request, discussion or commit. Use GitHub private vulnerability reporting when enabled for the repository.

A report should include the affected version/commit, component, security impact, reproducible steps, and a minimal proof of concept where safe.

## Security engineering requirements

- External inputs are treated as untrusted data.
- Parsers must reject malformed or ambiguous input rather than silently coercing it.
- Credentials and source payloads must not be committed to the repository.
- CI jobs follow least-privilege permissions.
- Release artifacts are built once and the exact published bytes are attested.
- Dependency and source integrity checks are part of release validation.
- Modeled PCI-X outputs are explicitly labeled and must retain provenance/assumption metadata.

## Scope limitations

Seraph is not a guarantee of exploit prevention, complete vulnerability coverage, or complete real-world causal inference. Security claims must be tied to the evidence and tests that produced them.
