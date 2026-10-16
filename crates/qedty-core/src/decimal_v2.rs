//! Exact decimal-string arithmetic for QEDTY's versioned monetary boundary.
//!
//! Values are coefficient/scale pairs backed by BigInt. Multiplication, division,
//! addition and subtraction use 34 significant decimal digits with half-even
//! arithmetic to match the v2 Python Decimal reference.

use num_bigint::BigInt;
use num_traits::{One, Signed, Zero};
use std::cmp::Ordering;
use thiserror::Error;

pub const DECIMAL_V2_PRECISION: u32 = 34;
const MAX_DECIMAL_TEXT_BYTES: usize = 10_000;

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum DecimalV2Error {
    #[error("decimal text is invalid or exceeds the supported input limit")]
    InvalidDecimal,
    #[error("division by zero")]
    DivisionByZero,
    #[error("unsupported decimal rounding mode: {0}")]
    InvalidRoundingMode(String),
}

#[derive(Debug, Clone)]
pub struct DecimalV2 {
    coefficient: BigInt,
    scale: i32,
}

impl DecimalV2 {
    pub fn parse(text: &str) -> Result<Self, DecimalV2Error> {
        if text.is_empty() || text.len() > MAX_DECIMAL_TEXT_BYTES {
            return Err(DecimalV2Error::InvalidDecimal);
        }
        let (negative, unsigned) = match text.strip_prefix('-') {
            Some(rest) => (true, rest),
            None => (false, text),
        };
        if unsigned.is_empty() || unsigned.starts_with('+') {
            return Err(DecimalV2Error::InvalidDecimal);
        }
        let mut parts = unsigned.split('.');
        let integer = parts.next().ok_or(DecimalV2Error::InvalidDecimal)?;
        let fraction = parts.next();
        if parts.next().is_some()
            || integer.is_empty()
            || !integer.bytes().all(|byte| byte.is_ascii_digit())
            || (integer.len() > 1 && integer.starts_with('0'))
        {
            return Err(DecimalV2Error::InvalidDecimal);
        }
        let fraction = match fraction {
            Some(value) if !value.is_empty() && value.bytes().all(|byte| byte.is_ascii_digit()) => {
                value
            }
            Some(_) => return Err(DecimalV2Error::InvalidDecimal),
            None => "",
        };
        let digits = format!("{integer}{fraction}");
        let mut coefficient =
            BigInt::parse_bytes(digits.as_bytes(), 10).ok_or(DecimalV2Error::InvalidDecimal)?;
        if negative && !coefficient.is_zero() {
            coefficient = -coefficient;
        }
        Ok(Self {
            coefficient,
            scale: i32::try_from(fraction.len()).map_err(|_| DecimalV2Error::InvalidDecimal)?,
        })
    }

    pub fn zero() -> Self {
        Self {
            coefficient: BigInt::zero(),
            scale: 0,
        }
    }

    pub fn one() -> Self {
        Self {
            coefficient: BigInt::one(),
            scale: 0,
        }
    }

    pub fn from_u64(value: u64) -> Self {
        Self {
            coefficient: BigInt::from(value),
            scale: 0,
        }
    }

    pub fn is_zero(&self) -> bool {
        self.coefficient.is_zero()
    }

    pub fn is_negative(&self) -> bool {
        self.coefficient.is_negative()
    }

    pub fn compare(&self, other: &Self) -> Ordering {
        let scale = self.scale.max(other.scale);
        let left = &self.coefficient * power_of_ten((scale - self.scale) as u32);
        let right = &other.coefficient * power_of_ten((scale - other.scale) as u32);
        left.cmp(&right)
    }

    pub fn add(&self, other: &Self) -> Self {
        let scale = self.scale.max(other.scale);
        let left = &self.coefficient * power_of_ten((scale - self.scale) as u32);
        let right = &other.coefficient * power_of_ten((scale - other.scale) as u32);
        Self {
            coefficient: left + right,
            scale,
        }
        .round_significant(DECIMAL_V2_PRECISION)
    }

    pub fn subtract(&self, other: &Self) -> Self {
        let scale = self.scale.max(other.scale);
        let left = &self.coefficient * power_of_ten((scale - self.scale) as u32);
        let right = &other.coefficient * power_of_ten((scale - other.scale) as u32);
        Self {
            coefficient: left - right,
            scale,
        }
        .round_significant(DECIMAL_V2_PRECISION)
    }

    pub fn multiply(&self, other: &Self) -> Self {
        Self {
            coefficient: &self.coefficient * &other.coefficient,
            scale: self.scale + other.scale,
        }
        .round_significant(DECIMAL_V2_PRECISION)
    }

    pub fn divide(&self, other: &Self, precision: u32) -> Result<Self, DecimalV2Error> {
        if other.is_zero() {
            return Err(DecimalV2Error::DivisionByZero);
        }
        if self.is_zero() {
            return Ok(Self::zero());
        }
        let numerator_abs = self.coefficient.abs();
        let denominator_abs = other.coefficient.abs();
        let numerator_digits = decimal_digits(&numerator_abs);
        let denominator_digits = decimal_digits(&denominator_abs);
        let mut ratio_exponent = numerator_digits as i32 - denominator_digits as i32;
        if ratio_exponent >= 0 {
            let scaled_denominator =
                &denominator_abs * power_of_ten(ratio_exponent as u32);
            if numerator_abs < scaled_denominator {
                ratio_exponent -= 1;
            }
        } else {
            let scaled_numerator =
                &numerator_abs * power_of_ten((-ratio_exponent) as u32);
            if scaled_numerator < denominator_abs {
                ratio_exponent -= 1;
            }
        }
        let value_exponent = ratio_exponent + other.scale - self.scale;
        let target_scale = i32::try_from(precision).map_err(|_| DecimalV2Error::InvalidDecimal)?
            - 1
            - value_exponent;
        let shift = other.scale - self.scale + target_scale;
        let (numerator, denominator) = if shift >= 0 {
            (numerator_abs * power_of_ten(shift as u32), denominator_abs)
        } else {
            (
                numerator_abs,
                denominator_abs * power_of_ten((-shift) as u32),
            )
        };
        let mut quotient = &numerator / &denominator;
        let remainder = numerator % &denominator;
        let twice_remainder = &remainder * BigInt::from(2u8);
        let quotient_is_odd = (&quotient % BigInt::from(2u8)) != BigInt::zero();
        if twice_remainder > denominator || (twice_remainder == denominator && quotient_is_odd) {
            quotient += BigInt::one();
        }
        if self.is_negative() != other.is_negative() && !quotient.is_zero() {
            quotient = -quotient;
        }
        Ok(Self {
            coefficient: quotient,
            scale: target_scale,
        }
        .round_significant(precision))
    }

    pub fn round_significant(&self, precision: u32) -> Self {
        if self.is_zero() || precision == 0 {
            return self.clone();
        }
        let absolute = self.coefficient.abs();
        let digits = decimal_digits(&absolute);
        if digits <= precision as usize {
            return self.clone();
        }
        let dropped = digits - precision as usize;
        let divisor = power_of_ten(dropped as u32);
        let mut quotient = &absolute / &divisor;
        let remainder = absolute % &divisor;
        let twice_remainder = &remainder * BigInt::from(2u8);
        let quotient_is_odd = (&quotient % BigInt::from(2u8)) != BigInt::zero();
        if twice_remainder > divisor || (twice_remainder == divisor && quotient_is_odd) {
            quotient += BigInt::one();
        }
        if self.is_negative() && !quotient.is_zero() {
            quotient = -quotient;
        }
        Self {
            coefficient: quotient,
            scale: self.scale - dropped as i32,
        }
    }

    pub fn quantize(&self, target_scale: u32, rounding_mode: &str) -> Result<Self, DecimalV2Error> {
        let target_scale =
            i32::try_from(target_scale).map_err(|_| DecimalV2Error::InvalidDecimal)?;
        if self.scale <= target_scale {
            return Ok(Self {
                coefficient: &self.coefficient * power_of_ten((target_scale - self.scale) as u32),
                scale: target_scale,
            });
        }
        let dropped = (self.scale - target_scale) as u32;
        let divisor = power_of_ten(dropped);
        let absolute = self.coefficient.abs();
        let mut quotient = &absolute / &divisor;
        let remainder = absolute % &divisor;
        if remainder.is_zero() {
            return Ok(Self {
                coefficient: signed(quotient, self.is_negative()),
                scale: target_scale,
            });
        }
        let twice_remainder = &remainder * BigInt::from(2u8);
        let quotient_is_odd = (&quotient % BigInt::from(2u8)) != BigInt::zero();
        let last_digit = quotient.to_str_radix(10).chars().last().unwrap_or('0');
        let increment = match rounding_mode {
            "ROUND_05UP" => last_digit == '0' || last_digit == '5',
            "ROUND_CEILING" => !self.is_negative(),
            "ROUND_DOWN" => false,
            "ROUND_FLOOR" => self.is_negative(),
            "ROUND_HALF_DOWN" => twice_remainder > divisor,
            "ROUND_HALF_EVEN" => {
                twice_remainder > divisor || (twice_remainder == divisor && quotient_is_odd)
            }
            "ROUND_HALF_UP" => twice_remainder >= divisor,
            "ROUND_UP" => true,
            other => return Err(DecimalV2Error::InvalidRoundingMode(other.to_owned())),
        };
        if increment {
            quotient += BigInt::one();
        }
        Ok(Self {
            coefficient: signed(quotient, self.is_negative()),
            scale: target_scale,
        })
    }

    /// Preserve the stored scale and render without exponent notation.
    pub fn format_fixed(&self) -> String {
        let negative = self.coefficient.is_negative();
        let digits = self.coefficient.abs().to_str_radix(10);
        let body = if self.scale <= 0 {
            format!("{digits}{}", "0".repeat((-self.scale) as usize))
        } else {
            let scale = self.scale as usize;
            if digits.len() <= scale {
                format!("0.{}{}", "0".repeat(scale - digits.len()), digits)
            } else {
                let split = digits.len() - scale;
                format!("{}.{}", &digits[..split], &digits[split..])
            }
        };
        if negative && !self.is_zero() {
            format!("-{body}")
        } else {
            body
        }
    }

    /// Canonical fixed-point form: no exponent, no redundant fractional zeroes, no signed zero.
    pub fn format_canonical(&self) -> String {
        if self.is_zero() {
            return "0".to_owned();
        }
        let rendered = self.format_fixed();
        if !rendered.contains('.') {
            return rendered;
        }
        rendered
            .trim_end_matches('0')
            .trim_end_matches('.')
            .to_owned()
    }
}

fn signed(value: BigInt, negative: bool) -> BigInt {
    if negative && !value.is_zero() {
        -value
    } else {
        value
    }
}

fn decimal_digits(value: &BigInt) -> usize {
    value.to_str_radix(10).len()
}

fn power_of_ten(exponent: u32) -> BigInt {
    BigInt::from(10u8).pow(exponent)
}

#[cfg(test)]
mod tests {
    use super::DecimalV2;

    #[test]
    fn decimal_arithmetic_uses_half_even_significant_precision() {
        let numerator = DecimalV2::parse("1").unwrap();
        let denominator = DecimalV2::parse("6").unwrap();
        assert_eq!(
            numerator
                .divide(&denominator, 34)
                .unwrap()
                .format_canonical(),
            "0.1666666666666666666666666666666667"
        );
    }

    #[test]
    fn decimal_division_and_multiplication_normalize_outputs() {
        let value = DecimalV2::parse("1.005").unwrap();
        let rate = DecimalV2::parse("2").unwrap();
        assert_eq!(value.multiply(&rate).format_canonical(), "2.01");
        assert_eq!(
            value.divide(&rate, 34).unwrap().format_canonical(),
            "0.5025"
        );
    }

    #[test]
    fn decimal_quantize_supports_target_rounding_mode() {
        assert_eq!(
            DecimalV2::parse("1.005")
                .unwrap()
                .quantize(2, "ROUND_HALF_UP")
                .unwrap()
                .format_fixed(),
            "1.01"
        );
        assert_eq!(
            DecimalV2::parse("1.005")
                .unwrap()
                .quantize(2, "ROUND_HALF_EVEN")
                .unwrap()
                .format_fixed(),
            "1.00"
        );
    }

    #[test]
    fn decimal_parser_rejects_exponents_and_noncanonical_integer_zeros() {
        assert!(DecimalV2::parse("1e-3").is_err());
        assert!(DecimalV2::parse("01.0").is_err());
    }
}
