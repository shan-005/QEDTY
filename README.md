# Seraph Guard

**Seraph Guard** is an open-source security intelligence engine for correlating heterogeneous security findings with repository structure, dependencies, data/control flow, reachability, impact, and causal relationships.

Instead of treating every scanner finding as an isolated alert, Seraph is designed to turn security signals into contextual, evidence-backed findings that can be investigated, prioritized, explained, and acted upon.

> **Current release status:** Seraph Guard is an active beta/pre-release project. The repository should be treated according to the exact validation status documented in this release. Passing an individual engineering gate does not imply universal security coverage, exploitability prediction, causal proof, or superiority over another security product.

## Why Seraph Guard?

Modern repositories are usually analyzed by multiple security tools:

- secret scanners
- dependency/SCA scanners
- SBOM tools
- SAST and taint analyzers
- IaC scanners
- container scanners
- policy engines
- CI/CD security checks

Those tools can produce valuable signals, but the resulting findings can be difficult to reason about collectively.

Seraph focuses on the layer between **detection** and **security decision-making**:

```text
security signals
      ↓
finding normalization
      ↓
ontology
      ↓
repository context
      ↓
relationships / topology
      ↓
reachability
      ↓
impact assessment
      ↓
priority
      ↓
evidence-backed explanation
      ↓
action
```

The scanners are inputs. The intelligence layer is the central product surface.

## Core capabilities

Seraph Guard currently contains security-analysis components for:

- secrets
- dependencies / software composition analysis
- SBOM ingestion
- infrastructure-as-code
- containers
- code and bounded taint analysis
- policy violations
- finding deduplication
- repository topology
- dependency relationships
- reachability analysis
- structural impact assessment
- causal prioritization
- confidence/conformal mechanisms
- evidence-backed explanations
- suppression
- adaptive learning
- automated fixes where supported
- CI/CD operation
- LSP integration
- JSON, SARIF and JUnit-oriented output paths
- GitHub-oriented output/integration paths

Capabilities are bounded by the language, repository structure, scanner coverage, and available evidence. The project does not claim universal semantic analysis of every programming language.

## Intelligence model

A central Seraph workflow is:

```text
Finding
  ↓
Repository context
  ↓
Structural graph evidence
  ↓
Dependency / topology relationships
  ↓
Reachability
  ↓
Impact
  ↓
Deterministic prioritization
  ↓
Explanation
  ↓
Machine-readable / developer-facing output
```

The intelligence path is designed to be deterministic and auditable where practical. Seraph does not require an LLM to manufacture evidence for the core v1 intelligence path.

If AI-assisted functionality is added in the future, the intended architecture is for AI to operate above an evidence layer rather than replace the underlying evidence.

## Detection domains

Seraph is designed to accept findings from multiple security domains through shared finding and intelligence contracts.

### Secrets

Secret and credential-like findings can be normalized into the common finding model and enriched with repository context.

### Dependencies and SBOM

Dependency and SBOM findings can be correlated with repository structure and other security evidence rather than being treated solely as isolated package/version alerts.

### Code and taint

The project includes static code-analysis and taint capabilities. The current taint implementation is bounded and should not be interpreted as universal multi-language semantic taint analysis.

### IaC and containers

Infrastructure and container findings can enter the same downstream intelligence and output surfaces.

### Policy

Policy violations can be represented as security findings and participate in common reporting and prioritization paths.

## What makes the intelligence layer different?

The intended distinction is not simply "another scanner."

Seraph attempts to answer questions such as:

```text
Where does this finding occur?

What repository component owns it?

What depends on it?

What does it reach?

What security-relevant relationships surround it?

What structural impact can be established?

How should the finding be prioritized?

What evidence supports that prioritization?

What can be explained to a developer or security analyst?
```

A representative security chain is:

```text
vulnerable dependency
        +
affected code
        +
reachable application surface
        +
repository topology
        +
data/control-flow evidence
        ↓
contextualized security finding
```

The exact evidence available depends on the repository and the scanners that produced the underlying findings.

## Installation

Seraph Guard currently targets Python 3.12 through 3.14.

From a checkout:

```bash
uv sync
```

or install the package using your preferred supported Python package workflow.

For a development environment:

```bash
uv sync --group dev
```

Verify the CLI:

```bash
seraph-guard --version
seraph-guard --help
```

## First scan

Run a scan against a repository:

```bash
seraph-guard scan --path .
```

Useful commands include:

```bash
seraph-guard scan --help
seraph-guard ci --help
seraph-guard explain --help
seraph-guard fix --help
seraph-guard init --help
seraph-guard config --help
seraph-guard status --help
seraph-guard cache --help
seraph-guard lsp --help
```

The exact options and output contracts are defined by the installed CLI version. Run `--help` rather than relying on examples that may change between releases.

## Output and integration

Seraph includes machine-readable and CI-oriented output paths, including:

- JSON
- SARIF
- JUnit
- GitHub-oriented output

This allows Seraph to operate as a component in existing engineering and security workflows instead of requiring users to replace every existing security tool.

## Repository architecture

The high-level source layout is:

```text
src/seraph/
├── guard/
│   ├── explanation/
│   ├── intelligence/
│   ├── orchestration/
│   ├── output/
│   ├── scanners/
│   ├── suppression/
│   ├── cli.py
│   ├── config.py
│   ├── deduplication.py
│   ├── fixer.py
│   ├── ontology.py
│   └── report.py
├── lsp/
├── ufic/
└── scanner_integration.py
```

The important conceptual boundary is:

```text
scanners
   ↓
shared finding contracts
   ↓
ontology / context
   ↓
repository intelligence
   ↓
impact / priority / explanation
   ↓
outputs / integrations
```

## Testing

The repository contains unit, integration, CLI, scanner, output, intelligence, LSP, production-hardening, and regression tests.

A basic test run is:

```bash
pytest -q
```

Additional project-specific validation should be run according to the current contribution and release documentation.

## Crucible

Seraph includes reproducible validation tooling under:

```text
tools/crucible/
```

The purpose of Crucible is to exercise Seraph against external repositories and verify observable contracts rather than relying exclusively on synthetic unit fixtures.

Do not commit private repository clones, proprietary source, credentials, raw sensitive scan results, or other private benchmark material to the public repository.

## Validation and engineering gates

Seraph has been developed using a staged engineering-gate model covering:

```text
G1  Foundation
G2  Core correctness
G3  Detection / regression
G4  External validation
G5  Intelligence / impact
G6  Adversarial / differential
G7  Scale / performance
G8  Remediation / developer experience
G9  Integration / enterprise
```

A gate is an engineering acceptance mechanism for a declared scope. A PASS must not be interpreted beyond the evidence actually produced by that gate.

In particular, a gate PASS does **not** by itself prove:

- universal security;
- zero false positives or zero false negatives;
- universal language coverage;
- production exploitability;
- exploit probability;
- calibrated causal effects from source code alone;
- cloud/runtime coverage;
- identity-graph coverage;
- complete code-to-cloud visibility;
- superiority over another security product;
- product-market fit or commercial success.

Public benchmark claims should identify the dataset, oracle construction, methodology, raw results, uncertainty, version identity, and limitations.

## Current limitations

Seraph is intentionally transparent about its boundaries.

The current project should not be interpreted as:

- a universal replacement for every security scanner;
- a complete DAST platform;
- a cloud-runtime security platform;
- a universal multi-language semantic analyzer;
- an exploit-probability predictor;
- a replacement for CVSS, EPSS, or CISA KEV;
- proof of real-world causal effects merely from source-code relationships;
- a guarantee that every finding is correct.

Structural impact values are prioritization signals. They are not automatically exploit probabilities, CVSS scores, EPSS probabilities, or independently measured business-loss estimates.

## Security

Please read [`SECURITY.md`](SECURITY.md) before reporting a security vulnerability.

Do not disclose an undisclosed vulnerability in a public GitHub issue.

## Contributing

Contributions are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.

Security-sensitive changes should include appropriate tests and a clear description of their security implications.

## Support

For normal usage and project-support questions, see [`SUPPORT.md`](SUPPORT.md).

Security vulnerabilities must follow [`SECURITY.md`](SECURITY.md), not normal support channels.

## Code of conduct

Participation in the project is subject to [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Citation

If you use Seraph Guard in research, technical work, benchmarking, or other published work, see [`CITATION.cff`](CITATION.cff).

## License

Seraph Guard is distributed under the Apache License 2.0. See [`LICENSE`](LICENSE) for the complete license text.

## Project status

Seraph Guard is an active beta/pre-release project.

The public repository is intended to make the implementation, tests, documentation, policies, and reproducible tooling inspectable. Validation status should always be interpreted against the exact source revision and release being evaluated.
