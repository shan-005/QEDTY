# Rust Core Expansion

> Current-state documentation: the implementation described here is already incorporated in `main`. Use `rust/LOCAL_VALIDATION.md` for verification. The original overlay bundle is a historical integration artifact and must not be re-applied to the current branch.

## API map

| Module | Scope | Contract caveat |
|---|---|---|
| `quantity` | Typed dimensions, bounded unit registry, conversion, affine-temperature restrictions | Uses `f64`; not general `Decimal` equivalence |
| `contract_result` | Evidence envelope, sorted unique IDs/assumptions, optional metadata and normalized `valid_at` | JSON-shaped initial API, not a replacement for Python model validation |
| `temporal_relations` | Allen relations, bitemporal membership, sorted interval timeline | Existing instants and intervals remain microsecond precision and half-open |
| `geodesy` | Checked inverse ECEF to geodetic conversion | Round-trip tests are present; expanded independently expected geodesy fixtures remain desirable |
| `spatial` | Deterministic latitude/longitude grid and point-radius query | Spherical mean-Earth distance; not ellipsoidal geodesics or global raster/H3 indexing |
| `graph` | Deterministic adjacency, BFS, shortest path, reliability path, components, PageRank, max flow | In-memory algorithmic primitives; not the full QEDTY world-graph service |
| `compute` | Weighted mean, interval arithmetic, capacity score, synchronous propagation, knapsack | General primitives require domain-specific reference/units before production integration |
| `columnar` | Typed null-aware column batch and JSON row conversion | Explicitly an adapter seam; not Arrow IPC/C Data Interface support |

## Test wiring

The existing `crates/qedty-core/tests/golden.rs` and `qedty-conformance` CLI remain
in place. `tests/rust_expansion.rs` covers the shared quantity, contract-result
and graph fixtures. The CLI checks `quantity.json` and `contract_result.json`,
and `rust-expansion-conformance` checks the eight currently defined graph golden
scenarios.

The expected core runner summary is 13/13 fixtures: two canonical JSON vectors,
one identity vector, seven WGS-84 ECEF vectors, one temporal normalization
vector, one quantity conversion vector, and one contract-result vector. The
separate graph runner exercises eight scenarios. Successful counts are to be
reported only after commands execute locally.

## Release gates still open after unit conformance

- Python/Rust differential and property tests across complete domain contracts.
- Arrow integration against canonical Arrow schemas and cross-language fixtures.
- Benchmarks and allocation/memory profiles using the accepted reproducible
  release-mode process.
- Fuzz targets and run evidence where justified by the parser/input surface.
- An explicit reviewed decision and platform wheel tests before introducing
  PyO3/maturin or another Python-native boundary.
- Full CI, manifest, package, and security gates on the final reviewed changes.

Do not claim that these gates passed just because the new source files exist or
because the included fixture runners pass.
