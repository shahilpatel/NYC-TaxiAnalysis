-- ============================================================================
-- 08_bqml_demand.sql  -- Phase 8: BigQuery ML demand forecasting
-- Predict hourly trip_count per spatial grid cell from the zone_demand table.
-- Three models trained for comparison (run top to bottom in the BQ console or
-- via `bq query --use_legacy_sql=false`):
--   1. demand_forecast      regularized linear, numeric features (plan baseline)
--   2. demand_forecast_cat  regularized linear, temporal features one-hot encoded
--   3. demand_forecast_bt   boosted-tree regressor (captures spatial nonlinearity)
--
-- RESULTS (2026-06-02, zone_demand = 563,696 rows):
--   model                 r2_score   MAE(trips)
--   1 linear_numeric       0.0554      389.9
--   2 linear_categorical   0.0589      392.3
--   3 boosted_tree         <see RESULTS.md>
-- Takeaway: a LINEAR model explains ~6% of demand variance; one-hot encoding the
-- temporal features barely helps -> the signal is spatial + highly skewed, which
-- the tree model captures by splitting on lat/lon. The regularized linear model
-- (l1_reg/l2_reg) is retained for the Lecture-7 penalized-regression connection.
-- ============================================================================

-- 1. Regularized linear, numeric features (Lasso + Ridge -> Lecture 7) ---------
CREATE OR REPLACE MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast`
OPTIONS(
  model_type = 'linear_reg',
  input_label_cols = ['trip_count'],
  data_split_method = 'random',
  data_split_eval_fraction = 0.2,
  l1_reg = 0.1,   -- Lasso
  l2_reg = 0.1    -- Ridge
) AS
SELECT pickup_hour, pickup_dow, pickup_month, lat_bucket, lon_bucket, trip_count
FROM `pstat135-nyc-taxi.taxi_analysis.zone_demand`;

-- 2. Regularized linear, temporal features one-hot encoded (CAST to STRING) -----
CREATE OR REPLACE MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast_cat`
OPTIONS(
  model_type = 'linear_reg',
  input_label_cols = ['trip_count'],
  data_split_method = 'random',
  data_split_eval_fraction = 0.2,
  l1_reg = 0.1, l2_reg = 0.1
) AS
SELECT CAST(pickup_hour AS STRING) AS hour, CAST(pickup_dow AS STRING) AS dow,
       CAST(pickup_month AS STRING) AS month, lat_bucket, lon_bucket, trip_count
FROM `pstat135-nyc-taxi.taxi_analysis.zone_demand`;

-- 3. Boosted-tree regressor (nonlinear; splits on lat/lon) ----------------------
CREATE OR REPLACE MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast_bt`
OPTIONS(
  model_type = 'BOOSTED_TREE_REGRESSOR',
  input_label_cols = ['trip_count'],
  data_split_method = 'random',
  data_split_eval_fraction = 0.2,
  max_iterations = 50, learn_rate = 0.1, subsample = 0.8
) AS
SELECT pickup_hour, pickup_dow, pickup_month, lat_bucket, lon_bucket, trip_count
FROM `pstat135-nyc-taxi.taxi_analysis.zone_demand`;

-- Evaluation ------------------------------------------------------------------
SELECT '1_linear_numeric' AS model, * FROM ML.EVALUATE(MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast`);
SELECT '2_linear_categorical' AS model, * FROM ML.EVALUATE(MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast_cat`);
SELECT '3_boosted_tree' AS model, * FROM ML.EVALUATE(MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast_bt`);

-- Feature importance ----------------------------------------------------------
-- Linear model: signed weights
SELECT processed_input, weight
FROM ML.WEIGHTS(MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast`)
ORDER BY ABS(weight) DESC;
-- Boosted tree: gain-based importance
SELECT * FROM ML.FEATURE_IMPORTANCE(MODEL `pstat135-nyc-taxi.taxi_analysis.demand_forecast_bt`)
ORDER BY importance_gain DESC;
