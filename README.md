# NYC Taxi Demand Zone Stability — PSTAT 135 Final Project

Analysis of whether taxi dispatch zones are stable across the day, and whether that changed with the arrival of rideshare. Uses 142M+ 2015 NYC yellow taxi trips and extends the comparison to 2024 Uber/Lyft data.

**Live interactive map:** https://storage.googleapis.com/pstat135-taxi-shahil/viz/index.html

## The question

If a taxi company fixed its 20 dispatch zones at, say, 8am and used them all day, how much efficiency would it lose compared to zones tuned per time period? The answer for 2015 yellow taxis is almost nothing (~0.2%). The follow-up: does that change with Uber/Lyft, whose demand spreads across all five boroughs instead of concentrating in Manhattan?

## Results

| Arm | Rides | Manhattan % | Adaptive gain |
|-----|-------|-------------|---------------|
| Yellow 2015 | 142M | 92% | +0.2% |
| Green 2015 | 19M | 28% | +7.5% |
| Yellow 2024 | 41M | 89% | +9.1% |
| Uber/Lyft 2019 | 44M | 44% | +4.3% |
| Uber/Lyft 2024 | 240M | 39% | −1.5% |

The relationship is non-monotone. Adaptive zoning helps when demand is **time-volatile** (concentrated but shifting through the day), not just when it's spatially dispersed. Uber/Lyft 2024 is so uniformly distributed that static zones already work fine.

## Structure

```
04_temporal_kmeans.py     PySpark job — K-means clustering on Dataproc
05_routing_plot.py        static vs adaptive routing distance
06_zone_drift.py          inter-period centroid displacement
07_pagerank.py            zone-to-zone flow PageRank
08_bqml_demand.sql        BigQuery ML demand forecasting
08_bqml_figures.py        figures from BQML results
10_era_compare.sql        5-arm aggregation across 263 TLC zones
11_era_cluster_compare.py weighted k-means + drift + routing gain for all 5 arms
run_era_pipeline.sh       loads BQ tables, runs SQL, exports, runs analysis
viz/index.html            interactive Google Maps explorer
```

Figures `figA`–`figD` correspond to the 5-arm study (§4.8 in the report). Figures `fig0`–`fig6` are from the original 2015 analysis.

## Setup

Requires a GCP project with BigQuery access. Set your service account key:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

Python dependencies: `google-cloud-bigquery`, `pyspark`, `numpy`, `pandas`, `matplotlib`.

The Dataproc job (`04_temporal_kmeans.py`) runs on a 5-node cluster. All other scripts run locally against BigQuery.

## Data

Raw data lives in GCS (`gs://pstat135-taxi-shahil/`). The 2015 yellow taxi dataset is from [NYC TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). 2024 HVFHV data was downloaded from the same source. Green 2015 is available as a BigQuery public dataset.
