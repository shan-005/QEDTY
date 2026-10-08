# Security Policy

## Scope

QEDTY is a contract-driven, evidence-backed modeling platform. Security concerns may involve code execution, dependency supply chain, CI/CD, credentials and secrets, provenance integrity, artifact integrity, serialization boundaries, input validation, service interfaces, storage isolation, data disclosure, and unsafe model or policy execution.

This policy applies to the maintained QEDTY release line and its repository automation.

## Supported versions

| Release line | Security support |
|---|---|
| `0.1a0` / current alpha | Supported for vulnerability reports |
| Older alpha snapshots | Best effort only |
| Unreleased development branches | Case-by-case; report against the affected branch |

A version may be technically usable while still being outside the supported security window.

## Reporting a vulnerability

**Do not disclose suspected vulnerabilities in a public GitHub issue, pull request, discussion, or public chat.**

Use GitHub's private vulnerability reporting / security advisory mechanism for the repository when it is enabled.

When private reporting is unavailable, contact the repository maintainer through the maintainer's published private contact route and include:

- affected version, commit, or branch;
- affected component or file;
- security impact;
- reproducible steps or a minimal proof of concept;
- required privileges or deployment assumptions;
- whether exploitation is known or suspected;
- any proposed mitigation, if available.

Do not include secrets, credentials, personal data, or unnecessary production data in a report.

## What makes a strong report

A useful report should establish:

1. **Reachability** — what input or trust boundary an attacker must cross.
2. **Impact** — confidentiality, integrity, availability, privilege, provenance, supply-chain, or model-integrity consequence.
3. **Reproduction** — the smallest deterministic reproduction available.
4. **Affected surface** — package, service, native component, workflow, contract, or deployment component.
5. **Mitigation** — temporary and permanent mitigations where known.

Reports that include exact versions, stack traces, minimal fixtures, and deterministic reproductions are substantially easier to triage.

## High-priority security classes

Particular attention should be given to:

### Supply chain

- compromised dependencies;
- malicious build-time dependencies;
- unsafe GitHub Actions changes;
- token or credential exposure;
- release artifact tampering;
- untrusted generated code.

### Input and serialization boundaries

- unsafe deserialization;
- schema confusion;
- resource-exhausting inputs;
- parser differentials between language implementations;
- malformed Arrow, Protobuf, JSON, geospatial, temporal, or domain-source inputs.

### Provenance and evidence integrity

- forged or detached provenance;
- loss of source identity;
- incorrect evidence-to-claim association;
- silent alteration of hashes or evidence records;
- ambiguity that causes a derived result to be represented as an observation.

### Cross-language execution

- FFI memory-safety issues;
- Rust/Go/C++/CUDA boundary errors;
- ABI incompatibilities;
- unsafe WASM/component execution;
- inconsistent validation between Python and native implementations.

### Repository and CI security

- secret leakage;
- workflow privilege escalation;
- untrusted pull-request execution;
- artifact poisoning;
- release credential exposure;
- dependency confusion.

## Disclosure expectations

QEDTY follows coordinated disclosure principles.

Maintainers may:

- acknowledge the report;
- request additional reproduction data;
- assess affected versions and exploitability;
- prepare a fix or mitigation;
- publish a security advisory after a reasonable coordination period.

Do not publicly publish exploit details before an agreed disclosure point.

## Safe harbor

Good-faith security research is welcome when it is:

- authorized against the researcher's own environment or an explicitly permitted test environment;
- performed without disrupting other users or services;
- performed without accessing, retaining, or exfiltrating data that does not belong to the researcher;
- disclosed privately and responsibly.

Security testing must not be used as a pretext for unauthorized access, denial of service, data theft, credential extraction, or persistence.

## Maintainer security controls

The repository should maintain, where supported by the hosting platform:

- dependency alerts and automated update review;
- secret scanning and push protection;
- code scanning;
- signed or attestable release artifacts where configured;
- least-privilege workflow permissions;
- protected default-branch rules;
- CODEOWNERS review for sensitive paths;
- dependency and release review;
- documented incident response procedures.

These controls complement, rather than replace, secure implementation and review.

## Supply-chain and release integrity

Releases should be traceable to source commits and reproducible or independently verifiable to the extent supported by the build system.

Security-sensitive changes should preserve:

- source-to-artifact traceability;
- dependency provenance;
- contract version integrity;
- generated-code provenance;
- test and verification evidence.

## Questions

General security questions belong in the project's normal support channels only when they do not disclose a suspected vulnerability.

For suspected vulnerabilities, use private reporting.

