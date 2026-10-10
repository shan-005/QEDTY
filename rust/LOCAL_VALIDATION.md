# Local Rust Core Validation

Run from the QEDTY repository root after extracting the overlay and applying its
installer:

```bash
python3 scripts/install_rust_core_expansion.py

git diff --check
cargo fmt --all -- --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo run --locked -p qedty-conformance --bin qedty-conformance
cargo run --locked -p qedty-conformance --bin rust-expansion-conformance
uv run python scripts/check_core_conformance.py
uv run python scripts/check_graph_conformance.py
uv run pytest -q
```

Or run the same sequence with logs and immediate failure using:

```bash
bash scripts/verify_rust_core_expansion.sh
```

The verifier never commits or pushes. A green result means the listed local
commands completed for that working tree; hosted CI, package/release checks and
review of the final diff are still separate gates.
