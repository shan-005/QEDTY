# Rust architecture and boundaries

## Existing boundary

```text
Python semantic/reference implementation
     │ defines intended domain behavior
     ├── shared JSON Schema / Protobuf / RDF / Arrow contracts
     ├── data/contracts/golden-vectors/<domain>/*.json
     │
     └── crates/qedty-core (existing canonical native crate)
              │
              └── rust/crates/qedty-conformance (verification CLI)
```

The CLI is a harness, not another semantic layer. Rust returns values; QEDTY contracts define what those values mean.

## Rust target dependency direction

```text
core types / errors / identity / canonicalization
            │
            ├── temporal primitives
            ├── geodesy and spatial primitives
            ├── graph primitives and indexing
            │
            └── deterministic numerical kernels
                    ├── propagation
                    ├── scenario operations
                    ├── continuity calculations
                    ├── uncertainty kernels
                    └── optimization kernels
```

This is a **conceptual dependency sequence**, not an instruction to split all domains into crates immediately. Start with modules in `qedty-core`; split into crates only when compilation, feature boundaries, dependency ownership, or release cadence justify it.

## Ownership of semantics

- Python remains the reference implementation and semantic authority.
- Golden vectors are language-neutral behavior fixtures; changing an expected result requires contract review.
- Rust may improve execution speed but may not quietly redefine the ontology, epistemic state, provenance model, units, interval inclusivity, propagation tie-breaking, or uncertainty meaning.
- Protobuf is a service/control contract, Arrow is a columnar data boundary, and Parquet/object storage is durable bulk data. Rust does not invent competing transports here.

## Determinism design

1. Canonicalize serialized JSON recursively according to the existing `qedty-canonical-json@1` profile.
2. Use SHA-256 identity inputs exactly as defined by the current Python/Rust vector.
3. Keep stable ordering for externally visible lists/maps where the contract requires it.
4. Separate deterministic identity/hash behavior from approximate numeric computations.
5. Use explicit tolerances only for numerical outputs whose contract permits tolerance.
6. Treat CPU/GPU cross-platform bitwise equality as an explicit requirement decision, not an assumption.

## API stability

The first module refactor should preserve all current public names and signatures (`canonical_json`, `sha256_hex`, `deterministic_id`, `ecef_wgs84`, `EntityRef`, `TimeWindow`, `Quantity`, and `CoreError`) by re-exporting through `lib.rs`. Avoid a public API break while moving code into modules.
