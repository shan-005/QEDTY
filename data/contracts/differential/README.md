# QEDTY Python–Rust differential cases

This directory holds small, deterministic JSON fixtures used by `scripts/check_python_rust_differential.py`.
They are tests, not production domain records or a replacement for `data/contracts/golden-vectors/`.

## Case format

Every document uses `schema_version: "qedty-differential-cases@1"` and a `cases` array. Each case has:

- `case_id`: immutable and unique regression identifier.
- `operation`: one of the operation IDs implemented by both adapters.
- `input`: the same JSON-compatible payload supplied to Python and Rust.
- `comparison.mode`: `exact`, `numeric`, or `vector_tolerance`.
- `comparison.absolute_tolerance` and `comparison.relative_tolerance`: required by policy for approximate output; these apply only to numeric comparisons and must be justified in the contract.
- `expected_error`: for negative cases, the shared error category required from both implementations.
- `expected_result`: optional independent expected value used for exact outputs and reviewed numerical oracles. Approximate expected values use the same declared per-case tolerance as cross-language comparisons.

Identity inputs follow the current hash preimage: `parts[0]` is the namespace, then remaining parts preserve their order. Quantity results compare numeric values because Python uses `Decimal` while Rust currently uses `f64`; this does **not** imply arbitrary-precision equivalence. ECEF comparison tolerance is in metres for each Cartesian coordinate.

## Run

From the repository root, after applying the bundle:

```bash
uv run pytest -q tests/differential
uv run python scripts/check_python_rust_differential.py --generated-count 64 --seed 20261010
```

The script builds/runs the actual native JSONL adapter with `cargo run --locked`. Set `QEDTY_DIFFERENTIAL_RUST_COMMAND` only when you need an alternate runner command. If the Rust toolchain, executable, or dependencies are missing, the command fails rather than skipping native comparisons.

The generator is deterministic and has no runtime dependency on Hypothesis or Proptest. `--generated-count N` adds N cases to each generated family and `--seed S` records a replayable pseudo-random seed. Fixed test fixtures always run. Generated cases use integer/string canonical JSON, in-range WGS-84 inputs, time instants, identity inputs, and finite unit conversions. Extended fuzzing can be added separately after toolchain/MSRV compatibility is verified.

## Adding a confirmed regression

1. Reproduce the failure with a fixed seed and copy the smallest complete input into a checked-in case document.
2. Choose `exact` only for contract-exact data; use a numeric comparator only when the contract defines a tolerance and its units.
3. For errors, set a specific stable `expected_error` category. Do not compare only that both sides crashed.
4. Add an independently justified expected result when one can be established from a reviewed contract or external golden fixture; never copy a failing Rust output into the oracle.
5. Run the fixed-case Python test and the full native differential command. Never automatically overwrite expected outputs from the current Rust implementation.
6. Preserve failure input and relevant seed in the pull request.

## Coverage boundary

The current direct operation set is deliberately limited to semantics that have a close, reviewed Python and Rust counterpart: canonical JSON, deterministic IDs, quantity conversion, RFC 3339 normalization, checked WGS-84 ECEF, `ContractResult` normalization, half-open interval membership, and Allen interval relation classification. This does not certify arbitrary behavior of every Rust kernel or every Python domain API.

In particular, `qedty_core::graph::DirectedGraph` documents itself as a primitive for small/medium native kernels and not a replacement for QEDTY's Python temporal world-graph API. Do not claim graph-wide parity until the two sides share an explicit request/result contract and a same-input adapter. The same rule applies to spatial, propagation, uncertainty, and scenario kernels without a direct counterpart.
