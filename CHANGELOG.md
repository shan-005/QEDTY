# Changelog

All notable changes are documented here.

## Unreleased

### Architecture

- Promoted shared world-model and intelligence primitives to the top-level `seraph` namespace.
- Retained `seraph.pci` as the PCI-X application boundary rather than a duplicate implementation tree.
- Added production-oriented validation and deterministic execution contracts.

### Security and supply chain

- Release configuration is being aligned with current SLSA provenance practices and least-privilege CI.

### Limitations

- PCI-X economic and propagation models remain declared models; they are not observations or universal causal estimates.
