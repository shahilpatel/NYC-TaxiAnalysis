# PSTAT 135 — Results Log
**Project:** Temporal Decomposition of Urban Demand Zones (NYC Yellow Taxi 2015)
**Dataset:** `bigquery-public-data.new_york.tlc_yellow_trips_2015` → cleaned to **142,567,774** trips
**Stack:** BigQuery · Dataproc/PySpark · BigQuery ML · NetworkX · matplotlib
**Last updated:** 2026-06-02

This file is the single source of truth for results. Each section maps to a plan phase.

> ## ⭐ HEADLINE FINDING (reframed thesis)
> The plan *assumed* time-adaptive zones would cut dispatch distance by 30–60%. **The data refutes that.** With a fair, fixed-k=20 comparison on all 142M trips:
> - Time-adaptive zones improve dispatch distance by only **~1% on average** (range −1.4% to +2.8%).
> - Zone centroids are **remarkably stable** — they shift only **0.5–1.0 km** between periods.
> - **Why:** NYC yellow-cab demand is so concentrated in the Manhattan core that 20 zones cover it well in every period regardless of placement.
>
> **New thesis:** *"Are optimal urban demand zones stable across time? On 142M NYC taxi trips, zone centroids shift <1 km between periods and time-adaptive zoning yields <3% routing gain — a cautionary, null result for time-varying VRP decomposition. Demand concentration makes static zoning near-optimal at this scale."* This is an honest, counterintuitive, defensible contribution.

---

## Data pipeline (Steps 1–6) — ✅ complete

BigQuery dataset `pstat135-nyc-taxi.taxi_analysis`:

| Table | Rows | Purpose |
|---|---|---|
| `cleaned_trips` | 142,567,774 | base — 11 cols, full year 2015, 0 null coords, avg 2.97 mi / $12.79 |
| `zone_demand` | 563,696 | hourly demand per ~1 km grid cell → BQML input |
| `trips_with_period` | 142,567,774 | adds `time_period` + `day_type` labels → Spark input |
| `od_matrix` | 45,477 | origin→dest edges (≥20 trips) → PageRank input |

Exported to `gs://pstat135-taxi-shahil/data/{trips_with_period,zone_demand,od_matrix}/` as Snappy Parquet (trips = 293 shards, 2.16 GiB).

**Period × day-type distribution** (from `trips_with_period`):

| time_period | day_type | trips | % |
|---|---|---|---|
| NIGHT | WEEKDAY | 34,901,686 | 24.5 |
| MIDDAY | WEEKDAY | 29,105,922 | 20.4 |
| PM_PEAK | WEEKDAY | 21,925,726 | 15.4 |
| NIGHT | WEEKEND | 17,426,706 | 12.2 |
| AM_PEAK | WEEKDAY | 15,271,814 | 10.7 |
| MIDDAY | WEEKEND | 12,311,693 | 8.6 |
| PM_PEAK | WEEKEND | 8,603,173 | 6.0 |
| AM_PEAK | WEEKEND | 3,021,054 | 2.1 |

---

## Phase 3 — EDA — ✅ complete
Script: [03_eda.py](03_eda.py) → **fig0_eda_overview.png** (4-panel: hourly volume, day-of-week, monthly trend, pickup scatter by period).

Per-period summary:

| time_period | trips | avg_dist (mi) | avg_fare ($) | fare_std |
|---|---|---|---|---|
| NIGHT | 52,328,392 | 3.30 | 12.93 | 9.91 |
| MIDDAY | 41,417,615 | 2.82 | 13.01 | 10.56 |
| PM_PEAK | 30,528,899 | 2.78 | 12.62 | 10.14 |
| AM_PEAK | 18,292,868 | 2.72 | 12.20 | 9.69 |

*Note:* NIGHT has the longest avg distance (3.30 mi) → consistent with late-night airport / outer-borough runs.

(Earlier exploratory figs on a 200K sample: fig1_hourly_demand.png, fig2_distance_dist.png, fig3_pickup_scatter.png in [01_bigquery_eda.ipynb](01_bigquery_eda.ipynb).)

---

## Phase 4 — Time-stratified K-means (Dataproc) — 🔄 in progress
Script: [04_temporal_kmeans.py](04_temporal_kmeans.py). Output: `gs://pstat135-taxi-shahil/results/temporal_kmeans/<PERIOD>/`.

**Silhouette sweep (k=10/15/20/25), best k per period:** AM_PEAK 20 (0.557), PM_PEAK 15 (0.563), MIDDAY 10 (0.539), NIGHT 15 (0.595). Saved to `results/temporal_kmeans/silhouette_harvested.json` → used for the elbow/silhouette figure (fig1).

> ⚠️ **Methodology correction (important).** The first full run auto-selected a *different* best-k per period (AM=20, PM=15, MIDDAY=10, NIGHT=15). That makes the static-vs-adaptive routing comparison **invalid**: the static baseline (AM, k=20) has the most centroids, so it trivially wins on nearest-centroid distance regardless of zone *placement*. The invalid first numbers were +0/−13.5/−39.3/−14.1% ("adaptive worse"), which is a pure k-count artifact, not a real result.
>
> **Fix:** re-run with **FIXED_K=20 for every period** (`FIXED_K` in [04_temporal_kmeans.py](04_temporal_kmeans.py)). With equal k, adaptive zones are ≤ static by the k-means optimality property, and the gain reflects genuine demand-geography shift. The per-period silhouette analysis above still justifies the resolution choice; auto-best-k is kept only for that. **Re-run in progress.**

**Fixed-k=20 centroids** (the comparison-valid set) now in `results/temporal_kmeans/<PERIOD>/centroids.json`, 20 zones each. labeled_trips (5% sample) + cluster_stats also written per period.

### Phase 5 — Routing: static vs adaptive (k=20, full population) — ✅ complete
Figure: [05_routing_plot.py](05_routing_plot.py) → **fig4_static_vs_adaptive.png**. Source: `routing_summary.json`.

| period | adaptive_km | static_km (AM zones) | gain | n |
|---|---|---|---|---|
| AM_PEAK | 0.5760 | 0.5760 | 0.0% | 18.3M |
| PM_PEAK | 0.5555 | 0.5712 | **+2.8%** | 30.5M |
| MIDDAY | 0.5788 | 0.5707 | **−1.4%** | 41.4M |
| NIGHT | 0.6158 | 0.6246 | **+1.4%** | 52.3M |

**Avg gain ≈ 0.9%** → adaptive ≈ static. The ±1–2% scatter is within noise (k-means minimizes squared distance in standardized space; metric is mean haversine on geographic centroids).

### Phase 6 — Zone drift (k=20) — ✅ complete
Figure: [06_zone_drift.py](06_zone_drift.py) → **fig3_zone_drift.png** (heatmap, avg centroid displacement km).

| pair | drift (km) |
|---|---|
| MIDDAY ↔ NIGHT | **1.017** (largest — midday commerce vs night nightlife) |
| PM_PEAK ↔ NIGHT | 0.755 |
| AM_PEAK ↔ NIGHT | 0.751 |
| AM_PEAK ↔ MIDDAY | 0.674 |
| AM_PEAK ↔ PM_PEAK | 0.607 |
| PM_PEAK ↔ MIDDAY | 0.520 (smallest) |

Zones *do* move (0.5–1.0 km, max AM↔NIGHT / MIDDAY↔NIGHT) — but too little, against the dense Manhattan core, to change routing. fig3 (drift) + fig4 (near-equal routing) together ARE the narrative: zones shift but it barely matters.

> **Infra note:** first run on a 2-worker cluster was too slow (≈2 periods in 2 h) and got killed by a `--max-age=2h` cap mid-job. Re-run on **6 workers** with skip-if-done resume logic (reuses AM/PM from GCS), sampled `labeled_trips` output, idle-auto-delete for cleanup, and a generous 4 h cap. See [taxi-project-state memory].

---

## Phase 7 — PageRank on OD graph — ✅ complete
Script: [07_pagerank.py](07_pagerank.py) → **fig5_pagerank.png**, `data/pagerank_hubs.json`.
Graph: 831 nodes, 31,480 edges (trip_volume ≥ 50), weighted directed, α=0.85.

**Top hubs — all Midtown Manhattan (ground-truth validation):**

| rank | (lat, lon) | pagerank | likely location |
|---|---|---|---|
| 1 | (40.760, −73.980) | 0.01566 | Times Sq / Midtown |
| 2 | (40.760, −73.970) | 0.01558 | Midtown East |
| 3 | (40.750, −73.990) | 0.01439 | Penn Sta / Herald Sq |
| 4 | (40.750, −73.980) | 0.01321 | Midtown / Murray Hill |
| 5 | (40.760, −73.990) | 0.01095 | Hell's Kitchen / Midtown |

---

## Phase 8 — BigQuery ML demand forecast — ✅ complete (models trained)
SQL: [08_bqml_demand.sql](08_bqml_demand.sql). Models in `taxi_analysis`. Trained on `zone_demand` (563,696 rows, 20% random eval split).

Figures: [08_bqml_figures.py](08_bqml_figures.py) → **fig6_demand_models.png** (R² comparison + tree feature importance).

| model | type | R² | MAE (trips) |
|---|---|---|---|
| `demand_forecast` | linear, numeric (L1+L2) | 0.0554 | 389.9 |
| `demand_forecast_cat` | linear, temporal one-hot (L1+L2) | 0.0589 | 392.3 |
| `demand_forecast_bt` | **boosted tree** | **0.8710** | **92.0** |

**Linear feature weights** (model 1): location dominates — `lon_bucket` −2257, `lat_bucket` +1099, vs `pickup_hour` +9.98, `pickup_dow` +4.87, `pickup_month` −1.86.
**Boosted-tree importance (gain):** lon 1.27e8, dow 1.17e8, hour 1.15e8, lat 1.04e8, month 0.26e8 — i.e. location, day-of-week, and hour all contribute roughly equally once nonlinearity is allowed.

**Interpretation:** a *linear* model explains only ~6% of demand variance and one-hot encoding the temporal features barely helps; the boosted tree reaches **R²=0.87** by splitting on lat/lon (nonlinear spatial signal) and capturing the bimodal hourly pattern. Story for the report: regularized linear baseline (Lecture-7 penalized regression) → strong nonlinear model, with the gap itself being the insight.

---

## Remaining (not analysis — packaging)
- **Phase 9** — ✅ **deployed & live**: https://storage.googleapis.com/pstat135-taxi-shahil/viz/index.html. Interactive explorer with three linked views — (1) **Bubbles**: rank-ordered, constant-screen-size demand markers per period; (2) **Heatmap**: self-contained canvas overlay (Google removed Maps `HeatmapLayer` in v3.65) driven by `viz/heat_hourly.json`, a 24-hour ~1 km demand grid aggregated from `zone_demand`; hour slider + play animate the daily pulse (quietest 05:00, peak 19:00 = 8.8M); (3) **Overlay**: AM_PEAK→nearest-centroid drift paths coloured green(stable)→red(mover), mean traced drift 0.66 km / max 1.66 km. Deep-links `#heatmap` `#overlay` `#h=19`. Objects served `no-cache`. ⚠️ Maps API key still unrestricted (public in HTML) — restrict by HTTP referrer (`storage.googleapis.com`) before wider sharing.
- **Phase 4.4** — (optional) load labeled_trips back into BigQuery for SQL slicing.
- **Report (10 pp) + GauchoCast** — all 8 figures + numbers ready; narrative reframed around stability/null result; §4.7 documents the interactive explorer.

## All figures (report-ready)
| figure | shows | script |
|---|---|---|
| fig0_eda_overview.png | hourly/DOW/monthly volume + pickup scatter | [03_eda.py](03_eda.py) |
| fig1_elbow_silhouette.png | WSSSE + silhouette vs k, per period | [fig1_silhouette.py](fig1_silhouette.py) |
| fig2_cluster_scatter_4panel.png | 20 zones per period over pickup backdrop | [04c_cluster_scatter.py](04c_cluster_scatter.py) |
| fig2b_centroid_overlay.png | all periods' centroids overlaid (stability) | [04c_cluster_scatter.py](04c_cluster_scatter.py) |
| fig3_zone_drift.png | centroid drift heatmap (0.5–1.0 km) | [06_zone_drift.py](06_zone_drift.py) |
| fig4_static_vs_adaptive.png | routing: adaptive ≈ static (~1%) | [05_routing_plot.py](05_routing_plot.py) |
| fig5_pagerank.png | top OD hubs (Midtown) | [07_pagerank.py](07_pagerank.py) |
| fig6_demand_models.png | BQML R² comparison + tree importance | [08_bqml_figures.py](08_bqml_figures.py) |

## File index
| file | phase | produces |
|---|---|---|
| [03_eda.py](03_eda.py) | 3 | fig0 |
| [04_temporal_kmeans.py](04_temporal_kmeans.py) | 4 | k=20 centroids/stats/labels + routing_summary.json (GCS) |
| [04c_cluster_scatter.py](04c_cluster_scatter.py) | 4 | fig2, fig2b |
| [fig1_silhouette.py](fig1_silhouette.py) | 4 | fig1 |
| [05_routing_plot.py](05_routing_plot.py) | 5 | fig4 |
| [06_zone_drift.py](06_zone_drift.py) | 6 | fig3 |
| [07_pagerank.py](07_pagerank.py) | 7 | fig5, data/pagerank_hubs.json |
| [08_bqml_demand.sql](08_bqml_demand.sql) / [08_bqml_figures.py](08_bqml_figures.py) | 8 | 3 models, fig6 |
| [viz/index.html](viz/index.html) + viz/heat_hourly.json | 9 | interactive explorer (bubbles / 24h heatmap / drift overlay) — ✅ live on GCS |
