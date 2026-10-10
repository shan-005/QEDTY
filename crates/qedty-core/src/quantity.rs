//! Deterministic, dimension-checked unit conversion for the Rust core.
//!
//! This is an additive native implementation of the restricted unit registry in
//! `src/qedty/core/units.py`. The registry intentionally excludes currencies and
//! exchange-rate semantics. Values are finite IEEE-754 `f64`; Python's reference
//! uses `Decimal`, so cross-language users must apply the vector's stated output
//! formatting and avoid claiming arbitrary-precision equivalence.

use thiserror::Error;

pub type Dimension = [i32; 8];
pub const DIMENSIONLESS: Dimension = [0; 8];
pub const LENGTH: Dimension = [1, 0, 0, 0, 0, 0, 0, 0];
pub const MASS: Dimension = [0, 1, 0, 0, 0, 0, 0, 0];
pub const TIME: Dimension = [0, 0, 1, 0, 0, 0, 0, 0];
pub const CURRENT: Dimension = [0, 0, 0, 1, 0, 0, 0, 0];
pub const TEMPERATURE: Dimension = [0, 0, 0, 0, 1, 0, 0, 0];
pub const AMOUNT: Dimension = [0, 0, 0, 0, 0, 1, 0, 0];
pub const LUMINOUS_INTENSITY: Dimension = [0, 0, 0, 0, 0, 0, 1, 0];
pub const INFORMATION: Dimension = [0, 0, 0, 0, 0, 0, 0, 1];

#[derive(Debug, Clone, PartialEq)]
pub struct UnitDefinition {
    pub code: String,
    pub dimension: Dimension,
    pub scale_to_si: f64,
    pub offset_to_si: f64,
}

impl UnitDefinition {
    pub fn is_affine(&self) -> bool {
        self.offset_to_si != 0.0
    }

    pub fn to_si(&self, value: f64) -> f64 {
        value * self.scale_to_si + self.offset_to_si
    }

    pub fn from_si(&self, value: f64) -> f64 {
        (value - self.offset_to_si) / self.scale_to_si
    }
}

#[derive(Debug, Clone, Error, PartialEq)]
pub enum QuantityError {
    #[error("quantity value must be finite")]
    NonFiniteValue,
    #[error("unit code must not be blank")]
    BlankUnit,
    #[error("unknown or unsupported unit: {0}")]
    UnknownUnit(String),
    #[error("unsupported unit expression: {0}")]
    InvalidExpression(String),
    #[error("unit exponent is outside the supported range [-16, 16]")]
    ExponentOutOfRange,
    #[error("affine units must stand alone and cannot be multiplied or divided")]
    AffineExpression,
    #[error("incompatible units: {from_unit} and {to_unit}")]
    IncompatibleUnits { from_unit: String, to_unit: String },
    #[error("affine absolute quantities cannot be scaled or combined directly")]
    AffineArithmetic,
    #[error("division by zero")]
    DivisionByZero,
}

fn definition(code: &str, dimension: Dimension, scale: f64) -> UnitDefinition {
    UnitDefinition {
        code: code.to_owned(),
        dimension,
        scale_to_si: scale,
        offset_to_si: 0.0,
    }
}

fn atom(code: &str) -> Result<UnitDefinition, QuantityError> {
    let unit = match code {
        "1" | "one" | "dimensionless" => definition("1", DIMENSIONLESS, 1.0),
        "m" | "meter" | "metre" => definition("m", LENGTH, 1.0),
        "km" | "kilometer" | "kilometre" => definition("km", LENGTH, 1_000.0),
        "cm" => definition("cm", LENGTH, 0.01),
        "mm" => definition("mm", LENGTH, 0.001),
        "um" | "µm" => definition("um", LENGTH, 0.000_001),
        "nm" => definition("nm", LENGTH, 0.000_000_001),
        "kg" => definition("kg", MASS, 1.0),
        "g" | "gram" => definition("g", MASS, 0.001),
        "mg" => definition("mg", MASS, 0.000_001),
        "t" | "tonne" => definition("t", MASS, 1_000.0),
        "s" | "sec" | "second" => definition("s", TIME, 1.0),
        "ms" => definition("ms", TIME, 0.001),
        "us" | "µs" => definition("us", TIME, 0.000_001),
        "ns" => definition("ns", TIME, 0.000_000_001),
        "min" => definition("min", TIME, 60.0),
        "h" | "hr" | "hour" => definition("h", TIME, 3_600.0),
        "d" | "day" => definition("d", TIME, 86_400.0),
        "K" => definition("K", TEMPERATURE, 1.0),
        "Cel" | "degC" | "°C" => UnitDefinition {
            code: "Cel".to_owned(),
            dimension: TEMPERATURE,
            scale_to_si: 1.0,
            offset_to_si: 273.15,
        },
        "A" | "amp" | "ampere" => definition("A", CURRENT, 1.0),
        "mol" => definition("mol", AMOUNT, 1.0),
        "cd" => definition("cd", LUMINOUS_INTENSITY, 1.0),
        "rad" | "radian" => definition("rad", DIMENSIONLESS, 1.0),
        "deg" | "degree" | "°" => definition("deg", DIMENSIONLESS, std::f64::consts::PI / 180.0),
        "Hz" => definition("Hz", [0, 0, -1, 0, 0, 0, 0, 0], 1.0),
        "N" => definition("N", [1, 1, -2, 0, 0, 0, 0, 0], 1.0),
        "kN" => definition("kN", [1, 1, -2, 0, 0, 0, 0, 0], 1_000.0),
        "Pa" => definition("Pa", [-1, 1, -2, 0, 0, 0, 0, 0], 1.0),
        "kPa" => definition("kPa", [-1, 1, -2, 0, 0, 0, 0, 0], 1_000.0),
        "MPa" => definition("MPa", [-1, 1, -2, 0, 0, 0, 0, 0], 1_000_000.0),
        "bar" => definition("bar", [-1, 1, -2, 0, 0, 0, 0, 0], 100_000.0),
        "J" => definition("J", [2, 1, -2, 0, 0, 0, 0, 0], 1.0),
        "kJ" => definition("kJ", [2, 1, -2, 0, 0, 0, 0, 0], 1_000.0),
        "MJ" => definition("MJ", [2, 1, -2, 0, 0, 0, 0, 0], 1_000_000.0),
        "W" => definition("W", [2, 1, -3, 0, 0, 0, 0, 0], 1.0),
        "kW" => definition("kW", [2, 1, -3, 0, 0, 0, 0, 0], 1_000.0),
        "MW" => definition("MW", [2, 1, -3, 0, 0, 0, 0, 0], 1_000_000.0),
        "GW" => definition("GW", [2, 1, -3, 0, 0, 0, 0, 0], 1_000_000_000.0),
        "Wh" => definition("Wh", [2, 1, -2, 0, 0, 0, 0, 0], 3_600.0),
        "kWh" => definition("kWh", [2, 1, -2, 0, 0, 0, 0, 0], 3_600_000.0),
        "MWh" => definition("MWh", [2, 1, -2, 0, 0, 0, 0, 0], 3_600_000_000.0),
        "GWh" => definition("GWh", [2, 1, -2, 0, 0, 0, 0, 0], 3_600_000_000_000.0),
        "bit" => definition("bit", INFORMATION, 1.0),
        "kbit" => definition("kbit", INFORMATION, 1_000.0),
        "Mbit" => definition("Mbit", INFORMATION, 1_000_000.0),
        "Gbit" => definition("Gbit", INFORMATION, 1_000_000_000.0),
        "B" | "byte" => definition("B", INFORMATION, 8.0),
        other => return Err(QuantityError::UnknownUnit(other.to_owned())),
    };
    Ok(unit)
}

/// Resolve a canonical unit code, alias, or explicitly supported product/quotient.
pub fn get_unit(code: &str) -> Result<UnitDefinition, QuantityError> {
    let text = code.trim();
    if text.is_empty() {
        return Err(QuantityError::BlankUnit);
    }
    if !text.contains('*') && !text.contains('/') && !text.contains('^') {
        return atom(text);
    }
    parse_unit_expression(text)
}

/// Parse a restricted product/quotient expression such as `kg*m/s^2`.
/// Parentheses, implicit multiplication, and unknown prefixes are rejected.
pub fn parse_unit_expression(expression: &str) -> Result<UnitDefinition, QuantityError> {
    let text: String = expression
        .chars()
        .filter(|ch| !ch.is_whitespace())
        .collect();
    if text.is_empty() {
        return Err(QuantityError::BlankUnit);
    }
    let mut dimension = DIMENSIONLESS;
    let mut scale = 1.0_f64;
    let mut numerator = true;
    let mut token = String::new();
    let mut parsed: Vec<(String, bool)> = Vec::new();
    for ch in text.chars() {
        if ch == '*' || ch == '/' {
            if token.is_empty() {
                return Err(QuantityError::InvalidExpression(text));
            }
            parsed.push((std::mem::take(&mut token), numerator));
            numerator = ch == '*';
        } else {
            token.push(ch);
        }
    }
    if token.is_empty() {
        return Err(QuantityError::InvalidExpression(text));
    }
    parsed.push((token, numerator));

    for (term, is_numerator) in &parsed {
        let (base, exponent) = match term.split_once('^') {
            Some((base, raw)) => {
                let parsed = raw
                    .parse::<i32>()
                    .map_err(|_| QuantityError::InvalidExpression(text.clone()))?;
                if !(-16..=16).contains(&parsed) {
                    return Err(QuantityError::ExponentOutOfRange);
                }
                (base, parsed)
            }
            None => (term.as_str(), 1),
        };
        if base.is_empty() || (base.contains('(') || base.contains(')')) {
            return Err(QuantityError::InvalidExpression(text));
        }
        let unit = atom(base)?;
        if unit.is_affine() {
            if parsed.len() != 1 || exponent != 1 || !is_numerator {
                return Err(QuantityError::AffineExpression);
            }
            return Ok(unit);
        }
        let signed_exponent = if *is_numerator { exponent } else { -exponent };
        for (index, value) in unit.dimension.iter().enumerate() {
            dimension[index] += signed_exponent * value;
        }
        scale *= unit.scale_to_si.powi(signed_exponent);
        if !scale.is_finite() || scale <= 0.0 {
            return Err(QuantityError::InvalidExpression(text));
        }
    }
    Ok(UnitDefinition {
        code: text,
        dimension,
        scale_to_si: scale,
        offset_to_si: 0.0,
    })
}

pub fn are_compatible(first: &str, second: &str) -> Result<bool, QuantityError> {
    Ok(get_unit(first)?.dimension == get_unit(second)?.dimension)
}

pub fn convert_value(value: f64, from_unit: &str, to_unit: &str) -> Result<f64, QuantityError> {
    if !value.is_finite() {
        return Err(QuantityError::NonFiniteValue);
    }
    let source = get_unit(from_unit)?;
    let target = get_unit(to_unit)?;
    if source.dimension != target.dimension {
        return Err(QuantityError::IncompatibleUnits {
            from_unit: from_unit.to_owned(),
            to_unit: to_unit.to_owned(),
        });
    }
    let result = target.from_si(source.to_si(value));
    if !result.is_finite() {
        return Err(QuantityError::NonFiniteValue);
    }
    Ok(result)
}

#[derive(Debug, Clone, PartialEq)]
pub struct Quantity {
    pub value: f64,
    pub unit: String,
}

impl Quantity {
    pub fn new(value: f64, unit: &str) -> Result<Self, QuantityError> {
        if !value.is_finite() {
            return Err(QuantityError::NonFiniteValue);
        }
        let unit = unit.trim();
        let _definition = get_unit(unit)?;
        Ok(Self {
            value,
            unit: unit.to_owned(),
        })
    }

    pub fn dimension(&self) -> Result<Dimension, QuantityError> {
        Ok(get_unit(&self.unit)?.dimension)
    }

    pub fn si_value(&self) -> Result<f64, QuantityError> {
        let definition = get_unit(&self.unit)?;
        let result = definition.to_si(self.value);
        if result.is_finite() {
            Ok(result)
        } else {
            Err(QuantityError::NonFiniteValue)
        }
    }

    pub fn to(&self, unit: &str) -> Result<Self, QuantityError> {
        let converted = convert_value(self.value, &self.unit, unit)?;
        Self::new(converted, unit)
    }

    pub fn scaled(&self, factor: f64) -> Result<Self, QuantityError> {
        if !factor.is_finite() {
            return Err(QuantityError::NonFiniteValue);
        }
        if get_unit(&self.unit)?.is_affine() {
            return Err(QuantityError::AffineArithmetic);
        }
        Self::new(self.value * factor, &self.unit)
    }

    pub fn add(&self, other: &Self) -> Result<Self, QuantityError> {
        let source = get_unit(&self.unit)?;
        let target = get_unit(&other.unit)?;
        if source.is_affine() || target.is_affine() {
            return Err(QuantityError::AffineArithmetic);
        }
        if source.dimension != target.dimension {
            return Err(QuantityError::IncompatibleUnits {
                from_unit: other.unit.clone(),
                to_unit: self.unit.clone(),
            });
        }
        Self::new(
            self.value + convert_value(other.value, &other.unit, &self.unit)?,
            &self.unit,
        )
    }

    pub fn subtract(&self, other: &Self) -> Result<Self, QuantityError> {
        let source = get_unit(&self.unit)?;
        let target = get_unit(&other.unit)?;
        if source.is_affine() || target.is_affine() {
            return Err(QuantityError::AffineArithmetic);
        }
        if source.dimension != target.dimension {
            return Err(QuantityError::IncompatibleUnits {
                from_unit: other.unit.clone(),
                to_unit: self.unit.clone(),
            });
        }
        Self::new(
            self.value - convert_value(other.value, &other.unit, &self.unit)?,
            &self.unit,
        )
    }

    /// Multiply quantities and retain the explicit product unit expression.
    pub fn multiply(&self, other: &Self) -> Result<Self, QuantityError> {
        if get_unit(&self.unit)?.is_affine() || get_unit(&other.unit)?.is_affine() {
            return Err(QuantityError::AffineArithmetic);
        }
        let unit = format!("{}*{}", self.unit, other.unit);
        Self::new(self.value * other.value, &unit)
    }

    /// Divide quantities and retain the explicit quotient unit expression.
    pub fn divide(&self, other: &Self) -> Result<Self, QuantityError> {
        if get_unit(&self.unit)?.is_affine() || get_unit(&other.unit)?.is_affine() {
            return Err(QuantityError::AffineArithmetic);
        }
        if other.value == 0.0 {
            return Err(QuantityError::DivisionByZero);
        }
        let unit = format!("{}/{}", self.unit, other.unit);
        Self::new(self.value / other.value, &unit)
    }
}

/// Format a scalar like Python `str(Decimal)` for the supported integer/decimal fixture shape.
pub fn format_value(value: f64) -> Result<String, QuantityError> {
    if !value.is_finite() {
        return Err(QuantityError::NonFiniteValue);
    }
    let mut output = value.to_string();
    if !output.contains('.') && !output.contains('e') && !output.contains('E') {
        output.push_str(".0");
    }
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::{
        are_compatible, convert_value, format_value, get_unit, parse_unit_expression, Quantity,
        QuantityError,
    };

    #[test]
    fn reference_quantity_vector_converts_kilometres_to_metres() {
        assert_eq!(
            format_value(convert_value(2.5, "km", "m").unwrap()).unwrap(),
            "2500.0"
        );
    }

    #[test]
    fn supports_aliases_and_derived_units() {
        assert_eq!(convert_value(1.0, "kilometre", "m").unwrap(), 1000.0);
        assert_eq!(
            get_unit("kg*m/s^2").unwrap().dimension,
            get_unit("N").unwrap().dimension
        );
        assert!(are_compatible("kWh", "J").unwrap());
        assert!(!are_compatible("km", "s").unwrap());
        assert_eq!(
            parse_unit_expression("MW").unwrap().dimension,
            get_unit("W").unwrap().dimension
        );
    }

    #[test]
    fn preserves_trimmed_aliases_and_compound_unit_labels() {
        let distance = Quantity::new(1.0, " kilometre ").unwrap();
        assert_eq!(distance.unit, "kilometre");

        let metres = distance.to(" meter ").unwrap();
        assert_eq!(metres.unit, "meter");
        assert_eq!(metres.value, 1000.0);

        let speed = Quantity::new(2.0, "kilometre")
            .unwrap()
            .divide(&Quantity::new(1.0, "hour").unwrap())
            .unwrap();
        assert_eq!(speed.unit, "kilometre/hour");

        let converted = speed.to("km/h").unwrap();
        assert_eq!(converted.unit, "km/h");
        assert!((converted.value - 2.0).abs() < 1e-12);
    }

    #[test]
    fn representative_compatible_units_round_trip_within_floating_tolerance() {
        for (value, first, second) in [
            (123.456, "km", "m"),
            (2.75, "h", "s"),
            (1.25, "kWh", "J"),
            (90.0, "deg", "rad"),
            (18.5, "Cel", "K"),
        ] {
            let converted = convert_value(value, first, second).unwrap();
            let returned = convert_value(converted, second, first).unwrap();
            assert!(
                (returned - value).abs() <= 1e-9 * value.abs().max(1.0),
                "{value} {first} -> {second} -> {first}: {returned}"
            );
        }
    }

    #[test]
    fn handles_affine_temperature_conversion_but_rejects_affine_products() {
        assert!((convert_value(0.0, "Cel", "K").unwrap() - 273.15).abs() < 1e-12);
        assert!(matches!(
            get_unit("Cel/s"),
            Err(QuantityError::AffineExpression)
        ));
        assert!(Quantity::new(20.0, "Cel").unwrap().scaled(2.0).is_err());
    }

    #[test]
    fn dimensional_multiplication_and_division_preserve_unit_expressions() {
        let power = Quantity::new(2.0, "kW").unwrap();
        let duration = Quantity::new(3.0, "h").unwrap();
        let energy = power.multiply(&duration).unwrap();
        assert_eq!(energy.to("kWh").unwrap().value, 6.0);
        assert_eq!(
            energy.divide(&duration).unwrap().to("kW").unwrap().value,
            2.0
        );
        assert!(matches!(
            power.divide(&Quantity::new(0.0, "h").unwrap()),
            Err(QuantityError::DivisionByZero)
        ));
    }

    #[test]
    fn rejects_invalid_and_dimensionally_incompatible_inputs() {
        assert!(matches!(
            convert_value(1.0, "km", "kg"),
            Err(QuantityError::IncompatibleUnits { .. })
        ));
        assert!(get_unit("furlong").is_err());
        assert!(get_unit("m//s").is_err());
        assert!(convert_value(f64::NAN, "m", "km").is_err());
        assert!(Quantity::new(1.0, " ").is_err());
    }
}
