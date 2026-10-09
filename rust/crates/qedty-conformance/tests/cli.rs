use std::path::Path;
use std::process::Command;

#[test]
fn cli_executes_every_implemented_shared_core_vector() {
    let vector_dir =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../data/contracts/golden-vectors/core");
    let geometry_count = std::fs::read_dir(&vector_dir)
        .expect("shared core vector directory should exist")
        .filter_map(Result::ok)
        .filter(|entry| entry.file_type().is_ok_and(|kind| kind.is_file()))
        .filter(|entry| {
            entry
                .file_name()
                .to_str()
                .is_some_and(|name| name.starts_with("geometry_ecef") && name.ends_with(".json"))
        })
        .count();
    assert!(geometry_count > 0, "geometry reference vectors must exist");

    let canonical_count = std::fs::read_dir(&vector_dir)
        .expect("shared core vector directory should exist")
        .filter_map(Result::ok)
        .filter(|entry| entry.file_type().is_ok_and(|kind| kind.is_file()))
        .filter(|entry| {
            entry
                .file_name()
                .to_str()
                .is_some_and(|name| name.starts_with("canonical_json") && name.ends_with(".json"))
        })
        .count();
    assert!(
        canonical_count > 0,
        "canonical JSON reference vectors must exist"
    );

    let expected_count = geometry_count + canonical_count + 2; // identity and time.
    let output = Command::new(env!("CARGO_BIN_EXE_qedty-conformance"))
        .output()
        .expect("the conformance CLI should launch");
    assert!(
        output.status.success(),
        "conformance CLI failed\nstdout:\n{}\nstderr:\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains(&format!(
            "PASS: {expected_count}/{expected_count} Rust-implemented core golden vectors conform"
        )),
        "summary did not account for every geometry fixture:\n{stdout}"
    );
    assert_eq!(
        stdout.matches("PASS core/canonical_json").count(),
        canonical_count,
        "every canonical JSON fixture must be explicitly reported as passing"
    );
    assert!(stdout.contains("PASS core/identity.json"));
    assert!(stdout.contains("PASS core/time.json"));
    assert_eq!(
        stdout.matches("PASS core/geometry_ecef").count(),
        geometry_count,
        "every geometry fixture must be explicitly reported as passing"
    );
    assert!(stdout.contains(
        "NOTE: contract_result.json and quantity.json remain pending Rust APIs"
    ));
    assert!(!stdout.contains("PASS core/quantity.json"));
    assert!(!stdout.contains("PASS core/contract_result.json"));
}
