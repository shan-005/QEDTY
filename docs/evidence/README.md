# QEDTY Evidence 2.0.0

Evidence is the system's durable record of an external representation and the context needed to interpret and audit it. The layer is intentionally stricter than a generic `source + timestamp + hash` table.

```text
source
  -> acquisition request/receipt
  -> immutable content digest
  -> evidence record
  -> quality measurement
  -> selector / pinpoint location
  -> normalization lineage
  -> provenance DAG
  -> ontology references
```

## File responsibilities

- `models.py`: immutable evidence identity and evidence metadata.
- `acquisition.py`: requested-vs-actual acquisition context and receipt creation.
- `hashstore.py`: SHA-256 content-addressed storage with atomic writes and integrity verification.
- `normalization.py`: deterministic, auditable transformations without implicit stringification.
- `provenance.py`: PROV-style activity DAG, parentage, cycle detection and topological traversal.
- `quality.py`: DQV-inspired dimensions and explicit metrics/measurements; aggregation is opt-in.
- `selectors.py`: fragment/position selectors for pinpointing evidentiary content.
- `licensing.py`: SPDX-oriented rights metadata with explicit unknown states.
- `registry.py`: thread-safe metadata index by evidence ID, digest, source and ontology entity.

The payload is intentionally not embedded in `EvidenceRecord`. It is stored separately using its SHA-256 content address. This keeps metadata portable while allowing high-volume evidence handling.
