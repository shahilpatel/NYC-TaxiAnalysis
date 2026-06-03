-- 10_era_compare.sql  --  controlled 5-arm longitudinal study.
-- Expresses every arm on the same 263 TLC taxi zones so mode and time are separable:
--   A yellow_2015  legacy taxi, pre-rideshare   (raw lat/long -> spatial join)
--   B green_2015   boro-taxi, outer boroughs    (already zone-level: pickup_location_id)
--   C yellow_2024  legacy taxi today            (zone-level: PULocationID)   <- mode control
--   D fhvhv_2019   early rideshare              (zone-level: PULocationID)
--   E fhvhv_2024   modern rideshare             (zone-level: PULocationID)
-- Period defs match the paper: AM_PEAK 7-9, MIDDAY 10-15, PM_PEAK 16-19, NIGHT else.
--
-- Run:  bq query --use_legacy_sql=false --project_id=pstat135-nyc-taxi < 10_era_compare.sql

CREATE OR REPLACE TABLE `taxi_analysis.zone_centroids` AS
SELECT CAST(zone_id AS INT64) AS zone_id, zone_name, borough,
       ST_Y(ST_CENTROID(zone_geom)) AS lat, ST_X(ST_CENTROID(zone_geom)) AS lon
FROM `bigquery-public-data.new_york_taxi_trips.taxi_zone_geom`
WHERE zone_geom IS NOT NULL;

CREATE TEMP FUNCTION period_of(h INT64) AS (
  CASE WHEN h BETWEEN 7 AND 9 THEN 'AM_PEAK'
       WHEN h BETWEEN 10 AND 15 THEN 'MIDDAY'
       WHEN h BETWEEN 16 AND 19 THEN 'PM_PEAK'
       ELSE 'NIGHT' END);

CREATE OR REPLACE TABLE `taxi_analysis.era_zone_period` AS
WITH
  a_yellow15 AS (
    SELECT 'yellow_2015' AS era, period_of(EXTRACT(HOUR FROM t.pickup_datetime)) AS period,
           CAST(g.zone_id AS INT64) AS zone_id
    FROM `taxi_analysis.cleaned_trips` t
    JOIN `bigquery-public-data.new_york_taxi_trips.taxi_zone_geom` g
      ON ST_CONTAINS(g.zone_geom, ST_GEOGPOINT(t.pickup_lon, t.pickup_lat))
  ),
  b_green15 AS (
    SELECT 'green_2015' AS era, period_of(EXTRACT(HOUR FROM pickup_datetime)) AS period,
           SAFE_CAST(pickup_location_id AS INT64) AS zone_id
    FROM `bigquery-public-data.new_york_taxi_trips.tlc_green_trips_2015`
    WHERE pickup_location_id IS NOT NULL
  ),
  c_yellow24 AS (
    SELECT 'yellow_2024' AS era, period_of(EXTRACT(HOUR FROM tpep_pickup_datetime)) AS period,
           CAST(PULocationID AS INT64) AS zone_id
    FROM `taxi_analysis.yellow_2024`
    WHERE PULocationID IS NOT NULL AND EXTRACT(YEAR FROM tpep_pickup_datetime) = 2024
  ),
  d_fhv19 AS (
    SELECT 'fhvhv_2019' AS era, period_of(EXTRACT(HOUR FROM pickup_datetime)) AS period,
           CAST(PULocationID AS INT64) AS zone_id
    FROM `taxi_analysis.fhvhv_2019`
    WHERE PULocationID IS NOT NULL AND EXTRACT(YEAR FROM pickup_datetime) = 2019
  ),
  e_fhv24 AS (
    SELECT 'fhvhv_2024' AS era, period_of(EXTRACT(HOUR FROM pickup_datetime)) AS period,
           CAST(PULocationID AS INT64) AS zone_id
    FROM `taxi_analysis.fhvhv_2024`
    WHERE PULocationID IS NOT NULL AND EXTRACT(YEAR FROM pickup_datetime) = 2024
  ),
  combined AS (
    SELECT * FROM a_yellow15 UNION ALL SELECT * FROM b_green15 UNION ALL
    SELECT * FROM c_yellow24 UNION ALL SELECT * FROM d_fhv19 UNION ALL SELECT * FROM e_fhv24
  )
SELECT c.era, c.period, c.zone_id, zc.zone_name, zc.borough, zc.lat, zc.lon, COUNT(*) AS trips
FROM combined c
JOIN `taxi_analysis.zone_centroids` zc USING (zone_id)
WHERE c.period IS NOT NULL
GROUP BY 1,2,3,4,5,6,7;
