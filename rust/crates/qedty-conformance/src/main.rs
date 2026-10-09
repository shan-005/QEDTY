use qedty_core::{canonical_json, deterministic_id, ecef_wgs84};
use serde_json::Value;
use std::error::Error;
use std::io;
use std::path::{Path, PathBuf};

fn invalid_vector(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.into())
}

fn repository_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..")
}

fn read_vector(vector_dir: &Path, file: &str) -> Result<Value, Box<dyn Error>> {
    let path = vector_dir.join(file);
    let raw = std::fs::read_to_string(&path)?;
    Ok(serde_json::from_str(raw.trim_start_matches('\u{feff}'))?)
}

fn str_field<'a>(value: &'a Value, key: &str) -> Result<&'a str, Box<dyn Error>> {
    value
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| invalid_vector(format!("missing string field `{key}`")).into())
}

fn usize_field(value: &Value, key: &str) -> Result<usize, Box<dyn Error>> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .and_then(|number| usize::try_from(number).ok())
        .ok_or_else(|| invalid_vector(format!("missing non-negative integer field `{key}`")).into())
}

fn f64_field(value: &Value, key: &str) -> Result<f64, Box<dyn Error>> {
    value
        .get(key)
        .and_then(Value::as_f64)
        .ok_or_else(|| invalid_vector(format!("missing numeric field `{key}`")).into())
}

fn check_canonical_json(vector_dir: &Path, filename: &str) -> Result<(), Box<dyn Error>> {
    let vector = read_vector(vector_dir, filename)?;
    if str_field(&vector, "kind")? != "canonical_json" {
        return Err(invalid_vector(format!("{filename} has an unexpected kind")).into());
    }
    let expected = str_field(&vector, "expected")?;
    let input = vector
        .get("value")
        .ok_or_else(|| invalid_vector(format!("{filename} lacks `value`")))?;
    let actual = canonical_json(input)?;
    if actual != expected {
        return Err(invalid_vector(format!(
            "{filename}: canonical JSON mismatch: actual={actual:?}, expected={expected:?}"
        ))
        .into());
    }
    println!("PASS core/{filename}");
    Ok(())
}

fn canonical_json_vector_files(vector_dir: &Path) -> Result<Vec<String>, Box<dyn Error>> {
    let mut files = Vec::new();
    for entry in std::fs::read_dir(vector_dir)? {
        let entry = entry?;
        if !entry.file_type()?.is_file() {
            continue;
        }
        let filename = entry.file_name();
        let Some(filename) = filename.to_str() else {
            continue;
        };
        if filename.starts_with("canonical_json") && filename.ends_with(".json") {
            files.push(filename.to_owned());
        }
    }
    files.sort();
    if files.is_empty() {
        return Err(invalid_vector("no canonical_json*.json reference vectors found").into());
    }
    Ok(files)
}

fn check_identity(vector_dir: &Path) -> Result<(), Box<dyn Error>> {
    let vector = read_vector(vector_dir, "identity.json")?;
    if str_field(&vector, "kind")? != "identity" {
        return Err(invalid_vector("identity vector has an unexpected kind").into());
    }
    let namespace = str_field(&vector, "namespace")?;
    let length = usize_field(&vector, "length")?;
    let kind = str_field(&vector, "kind")?;
    let parts = vector
        .get("parts")
        .and_then(Value::as_array)
        .ok_or_else(|| invalid_vector("identity vector lacks an array `parts`"))?;
    let expected = str_field(&vector, "expected_id")?;
    let actual = deterministic_id(kind, namespace, parts, length)?;
    if actual != expected {
        return Err(invalid_vector(format!(
            "identity mismatch: actual={actual}, expected={expected}"
        ))
        .into());
    }
    println!("PASS core/identity.json");
    Ok(())
}

fn check_geometry(vector_dir: &Path, filename: &str) -> Result<(), Box<dyn Error>> {
    let vector = read_vector(vector_dir, filename)?;
    if str_field(&vector, "kind")? != "geometry_ecef" {
        return Err(invalid_vector(format!("{filename} has an unexpected kind")).into());
    }
    let latitude = f64_field(&vector, "latitude")?;
    let longitude = f64_field(&vector, "longitude")?;
    let height_m = f64_field(&vector, "height_m")?;
    let tolerance = f64_field(&vector, "absolute_tolerance_m")?;
    if !tolerance.is_finite() || tolerance < 0.0 {
        return Err(invalid_vector(format!(
            "{filename}: tolerance must be finite and non-negative"
        ))
        .into());
    }
    let expected = vector
        .get("expected_ecef_m")
        .and_then(Value::as_array)
        .filter(|coordinates| coordinates.len() == 3)
        .ok_or_else(|| invalid_vector(format!("{filename}: expected three ECEF coordinates")))?;
    let expected: Vec<f64> = expected
        .iter()
        .map(|value| {
            value.as_f64().ok_or_else(|| {
                invalid_vector(format!("{filename}: ECEF coordinate is not numeric"))
            })
        })
        .collect::<Result<_, _>>()?;
    let actual_tuple = ecef_wgs84(latitude, longitude, height_m);
    let actual = [actual_tuple.0, actual_tuple.1, actual_tuple.2];
    for (axis, (actual_value, expected_value)) in actual.iter().zip(expected.iter()).enumerate() {
        if !actual_value.is_finite() || (*actual_value - *expected_value).abs() > tolerance {
            return Err(invalid_vector(format!(
                "{filename}: ECEF coordinate {axis} mismatch: actual={actual_value}, expected={expected_value}, tolerance={tolerance} m"
            ))
            .into());
        }
    }
    println!("PASS core/{filename} (tolerance {tolerance} m)");
    Ok(())
}

fn geometry_vector_files(vector_dir: &Path) -> Result<Vec<String>, Box<dyn Error>> {
    let mut files = Vec::new();
    for entry in std::fs::read_dir(vector_dir)? {
        let entry = entry?;
        if !entry.file_type()?.is_file() {
            continue;
        }
        let filename = entry.file_name();
        let Some(filename) = filename.to_str() else {
            continue;
        };
        if filename.starts_with("geometry_ecef") && filename.ends_with(".json") {
            files.push(filename.to_owned());
        }
    }
    files.sort();
    if files.is_empty() {
        return Err(invalid_vector("no geometry_ecef*.json reference vectors found").into());
    }
    Ok(files)
}

fn run() -> Result<(), Box<dyn Error>> {
    let root = repository_root();
    let vector_dir = root.join("data/contracts/golden-vectors/core");
    if !vector_dir.is_dir() {
        return Err(invalid_vector(format!(
            "golden vector directory not found: {}",
            vector_dir.display()
        ))
        .into());
    }
    let canonical_files = canonical_json_vector_files(&vector_dir)?;
    for filename in &canonical_files {
        check_canonical_json(&vector_dir, filename)?;
    }
    check_identity(&vector_dir)?;
    let geometry_files = geometry_vector_files(&vector_dir)?;
    for filename in &geometry_files {
        check_geometry(&vector_dir, filename)?;
    }
    let implemented_vectors = canonical_files.len() + 1 + geometry_files.len();
    println!(
        "PASS: {implemented_vectors}/{implemented_vectors} Rust-implemented core golden vectors conform (canonical JSON vectors, identity, WGS-84 geometry)"
    );
    println!("NOTE: contract_result.json, quantity.json and time.json remain pending Rust APIs");
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("FAIL: {error}");
        std::process::exit(1);
    }
}
