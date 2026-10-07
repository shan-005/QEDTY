# SERAPH-PCI-X all-at-once compatibility hotfix v2

This patch fixes the two collection blockers reported by the WSL repository run:

1. Propagation: removes the fragile unconditional `PropagationEvent.model_rebuild()` call that caused Pydantic to raise `PydanticUndefinedAnnotation: name 'datetime' is not defined` during test collection.
2. Uncertainty: supplies the deterministic public `latin_hypercube(seed, n, dimensions)` function required by the repository tests.

No tests or frozen-layer semantics are changed by this compatibility patch.
