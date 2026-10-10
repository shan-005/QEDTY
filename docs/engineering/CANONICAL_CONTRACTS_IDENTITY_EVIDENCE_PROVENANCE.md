# Canonical Contracts, Identity, Evidence and Provenance

**Status:** engineering audit baseline; no normative contract change  
**Audit baseline:** `30b415a346efe05554e8a79633d0d74644e7c18a` (2026-10-10)  
**Principle:** preserve current behavior until a specific, versioned migration is approved.

## Objective

Make QEDTY's canonical contracts, deterministic identifiers, evidence records, and provenance lineage explicit and testable across the representations that the repository actually ships. Python remains the semantic/reference authority. Rust must conform to the language-neutral behavior and approved golden vectors; RDF, SHACL, JSON-LD, Protobuf, and Arrow are bounded interoperability surfaces rather than independent semantic authorities.

This document records observations from the current repository baseline. It is not a claim that every listed external standard is fully implemented or that every boundary is currently equivalent.

## Existing implementation surface

| Concern | Existing source of behavior | Contract/interchange surfaces | Current evidence |
|---|---|---|---|
| Canonical JSON and IDs | `src/qedty/core/hash.py` | Rust `crates/qedty-core/src/lib.rs`; core identity golden vector | Python/Rust differential runner covers generic canonical JSON and identity cases |
| Domain entity identity | `src/qedty/ontology/entities.py` | ontology JSON Schema, RDF/JSON-LD, Protobuf, Arrow artifacts | Python model tests and ontology vectors |
| Evidence descriptor | `src/qedty/evidence/models.py` | `contracts/evidence/json-schema/evidence.schema.json`, Arrow schema, Protobuf, RDF and SHACL | Golden evidence record and Python evidence tests |
| Immutable payload integrity | `src/qedty/evidence/hashstore.py` | SHA-256 content-address contract | Python storage tests |
| Provenance activity/DAG | `src/qedty/evidence/provenance.py` | evidence JSON Schema and PROV-oriented RDF vocabulary | Provenance golden vector and DAG tests |
| Result envelope | `src/qedty/core/contracts.py` | core JSON Schema, Arrow, Protobuf, Rust contract result | Existing Python/Rust differential cases |

## Baseline findings

### CCIP-01 — Keep the canonicalization profiles separate

The current profile is named `qedty-canonical-json@1`. Python also exposes an explicitly separate, optional RFC 8785/JCS serializer. Rust's current serializer is designed to match QEDTY's established profile, including Python-compatible exponent spelling.

These profiles must not be silently substituted. Existing deterministic IDs and hashes are compatibility outputs. Any move to JCS, change to numeric/string treatment, or change to ID preimages requires a named profile/version, reviewed before-and-after golden vectors, and a migration/compatibility policy. A successful JCS implementation test does not by itself prove that legacy QEDTY IDs can change safely.

### CCIP-02 — Decide the permanent public namespace before changing RDF identifiers

Several contract artifacts currently use `https://qedty.local/...`, and the evidence RDF/SHACL files use a `ser:` prefix for terms in that namespace. RFC 6762 defines names ending in `.local.` as link-local names. They should therefore be treated as development/internal identifiers, not assumed to be globally stable public ontology identifiers.

Do not mechanically replace these IRIs in this milestone's first change. First decide a namespace rooted in a domain/URI space that QEDTY can actually maintain, document persistence and versioning rules, and specify how existing stored RDF, JSON-LD contexts, schema IDs, linked data, and consumers will migrate. A namespace decision must be an explicit architecture decision, not an incidental rename.

### CCIP-03 — Make evidence boundary coverage field-aware

The Python evidence model, JSON Schema, Arrow schema, Protobuf message, and RDF/SHACL vocabulary intentionally have different shapes, but the translation rules are not yet presented as one executable field mapping.

Specific review points from the baseline:

- The JSON Schema and Python model represent `license_policy`; `proto/qedty/evidence/v1/evidence.proto` has no corresponding license-policy message/field.
- JSON Schema represents quality as a profile plus measurement collection; Protobuf represents measurements as a repeated field and does not represent the declared profile or every measurement metadata field.
- JSON Schema models acquisition response headers as a sequence of key/value pairs, while Protobuf uses a map. A map cannot preserve duplicate header names or original header order; conversion must therefore state whether it is intentionally lossy.
- The Arrow evidence schema is a compact bulk-metadata projection, not a complete serialization of the entire Python `EvidenceRecord`.

These may be valid boundary choices, but they need to be explicit. Publish a mapping table marking each semantic field as **lossless**, **derived**, **omitted by design**, or **not yet mapped**. Do not label all surfaces as field-equivalent merely because required types/messages exist.

### CCIP-04 — Separate structural validation from semantic invariants

The existing evidence tests validate the Draft 2020-12 schema itself and validate the evidence golden record against it. They also check for expected RDF/SHACL/Protobuf terms. Those checks are useful, but substring checks do not execute a SHACL processor or prove graph conformance.

Some invariants belong to semantic validation rather than JSON Schema alone, such as:

- the record's evidence ID follows the approved identity profile;
- acquisition and evidence content digests and byte lengths agree;
- observation time is consistent with a supplied valid-time interval;
- provenance parent references exist and the graph remains acyclic;
- reference objects resolve to the intended evidence/entities;
- a declared license expression is syntactically valid under the selected SPDX grammar/version.

The next implementation should distinguish structural-schema failures from semantic-invariant failures and from external-standard validation results. It should include positive and negative fixtures for each layer.

### CCIP-05 — Review provenance activity identity scope

`ProvenanceActivity` currently derives its ID from activity name, agent, start/end timestamps and the parameters digest. It does not include `used_evidence_ids`, `generated_evidence_ids`, `parent_ids`, `software_name`, or `software_version`.

This is a policy decision to resolve, not a change to make casually. Test whether two otherwise identical activities with different lineage or software versions should be the same identified activity, distinct activities, or a collision. Document the answer, add regression vectors, and version the identity profile if the current preimage must change. Keep historical IDs readable and reproducible.

### CCIP-06 — Keep claims about cross-language coverage bounded

The current differential runner covers core primitives including canonical JSON, generic deterministic identity, quantity conversion, time normalization, geometry, core result envelopes, and temporal operations. The current Rust core does not define a full duplicate of the Python evidence/provenance domain models. Therefore, core differential success must not be presented as full evidence/provenance-model parity.

First establish language-neutral evidence and provenance boundary contracts and independent fixtures. Add Rust domain behavior only when it has an agreed contract and can be checked against the Python semantic authority.

### CCIP-07 — Align contract versions and compatibility statements

The evidence documentation labels the evidence contract 2.0.0; the Arrow artifact identifies `qedty.evidence.v2` and a separate `qedty-arrow-evidence@1` profile; the Protobuf package is `qedty.evidence.v1`. These names may describe different version axes, but the axes and compatibility rules need to be documented in a contract registry or mapping.

For each contract artifact, record its semantic contract version, serialization/profile version, canonical schema URI, compatibility policy, and golden-vector set. Avoid inferring API compatibility from a directory name alone.

## Recommended work packages

1. **Freeze and inventory the baseline.** Preserve the current canonical JSON/ID outputs and record the exact source commit and fixtures used for each contract surface.
2. **Write identity rules and vectors.** Define identity inputs, normalization order, timestamp normalization, numeric boundaries, Unicode behavior, digest encoding, and profile/version selection. Add edge vectors to Python and Rust conformance without changing existing expected IDs.
3. **Record a namespace decision.** Choose a persistent public namespace only after ownership and lifecycle are established. Until then, retain the current IRIs as a documented development namespace and plan a controlled migration.
4. **Map evidence contracts.** Build a field-by-field matrix across the Python model, JSON Schema, Arrow projection, Protobuf, and RDF/SHACL. Mark deliberate loss and unsupported fields.
5. **Specify provenance identity and graph integrity.** Decide activity-ID semantics; test identical activity inputs with different evidence/parent/software links, unknown parents, duplicate IDs, cycle rejection and deterministic topological ordering.
6. **Make validation executable.** Retain JSON Schema meta-validation and golden-record checks; add negative semantic fixtures, real SHACL execution against representative RDF data, Protobuf conversion tests, and Arrow schema/round-trip tests where supported.
7. **Integrate with CI and migration docs.** Run manifest inventory checks, existing Python/Rust differential tests and the repository verification gate. Any intentional contract incompatibility needs an explicit migration note and compatibility fixture.

## Acceptance gates

- Existing canonical JSON and deterministic-ID golden vectors remain unchanged unless an approved versioned migration explicitly says otherwise.
- Canonicalization, hashing of JSON metadata, and hashing of raw evidence bytes are separately named and tested.
- Each field in the full evidence model has a documented representation or an explicit omission/derivation rule for every supported boundary.
- Evidence and provenance invariants have positive and negative tests; the tests assert behavior rather than only checking for strings in files.
- At least one SHACL engine executes the evidence shapes against representative valid and invalid RDF graphs, with the validator version and command recorded.
- Provenance ID scope and namespace lifecycle are documented decisions before any breaking implementation change.
- The project inventory, existing core conformance suites, full Python tests, Rust checks and CI pass on the exact candidate commit.
- Documentation accurately distinguishes implemented capability, tested interoperability, and future work.

## Standards references

- RFC 8785, JSON Canonicalization Scheme: https://www.rfc-editor.org/rfc/rfc8785
- RFC 6762, Multicast DNS (`.local.` semantics): https://www.rfc-editor.org/rfc/rfc6762
- RFC 9530, HTTP Digest Fields: https://www.rfc-editor.org/rfc/rfc9530
- JSON Schema 2020-12: https://json-schema.org/specification
- W3C PROV-O: https://www.w3.org/TR/prov-o/
- W3C PROV-DM: https://www.w3.org/TR/prov-dm/
- W3C SHACL: https://www.w3.org/TR/shacl/
- W3C JSON-LD 1.1: https://www.w3.org/TR/json-ld11/
- W3C Data Quality Vocabulary: https://www.w3.org/TR/vocab-dqv/
- W3C Data Catalog Vocabulary 3: https://www.w3.org/TR/vocab-dcat-3/

These references are the selected standards baselines for this review. QEDTY's mapping to individual concepts is not a claim of complete conformance to every feature of those standards.
