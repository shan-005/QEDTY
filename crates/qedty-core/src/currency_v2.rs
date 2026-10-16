//! Currency-neutral conversion v2 with explicit metadata and FX snapshots.
//!
//! No network access, currency allowlist, implicit triangulation, or binary-float
//! money arithmetic is permitted in this module.

use crate::decimal_v2::{DecimalV2, DecimalV2Error, DECIMAL_V2_PRECISION};
use crate::temporal::{parse_rfc3339, to_rfc3339, UtcInstant};
use serde_json::{json, Map, Value};
use std::cmp::Ordering;
use std::collections::BTreeSet;

type ContractError = (String, String);

#[derive(Debug, Clone)]
struct MoneyAmount {
    amount: DecimalV2,
    amount_text: String,
    currency_code: String,
    metadata_profile_version: String,
}

#[derive(Debug, Clone)]
struct CurrencyMetadata {
    currency_code: String,
    minor_unit_scale: u32,
    rounding_mode: String,
}

#[derive(Debug, Clone)]
struct CurrencyProfile {
    profile_version: String,
    currencies: Vec<CurrencyMetadata>,
}

#[derive(Debug, Clone)]
struct FxRate {
    base_currency: String,
    quote_currency: String,
    rate: DecimalV2,
    observed_at_text: String,
    source: String,
    provenance_id: String,
}

#[derive(Debug, Clone)]
struct FxSnapshot {
    snapshot_id: String,
    as_of_text: String,
    valid_from: UtcInstant,
    valid_from_text: String,
    valid_to: UtcInstant,
    valid_to_text: String,
    rates: Vec<FxRate>,
}

fn fail(category: &str, message: impl Into<String>) -> ContractError {
    (category.to_owned(), message.into())
}

fn object_field<'a>(value: &'a Value, name: &str) -> Result<&'a Value, ContractError> {
    value
        .get(name)
        .filter(|field| field.is_object())
        .ok_or_else(|| fail("invalid_input", format!("field `{name}` must be an object")))
}

fn string_field<'a>(value: &'a Value, name: &str) -> Result<&'a str, ContractError> {
    value
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| fail("invalid_input", format!("field `{name}` must be a string")))
}

fn optional_string<'a>(value: &'a Value, name: &str) -> Result<Option<&'a str>, ContractError> {
    match value.get(name) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(text)) => Ok(Some(text)),
        _ => Err(fail(
            "invalid_input",
            format!("field `{name}` must be a string or null"),
        )),
    }
}

fn required_text(value: &str, field: &str) -> Result<(), ContractError> {
    if value.trim().is_empty() {
        return Err(fail("invalid_input", format!("{field} must be non-empty")));
    }
    Ok(())
}

fn validate_currency_code(value: &str, field: &str) -> Result<(), ContractError> {
    if value.len() != 3 || !value.bytes().all(|byte| byte.is_ascii_uppercase()) {
        return Err(fail(
            "invalid_currency",
            format!("{field} must be a three-letter uppercase currency code"),
        ));
    }
    Ok(())
}

fn decimal_field(value: &Value, name: &str) -> Result<DecimalV2, ContractError> {
    let text = string_field(value, name)?;
    DecimalV2::parse(text).map_err(decimal_error)
}

fn decimal_error(error: DecimalV2Error) -> ContractError {
    let message = error.to_string();
    let category = if message == "division by zero" {
        "division_by_zero"
    } else {
        "invalid_number"
    };
    fail(category, message)
}

fn normalize_time(value: &str, field: &str) -> Result<(UtcInstant, String), ContractError> {
    let instant =
        parse_rfc3339(value).map_err(|error| fail("invalid_timestamp", error.to_string()))?;
    let fixed =
        to_rfc3339(instant).map_err(|error| fail("invalid_timestamp", error.to_string()))?;
    let normalized = if instant.microseconds() == 0 {
        fixed.replace(".000000Z", "Z")
    } else {
        fixed
    };
    if normalized.is_empty() {
        return Err(fail("invalid_timestamp", format!("{field} is invalid")));
    }
    Ok((instant, normalized))
}

fn parse_money_amount(value: &Value) -> Result<MoneyAmount, ContractError> {
    let amount_text = string_field(value, "amount")?.to_owned();
    let amount = DecimalV2::parse(&amount_text).map_err(decimal_error)?;
    if amount.is_negative() {
        return Err(fail("invalid_money", "money amount must be non-negative"));
    }
    let currency_code = string_field(value, "currency_code")?.to_owned();
    validate_currency_code(&currency_code, "currency_code")?;
    let metadata_profile_version = string_field(value, "metadata_profile_version")?.to_owned();
    required_text(&metadata_profile_version, "metadata_profile_version")?;
    Ok(MoneyAmount {
        amount,
        amount_text,
        currency_code,
        metadata_profile_version,
    })
}

fn parse_currency_profile(value: &Value) -> Result<CurrencyProfile, ContractError> {
    let profile_version = string_field(value, "profile_version")?.to_owned();
    required_text(&profile_version, "profile_version")?;
    let raw_currencies = value
        .get("currencies")
        .and_then(Value::as_array)
        .ok_or_else(|| fail("invalid_currency_profile", "currencies must be an array"))?;
    if raw_currencies.is_empty() {
        return Err(fail(
            "invalid_currency_profile",
            "currency metadata profile must contain at least one currency",
        ));
    }
    let mut seen = BTreeSet::new();
    let mut currencies = Vec::with_capacity(raw_currencies.len());
    for raw in raw_currencies {
        let code = string_field(raw, "currency_code")?.to_owned();
        validate_currency_code(&code, "currency_code")?;
        if !seen.insert(code.clone()) {
            return Err(fail(
                "invalid_currency_profile",
                "currency metadata profile contains duplicate currency codes",
            ));
        }
        let scale = raw
            .get("minor_unit_scale")
            .and_then(Value::as_u64)
            .ok_or_else(|| {
                fail(
                    "invalid_currency_profile",
                    "minor_unit_scale must be an integer",
                )
            })?;
        if scale > 9 {
            return Err(fail(
                "invalid_currency_profile",
                "minor_unit_scale must be between 0 and 9",
            ));
        }
        let rounding_mode = string_field(raw, "rounding_mode")?.to_owned();
        if ![
            "ROUND_05UP",
            "ROUND_CEILING",
            "ROUND_DOWN",
            "ROUND_FLOOR",
            "ROUND_HALF_DOWN",
            "ROUND_HALF_EVEN",
            "ROUND_HALF_UP",
            "ROUND_UP",
        ]
        .contains(&rounding_mode.as_str())
        {
            return Err(fail(
                "invalid_currency_profile",
                "unsupported rounding mode",
            ));
        }
        currencies.push(CurrencyMetadata {
            currency_code: code,
            minor_unit_scale: scale as u32,
            rounding_mode,
        });
    }
    currencies.sort_by(|a, b| a.currency_code.cmp(&b.currency_code));
    Ok(CurrencyProfile {
        profile_version,
        currencies,
    })
}

impl CurrencyProfile {
    fn metadata_for(&self, code: &str) -> Result<&CurrencyMetadata, ContractError> {
        validate_currency_code(code, "currency_code")?;
        self.currencies
            .iter()
            .find(|metadata| metadata.currency_code == code)
            .ok_or_else(|| {
                fail(
                    "invalid_currency",
                    format!(
                        "currency {code:?} is absent from metadata profile {:?}",
                        self.profile_version
                    ),
                )
            })
    }

    fn validate_amount(&self, amount: &MoneyAmount) -> Result<&CurrencyMetadata, ContractError> {
        if amount.metadata_profile_version != self.profile_version {
            return Err(fail(
                "metadata_profile_mismatch",
                "money amount metadata profile version does not match supplied profile",
            ));
        }
        let metadata = self.metadata_for(&amount.currency_code)?;
        let rounded = amount
            .amount
            .quantize(metadata.minor_unit_scale, &metadata.rounding_mode)
            .map_err(decimal_error)?;
        if rounded.compare(&amount.amount) != Ordering::Equal {
            return Err(fail(
                "invalid_money_precision",
                format!(
                    "amount for {} exceeds its declared minor-unit scale",
                    amount.currency_code
                ),
            ));
        }
        Ok(metadata)
    }

    fn money_json(&self, amount: &MoneyAmount) -> Value {
        json!({
            "amount": amount.amount_text,
            "currency_code": amount.currency_code,
            "metadata_profile_version": amount.metadata_profile_version
        })
    }
}

fn parse_fx_snapshot(value: &Value) -> Result<FxSnapshot, ContractError> {
    let snapshot_id = string_field(value, "snapshot_id")?.to_owned();
    required_text(&snapshot_id, "snapshot_id")?;
    let (as_of, as_of_text) = normalize_time(string_field(value, "as_of")?, "as_of")?;
    let (valid_from, valid_from_text) =
        normalize_time(string_field(value, "valid_from")?, "valid_from")?;
    let (valid_to, valid_to_text) = normalize_time(string_field(value, "valid_to")?, "valid_to")?;
    if valid_from >= valid_to {
        return Err(fail(
            "invalid_interval",
            "FX snapshot valid_from must be before valid_to",
        ));
    }
    if !(valid_from <= as_of && as_of < valid_to) {
        return Err(fail(
            "invalid_interval",
            "FX snapshot as_of must lie inside [valid_from, valid_to)",
        ));
    }
    let raw_rates = value
        .get("rates")
        .and_then(Value::as_array)
        .ok_or_else(|| fail("invalid_fx_snapshot", "rates must be an array"))?;
    if raw_rates.is_empty() {
        return Err(fail(
            "invalid_fx_snapshot",
            "FX snapshot must contain at least one rate",
        ));
    }
    let mut seen = BTreeSet::new();
    let mut rates = Vec::with_capacity(raw_rates.len());
    for raw in raw_rates {
        let base_currency = string_field(raw, "base_currency")?.to_owned();
        let quote_currency = string_field(raw, "quote_currency")?.to_owned();
        validate_currency_code(&base_currency, "base_currency")?;
        validate_currency_code(&quote_currency, "quote_currency")?;
        if base_currency == quote_currency {
            return Err(fail(
                "invalid_fx_rate",
                "FX base and quote currencies must differ",
            ));
        }
        let rate = decimal_field(raw, "rate")?;
        if rate.is_zero() || rate.is_negative() {
            return Err(fail(
                "invalid_fx_rate",
                "FX rate must be a finite positive Decimal",
            ));
        }
        let (observed_at, observed_at_text) =
            normalize_time(string_field(raw, "observed_at")?, "observed_at")?;
        if observed_at > as_of {
            return Err(fail(
                "invalid_fx_snapshot",
                "FX rate observation must not be later than snapshot as_of",
            ));
        }
        let source = string_field(raw, "source")?.to_owned();
        let provenance_id = string_field(raw, "provenance_id")?.to_owned();
        required_text(&source, "source")?;
        required_text(&provenance_id, "provenance_id")?;
        let pair = if base_currency < quote_currency {
            (base_currency.clone(), quote_currency.clone())
        } else {
            (quote_currency.clone(), base_currency.clone())
        };
        if !seen.insert(pair) {
            return Err(fail(
                "invalid_fx_snapshot",
                "FX snapshot may contain only one directional quote per unordered currency pair",
            ));
        }
        rates.push(FxRate {
            base_currency,
            quote_currency,
            rate,
            observed_at_text,
            source,
            provenance_id,
        });
    }
    rates.sort_by(|a, b| {
        (&a.base_currency, &a.quote_currency).cmp(&(&b.base_currency, &b.quote_currency))
    });
    Ok(FxSnapshot {
        snapshot_id,
        as_of_text,
        valid_from,
        valid_from_text,
        valid_to,
        valid_to_text,
        rates,
    })
}

impl FxSnapshot {
    fn json(&self) -> Value {
        json!({
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of_text,
            "valid_from": self.valid_from_text,
            "valid_to": self.valid_to_text,
            "rates": self.rates.iter().map(|rate| json!({
                "base_currency": rate.base_currency,
                "quote_currency": rate.quote_currency,
                "rate": rate.rate.format_canonical(),
                "observed_at": rate.observed_at_text,
                "source": rate.source,
                "provenance_id": rate.provenance_id
            })).collect::<Vec<_>>()
        })
    }

    fn rate_for(
        &self,
        source_currency: &str,
        target_currency: &str,
    ) -> Result<(DecimalV2, &FxRate, bool), ContractError> {
        for rate in &self.rates {
            if rate.base_currency == source_currency && rate.quote_currency == target_currency {
                return Ok((rate.rate.clone(), rate, false));
            }
            if rate.base_currency == target_currency && rate.quote_currency == source_currency {
                let reciprocal = DecimalV2::one()
                    .divide(&rate.rate, DECIMAL_V2_PRECISION)
                    .map_err(decimal_error)?;
                if reciprocal.is_zero() {
                    return Err(fail(
                        "invalid_fx_rate",
                        "reciprocal FX rate underflowed supported precision",
                    ));
                }
                return Ok((reciprocal, rate, true));
            }
        }
        Err(fail(
            "missing_fx_rate",
            format!(
                "missing direct or reciprocal FX quote for {source_currency}/{target_currency}; triangulation is disabled"
            ),
        ))
    }

    fn require_valid_at(&self, instant: UtcInstant) -> Result<(), ContractError> {
        if self.valid_from <= instant && instant < self.valid_to {
            Ok(())
        } else {
            Err(fail(
                "invalid_interval",
                "FX snapshot is not valid at the requested instant",
            ))
        }
    }
}

struct MoneyConversionAudit<'a> {
    source: &'a MoneyAmount,
    target: &'a MoneyAmount,
    applied_rate: &'a DecimalV2,
    unrounded_target_amount: &'a DecimalV2,
    rounding_mode: &'a str,
    profile: &'a CurrencyProfile,
    snapshot: Option<&'a FxSnapshot>,
    source_rate: Option<&'a FxRate>,
    rate_was_inverted: bool,
    effective_at: Option<String>,
}

fn money_conversion_json(audit: MoneyConversionAudit<'_>) -> Value {
    let MoneyConversionAudit {
        source,
        target,
        applied_rate,
        unrounded_target_amount,
        rounding_mode,
        profile,
        snapshot,
        source_rate,
        rate_was_inverted,
        effective_at,
    } = audit;
    json!({
        "source": profile.money_json(source),
        "target": profile.money_json(target),
        "applied_rate": applied_rate.format_canonical(),
        "unrounded_target_amount": unrounded_target_amount.format_canonical(),
        "rounding_mode": rounding_mode,
        "metadata_profile_version": profile.profile_version,
        "fx_snapshot_id": snapshot.map(|value| value.snapshot_id.clone()),
        "rate_base_currency": source_rate.map(|value| value.base_currency.clone()),
        "rate_quote_currency": source_rate.map(|value| value.quote_currency.clone()),
        "rate_was_inverted": rate_was_inverted,
        "fx_source": source_rate.map(|value| value.source.clone()),
        "fx_provenance_id": source_rate.map(|value| value.provenance_id.clone()),
        "effective_at": effective_at,
        "fx_snapshot_as_of": snapshot.map(|value| value.as_of_text.clone()),
        "calculation_precision": DECIMAL_V2_PRECISION
    })
}

/// Evaluate the v2 currency conversion request. All monetary values are strings.
pub fn convert_money_v2(request: &Value) -> Result<Value, ContractError> {
    let source = parse_money_amount(object_field(request, "source")?)?;
    let target_currency = string_field(request, "target_currency_code")?.to_owned();
    validate_currency_code(&target_currency, "target_currency_code")?;
    let profile = parse_currency_profile(object_field(request, "currency_profile")?)?;
    profile.validate_amount(&source)?;
    let target_metadata = profile.metadata_for(&target_currency)?;
    let snapshot = match request.get("fx_snapshot") {
        None | Some(Value::Null) => None,
        Some(value) if value.is_object() => Some(parse_fx_snapshot(value)?),
        Some(_) => {
            return Err(fail(
                "invalid_fx_snapshot",
                "fx_snapshot must be an object or null",
            ))
        }
    };

    if source.currency_code == target_currency {
        let target_amount = source
            .amount
            .quantize(
                target_metadata.minor_unit_scale,
                &target_metadata.rounding_mode,
            )
            .map_err(decimal_error)?;
        let target = MoneyAmount {
            amount_text: target_amount.format_fixed(),
            amount: target_amount.clone(),
            currency_code: target_currency,
            metadata_profile_version: profile.profile_version.clone(),
        };
        let unit_rate = DecimalV2::one();
        let conversion = money_conversion_json(MoneyConversionAudit {
            source: &source,
            target: &target,
            applied_rate: &unit_rate,
            unrounded_target_amount: &source.amount,
            rounding_mode: &target_metadata.rounding_mode,
            profile: &profile,
            snapshot: None,
            source_rate: None,
            rate_was_inverted: false,
            effective_at: None,
        });
        return Ok(conversion);
    }

    let snapshot = snapshot.ok_or_else(|| {
        fail(
            "missing_fx_snapshot",
            "cross-currency conversion requires an explicit FX snapshot",
        )
    })?;
    let effective_at = match optional_string(request, "effective_at")? {
        Some(text) => {
            let (instant, normalized) = normalize_time(text, "effective_at")?;
            snapshot.require_valid_at(instant)?;
            normalized
        }
        None => snapshot.as_of_text.clone(),
    };
    let instant = parse_rfc3339(&effective_at)
        .map_err(|error| fail("invalid_timestamp", error.to_string()))?;
    snapshot.require_valid_at(instant)?;
    let (applied_rate, source_rate, inverted) =
        snapshot.rate_for(&source.currency_code, &target_currency)?;
    let unrounded = source.amount.multiply(&applied_rate);
    let target_amount = unrounded
        .quantize(
            target_metadata.minor_unit_scale,
            &target_metadata.rounding_mode,
        )
        .map_err(decimal_error)?;
    let target = MoneyAmount {
        amount_text: target_amount.format_fixed(),
        amount: target_amount,
        currency_code: target_currency,
        metadata_profile_version: profile.profile_version.clone(),
    };
    Ok(money_conversion_json(MoneyConversionAudit {
        source: &source,
        target: &target,
        applied_rate: &applied_rate,
        unrounded_target_amount: &unrounded,
        rounding_mode: &target_metadata.rounding_mode,
        profile: &profile,
        snapshot: Some(&snapshot),
        source_rate: Some(source_rate),
        rate_was_inverted: inverted,
        effective_at: Some(effective_at),
    }))
}

/// Canonical request data used by cross-language fixtures and audit digests.
pub fn canonicalize_currency_request(request: &Value) -> Result<Value, ContractError> {
    let source = parse_money_amount(object_field(request, "source")?)?;
    let profile = parse_currency_profile(object_field(request, "currency_profile")?)?;
    profile.validate_amount(&source)?;
    let target = string_field(request, "target_currency_code")?;
    validate_currency_code(target, "target_currency_code")?;
    let target_metadata = profile.metadata_for(target)?;
    let mut result = Map::new();
    result.insert("schema_version".to_owned(), json!("2.0"));
    result.insert(
        "source".to_owned(),
        json!({
            "amount": source.amount_text,
            "currency_code": source.currency_code,
            "metadata_profile_version": source.metadata_profile_version
        }),
    );
    result.insert("target_currency_code".to_owned(), json!(target));
    result.insert("currency_profile".to_owned(), profile.json());
    result.insert(
        "target_minor_unit_scale".to_owned(),
        json!(target_metadata.minor_unit_scale),
    );
    result.insert(
        "target_rounding_mode".to_owned(),
        json!(target_metadata.rounding_mode),
    );
    match request.get("fx_snapshot") {
        None | Some(Value::Null) => {
            result.insert("fx_snapshot".to_owned(), Value::Null);
        }
        Some(snapshot) if snapshot.is_object() => {
            result.insert(
                "fx_snapshot".to_owned(),
                parse_fx_snapshot(snapshot)?.json(),
            );
        }
        Some(_) => {
            return Err(fail(
                "invalid_fx_snapshot",
                "fx_snapshot must be an object or null",
            ))
        }
    }
    if let Some(effective_at) = optional_string(request, "effective_at")? {
        let (_, normalized) = normalize_time(effective_at, "effective_at")?;
        result.insert("effective_at".to_owned(), json!(normalized));
    } else {
        result.insert("effective_at".to_owned(), Value::Null);
    }
    Ok(Value::Object(result))
}

#[cfg(test)]
mod tests {
    use super::convert_money_v2;
    use serde_json::json;

    fn request(rate: &str) -> serde_json::Value {
        json!({
            "schema_version": "2.0",
            "source": {
                "amount": "1.005",
                "currency_code": "AAA",
                "metadata_profile_version": "fixture-v1"
            },
            "target_currency_code": "BBB",
            "currency_profile": {
                "profile_version": "fixture-v1",
                "currencies": [
                    {"currency_code":"AAA","minor_unit_scale":3,"rounding_mode":"ROUND_HALF_UP"},
                    {"currency_code":"BBB","minor_unit_scale":2,"rounding_mode":"ROUND_HALF_UP"}
                ]
            },
            "fx_snapshot": {
                "snapshot_id":"fx-1",
                "as_of":"2026-01-02T00:00:00Z",
                "valid_from":"2026-01-01T00:00:00Z",
                "valid_to":"2026-01-03T00:00:00Z",
                "rates":[{
                    "base_currency":"AAA","quote_currency":"BBB","rate":rate,
                    "observed_at":"2026-01-01T00:00:00Z","source":"fixture","provenance_id":"fixture:AAA/BBB"
                }]
            }
        })
    }

    #[test]
    fn explicit_currency_conversion_is_rounded_once_to_target_scale() {
        let result = convert_money_v2(&request("1")).unwrap();
        assert_eq!(result["target"]["amount"], "1.01");
        assert_eq!(result["unrounded_target_amount"], "1.005");
        assert_eq!(result["fx_snapshot_id"], "fx-1");
    }

    #[test]
    fn direct_fx_rate_must_be_positive() {
        assert!(convert_money_v2(&request("0")).is_err());
    }
}
