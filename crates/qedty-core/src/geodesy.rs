//! Checked inverse WGS-84 ECEF conversion.
//!
//! The API returns ellipsoidal height in metres and degrees for latitude and
//! longitude. It complements `geometry::ecef_wgs84_point`; it does not replace
//! high-accuracy GeographicLib/PROJ inverse-geodesic algorithms.

use crate::geometry::{EcefPoint, GeodeticCoordinate};
use thiserror::Error;

const A_M: f64 = 6_378_137.0;
const INV_F: f64 = 298.257_223_563;
const F: f64 = 1.0 / INV_F;
const E2: f64 = 2.0 * F - F * F;
const B_M: f64 = A_M * (1.0 - F);

/// Compute ellipsoidal height using the better-conditioned ECEF component.
fn stable_height(p: f64, z: f64, latitude: f64, n: f64) -> f64 {
    let sin_lat = latitude.sin();
    let cos_lat = latitude.cos();

    if sin_lat.abs() >= cos_lat.abs() {
        z / sin_lat - n * (1.0 - E2)
    } else {
        p / cos_lat - n
    }
}

#[derive(Debug, Clone, Copy, Error, PartialEq, Eq)]
pub enum GeodesyError {
    #[error("ECEF coordinates must be finite")]
    NonFinite,
    #[error("ECEF origin has no unique geodetic coordinate")]
    Origin,
    #[error("ECEF inverse did not converge within the iteration limit")]
    NoConvergence,
    #[error("geodetic result lies outside the checked coordinate range")]
    InvalidResult,
}

/// Convert ECEF metres to WGS-84 geodetic coordinates using a bounded iteration.
pub fn ecef_to_geodetic(point: EcefPoint) -> Result<GeodeticCoordinate, GeodesyError> {
    let (x, y, z) = (point.x_m, point.y_m, point.z_m);
    if !x.is_finite() || !y.is_finite() || !z.is_finite() {
        return Err(GeodesyError::NonFinite);
    }
    let p = x.hypot(y);
    if !p.is_finite() {
        return Err(GeodesyError::NonFinite);
    }
    if p == 0.0 && z == 0.0 {
        return Err(GeodesyError::Origin);
    }
    let longitude = y.atan2(x).to_degrees();
    if p < 1e-10 {
        let latitude = if z > 0.0 { 90.0 } else { -90.0 };
        let coordinate = GeodeticCoordinate::new(latitude, 0.0, z.abs() - B_M)
            .map_err(|_| GeodesyError::InvalidResult)?;
        return Ok(coordinate);
    }

    let mut latitude = z.atan2(p * (1.0 - E2));
    let mut height = 0.0;
    let mut converged = false;
    for _ in 0..32 {
        let sin_lat = latitude.sin();
        let n = A_M / (1.0 - E2 * sin_lat * sin_lat).sqrt();
        height = stable_height(p, z, latitude, n);
        let next = z.atan2(p * (1.0 - E2 * n / (n + height)));
        if (next - latitude).abs() * A_M < 1e-8 {
            latitude = next;
            // Re-evaluate height using the converged latitude, rather than the
            // previous iterate, so the returned pair is internally consistent.
            let sin_lat = latitude.sin();
            let n = A_M / (1.0 - E2 * sin_lat * sin_lat).sqrt();
            height = stable_height(p, z, latitude, n);
            converged = true;
            break;
        }
        latitude = next;
    }
    if !converged {
        return Err(GeodesyError::NoConvergence);
    }
    GeodeticCoordinate::new(latitude.to_degrees(), longitude, height)
        .map_err(|_| GeodesyError::InvalidResult)
}

#[cfg(test)]
mod tests {
    use super::{ecef_to_geodetic, GeodesyError};
    use crate::geometry::{ecef_wgs84_point, EcefPoint, GeodeticCoordinate};

    #[test]
    fn inverse_round_trips_reference_and_negative_height() {
        for (lat, lon, h) in [
            (0.0, 0.0, 0.0),
            (17.385, 78.4867, -10.0),
            (-42.5, 179.8, 1234.5),
        ] {
            let input = GeodeticCoordinate::new(lat, lon, h).unwrap();
            let output = ecef_to_geodetic(ecef_wgs84_point(input)).unwrap();
            assert!((output.latitude_deg() - lat).abs() < 1e-8);
            let longitude_error = ((output.longitude_deg() - lon + 540.0) % 360.0) - 180.0;
            assert!(longitude_error.abs() < 1e-8);
            assert!((output.height_m() - h).abs() < 1e-4);
        }
    }

    #[test]
    fn handles_axis_and_rejects_invalid_ecef() {
        let north = ecef_to_geodetic(EcefPoint {
            x_m: 0.0,
            y_m: 0.0,
            z_m: 6_356_752.314_245,
        })
        .unwrap();
        assert!((north.latitude_deg() - 90.0).abs() < 1e-12);
        // Check height stability near both polar axes.
        for sign in [1.0, -1.0] {
            let near_axis = ecef_to_geodetic(EcefPoint {
                x_m: 1e-9,
                y_m: 0.0,
                z_m: sign * 6_356_752.314_245,
            })
            .unwrap();

            assert!(
                (near_axis.latitude_deg() - sign * 90.0).abs() < 1e-10,
                "unexpected latitude: {}",
                near_axis.latitude_deg()
            );
            assert!(
                near_axis.height_m().abs() < 1e-3,
                "unexpected near-pole height: {}",
                near_axis.height_m()
            );
        }
        assert_eq!(
            ecef_to_geodetic(EcefPoint {
                x_m: 0.0,
                y_m: 0.0,
                z_m: 0.0
            }),
            Err(GeodesyError::Origin)
        );
        assert_eq!(
            ecef_to_geodetic(EcefPoint {
                x_m: f64::NAN,
                y_m: 0.0,
                z_m: 1.0
            }),
            Err(GeodesyError::NonFinite)
        );
    }
}
