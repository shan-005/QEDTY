# Seraph

Seraph is a security and planetary-continuity intelligence platform. The project combines repository security evidence with a temporal, evidence-backed model of dependencies, infrastructure, services, and economic functions.

## Product surfaces

### Seraph Guard

Repository security analysis accepts heterogeneous findings from secrets, dependencies/SBOM, IaC, containers, policy and bounded code/taint analysis. The intelligence layer contextualizes findings with repository topology, reachability, impact, prioritization, explanations, and remediation workflows.

### SERAPH-PCI-X

Planetary Continuity Intelligence models real-world entities and time-bounded relationships across space, infrastructure, services, supply chains, transport, energy, telecom and economic functions. Its core chain is:

```
evidence → entities → temporal graph → shock propagation
        → continuity → economic impact
        → counterfactual intervention → resilience optimization
```

The system distinguishes observed evidence from derived, inferred, modeled, counterfactual and unknown states. Modeled outputs are never treated as observations.

## Enterprise design principles

- Deterministic identities and reproducible calculations.
- Immutable validated domain contracts.
- Explicit temporal validity and UTC normalization.
- Evidence provenance, licensing and source-quality metadata.
- Fail-closed parsing and collision detection.
- No silent fallbacks for invalid first-party state.
- Machine-readable output suitable for CI and downstream systems.
- Security and release controls based on least privilege, signed artifacts and verifiable provenance.
- Claims are scoped to the evidence and model actually used; the project does not claim universal prediction or universal coverage.

## Installation

Seraph targets Python 3.12–3.14.

```bash
uv sync --all-groups
```

Repository security CLI:

```bash
seraph scan --help
seraph-guard scan --help
```

PCI-X CLI:

```bash
seraph-pci demo
seraph-pci validate
python -m seraph.pci validate
```

## Architecture

```
src/seraph/
├── core/             # identity, time, enums, shared contracts
├── entities/         # world-entity identity and resolution
├── evidence/         # source evidence, provenance, quality, licensing
├── graph/            # deterministic temporal world graph
├── shocks/           # shock definitions and propagation
├── continuity/       # service/capacity continuity modeling
├── economics/        # explicit economic exposure/loss model
├── counterfactual/   # intervention comparison
├── optimization/     # resilience intervention ranking
├── uncertainty/      # uncertainty intervals and methods
├── intelligence/     # repository/security intelligence
├── sources/          # repository, space and future cross-domain adapters
├── storage/          # persistence
├── output/           # machine/human-readable outputs
├── orchestration/    # scheduling and execution
├── integrations/     # LSP and external integrations
├── cli/              # user-facing command surfaces
└── pci/              # PCI-X application entry point
```

## Evidence and epistemics

Every important world-state assertion should be traceable to source evidence or an explicit model transformation. PCI-X uses these epistemic states:

```
OBSERVED        directly supported by source evidence
DERIVED         deterministic transformation of supported inputs
INFERRED        analytical inference from evidence
MODELED         output of a declared model/simulation
COUNTERFACTUAL  result under an explicit intervention/scenario
UNKNOWN         insufficient evidence
```

## Validation status

The repository is an active engineering project. A passing unit, integration, or gate check establishes only the declared scope of that check. It does not prove universal security, complete dependency visibility, causal truth, economic forecast accuracy, or superiority over another platform.

## Security

Report undisclosed vulnerabilities through GitHub private vulnerability reporting when enabled. See [SECURITY.md](SECURITY.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
