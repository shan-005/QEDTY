//! Typed, opt-in WGS-84 ECEF input/result boundary.
//!
//! The existing crate::ecef_wgs84 remains the compatibility API and retains its
//! current input behavior. This module adds checked input construction without
//! duplicating the numerical implementation. Its range policy is an additive Rust
//! convenience; mirror it in the Python reference/contracts before treating it as a
//! normative cross-language validation contract.

use thiserror::Error;

/// Geographic latitude, longitude and ellipsoidal height for a WGS-84 calculation.
///
/// Successful instances contain finite coordinates with latitude in the range
/// [-90, 90] degrees, longitude in [-180, 180] degrees, and finite height in metres.
/// Negative height is allowed.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GeodeticCoordinate {
    latitude_deg: f64,
    longitude_deg: f64,
    height_m: f64,
}

impl GeodeticCoordinate {
    /// Construct a checked geographic coordinate.
    pub fn new(
        latitude_deg: f64,
        longitude_deg: f64,
        height_m: f64,
    ) -> Result<Self, GeometryError> {
        if !latitude_deg.is_finite() {
            return Err(GeometryError::NonFiniteLatitude);
        }
        if !(-90.0..=90.0).contains(&latitude_deg) {
            return Err(GeometryError::LatitudeOutOfRange);
        }
        if !longitude_deg.is_finite() {
            return Err(GeometryError::NonFiniteLongitude);
        }
        if !(-180.0..=180.0).contains(&longitude_deg) {
            return Err(GeometryError::LongitudeOutOfRange);
        }
        if !height_m.is_finite() {
            return Err(GeometryError::NonFiniteHeight);
        }

        Ok(Self {
            latitude_deg,
            longitude_deg,
            height_m,
        })
    }

    /// Latitude in degrees.
    pub fn latitude_deg(self) -> f64 {
        self.latitude_deg
    }

    /// Longitude in degrees.
    pub fn longitude_deg(self) -> f64 {
        self.longitude_deg
    }

    /// Ellipsoidal height in metres.
    pub fn height_m(self) -> f64 {
        self.height_m
    }
}

/// Earth-centred, Earth-fixed Cartesian coordinates in metres.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct EcefPoint {
    pub x_m: f64,
    pub y_m: f64,
    pub z_m: f64,
}

/// Errors produced while constructing a checked WGS-84 coordinate.
#[derive(Debug, Clone, Copy, Error, PartialEq, Eq)]
pub enum GeometryError {
    #[error("latitude must be finite")]
    NonFiniteLatitude,
    #[error("latitude must be within [-90, 90] degrees")]
    LatitudeOutOfRange,
    #[error("longitude must be finite")]
    NonFiniteLongitude,
    #[error("longitude must be within [-180, 180] degrees")]
    LongitudeOutOfRange,
    #[error("height must be finite")]
    NonFiniteHeight,
}

/// Convert a checked coordinate to ECEF using the existing compatibility calculation.
///
/// This does not introduce a second geodesy implementation; it delegates to
/// crate::ecef_wgs84.
pub fn ecef_wgs84_point(coordinate: GeodeticCoordinate) -> EcefPoint {
    let (x_m, y_m, z_m) = crate::ecef_wgs84(
        coordinate.latitude_deg,
        coordinate.longitude_deg,
        coordinate.height_m,
    );
    EcefPoint { x_m, y_m, z_m }
}

/// Validate a geographic input and return its WGS-84 ECEF coordinates.
///
/// This checked API is opt-in. Existing callers of crate::ecef_wgs84 retain
/// their current behavior.
pub fn try_ecef_wgs84(
    latitude_deg: f64,
    longitude_deg: f64,
    height_m: f64,
) -> Result<EcefPoint, GeometryError> {
    let coordinate = GeodeticCoordinate::new(latitude_deg, longitude_deg, height_m)?;
    Ok(ecef_wgs84_point(coordinate))
}

#[cfg(test)]
mod tests {
    use super::{try_ecef_wgs84, GeodeticCoordinate, GeometryError};

    #[test]
    fn accepts_valid_coordinate_and_negative_height() {
        let coordinate = GeodeticCoordinate::new(17.385, 78.4867, -10.0)
            .expect("finite WGS-84 coordinate should be accepted");
        assert_eq!(coordinate.latitude_deg(), 17.385);
        assert_eq!(coordinate.longitude_deg(), 78.4867);
        assert_eq!(coordinate.height_m(), -10.0);
    }

    #[test]
    fn accepts_inclusive_latitude_and_longitude_boundaries() {
        for latitude in [-90.0, 90.0] {
            for longitude in [-180.0, 180.0] {
                let coordinate = GeodeticCoordinate::new(latitude, longitude, 0.0)
                    .expect("documented inclusive coordinate boundary should be accepted");
                assert_eq!(coordinate.latitude_deg(), latitude);
                assert_eq!(coordinate.longitude_deg(), longitude);
            }
        }
    }

    #[test]
    fn rejects_non_finite_values_for_each_input_dimension() {
        for latitude in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert_eq!(
                GeodeticCoordinate::new(latitude, 0.0, 0.0),
                Err(GeometryError::NonFiniteLatitude)
            );
        }
        for longitude in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert_eq!(
                GeodeticCoordinate::new(0.0, longitude, 0.0),
                Err(GeometryError::NonFiniteLongitude)
            );
        }
        for height in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            assert_eq!(
                GeodeticCoordinate::new(0.0, 0.0, height),
                Err(GeometryError::NonFiniteHeight)
            );
        }
    }

    #[test]
    fn rejects_coordinates_outside_documented_ranges() {
        for latitude in [-90.000_001, -91.0, 90.000_001, 91.0] {
            assert_eq!(
                GeodeticCoordinate::new(latitude, 0.0, 0.0),
                Err(GeometryError::LatitudeOutOfRange)
            );
        }
        for longitude in [-180.000_001, -181.0, 180.000_001, 181.0] {
            assert_eq!(
                GeodeticCoordinate::new(0.0, longitude, 0.0),
                Err(GeometryError::LongitudeOutOfRange)
            );
        }
    }

    #[test]
    fn checked_api_has_finite_bounded_results_over_coordinate_grid() {
        // Deterministic boundary/interior grid: no randomness and no hidden test seed.
        // Exact numerical expectations are separately checked against shared fixtures.
        let latitudes = [-90.0, -89.5, -45.0, 0.0, 45.0, 89.5, 90.0];
        let longitudes = [-180.0, -179.5, -90.0, 0.0, 90.0, 179.5, 180.0];
        let heights_m = [-10_000.0, 0.0, 100_000.0];

        for latitude in latitudes {
            for longitude in longitudes {
                for height_m in heights_m {
                    let point = try_ecef_wgs84(latitude, longitude, height_m)
                        .expect("all grid coordinates are within the declared input domain");
                    assert!(point.x_m.is_finite(), "x non-finite at {latitude}, {longitude}, {height_m}");
                    assert!(point.y_m.is_finite(), "y non-finite at {latitude}, {longitude}, {height_m}");
                    assert!(point.z_m.is_finite(), "z non-finite at {latitude}, {longitude}, {height_m}");
                    let radius_m = point
                        .x_m
                        .hypot(point.y_m)
                        .hypot(point.z_m);
                    assert!(
                        radius_m > 6_300_000.0 + height_m
                            && radius_m < 6_500_000.0 + height_m,
                        "ECEF radius out of broad WGS-84 bounds at {latitude}, {longitude}, {height_m}: {radius_m}"
                    );
                }
            }
        }
    }
}
