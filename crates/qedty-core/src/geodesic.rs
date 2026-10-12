//! Checked WGS-84 ellipsoidal inverse-geodesic distance.
//!
//! Distances are surface geodesic lengths in metres. The implementation is
//! GeographicLib's Karney-family algorithm, not spherical Haversine distance.

use geographiclib_rs::{Geodesic, InverseGeodesic};
use thiserror::Error;

#[derive(Debug, Clone, Copy, Error, PartialEq, Eq)]
pub enum GeodesicError {
    #[error("latitude/longitude coordinates must be finite and inside WGS-84 bounds")]
    InvalidCoordinate,
    #[error("WGS-84 inverse geodesic returned an invalid distance")]
    InvalidResult,
}

/// Return the shortest surface geodesic distance between two WGS-84 positions.
///
/// Latitude and longitude are in degrees. Heights, if present in an upstream
/// point model, are intentionally ignored by the ellipsoidal surface contract.
pub fn wgs84_inverse_distance_m(
    first_latitude_deg: f64,
    first_longitude_deg: f64,
    second_latitude_deg: f64,
    second_longitude_deg: f64,
) -> Result<f64, GeodesicError> {
    let coordinates = [
        (first_latitude_deg, -90.0, 90.0),
        (second_latitude_deg, -90.0, 90.0),
        (first_longitude_deg, -180.0, 180.0),
        (second_longitude_deg, -180.0, 180.0),
    ];
    if coordinates
        .iter()
        .any(|(value, min, max)| !value.is_finite() || value < min || value > max)
    {
        return Err(GeodesicError::InvalidCoordinate);
    }

    let distance_m: f64 = Geodesic::wgs84().inverse(
        first_latitude_deg,
        first_longitude_deg,
        second_latitude_deg,
        second_longitude_deg,
    );
    if distance_m.is_finite() && distance_m >= 0.0 {
        Ok(distance_m)
    } else {
        Err(GeodesicError::InvalidResult)
    }
}

#[cfg(test)]
mod tests {
    use super::{wgs84_inverse_distance_m, GeodesicError};

    #[test]
    fn matches_fixed_wgs84_inverse_distance_references() {
        let equator_degree =
            wgs84_inverse_distance_m(0.0, 0.0, 0.0, 1.0).expect("valid equator points");
        assert!((equator_degree - 111_319.490_793_273_57).abs() < 1e-6);

        let transatlantic =
            wgs84_inverse_distance_m(34.095925, -118.2884237, 59.4323439, 24.7341649)
                .expect("valid reference points");
        assert!((transatlantic - 9_094_718.727_511_38).abs() < 1e-5);

        let antipodal = wgs84_inverse_distance_m(0.0, 0.0, 0.0, 180.0)
            .expect("valid antipodal points");
        assert!((antipodal - 20_003_931.458_625_447).abs() < 1e-3);

        assert_eq!(wgs84_inverse_distance_m(17.4, 78.4, 17.4, 78.4), Ok(0.0));
    }

    #[test]
    fn rejects_non_finite_or_out_of_range_coordinates() {
        for invalid in [
            wgs84_inverse_distance_m(90.000_001, 0.0, 0.0, 0.0),
            wgs84_inverse_distance_m(0.0, -180.000_001, 0.0, 0.0),
            wgs84_inverse_distance_m(f64::NAN, 0.0, 0.0, 0.0),
            wgs84_inverse_distance_m(0.0, 0.0, 0.0, f64::INFINITY),
        ] {
            assert_eq!(invalid, Err(GeodesicError::InvalidCoordinate));
        }
    }
}
