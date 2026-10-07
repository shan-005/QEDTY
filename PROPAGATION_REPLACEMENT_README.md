# SERAPH-PCI-X Propagation replacement

Version: 1.0.0.

Replace the complete `src/seraph/propagation/` directory with the included implementation and add the included contract/tests/docs/scripts.

The legacy API `PropagationEngine(graph).propagate(shock, transmission_reduction=..., capacity_gain=...) -> tuple[PropagationEvent, ...]` remains available.

The new canonical API adds `propagate_many(...)`, `run(...) -> PropagationResult`, deterministic summaries/evidence, time-respecting propagation, bounded execution, configurable aggregation (`max`, `sum_cap`, `noisy_or`), explicit edge latency attributes, relationship-type filtering, cycle policy, and Arrow/JSON Schema/Protobuf boundaries.

Do not freeze this layer until the actual project-wide Ruff, mypy, pytest, conformance and protobuf checks pass in the repository environment.
