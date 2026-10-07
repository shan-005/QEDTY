# SERAPH-PCI-X Propagation compatibility hotfix

This refresh fixes the two repository-level compatibility failures found in the 2026-10-06 validation run:

1. `PropagationEvent.arrival_delay_seconds` is explicitly defaulted to `0.0`, preserving construction sites that predate the timing extension.
2. `PropagationResult.digest` is exposed as a deterministic compatibility property.

No propagation algorithm semantics are changed.

After extraction, verify the imported source path with:

```bash
python - <<'PY'
import seraph.propagation.models as m
print(m.__file__)
print(hasattr(m.PropagationResult, "digest"))
print(m.PropagationEvent.model_fields["arrival_delay_seconds"].default)
PY
```
