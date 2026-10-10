#![no_main]

use libfuzzer_sys::fuzz_target;
use serde_json::Value;

fuzz_target!(|data: &[u8]| {
    let Ok(value) = serde_json::from_slice::<Value>(data) else {
        return;
    };

    let canonical = qedty_core::canonical_json(&value)
        .expect("a parsed serde_json value should be canonicalizable");
    let reparsed = serde_json::from_str::<Value>(&canonical)
        .expect("canonical JSON output should itself parse");
    let canonical_again = qedty_core::canonical_json(&reparsed)
        .expect("reparsed canonical JSON should be canonicalizable");

    assert_eq!(canonical, canonical_again, "canonicalization must be idempotent");
});
