//! Machine-readable JSONL runner for direct QEDTY Python/Rust differential tests.
//!
//! Each input line is one request: {"case_id":"...","operation":"...","input":{...}}.
//! Each output line is one response. Diagnostics are never written to stdout.

use qedty_core::contract_result::{ContractResult, ContractResultError};
use qedty_core::geometry::try_ecef_wgs84;
use qedty_core::graph::{DirectedGraph, GraphError};
use qedty_core::quantity::{convert_value, QuantityError};
use qedty_core::spatial::{haversine_m, GeoPoint, SpatialError, SpatialGridIndex};
use qedty_core::temporal::{
    in_window, parse_rfc3339, to_rfc3339, TemporalError, TimeInterval, UtcInstant,
};
use qedty_core::temporal_relations::{
    relation, AllenRelation, BitemporalExtent, OpenTimeExtent, PointTimeline, PointTimelineEntry,
    TemporalHistory, TemporalHistoryError, TemporalIndex, TemporalIndexEntry, TemporalIndexError,
    TemporalVersionRecord,
};
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

fn optional_time_field(value: &Value, name: &str) -> Result<Option<UtcInstant>, (String, String)> {
    match value.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) => parse_rfc3339(text).map(Some).map_err(time_error),
        _ => Err((
            "invalid_timestamp".to_owned(),
            format!("field `{name}` must be a timestamp string or null"),
        )),
    }
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

fn temporal_version_error(error: String) -> (String, String) {
    let category = if error.contains("version_id does not match canonical version identity") {
        "version_id_mismatch"
    } else if error.contains("start < end") || error.contains("invalid interval") {
        "invalid_interval"
    } else if error.contains("timestamp")
        || error.contains("timezone")
        || error.contains("date is invalid")
        || error.contains("time-of-day")
        || error.contains("offset")
    {
        "invalid_timestamp"
    } else {
        "invalid_input"
    };
    (category.to_owned(), error)
}

fn temporal_history_error(error: TemporalHistoryError) -> (String, String) {
    let category = match &error {
        TemporalHistoryError::Collision(_) => "version_collision",
        TemporalHistoryError::MissingVersion(_) => "missing_version",
    };
    (category.to_owned(), error.to_string())
}

fn version_optional_instant(
    value: &Value,
    name: &str,
) -> Result<Option<UtcInstant>, (String, String)> {
    match value.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(timestamp)) => parse_rfc3339(timestamp).map(Some).map_err(time_error),
        Some(_) => Err((
            "invalid_timestamp".to_owned(),
            format!("field {name} must be a timestamp or null"),
        )),
    }
}

fn temporal_version_extent(value: &Value) -> Result<OpenTimeExtent, (String, String)> {
    let object = value.as_object().ok_or_else(|| {
        (
            "invalid_input".to_owned(),
            "temporal version extent must be an object".to_owned(),
        )
    })?;
    if object
        .keys()
        .any(|key| !["start", "end", "start_inclusive", "end_inclusive"].contains(&key.as_str()))
    {
        return Err((
            "invalid_input".to_owned(),
            "temporal version extent has unknown fields".to_owned(),
        ));
    }
    let start_inclusive = match object.get("start_inclusive") {
        None => true,
        Some(Value::Bool(value)) => *value,
        Some(_) => {
            return Err((
                "invalid_input".to_owned(),
                "temporal extent inclusion flags must be booleans".to_owned(),
            ));
        }
    };
    let end_inclusive = match object.get("end_inclusive") {
        None => false,
        Some(Value::Bool(value)) => *value,
        Some(_) => {
            return Err((
                "invalid_input".to_owned(),
                "temporal extent inclusion flags must be booleans".to_owned(),
            ));
        }
    };
    if !start_inclusive || end_inclusive {
        return Err((
            "invalid_input".to_owned(),
            "QEDTY temporal extents use canonical [start, end) bounds".to_owned(),
        ));
    }
    OpenTimeExtent::new(
        version_optional_instant(value, "start")?,
        version_optional_instant(value, "end")?,
    )
    .map_err(time_error)
}

fn temporal_version_from_json(
    value: &Value,
    require_version_id: bool,
) -> Result<TemporalVersionRecord, (String, String)> {
    let object = value.as_object().ok_or_else(|| {
        (
            "invalid_input".to_owned(),
            "temporal version must be an object".to_owned(),
        )
    })?;
    let allowed = if require_version_id {
        vec![
            "version_id",
            "record_key",
            "value",
            "valid_time",
            "transaction_time",
            "supersedes",
            "metadata",
        ]
    } else {
        vec![
            "record_key",
            "value",
            "valid_time",
            "transaction_time",
            "supersedes",
            "metadata",
        ]
    };
    if object.keys().any(|key| !allowed.contains(&key.as_str())) {
        return Err((
            "invalid_input".to_owned(),
            "temporal version has unknown fields".to_owned(),
        ));
    }
    let record_key = required_string_field(value, "record_key")?;
    if record_key.is_empty() || record_key.chars().count() > 512 {
        return Err((
            "invalid_input".to_owned(),
            "record_key must contain between 1 and 512 characters".to_owned(),
        ));
    }
    let raw_value = value.get("value").ok_or_else(|| {
        (
            "invalid_input".to_owned(),
            "temporal version is missing value".to_owned(),
        )
    })?;
    let valid = temporal_version_extent(value.get("valid_time").ok_or_else(|| {
        (
            "invalid_input".to_owned(),
            "temporal version is missing valid_time".to_owned(),
        )
    })?)?;
    let transaction = temporal_version_extent(value.get("transaction_time").ok_or_else(|| {
        (
            "invalid_input".to_owned(),
            "temporal version is missing transaction_time".to_owned(),
        )
    })?)?;
    let supersedes = match object.get("supersedes") {
        None => Vec::new(),
        Some(Value::Array(values)) => values
            .iter()
            .map(|value| {
                value.as_str().map(str::to_owned).ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "supersedes must be an array of strings".to_owned(),
                    )
                })
            })
            .collect::<Result<Vec<_>, _>>()?,
        Some(_) => {
            return Err((
                "invalid_input".to_owned(),
                "supersedes must be an array of strings".to_owned(),
            ));
        }
    };
    let metadata = match object.get("metadata") {
        None => json!({}),
        Some(value) if value.is_object() => value.clone(),
        Some(_) => {
            return Err((
                "invalid_input".to_owned(),
                "metadata must be an object".to_owned(),
            ));
        }
    };
    let version = TemporalVersionRecord::create(
        record_key.to_owned(),
        raw_value.clone(),
        valid,
        transaction,
        supersedes,
        metadata,
    )
    .map_err(temporal_version_error)?;
    if require_version_id {
        let supplied_id = required_string_field(value, "version_id")?;
        if supplied_id.is_empty() || supplied_id.chars().count() > 256 {
            return Err((
                "invalid_input".to_owned(),
                "version_id must contain between 1 and 256 characters".to_owned(),
            ));
        }
        if supplied_id != version.version_id {
            return Err(temporal_version_error(
                "version_id does not match canonical version identity".to_owned(),
            ));
        }
    }
    Ok(version)
}

fn temporal_version_json(version: &TemporalVersionRecord) -> Result<Value, (String, String)> {
    version.to_json().map_err(temporal_version_error)
}

fn temporal_index_error(error: TemporalIndexError) -> (String, String) {
    let category = match &error {
        TemporalIndexError::Collision(_) => "temporal_index_collision",
        TemporalIndexError::MissingKey(_) => "missing_key",
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

fn graph_error(error: GraphError) -> (String, String) {
    ("invalid_input".to_owned(), error.to_string())
}

fn spatial_error(error: SpatialError) -> (String, String) {
    let category = match error {
        SpatialError::InvalidCoordinate => "invalid_coordinate",
        SpatialError::InvalidCellSize => "invalid_cell_size",
        SpatialError::BlankId => "invalid_input",
        SpatialError::InvalidRadius => "invalid_radius",
    };
    (category.to_owned(), error.to_string())
}

fn spatial_number_field(value: &Value, name: &str) -> Result<f64, (String, String)> {
    value.get(name).and_then(Value::as_f64).ok_or_else(|| {
        (
            "invalid_input".to_owned(),
            format!("field `{name}` must be a JSON number"),
        )
    })
}

fn spatial_point(value: &Value) -> Result<GeoPoint, (String, String)> {
    let latitude = spatial_number_field(value, "latitude")?;
    let longitude = spatial_number_field(value, "longitude")?;
    GeoPoint::new(latitude, longitude).map_err(spatial_error)
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

fn optional_instant_field(
    value: &Value,
    name: &str,
) -> Result<Option<qedty_core::temporal::UtcInstant>, (String, String)> {
    match value.get(name) {
        Some(Value::Null) => Ok(None),
        Some(Value::String(timestamp)) => parse_rfc3339(timestamp).map(Some).map_err(time_error),
        Some(_) => Err((
            "invalid_timestamp".to_owned(),
            format!("field `{name}` must be a timestamp or null"),
        )),
        None => Err((
            "invalid_input".to_owned(),
            format!("missing field `{name}`"),
        )),
    }
}

fn required_string_field<'a>(value: &'a Value, name: &str) -> Result<&'a str, (String, String)> {
    match value.get(name) {
        Some(Value::String(text)) => Ok(text),
        None => Err((
            "invalid_input".to_owned(),
            format!("missing string field `{name}`"),
        )),
        Some(_) => Err((
            "invalid_input".to_owned(),
            format!("field `{name}` must be a string"),
        )),
    }
}

fn timestamp_field(
    value: &Value,
    name: &str,
) -> Result<qedty_core::temporal::UtcInstant, (String, String)> {
    parse_rfc3339(required_string_field(value, name)?).map_err(time_error)
}

fn open_extent(value: &Value) -> Result<OpenTimeExtent, (String, String)> {
    if !value.is_object() {
        return Err((
            "invalid_input".to_owned(),
            "temporal extent must be an object".to_owned(),
        ));
    }
    OpenTimeExtent::new(
        optional_instant_field(value, "start")?,
        optional_instant_field(value, "end")?,
    )
    .map_err(time_error)
}

fn temporal_index_entry_json(
    entry: &TemporalIndexEntry<String>,
) -> Result<Value, (String, String)> {
    let start = match entry.extent.start {
        Some(instant) => Value::String(to_rfc3339(instant).map_err(time_error)?),
        None => Value::Null,
    };
    let end = match entry.extent.end {
        Some(instant) => Value::String(to_rfc3339(instant).map_err(time_error)?),
        None => Value::Null,
    };
    Ok(json!({
        "key": entry.key,
        "extent": {"start": start, "end": end},
        "value": entry.value,
    }))
}

fn point_json(entry: &PointTimelineEntry<String>) -> Result<Value, (String, String)> {
    let at = to_rfc3339(entry.at).map_err(time_error)?;
    Ok(json!({
        "at": at,
        "value": entry.value,
        "sequence": entry.sequence,
    }))
}

fn point_array(
    entries: impl Iterator<Item = PointTimelineEntry<String>>,
) -> Result<Value, (String, String)> {
    entries
        .map(|entry| point_json(&entry))
        .collect::<Result<Vec<_>, _>>()
        .map(Value::Array)
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
        "spatial.distance.haversine" => {
            let first = spatial_point(input.get("first").ok_or_else(|| {
                (
                    "invalid_input".to_owned(),
                    "first point is required".to_owned(),
                )
            })?)?;
            let second = spatial_point(input.get("second").ok_or_else(|| {
                (
                    "invalid_input".to_owned(),
                    "second point is required".to_owned(),
                )
            })?)?;
            Ok(json!(haversine_m(first, second)))
        }
        "spatial.radius.query" => {
            let center = spatial_point(input.get("center").ok_or_else(|| {
                (
                    "invalid_input".to_owned(),
                    "center point is required".to_owned(),
                )
            })?)?;
            let radius_m = spatial_number_field(input, "radius_m")?;
            if !radius_m.is_finite() || radius_m < 0.0 {
                return Err(spatial_error(SpatialError::InvalidRadius));
            }
            let cell_degrees = match input.get("cell_degrees") {
                Some(_) => spatial_number_field(input, "cell_degrees")?,
                None => 1.0,
            };
            let mut index = SpatialGridIndex::new(cell_degrees).map_err(spatial_error)?;
            let points = input
                .get("points")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "points must be an array".to_owned(),
                    )
                })?;
            for item in points {
                let id = item.get("id").and_then(Value::as_str).ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "point id must be a string".to_owned(),
                    )
                })?;
                let point = spatial_point(item)?;
                index.insert(id, point).map_err(spatial_error)?;
            }
            let matches = index
                .query_radius(center, radius_m)
                .map_err(spatial_error)?;
            Ok(json!(matches
                .into_iter()
                .map(|(id, _distance_m)| id)
                .collect::<Vec<_>>()))
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
        "bitemporal.contains" => {
            let valid_at = parse_rfc3339(str_field(input, "valid_at")?).map_err(time_error)?;
            let transaction_at =
                parse_rfc3339(str_field(input, "transaction_at")?).map_err(time_error)?;
            let valid_start = optional_time_field(input, "valid_start")?;
            let valid_end = optional_time_field(input, "valid_end")?;
            let transaction_start = optional_time_field(input, "transaction_start")?;
            let transaction_end = optional_time_field(input, "transaction_end")?;
            let valid_contains = in_window(valid_at, valid_start, valid_end).map_err(time_error)?;
            let transaction_contains =
                in_window(transaction_at, transaction_start, transaction_end)
                    .map_err(time_error)?;
            Ok(Value::Bool(valid_contains && transaction_contains))
        }
        "temporal.bitemporal.contains" => {
            let valid_time = open_extent(input.get("valid_time").ok_or_else(|| {
                (
                    "invalid_input".to_owned(),
                    "missing field `valid_time`".to_owned(),
                )
            })?)?;
            let transaction_time =
                open_extent(input.get("transaction_time").ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "missing field `transaction_time`".to_owned(),
                    )
                })?)?;
            let valid_at = timestamp_field(input, "valid_at")?;
            let transaction_at = timestamp_field(input, "transaction_at")?;
            let extent = BitemporalExtent::new(
                valid_time.start,
                valid_time.end,
                transaction_time.start,
                transaction_time.end,
            )
            .map_err(time_error)?;
            Ok(Value::Bool(extent.contains(valid_at, transaction_at)))
        }
        "temporal.timeline.query" => {
            let points = input
                .get("points")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "`points` must be an array".to_owned(),
                    )
                })?;
            let mut timeline = PointTimeline::new();
            for (index, point) in points.iter().enumerate() {
                if !point.is_object() {
                    return Err((
                        "invalid_input".to_owned(),
                        "each timeline point must be an object".to_owned(),
                    ));
                }
                let at = timestamp_field(point, "at")?;
                let value = required_string_field(point, "value")?.to_owned();
                let sequence = match point.get("sequence") {
                    None | Some(Value::Null) => i64::try_from(index).map_err(|_| {
                        (
                            "invalid_input".to_owned(),
                            "too many timeline points".to_owned(),
                        )
                    })?,
                    Some(Value::Number(number)) => number.as_i64().ok_or_else(|| {
                        (
                            "invalid_input".to_owned(),
                            "sequence must be an integer".to_owned(),
                        )
                    })?,
                    Some(_) => {
                        return Err((
                            "invalid_input".to_owned(),
                            "sequence must be an integer or null".to_owned(),
                        ));
                    }
                };
                timeline.put(at, value, sequence);
            }

            let mode = required_string_field(input, "mode")?;
            match mode {
                "at_or_before" => {
                    let at = timestamp_field(input, "at")?;
                    Ok(timeline
                        .at_or_before(at)
                        .map_or(Value::Null, |point| json!(point.value)))
                }
                "at_or_after" => {
                    let at = parse_rfc3339(str_field(input, "at")?).map_err(time_error)?;
                    Ok(timeline
                        .at_or_after(at)
                        .map_or(Value::Null, |point| json!(point.value)))
                }
                "between" => {
                    let start = timestamp_field(input, "start")?;
                    let end = timestamp_field(input, "end")?;
                    if end < start {
                        return Err((
                            "invalid_interval".to_owned(),
                            "end must not precede start".to_owned(),
                        ));
                    }
                    let include_end = match input.get("include_end") {
                        None => false,
                        Some(Value::Bool(value)) => *value,
                        Some(_) => {
                            return Err((
                                "invalid_input".to_owned(),
                                "`include_end` must be a boolean".to_owned(),
                            ));
                        }
                    };
                    let entries = timeline
                        .between(start, end, include_end)
                        .cloned()
                        .collect::<Vec<_>>();
                    point_array(entries.into_iter())
                }
                "latest" => match timeline.latest() {
                    Some(point) => point_json(point),
                    None => Ok(Value::Null),
                },
                "ordered" => timeline
                    .entries()
                    .iter()
                    .map(point_json)
                    .collect::<Result<Vec<_>, _>>()
                    .map(Value::Array),
                "values" => Ok(json!(timeline.values().cloned().collect::<Vec<_>>())),
                _ => Err((
                    "invalid_input".to_owned(),
                    format!("unsupported timeline query mode `{mode}`"),
                )),
            }
        }
        "temporal.history.query" => {
            let mode = required_string_field(input, "mode")?;
            if mode == "create" {
                let raw_version = input.get("version").ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "temporal history create requires a version object".to_owned(),
                    )
                })?;
                return temporal_version_json(&temporal_version_from_json(raw_version, false)?);
            }

            let raw_versions = input
                .get("versions")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "temporal history versions must be an array".to_owned(),
                    )
                })?;
            let mut history = TemporalHistory::new();
            for raw_version in raw_versions {
                history
                    .add(temporal_version_from_json(raw_version, true)?)
                    .map_err(temporal_history_error)?;
            }

            match mode {
                "all" => history
                    .all()
                    .iter()
                    .map(temporal_version_json)
                    .collect::<Result<Vec<_>, _>>()
                    .map(Value::Array),
                "get" => {
                    let version_id = required_string_field(input, "version_id")?;
                    temporal_version_json(
                        history.get(version_id).map_err(temporal_history_error)?,
                    )
                }
                "as_of" => {
                    let valid_at = timestamp_field(input, "valid_at")?;
                    let transaction_at = timestamp_field(input, "transaction_at")?;
                    history
                        .as_of(valid_at, transaction_at)
                        .iter()
                        .map(temporal_version_json)
                        .collect::<Result<Vec<_>, _>>()
                        .map(Value::Array)
                }
                "latest_known" => {
                    let record_key = required_string_field(input, "record_key")?;
                    let transaction_at = timestamp_field(input, "transaction_at")?;
                    match history.latest_known(record_key, transaction_at) {
                        Some(version) => temporal_version_json(&version),
                        None => Ok(Value::Null),
                    }
                }
                "add" => {
                    let raw_version = input.get("new_version").ok_or_else(|| {
                        (
                            "invalid_input".to_owned(),
                            "temporal history add requires new_version".to_owned(),
                        )
                    })?;
                    history
                        .add(temporal_version_from_json(raw_version, true)?)
                        .map_err(temporal_history_error)?;
                    history
                        .all()
                        .iter()
                        .map(temporal_version_json)
                        .collect::<Result<Vec<_>, _>>()
                        .map(Value::Array)
                }
                _ => Err((
                    "invalid_input".to_owned(),
                    format!("unsupported temporal history mode {mode}"),
                )),
            }
        }
        "temporal.index.query" => {
            let raw_entries = input
                .get("entries")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "entries must be an array".to_owned(),
                    )
                })?;
            let mut index = TemporalIndex::new();
            for entry in raw_entries {
                if !entry.is_object() {
                    return Err((
                        "invalid_input".to_owned(),
                        "each temporal index entry must be an object".to_owned(),
                    ));
                }
                let key = required_string_field(entry, "key")?.to_owned();
                let extent_value = entry.get("extent").ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "temporal index entry is missing extent".to_owned(),
                    )
                })?;
                let extent = open_extent(extent_value)?;
                let value = required_string_field(entry, "value")?.to_owned();
                index
                    .add(key, extent, value)
                    .map_err(temporal_index_error)?;
            }

            let mode = required_string_field(input, "mode")?;
            match mode {
                "at" => {
                    let instant = timestamp_field(input, "instant")?;
                    Ok(json!(index.at(instant)))
                }
                "overlapping" => {
                    let query_value = input.get("query").ok_or_else(|| {
                        (
                            "invalid_input".to_owned(),
                            "missing query extent".to_owned(),
                        )
                    })?;
                    let query = open_extent(query_value)?;
                    Ok(json!(index.overlapping(query)))
                }
                "all" => index
                    .all()
                    .iter()
                    .map(temporal_index_entry_json)
                    .collect::<Result<Vec<_>, _>>()
                    .map(Value::Array),
                "get" => {
                    let key = required_string_field(input, "key")?;
                    temporal_index_entry_json(index.get(key).map_err(temporal_index_error)?)
                }
                "remove" => {
                    let key = required_string_field(input, "key")?;
                    let entry = index.remove(key).map_err(temporal_index_error)?;
                    temporal_index_entry_json(&entry)
                }
                "len" => Ok(json!(index.len())),
                "clear" => {
                    index.clear();
                    Ok(json!(index.len()))
                }
                "add" => {
                    let raw = input.get("new_entry").ok_or_else(|| {
                        ("invalid_input".to_owned(), "missing new_entry".to_owned())
                    })?;
                    if !raw.is_object() {
                        return Err((
                            "invalid_input".to_owned(),
                            "new_entry must be an object".to_owned(),
                        ));
                    }
                    let key = required_string_field(raw, "key")?.to_owned();
                    let extent_value = raw.get("extent").ok_or_else(|| {
                        (
                            "invalid_input".to_owned(),
                            "new_entry is missing extent".to_owned(),
                        )
                    })?;
                    let extent = open_extent(extent_value)?;
                    let value = required_string_field(raw, "value")?.to_owned();
                    index
                        .add(key, extent, value)
                        .map_err(temporal_index_error)?;
                    Ok(json!(index.len()))
                }
                _ => Err((
                    "invalid_input".to_owned(),
                    format!("unsupported temporal index mode `{mode}`"),
                )),
            }
        }
        "graph.static.bfs" => {
            let mut graph = DirectedGraph::new();
            let nodes = input
                .get("nodes")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "`nodes` must be an array".to_owned(),
                    )
                })?;
            for node in nodes {
                let label = node.as_str().ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "node labels must be strings".to_owned(),
                    )
                })?;
                graph.add_node(label).map_err(graph_error)?;
            }
            let edges = input
                .get("edges")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "`edges` must be an array".to_owned(),
                    )
                })?;
            for edge in edges {
                let pair = edge
                    .as_array()
                    .filter(|pair| pair.len() == 2)
                    .ok_or_else(|| {
                        (
                            "invalid_input".to_owned(),
                            "each edge must be a two-item array".to_owned(),
                        )
                    })?;
                let from = pair[0].as_str().ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "edge source label must be a string".to_owned(),
                    )
                })?;
                let to = pair[1].as_str().ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "edge target label must be a string".to_owned(),
                    )
                })?;
                graph
                    .add_edge(from, to, 1.0, 1.0, 0.0)
                    .map_err(graph_error)?;
            }
            let source = input.get("source").and_then(Value::as_str).ok_or_else(|| {
                (
                    "invalid_input".to_owned(),
                    "source label must be a string".to_owned(),
                )
            })?;
            graph
                .breadth_first(source)
                .map(|labels| json!(labels))
                .map_err(graph_error)
        }
        "graph.static.scc" => {
            let mut graph = DirectedGraph::new();
            let nodes = input
                .get("nodes")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "nodes must be an array".to_owned(),
                    )
                })?;
            for node in nodes {
                let label = node.as_str().ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "node labels must be strings".to_owned(),
                    )
                })?;
                graph.add_node(label).map_err(graph_error)?;
            }
            let edges = input
                .get("edges")
                .and_then(Value::as_array)
                .ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "edges must be an array".to_owned(),
                    )
                })?;
            for edge in edges {
                let pair = edge
                    .as_array()
                    .filter(|pair| pair.len() == 2)
                    .ok_or_else(|| {
                        (
                            "invalid_input".to_owned(),
                            "each edge must be a two-item array".to_owned(),
                        )
                    })?;
                let from = pair[0].as_str().ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "edge source label must be a string".to_owned(),
                    )
                })?;
                let to = pair[1].as_str().ok_or_else(|| {
                    (
                        "invalid_input".to_owned(),
                        "edge target label must be a string".to_owned(),
                    )
                })?;
                graph
                    .add_edge(from, to, 1.0, 1.0, 0.0)
                    .map_err(graph_error)?;
            }
            Ok(json!(graph.strongly_connected_components()))
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
