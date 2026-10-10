//! Deterministic latitude/longitude grid index for point-radius queries.
//!
//! Radius distances use a spherical mean-Earth approximation. This module is a
//! candidate-generation/index primitive, not an ellipsoidal geodesic solver.

use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

const EARTH_MEAN_RADIUS_M: f64 = 6_371_008.8;
const FULL_CIRCLE_M: f64 = 2.0 * std::f64::consts::PI * EARTH_MEAN_RADIUS_M;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GeoPoint {
    latitude_deg: f64,
    longitude_deg: f64,
}

impl GeoPoint {
    pub fn new(latitude_deg: f64, longitude_deg: f64) -> Result<Self, SpatialError> {
        if !latitude_deg.is_finite() || !(-90.0..=90.0).contains(&latitude_deg) {
            return Err(SpatialError::InvalidCoordinate);
        }
        if !longitude_deg.is_finite() || !(-180.0..=180.0).contains(&longitude_deg) {
            return Err(SpatialError::InvalidCoordinate);
        }
        Ok(Self {
            latitude_deg,
            longitude_deg,
        })
    }

    pub const fn latitude_deg(self) -> f64 {
        self.latitude_deg
    }
    pub const fn longitude_deg(self) -> f64 {
        self.longitude_deg
    }
}

#[derive(Debug, Clone, Copy, Error, PartialEq, Eq)]
pub enum SpatialError {
    #[error("coordinate must be finite with latitude in [-90,90] and longitude in [-180,180]")]
    InvalidCoordinate,
    #[error("cell size must be finite and in [0.01, 180]")]
    InvalidCellSize,
    #[error("point identifier must not be blank")]
    BlankId,
    #[error("radius must be finite and non-negative")]
    InvalidRadius,
}

#[derive(Debug, Clone)]
pub struct SpatialGridIndex {
    cell_degrees: f64,
    latitude_cells: i32,
    longitude_cells: i32,
    cells: BTreeMap<(i32, i32), BTreeSet<String>>,
    points: BTreeMap<String, GeoPoint>,
}

impl SpatialGridIndex {
    pub fn new(cell_degrees: f64) -> Result<Self, SpatialError> {
        if !cell_degrees.is_finite() || cell_degrees < 0.01 || cell_degrees > 180.0 {
            return Err(SpatialError::InvalidCellSize);
        }
        let latitude_cells = (180.0 / cell_degrees).ceil() as i32;
        let longitude_cells = (360.0 / cell_degrees).ceil() as i32;
        Ok(Self {
            cell_degrees,
            latitude_cells,
            longitude_cells,
            cells: BTreeMap::new(),
            points: BTreeMap::new(),
        })
    }

    fn cell(&self, point: GeoPoint) -> (i32, i32) {
        let lat = (((point.latitude_deg + 90.0) / self.cell_degrees).floor() as i32)
            .clamp(0, self.latitude_cells - 1);
        let lon = (((point.longitude_deg + 180.0) / self.cell_degrees).floor() as i32)
            .rem_euclid(self.longitude_cells);
        (lat, lon)
    }

    pub fn insert(&mut self, id: &str, point: GeoPoint) -> Result<(), SpatialError> {
        let id = id.trim();
        if id.is_empty() {
            return Err(SpatialError::BlankId);
        }
        self.remove(id);
        let cell = self.cell(point);
        self.cells.entry(cell).or_default().insert(id.to_owned());
        self.points.insert(id.to_owned(), point);
        Ok(())
    }

    pub fn remove(&mut self, id: &str) -> bool {
        let id = id.trim();
        if id.is_empty() {
            return false;
        }
        let Some(point) = self.points.remove(id) else {
            return false;
        };
        let cell = self.cell(point);
        if let Some(ids) = self.cells.get_mut(&cell) {
            ids.remove(id);
            if ids.is_empty() {
                self.cells.remove(&cell);
            }
        }
        true
    }

    pub fn len(&self) -> usize {
        self.points.len()
    }
    pub fn is_empty(&self) -> bool {
        self.points.is_empty()
    }

    fn extend_row(&self, row: i32, candidate_ids: &mut BTreeSet<String>) {
        for (_, ids) in self.cells.range((row, 0)..=(row, self.longitude_cells - 1)) {
            candidate_ids.extend(ids.iter().cloned());
        }
    }

    pub fn query_radius(
        &self,
        center: GeoPoint,
        radius_m: f64,
    ) -> Result<Vec<(String, f64)>, SpatialError> {
        if !radius_m.is_finite() || radius_m < 0.0 {
            return Err(SpatialError::InvalidRadius);
        }
        let mut candidate_ids = BTreeSet::new();
        if radius_m >= FULL_CIRCLE_M / 2.0 {
            candidate_ids.extend(self.points.keys().cloned());
        } else {
            let angular = radius_m / EARTH_MEAN_RADIUS_M;
            let latitude_delta = angular.to_degrees();
            let min_lat = (center.latitude_deg - latitude_delta).max(-90.0);
            let max_lat = (center.latitude_deg + latitude_delta).min(90.0);
            let min_row = (((min_lat + 90.0) / self.cell_degrees).floor() as i32)
                .clamp(0, self.latitude_cells - 1);
            let max_row = (((max_lat + 90.0) / self.cell_degrees).floor() as i32)
                .clamp(0, self.latitude_cells - 1);
            for row in min_row..=max_row {
                // Use the most polar boundary of this cell to derive a
                // conservative longitude span. A cell-center estimate can
                // under-fetch valid candidates near the poles.
                let row_min_lat = (-90.0 + row as f64 * self.cell_degrees).max(-90.0);
                let row_max_lat = (-90.0 + (row as f64 + 1.0) * self.cell_degrees).min(90.0);
                let max_abs_lat = row_min_lat.abs().max(row_max_lat.abs());
                let cos_lat = max_abs_lat.to_radians().cos().abs();
                let all_longitudes = angular >= std::f64::consts::FRAC_PI_2
                    || cos_lat < 1e-9
                    || (angular.sin() / cos_lat) >= 1.0;
                if all_longitudes {
                    self.extend_row(row, &mut candidate_ids);
                } else {
                    let delta_lon =
                        (angular.sin() / cos_lat).asin().to_degrees() + self.cell_degrees;
                    let min_lon = center.longitude_deg - delta_lon;
                    let max_lon = center.longitude_deg + delta_lon;
                    if delta_lon >= 180.0 {
                        self.extend_row(row, &mut candidate_ids);
                    } else {
                        let first = (((min_lon + 180.0) / self.cell_degrees).floor() as i32)
                            .rem_euclid(self.longitude_cells);
                        let last = (((max_lon + 180.0) / self.cell_degrees).floor() as i32)
                            .rem_euclid(self.longitude_cells);
                        let mut col = first;
                        loop {
                            if let Some(ids) = self.cells.get(&(row, col)) {
                                candidate_ids.extend(ids.iter().cloned());
                            }
                            if col == last {
                                break;
                            }
                            col = (col + 1).rem_euclid(self.longitude_cells);
                        }
                    }
                }
            }
        }
        let mut output: Vec<(String, f64)> = candidate_ids
            .into_iter()
            .filter_map(|id| {
                let point = self.points.get(&id)?;
                let distance = haversine_m(center, *point);
                (distance <= radius_m + 1e-7).then_some((id, distance))
            })
            .collect();
        output.sort_by(|a, b| a.1.total_cmp(&b.1).then_with(|| a.0.cmp(&b.0)));
        Ok(output)
    }
}

pub fn haversine_m(first: GeoPoint, second: GeoPoint) -> f64 {
    let lat1 = first.latitude_deg.to_radians();
    let lat2 = second.latitude_deg.to_radians();
    let dlat = lat2 - lat1;
    let dlon = (second.longitude_deg - first.longitude_deg).to_radians();
    let sin_lat = (dlat / 2.0).sin();
    let sin_lon = (dlon / 2.0).sin();
    let a = (sin_lat * sin_lat + lat1.cos() * lat2.cos() * sin_lon * sin_lon).clamp(0.0, 1.0);
    2.0 * EARTH_MEAN_RADIUS_M * a.sqrt().atan2((1.0 - a).sqrt())
}

#[cfg(test)]
mod tests {
    use super::{haversine_m, GeoPoint, SpatialGridIndex};

    #[test]
    fn radius_query_is_sorted_and_handles_antimeridian() {
        let mut index = SpatialGridIndex::new(1.0).unwrap();
        index
            .insert("east", GeoPoint::new(0.0, 179.9).unwrap())
            .unwrap();
        index
            .insert("west", GeoPoint::new(0.0, -179.9).unwrap())
            .unwrap();
        index
            .insert("far", GeoPoint::new(0.0, 170.0).unwrap())
            .unwrap();
        let results = index
            .query_radius(GeoPoint::new(0.0, 180.0).unwrap(), 30_000.0)
            .unwrap();
        assert_eq!(
            results.iter().map(|v| v.0.as_str()).collect::<Vec<_>>(),
            vec!["east", "west"]
        );
    }

    #[test]
    fn radius_query_is_conservative_near_the_poles() {
        let mut index = SpatialGridIndex::new(1.0).unwrap();
        let center = GeoPoint::new(89.9, 0.0).unwrap();
        // At this latitude, four degrees of longitude is less than 1 km on
        // the mean-radius sphere. A cell-center-only longitude bound can miss it.
        let nearby = GeoPoint::new(89.9, 4.0).unwrap();
        index.insert("near-polar", nearby).unwrap();
        let results = index.query_radius(center, 1_000.0).unwrap();
        assert_eq!(
            results
                .iter()
                .map(|entry| entry.0.as_str())
                .collect::<Vec<_>>(),
            vec!["near-polar"]
        );
    }

    #[test]
    fn grid_queries_match_brute_force_for_representative_global_points() {
        use std::collections::BTreeSet;

        let latitudes = [-89.9, -85.0, -45.0, 0.0, 45.0, 85.0, 89.9];
        let longitudes = [-179.9, -179.0, -90.0, 0.0, 90.0, 179.0, 179.9];
        let mut index = SpatialGridIndex::new(1.0).unwrap();
        let mut all = Vec::new();
        for (i, latitude) in latitudes.iter().enumerate() {
            for (j, longitude) in longitudes.iter().enumerate() {
                let id = format!("p-{i}-{j}");
                let point = GeoPoint::new(*latitude, *longitude).unwrap();
                index.insert(&id, point).unwrap();
                all.push((id, point));
            }
        }

        for center_latitude in latitudes {
            for center_longitude in longitudes {
                let center = GeoPoint::new(center_latitude, center_longitude).unwrap();
                for radius in [1_000.0, 100_000.0, 1_000_000.0, 15_000_000.0, 20_000_000.0] {
                    let actual: BTreeSet<String> = index
                        .query_radius(center, radius)
                        .unwrap()
                        .into_iter()
                        .map(|(id, _)| id)
                        .collect();
                    let expected: BTreeSet<String> = all
                        .iter()
                        .filter(|(_, point)| haversine_m(center, *point) <= radius + 1e-7)
                        .map(|(id, _)| id.clone())
                        .collect();
                    assert_eq!(
                        actual, expected,
                        "center=({center_latitude},{center_longitude}), radius={radius}"
                    );
                }
            }
        }
    }

    #[test]
    fn rejects_pathologically_small_grid_cells() {
        assert!(matches!(
            SpatialGridIndex::new(0.009),
            Err(super::SpatialError::InvalidCellSize)
        ));
        assert!(SpatialGridIndex::new(0.01).is_ok());
        assert!(SpatialGridIndex::new(180.0).is_ok());
    }

    #[test]
    fn non_divisor_grid_cells_preserve_radius_query_completeness() {
        use std::collections::BTreeSet;

        let points = vec![
            ("east".to_owned(), GeoPoint::new(0.0, 179.9).unwrap()),
            ("west".to_owned(), GeoPoint::new(0.0, -179.9).unwrap()),
            (
                "positive-seam".to_owned(),
                GeoPoint::new(0.0, 180.0).unwrap(),
            ),
            (
                "negative-seam".to_owned(),
                GeoPoint::new(0.0, -180.0).unwrap(),
            ),
            ("north-east".to_owned(), GeoPoint::new(45.0, 179.9).unwrap()),
            (
                "north-west".to_owned(),
                GeoPoint::new(45.0, -179.9).unwrap(),
            ),
            (
                "south-west".to_owned(),
                GeoPoint::new(-45.0, -179.9).unwrap(),
            ),
            ("far-east".to_owned(), GeoPoint::new(0.0, 170.0).unwrap()),
            ("far-west".to_owned(), GeoPoint::new(0.0, -170.0).unwrap()),
        ];

        let mut index = SpatialGridIndex::new(7.0).unwrap();
        for (id, point) in &points {
            index.insert(id, *point).unwrap();
        }

        for (latitude, longitude) in [(0.0, 179.8), (0.0, -179.8), (45.0, 179.5), (-45.0, -179.5)] {
            let center = GeoPoint::new(latitude, longitude).unwrap();

            for radius in [0.0, 25_000.0, 100_000.0, 1_000_000.0, 6_000_000.0] {
                let actual: BTreeSet<String> = index
                    .query_radius(center, radius)
                    .unwrap()
                    .into_iter()
                    .map(|(id, _)| id)
                    .collect();

                let expected: BTreeSet<String> = points
                    .iter()
                    .filter(|(_, point)| haversine_m(center, *point) <= radius + 1e-7)
                    .map(|(id, _)| id.clone())
                    .collect();

                assert_eq!(
                    actual, expected,
                    "center=({latitude},{longitude}), radius={radius}"
                );
            }
        }
    }

    #[test]
    fn replacing_and_removing_identifier_keeps_index_consistent() {
        let mut index = SpatialGridIndex::new(2.0).unwrap();
        index
            .insert("site", GeoPoint::new(0.0, 0.0).unwrap())
            .unwrap();
        index
            .insert("site", GeoPoint::new(20.0, 20.0).unwrap())
            .unwrap();
        assert_eq!(index.len(), 1);
        assert!(index
            .query_radius(GeoPoint::new(0.0, 0.0).unwrap(), 1.0)
            .unwrap()
            .is_empty());
        assert!(index.remove(" site "));
        assert!(!index.remove("site"));
    }
}
