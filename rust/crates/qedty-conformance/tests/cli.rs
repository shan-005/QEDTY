use std::process::Command;

#[test]
fn cli_executes_shared_core_vectors() {
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
    assert!(stdout.contains("PASS: 9/9 Rust-implemented core golden vectors conform"));
    assert!(stdout.contains("PASS core/canonical_json.json"));
    assert!(stdout.contains("PASS core/identity.json"));
    assert!(stdout.contains("PASS core/geometry_ecef.json"));
}
