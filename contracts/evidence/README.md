# QEDTY Evidence Contract

Version: 2.0.0

The Evidence layer records **what was observed/acquired, where it came from, which immutable representation was captured, when it was retrieved/observed, how it was selected, transformed, assessed for quality, and what rights apply**. It does not turn evidence into truth: interpretation belongs to the ontology/assertion and intelligence layers.

## Standards boundaries

- W3C PROV-DM / PROV-O: derivation, activities, agents, generation and usage.
- W3C DCAT 3: dataset/distribution catalog semantics where evidence is distributed data.
- W3C DQV: explicit, metric-based quality measurements; no mandatory universal quality score.
- W3C Web Annotation: stable selectors for fragments of documents/media/data.
- SPDX expressions: license identification; unknown permissions remain unknown.
- RFC 9530: HTTP `Content-Digest` compatibility at acquisition boundaries.
- JSON Schema 2020-12: machine validation contract.
- Protobuf: typed service/control representation.
- Arrow: bulk metadata interchange; evidence bytes remain content-addressed.
- FAIR: findability, accessibility, interoperability and reusability metadata principles.

The implementation deliberately distinguishes **integrity** (the captured bytes match their digest) from **provenance** (how/why the bytes entered the pipeline) and **quality** (fitness information measured under an explicit metric). A digest does not establish truthfulness.

## Executable field mapping

`field-mapping.json` records the top-level `EvidenceRecord` mapping to the JSON Schema, Arrow projection, Protobuf message, and the limited RDF/SHACL vocabulary. Its statuses deliberately distinguish direct fields, renamed/transformed fields, partial representations, omissions and properties currently constrained only by SHACL.

The mapping is guarded by `tests/evidence/test_contract_mapping.py`, which compares it with the live Python model and the declared schema, Arrow columns, Protobuf fields, and SHACL paths. That is a structural drift check, not a substitute for round-trip testing or semantic-invariant tests.

The executable SHACL gate, `scripts/check_evidence_shacl_conformance.py`, runs the current shapes through pySHACL with meta-SHACL checking enabled. It verifies that a valid evidence graph conforms and that invalid graphs are rejected for the expected constraint components and paths (presence, cardinality, datatype, and SHA-256 pattern). CI pins the validator to `pyshacl==0.40.1` through `uv run --with`, keeping this conformance-only tool out of QEDTY's application dependency graph and existing `uv.lock`.

Run it locally with:

```bash
uv run --with pyshacl==0.40.1 python scripts/check_evidence_shacl_conformance.py
```

This gate executes the currently declared shapes; it does not claim that RDF is a complete serialization of `EvidenceRecord`. The current `sourceUri` shape expects a literal typed as `xsd:anyURI`. Any change to that model or to the provisional `ser:` namespace requires an explicit contract decision rather than a mechanical rename.

Known nested gaps (including absent licensing metadata and potentially lossy Protobuf header maps) are listed in the mapping file; consumers must not infer that Arrow or Protobuf alone can reconstruct the full Python model.

