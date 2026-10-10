#![no_main]

use libfuzzer_sys::fuzz_target;
use serde_json::Value;

fuzz_target!(|data: &[u8]| {
    let digest_length = data
        .first()
        .map(|byte| usize::from(*byte % 64) + 1)
        .unwrap_or(1);
    let part = match serde_json::from_slice::<Value>(data) {
        Ok(value) => value,
        Err(_) => Value::String(String::from_utf8_lossy(data).into_owned()),
    };

    let id = qedty_core::deterministic_id(
        "fuzz-entity",
        "fuzz-namespace",
        &[part],
        digest_length,
    )
    .expect("the fuzz target supplies valid kind, namespace and digest length");

    let digest = id
        .strip_prefix("fuzz-entity:")
        .expect("identity must retain its kind prefix");
    assert_eq!(digest.len(), digest_length);
    assert!(digest.bytes().all(|byte| byte.is_ascii_hexdigit()));
});
