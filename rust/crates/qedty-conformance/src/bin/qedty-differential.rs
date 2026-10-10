//! Machine-readable JSONL runner for direct QEDTY Python/Rust differential tests.
//!
//! Each input line is one request: {"case_id":"...","operation":"...","input":{...}}.
//! Each output line is one response. Diagnostics are never written to stdout.

use qedty_core::contract_result::{ContractResult, ContractResultError};
use qedty_core::geometry::try_ecef_wgs84;
use qedty_core::quantity::{convert_value, QuantityError};
use qedty_core::temporal::{in_window, parse_rfc3339, to_rfc3339, TemporalError, TimeInterval};
use qedty_core::temporal_relations::{relation, AllenRelation};
use qedty_core::{canonical_json, deterministic_id, CoreError};
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};

fn str_field<'a>(value: &'a Value, name: &str) -> Result<&'a str, (String, String)> {
    value.get(name).and_then(Value::as_str).ok_or_else(|| {
        (
            "invalid_request".to_owned(),
            format!("missing string field `{name}`"),
        )
    })
}

fn number_field(value: &Value, name: &str) -> Result<f64, (String, String)> {
    let field = value.get(name).ok_or_else(|| {
        (
            "invalid_request".to_owned(),
            format!("missing numeric field `{name}`"),
        )
    })?;
    if let Some(number) = field.as_f64() {
        return Ok(number);
    }
    if let Some(text) = field.as_str() {
        return text.parse::<f64>().map_err(|_| {
            (
                "invalid_number".to_owned(),
                format!("field `{name}` is not a valid number"),
            )
        });
    }
    Err((
        "invalid_number".to_owned(),
        format!("field `{name}` is not numeric"),
    ))
}

fn input_object(request: &Value) -> Result<&Value, (String, String)> {
    request
        .get("input")
        .filter(|value| value.is_object())
        .ok_or_else(|| {
            (
                "invalid_request".to_owned(),
                "`input` must be a JSON object".to_owned(),
            )
        })
}

fn time_error(error: TemporalError) -> (String, String) {
    let category = match error {
        TemporalError::InvalidInterval => "invalid_interval",
        TemporalError::MissingTimezone
        | TemporalError::InvalidTimestamp
        | TemporalError::InvalidDate
        | TemporalError::InvalidTime
        | TemporalError::InvalidOffset
        | TemporalError::UtcOutOfRange => "invalid_timestamp",
    };
    (category.to_owned(), error.to_string())
}

fn quantity_error(error: QuantityError) -> (String, String) {
    let category = match &error {
        QuantityError::NonFiniteValue => "non_finite",
        QuantityError::IncompatibleUnits { .. } => "incompatible_units",
        QuantityError::UnknownUnit(_) => "unknown_unit",
        QuantityError::BlankUnit
        | QuantityError::InvalidExpression(_)
        | QuantityError::ExponentOutOfRange => "invalid_unit",
        QuantityError::AffineExpression | QuantityError::AffineArithmetic => {
            "invalid_unit_arithmetic"
        }
        QuantityError::DivisionByZero => "division_by_zero",
    };
    (category.to_owned(), error.to_string())
}

fn core_error(error: CoreError) -> (String, String) {
    let category = match &error {
        CoreError::EmptyIdentity => "invalid_identity",
        CoreError::InvalidDigestLength => "invalid_digest_length",
        CoreError::Json(_) => "invalid_input",
    };
    (category.to_owned(), error.to_string())
}

fn contract_error(error: ContractResultError) -> (String, String) {
    ("invalid_contract".to_owned(), error.to_string())
}

fn allen_name(value: AllenRelation) -> &'static str {
    match value {
        AllenRelation::Before => "before",
        AllenRelation::Meets => "meets",
        AllenRelation::Overlaps => "overlaps",
        AllenRelation::Starts => "starts",
        AllenRelation::During => "during",
        AllenRelation::Finishes => "finishes",
        AllenRelation::Equals => "equals",
        AllenRelation::FinishedBy => "finished_by",
        AllenRelation::Contains => "contains",
        AllenRelation::StartedBy => "started_by",
        AllenRelation::OverlappedBy => "overlapped_by",
        AllenRelation::MetBy => "met_by",
        AllenRelation::After => "after",
    }
}

fn execute(operation: &str, input: &Value) -> Result<Value, (String, String)> {
    match operation {
        "canonical_json" => {
            let value = input.get("value").ok_or_else(|| {
                (
                    "invalid_request".to_owned(),
                    "missing field `value`".to_owned(),
                )
            })?;
            canonical_json(value).map(Value::String).map_err(core_error)
        }
        "identity" => {
            let kind = str_field(input, "kind")?;
            let parts = input
                .get("parts")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_request".to_owned(),
                        "`parts` must be an array with namespace first".to_owned(),
                    )
                })?;
            let (namespace_value, tail) = parts.split_first().ok_or_else(|| {
                (
                    "invalid_identity".to_owned(),
                    "identity requires namespace as first part".to_owned(),
                )
            })?;
            let namespace = namespace_value.as_str().ok_or_else(|| {
                (
                    "invalid_identity".to_owned(),
                    "identity namespace (first part) must be a string".to_owned(),
                )
            })?;
            let length = input.get("length").and_then(Value::as_u64).ok_or_else(|| {
                (
                    "invalid_request".to_owned(),
                    "`length` must be a positive integer".to_owned(),
                )
            })? as usize;
            deterministic_id(kind, namespace, tail, length)
                .map(Value::String)
                .map_err(core_error)
        }
        "quantity.convert" => {
            let value = number_field(input, "value")?;
            let from_unit = str_field(input, "from_unit")?;
            let to_unit = str_field(input, "to_unit")?;
            let converted = convert_value(value, from_unit, to_unit).map_err(quantity_error)?;
            if !converted.is_finite() {
                return Err((
                    "non_finite".to_owned(),
                    "quantity result is not finite".to_owned(),
                ));
            }
            Ok(json!(converted))
        }
        "time.normalize" => {
            let timestamp = str_field(input, "timestamp")?;
            let instant = parse_rfc3339(timestamp).map_err(time_error)?;
            to_rfc3339(instant).map(Value::String).map_err(time_error)
        }
        "geometry.ecef" => {
            let latitude = number_field(input, "latitude_deg")?;
            let longitude = number_field(input, "longitude_deg")?;
            let height = number_field(input, "height_m")?;
            let point = try_ecef_wgs84(latitude, longitude, height)
                .map_err(|error| ("invalid_coordinate".to_owned(), error.to_string()))?;
            Ok(json!([point.x_m, point.y_m, point.z_m]))
        }
        "contract_result" => {
            let contract = input.get("contract").ok_or_else(|| {
                (
                    "invalid_request".to_owned(),
                    "missing field `contract`".to_owned(),
                )
            })?;
            let result = ContractResult::from_value(contract).map_err(contract_error)?;
            result
                .canonical_json()
                .map(Value::String)
                .map_err(contract_error)
        }
        "interval.contains" => {
            let instant = parse_rfc3339(str_field(input, "instant")?).map_err(time_error)?;
            let start = match input.get("start") {
                None | Some(Value::Null) => None,
                Some(Value::String(value)) => Some(parse_rfc3339(value).map_err(time_error)?),
                _ => {
                    return Err((
                        "invalid_timestamp".to_owned(),
                        "`start` must be a timestamp or null".to_owned(),
                    ));
                }
            };
            let end = match input.get("end") {
                None | Some(Value::Null) => None,
                Some(Value::String(value)) => Some(parse_rfc3339(value).map_err(time_error)?),
                _ => {
                    return Err((
                        "invalid_timestamp".to_owned(),
                        "`end` must be a timestamp or null".to_owned(),
                    ));
                }
            };
            in_window(instant, start, end)
                .map(Value::Bool)
                .map_err(time_error)
        }
        "temporal.relation" => {
            let left = input.get("left").ok_or_else(|| {
                (
                    "invalid_request".to_owned(),
                    "missing field `left`".to_owned(),
                )
            })?;
            let right = input.get("right").ok_or_else(|| {
                (
                    "invalid_request".to_owned(),
                    "missing field `right`".to_owned(),
                )
            })?;
            let left_start = parse_rfc3339(str_field(left, "start")?).map_err(time_error)?;
            let left_end = parse_rfc3339(str_field(left, "end")?).map_err(time_error)?;
            let right_start = parse_rfc3339(str_field(right, "start")?).map_err(time_error)?;
            let right_end = parse_rfc3339(str_field(right, "end")?).map_err(time_error)?;
            let left_interval = TimeInterval::new(left_start, left_end).map_err(time_error)?;
            let right_interval = TimeInterval::new(right_start, right_end).map_err(time_error)?;
            let relation = relation(left_interval, right_interval);
            Ok(Value::String(allen_name(relation).to_owned()))
        }
        other => Err((
            "unsupported_operation".to_owned(),
            format!("unsupported operation `{other}`"),
        )),
    }
}

fn handle_line(line: &str) -> Value {
    let request: Value = match serde_json::from_str(line) {
        Ok(value) => value,
        Err(error) => {
            return json!({
                "case_id": null,
                "ok": false,
                "error": {"category": "invalid_request", "message": error.to_string()}
            });
        }
    };
    let case_id = request.get("case_id").cloned().unwrap_or(Value::Null);
    let operation = match request.get("operation").and_then(Value::as_str) {
        Some(value) => value,
        None => {
            return json!({
                "case_id": case_id,
                "ok": false,
                "error": {
                    "category": "invalid_request",
                    "message": "missing string field `operation`"
                }
            });
        }
    };
    let input = match input_object(&request) {
        Ok(value) => value,
        Err((category, message)) => {
            return json!({
                "case_id": case_id,
                "ok": false,
                "error": {"category": category, "message": message}
            });
        }
    };
    match execute(operation, input) {
        Ok(result) => json!({"case_id": case_id, "ok": true, "result": result}),
        Err((category, message)) => json!({
            "case_id": case_id,
            "ok": false,
            "error": {"category": category, "message": message}
        }),
    }
}

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut out = io::BufWriter::new(stdout.lock());
    for line in stdin.lock().lines() {
        let response = match line {
            Ok(line) if line.trim().is_empty() => continue,
            Ok(line) => handle_line(&line),
            Err(error) => {
                eprintln!("failed to read differential request: {error}");
                std::process::exit(2);
            }
        };
        if serde_json::to_writer(&mut out, &response).is_err() || writeln!(&mut out).is_err() {
            eprintln!("failed to write differential response");
            std::process::exit(2);
        }
    }
    if out.flush().is_err() {
        eprintln!("failed to flush differential responses");
        std::process::exit(2);
    }
}
