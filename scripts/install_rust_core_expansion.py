#!/usr/bin/env python3
"""Safely wire the Rust core expansion overlay into the QEDTY repository.

This installer is intentionally local-only: it never creates commits, branches,
PRs, pushes, or invokes any remote GitHub operation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

BASELINE = "d68af5e31e0707256c0834c139f710eefc961e2f"
NEW_PATHS = [
    "RUST_CORE_EXPANSION_BUNDLE.md",
    "crates/qedty-core/src/quantity.rs",
    "crates/qedty-core/src/contract_result.rs",
    "crates/qedty-core/src/temporal_relations.rs",
    "crates/qedty-core/src/geodesy.rs",
    "crates/qedty-core/src/spatial.rs",
    "crates/qedty-core/src/graph.rs",
    "crates/qedty-core/src/compute.rs",
    "crates/qedty-core/src/columnar.rs",
    "crates/qedty-core/tests/rust_expansion.rs",
    "rust/crates/qedty-conformance/src/bin/rust-expansion-conformance.rs",
    "rust/CORE_EXPANSION.md",
    "rust/LOCAL_VALIDATION.md",
    "scripts/install_rust_core_expansion.py",
    "scripts/verify_rust_core_expansion.sh",
]
MODULES = [
    "quantity",
    "contract_result",
    "temporal_relations",
    "geodesy",
    "spatial",
    "graph",
    "compute",
    "columnar",
]


def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], text=True, capture_output=True, check=True)
    return result.stdout.strip()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def replace_once(path: Path, old: str, new: str, description: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        fail(
            f"could not locate expected source text in {path.relative_to(ROOT)} ({description}); no patch applied to this section"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def inventory(paths: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    by_extension: Counter[str] = Counter()
    by_root: Counter[str] = Counter()
    for path in paths:
        item = Path(path)
        by_extension[item.suffix.lower() if item.suffix else "<no-extension>"] += 1
        by_root[item.parts[0] if item.parts else "."] += 1
    return dict(sorted(by_extension.items())), dict(sorted(by_root.items()))


def update_manifest() -> None:
    path = ROOT / "QEDTY-PROJECT-MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    paths = set(manifest.get("files", []))
    paths.update(NEW_PATHS)
    ordered = sorted(paths)
    ext, root_counts = inventory(ordered)
    manifest["files"] = ordered
    manifest["tracked_file_count"] = len(ordered)
    manifest["extension_counts"] = ext
    manifest["root_counts"] = root_counts
    manifest["python_files"] = sum(Path(p).suffix.lower() == ".py" for p in ordered)
    manifest["rust_files"] = sum(Path(p).suffix.lower() == ".rs" for p in ordered)
    manifest["protobuf_files"] = sum(Path(p).suffix.lower() == ".proto" for p in ordered)
    manifest["markdown_files"] = sum(Path(p).suffix.lower() == ".md" for p in ordered)
    manifest["json_files"] = sum(Path(p).suffix.lower() == ".json" for p in ordered)
    manifest["turtle_files"] = sum(Path(p).suffix.lower() == ".ttl" for p in ordered)
    manifest["yaml_files"] = sum(Path(p).suffix.lower() in {".yaml", ".yml"} for p in ordered)
    manifest["shell_files"] = sum(Path(p).suffix.lower() == ".sh" for p in ordered)
    manifest["generated_on"] = date.today().isoformat()
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if (
        not (ROOT / ".git").exists()
        or not (ROOT / "Cargo.toml").exists()
        or not (ROOT / "pyproject.toml").exists()
    ):
        fail("installer must live in the QEDTY repository root/scripts directory")
    git_root = Path(run_git("rev-parse", "--show-toplevel")).resolve()
    if git_root != ROOT.resolve():
        fail(f"repository root mismatch: expected {ROOT}, got {git_root}")
    head = run_git("rev-parse", "HEAD")
    if head != BASELINE:
        fail(
            f"unexpected HEAD {head}; bundle was reviewed against {BASELINE}. Fetch/review a matching baseline before applying it"
        )
    if run_git("status", "--porcelain", "--untracked-files=no"):
        fail(
            "tracked files already have local modifications. Commit, stash, or review them before applying the overlay"
        )
    for item in NEW_PATHS:
        if not (ROOT / item).is_file():
            fail(f"overlay file is missing after ZIP extraction: {item}")

    lib = ROOT / "crates/qedty-core/src/lib.rs"
    lib_text = lib.read_text(encoding="utf-8")
    required = "pub mod geometry;\npub mod temporal;\n"
    declarations = "pub mod geometry;\npub mod temporal;\n" + "".join(
        f"pub mod {module};\n" for module in MODULES
    )
    present = [f"pub mod {module};" in lib_text for module in MODULES]
    if all(present):
        pass
    elif any(present):
        fail(
            "core module declarations are only partially present; review crates/qedty-core/src/lib.rs manually"
        )
    elif required in lib_text:
        lib.write_text(lib_text.replace(required, declarations, 1), encoding="utf-8", newline="\n")
    else:
        fail(
            "could not safely locate core module declaration marker in crates/qedty-core/src/lib.rs"
        )

    main = ROOT / "rust/crates/qedty-conformance/src/main.rs"
    function_marker = (
        "fn geometry_vector_files(vector_dir: &Path) -> Result<Vec<String>, Box<dyn Error>> {"
    )
    functions = r"""fn check_quantity(vector_dir: &Path) -> Result<(), Box<dyn Error>> {
    let vector = read_vector(vector_dir, "quantity.json")?;
    if str_field(&vector, "kind")? != "quantity" {
        return Err(invalid_vector("quantity.json has an unexpected kind").into());
    }
    let value: f64 = str_field(&vector, "value")?.parse()?;
    let actual = qedty_core::quantity::format_value(qedty_core::quantity::convert_value(
        value,
        str_field(&vector, "from_unit")?,
        str_field(&vector, "to_unit")?,
    )?)?;
    let expected = str_field(&vector, "expected_value")?;
    if actual != expected {
        return Err(invalid_vector(format!("quantity.json mismatch: actual={actual}, expected={expected}")).into());
    }
    println!("PASS core/quantity.json");
    Ok(())
}

fn check_contract_result(vector_dir: &Path) -> Result<(), Box<dyn Error>> {
    let vector = read_vector(vector_dir, "contract_result.json")?;
    if str_field(&vector, "kind")? != "contract_result" {
        return Err(invalid_vector("contract_result.json has an unexpected kind").into());
    }
    let result = qedty_core::contract_result::ContractResult::from_value(&vector)?;
    let actual = result.canonical_json()?;
    let expected = str_field(&vector, "expected_canonical_json")?;
    if actual != expected {
        return Err(invalid_vector(format!("contract_result.json mismatch: actual={actual:?}, expected={expected:?}")).into());
    }
    println!("PASS core/contract_result.json");
    Ok(())
}

"""
    main_text = main.read_text(encoding="utf-8")
    if "fn check_contract_result(" not in main_text:
        if function_marker not in main_text:
            fail("could not safely locate conformance CLI insertion marker")
        main.write_text(
            main_text.replace(function_marker, functions + function_marker, 1),
            encoding="utf-8",
            newline="\n",
        )
    replace_once(
        main,
        """    check_time(&vector_dir)?;
    let implemented_vectors = canonical_files.len() + 1 + geometry_files.len() + 1;
    println!(
        \"PASS: {implemented_vectors}/{implemented_vectors} Rust-implemented core golden vectors conform (canonical JSON vectors, identity, WGS-84 geometry, temporal normalization)\"
    );
    println!(\"NOTE: contract_result.json and quantity.json remain pending Rust APIs\");
""",
        """    check_time(&vector_dir)?;
    check_quantity(&vector_dir)?;
    check_contract_result(&vector_dir)?;
    let implemented_vectors = canonical_files.len() + 1 + geometry_files.len() + 3;
    println!(
        \"PASS: {implemented_vectors}/{implemented_vectors} Rust-implemented core golden vectors conform (canonical JSON, identity, WGS-84 geometry, temporal normalization, quantity conversion, contract result)\"
    );
""",
        "expanded conformance runner",
    )

    workflow = ROOT / ".github/workflows/rust.yml"
    replace_once(
        workflow,
        """      - name: Run shared core conformance vectors
        run: cargo run --locked -p qedty-conformance
""",
        """      - name: Run shared core conformance vectors
        run: cargo run --locked -p qedty-conformance --bin qedty-conformance
      - name: Run expanded graph/spatial conformance vectors
        run: cargo run --locked -p qedty-conformance --bin rust-expansion-conformance
""",
        "Rust CI extended conformance job",
    )

    ci_workflow = ROOT / ".github/workflows/ci.yml"
    replace_once(
        ci_workflow,
        """      - name: Run Rust shared golden-vector conformance
        run: cargo run --locked -p qedty-conformance
""",
        """      - name: Run Rust shared golden-vector conformance
        run: cargo run --locked -p qedty-conformance --bin qedty-conformance
      - name: Run expanded graph/spatial conformance
        run: cargo run --locked -p qedty-conformance --bin rust-expansion-conformance
""",
        "platform CI extended conformance runners",
    )

    verify = ROOT / "rust/scripts/verify.sh"
    replace_once(
        verify,
        "cargo run --locked -p qedty-conformance\n# Preserve the original crate entry point as an independent compatibility gate.",
        "cargo run --locked -p qedty-conformance --bin qedty-conformance\ncargo run --locked -p qedty-conformance --bin rust-expansion-conformance\n# Preserve the original crate entry point as an independent compatibility gate.",
        "local verification extended conformance",
    )

    cli = ROOT / "rust/crates/qedty-conformance/tests/cli.rs"
    replace_once(
        cli,
        "let expected_count = geometry_count + canonical_count + 2; // identity and time.",
        "let expected_count = geometry_count + canonical_count + 4; // identity, time, quantity, contract result.",
        "conformance vector count",
    )
    replace_once(
        cli,
        """    assert!(
        stdout.contains(\"NOTE: contract_result.json and quantity.json remain pending Rust APIs\")
    );
    assert!(!stdout.contains(\"PASS core/quantity.json\"));
    assert!(!stdout.contains(\"PASS core/contract_result.json\"));
""",
        """    assert!(stdout.contains(\"PASS core/quantity.json\"));
    assert!(stdout.contains(\"PASS core/contract_result.json\"));
    assert!(!stdout.contains(\"remain pending Rust APIs\"));
""",
        "conformance CLI assertions",
    )

    conformance = ROOT / "rust/CONFORMANCE.md"
    replace_once(
        conformance,
        "| `core/quantity.json` | No conversion API currently exposed | Not yet implemented in Rust; must not be counted as pass |",
        "| `core/quantity.json` | `quantity::convert_value` | Exact fixture value formatting; dimension mismatch and non-finite inputs rejected |",
        "quantity fixture table",
    )
    replace_once(
        conformance,
        "| `core/contract_result.json` | No matching Rust API yet | Pending Rust support; must not be counted as pass |",
        "| `core/contract_result.json` | `contract_result::ContractResult` | Exact canonical JSON after sorted/deduplicated identifiers and UTC timestamp normalization |",
        "contract result fixture table",
    )
    replace_once(
        conformance,
        "The CLI reports only implemented Rust APIs; `contract_result.json` and `quantity.json` remain pending and must not be represented as Rust passes. The initial temporal interval APIs have unit coverage for half-open boundaries and invalid ranges, while expanded temporal relations and indexing remain future work.",
        "The primary `qedty-conformance` CLI validates both fixture files in addition to canonical JSON, identity, geometry, and UTC timestamp normalization. `temporal_relations.rs` provides the 13 Allen interval relations, bitemporal membership and sorted timeline queries; `spatial.rs` provides a deterministic point-grid candidate index; `graph.rs` implements deterministic traversal, shortest/reliability paths, connectivity, PageRank and max flow. `compute.rs` adds pure numeric/uncertainty/propagation/knapsack kernels. The columnar batch is an Arrow-neutral adapter seam, not Arrow IPC. Full completion still requires broader Python differential vectors, a maintained property/fuzz strategy, Criterion release benchmarks, real Arrow interoperability, and a separately reviewed Python-binding/package decision.",
        "conformance scope boundary",
    )

    plan = ROOT / "rust/RUST_PLAN.md"
    replace_once(
        plan,
        "Remaining temporal work includes granularity, bitemporal distinctions, Allen relations, timeline/query/index operations, and additional differential vectors grounded in Python reference behavior.",
        "Remaining temporal work includes granularity systems, temporal indexes and query optimization, and broader differential vectors grounded in Python reference behavior. Bitemporal membership, the 13 Allen relations, and sorted timeline overlap/active queries are now implemented as initial primitives.",
        "temporal plan scope",
    )
    replace_once(
        plan,
        "Passing current core vectors does not close the whole Rust roadmap. `contract_result`, `quantity`, and `time` remain pending Rust APIs and must not count as passing Rust conformance.",
        "Passing current core vectors does not close the whole Rust roadmap. `contract_result`, `quantity`, and `time` now have Rust APIs and shared-vector checks; full completion still requires expanded Python differential/property coverage, real Arrow interoperability, reproducible release benchmarks, fuzz targets where justified, and a reviewed Python binding/package decision.",
        "Rust roadmap exit statement",
    )

    tree = ROOT / "rust/TARGET_TREE.md"
    replace_once(
        tree,
        """│       ├── src/
│       │   ├── lib.rs
│       │   └── geometry.rs
│       └── tests/
│           └── golden.rs""",
        """│       ├── src/
│       │   ├── lib.rs
│       │   ├── geometry.rs
│       │   ├── temporal.rs
│       │   ├── quantity.rs
│       │   ├── contract_result.rs
│       │   ├── temporal_relations.rs
│       │   ├── geodesy.rs
│       │   ├── spatial.rs
│       │   ├── graph.rs
│       │   ├── compute.rs
│       │   └── columnar.rs
│       └── tests/
│           ├── golden.rs
│           └── rust_expansion.rs""",
        "core source tree",
    )
    replace_once(
        tree,
        """    └── crates/qedty-conformance/
        ├── Cargo.toml
        ├── src/main.rs
        └── tests/cli.rs""",
        """    └── crates/qedty-conformance/
        ├── Cargo.toml
        ├── src/main.rs
        ├── src/bin/rust-expansion-conformance.rs
        └── tests/cli.rs""",
        "expanded runner tree",
    )

    crate_map = ROOT / "rust/crate-map.toml"
    replace_once(
        crate_map,
        'responsibility = "Deterministic core types, canonical JSON, identities, WGS-84 ECEF"',
        'responsibility = "Deterministic core types, canonical JSON, identities, WGS-84 geometry, temporal relations, quantity conversion, contract results, graph/spatial and numeric kernels"',
        "core crate registry",
    )

    replace_once(
        tree,
        "│   ├── contract_result.json            # no Rust API yet",
        "│   ├── contract_result.json            # shared Rust contract-result vector",
        "contract result tree annotation",
    )
    replace_once(
        tree,
        "│   ├── quantity.json                   # no Rust quantity conversion API yet",
        "│   ├── quantity.json                   # shared Rust unit-conversion vector",
        "quantity tree annotation",
    )
    replace_once(
        tree,
        "│   └── time.json                       # no Rust time normalization API yet",
        "│   └── time.json                       # shared Rust UTC-normalization vector",
        "time tree annotation",
    )

    replace_once(
        tree,
        "The Python semantic/reference implementation and its contracts remain the semantic authority. The Rust workspace currently implements deterministic canonical JSON, identity, WGS-84 ECEF conversion, RFC 3339 timestamp normalization, and initial half-open interval primitives, plus a CLI that checks the supported shared vectors.",
        "The Python semantic/reference implementation and its contracts remain the semantic authority. The Rust workspace includes canonical JSON, identity, checked WGS-84 ECEF, inverse ECEF, RFC 3339 normalization, temporal relations/bitemporal timelines, dimension-checked quantities, contract-result normalization, deterministic graph algorithms, point-grid spatial queries, numeric propagation/uncertainty/selection kernels, and an Arrow-neutral columnar batch seam. The primary CLI checks the implemented shared core vectors; the separate expanded runner also verifies graph/spatial scenarios.",
        "implementation summary",
    )
    replace_once(
        tree,
        "The canonical core fixture directory contains 13 JSON fixtures. Eleven implemented behavior cases pass in Rust: canonical JSON (2), deterministic identity (1), ECEF geometry (7), and timestamp normalization (1). Two fixture types remain pending Rust APIs: `contract_result.json` and `quantity.json`. The time vector validates timestamp normalization; broader temporal relations, bitemporal semantics, timelines and indexing remain future work. A fixture being present is not evidence that a matching Rust API exists.",
        "The canonical core fixture directory contains 13 JSON fixtures. The Rust conformance runner now checks all 13 behavior cases: canonical JSON (2), deterministic identity (1), ECEF geometry (7), timestamp normalization (1), quantity conversion (1), and contract-result canonicalization (1). The graph conformance runner also checks eight versioned scenarios. Additional property/differential evidence is still required; a fixture pass does not prove every domain integration or release gate is complete.",
        "current conformance summary",
    )
    with (tree).open("a", encoding="utf-8", newline="\n") as handle:
        if "## Expanded core modules" not in tree.read_text(encoding="utf-8"):
            handle.write(
                "\n\n## Expanded core modules\n\nThe following source modules are now included in `qedty-core`: `quantity.rs`, `contract_result.rs`, `temporal_relations.rs`, `geodesy.rs`, `spatial.rs`, `graph.rs`, `compute.rs`, and `columnar.rs`. The columnar module deliberately avoids claiming Arrow IPC support. `rust/CORE_EXPANSION.md` defines the APIs and residual release gates.\n"
            )

    # Format all affected Rust files with the repository's pinned local toolchain.
    fmt = subprocess.run(["cargo", "fmt", "--all"], cwd=ROOT, text=True, capture_output=True)
    if fmt.returncode != 0:
        fail(
            "cargo fmt --all failed; review the output below and run cargo fmt manually\n"
            + fmt.stdout
            + fmt.stderr
        )

    update_manifest()
    print("PASS: Rust core source modules wired into lib.rs")
    print("PASS: quantity and contract-result golden vectors wired into qedty-conformance")
    print("PASS: Rust conformance documentation and project manifest updated")
    print("No commit, branch, push, PR, or GitHub write was performed.")
    print("Next: run scripts/verify_rust_core_expansion.sh and review the complete local diff.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
