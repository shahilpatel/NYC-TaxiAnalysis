# Are Urban Demand Zones Stable? Distributed Spatial Clustering of 142 Million NYC Taxi Trips on Google Cloud

**PSTAT 135 Final Project — Shahil ([shahil@ucsb.edu](mailto:shahil@ucsb.edu))**
**Dataset:** `bigquery-public-data.new_york.tlc_yellow_trips_2015` · **Stack:** BigQuery · Dataproc/PySpark · BigQuery ML · NetworkX

---

## Abstract

Vehicle-routing problems (VRP) are NP-hard, but a common tractable heuristic decomposes a city into demand *zones* and routes within each. A natural hypothesis in operations research is that these zones should be **time-adaptive** — re-optimized for each operational period — because demand geography shifts between morning rush, midday, evening rush, and night. We test this hypothesis empirically at scale: 142,567,774 cleaned 2015 NYC yellow-taxi trips, clustered with distributed K-means (Apache Spark on Google Cloud Dataproc) into 20 zones for each of four time periods, with a full-population routing simulation comparing static vs. time-adaptive zoning. **Contrary to the hypothesis, we find that optimal zones are remarkably stable:** centroids shift only 0.5–1.0 km between periods, and time-adaptive zoning reduces mean dispatch distance by only ~1% (range −1.4% to +2.8%) versus a fixed design. The cause is demand concentration — NYC yellow-cab pickups are so dominated by the Manhattan core that 20 zones cover them well in every period. We complement this with PageRank hub analysis (validating Midtown as the network center) and BigQuery ML demand forecasting (a regularized linear model reaches R²=0.06, a boosted tree R²=0.87). The result is a cautionary, empirically-grounded counterpoint to the assumption that temporal zone adaptation yields large routing gains.

---

## 1. Introduction

Urban logistics and ride-dispatch operations rest on the vehicle-routing problem, which is NP-hard in general. A standard engineering response is **zone decomposition**: partition the service area into a small number of zones, assign vehicles to zones, and solve a far smaller routing problem within each. The quality of this decomposition hinges on where the zones are placed.

It is widely assumed that good zones must be **time-adaptive** — that the partition optimal for the 8 a.m. Financial District commute is wasteful at 2 a.m. when demand migrates to nightlife districts. If true, this motivates time-varying VRP decomposition and dynamic dispatch. **This project asks whether that assumption actually holds for a real, large-scale demand dataset**, and quantifies the routing efficiency at stake.

Our contribution is threefold:
1. A reproducible, fully cloud-native pipeline that clusters 142M trips with distributed K-means — an analysis infeasible on a single machine.
2. A fair, full-population routing simulation (fixed number of zones) measuring the dispatch-distance gain of adaptive vs. static zoning.
3. An honest, somewhat counterintuitive finding: **zones are stable and adaptivity buys almost nothing** for this dataset, with a clear structural explanation.

---

## 2. Data

**Source.** `bigquery-public-data.new_york.tlc_yellow_trips_2015`, the NYC Taxi & Limousine Commission trip records. 2015 is the last full year of peak yellow-cab dominance before ride-hailing structurally reduced demand, and the highest-volume year with raw pickup/dropoff latitude-longitude (later years publish only zone IDs, which would preclude true spatial clustering).

**Cleaning.** We retained trips within an NYC bounding box (lat 40.5–40.9, lon −74.3 to −73.7 for both pickup and dropoff), fares \$2.50–\$100, and trip distance 0.1–50 mi, yielding **142,567,774 trips** (Jan 1 – Dec 31 2015; 0 null coordinates; mean 2.97 mi, \$12.79). The cleaned table is 11 columns.

**Derived tables (BigQuery SQL).** `zone_demand` (563,696 rows — hourly demand per ~1 km grid cell), `trips_with_period` (142.5M rows, adds `time_period` and `day_type` labels), `od_matrix` (45,477 origin→destination edges with ≥20 trips).

**Time periods.** AM_PEAK (7–9 a.m.), MIDDAY (10 a.m.–3 p.m.), PM_PEAK (4–7 p.m.), NIGHT (8 p.m.–6 a.m.). Distribution by volume (Fig. 0): NIGHT is largest (52.3M) with the longest mean trip (3.30 mi — late-night airport/outer-borough runs), AM_PEAK smallest (18.3M).

**Architecture.** Public BigQuery → cleaned `taxi_analysis` dataset → Parquet export to Cloud Storage (293 shards, 2.16 GiB) → Dataproc/PySpark clustering → results back to GCS/BigQuery → figures and an interactive Google Maps page hosted on GCS.

---

## 3. Methodology

**Time-stratified K-means (Dataproc/PySpark).** For each period we standardize (pickup_lat, pickup_lon), then fit K-means. Model selection used a silhouette + elbow sweep over k ∈ {10,15,20,25} per period (Fig. 1); silhouette scores were stable (~0.51–0.60), so for the cross-period comparison we **fix k = 20 for every period**. This fixed-k choice is essential: with different k per period, the period with more centroids trivially achieves shorter nearest-centroid distance, confounding any static-vs-adaptive comparison. Clustering ran on a 6-worker `n1-standard-4` cluster.

**Zone-stability metric.** For each pair of periods we compute an average (symmetric) nearest-centroid displacement in kilometers — a Hausdorff-inspired drift measure (Fig. 3): for centroid sets C₁, C₂, ½·(mean over C₁ of min haversine to C₂ + mean over C₂ of min haversine to C₁).

**Routing simulation (the key OR result).** For every one of the 142M trips we compute the haversine distance to its nearest zone centroid under (a) **adaptive** zoning — that period's own k=20 centroids — and (b) **static** zoning — a fixed baseline period's (AM_PEAK) centroids used all day. This was implemented as a vectorized Spark `pandas_udf` broadcasting the ≤20 centroids and computing pairwise haversine inside each Arrow batch, so it scales to the full population rather than a small sample. We report the mean per period and the percentage reduction.

**Graph analytics.** From `od_matrix` we build a weighted directed graph (831 nodes, 31,480 edges with ≥50 trips) and compute PageRank (α=0.85) to identify high-centrality hubs (Fig. 5).

**Demand forecasting (BigQuery ML).** We predict hourly `trip_count` per grid cell with three models: a regularized linear regression (L1=L2=0.1, the Lecture-7 penalized-regression connection), the same with temporal features one-hot encoded, and a boosted-tree regressor (Fig. 6).

---

## 4. Results

### 4.1 Exploratory analysis
Demand follows the expected bimodal weekday rhythm with AM and PM peaks, a Friday/Saturday weekly maximum, and mild seasonal variation across 2015 (Fig. 0). Pickups are overwhelmingly concentrated in Manhattan in every period — already foreshadowing the stability result.

### 4.2 Temporal clustering
Per-period K-means produces sensible 20-zone partitions (Fig. 2). Overlaying all four periods' centroids (Fig. 2b) shows them occupying nearly the same Manhattan core — a direct visual of stability.

### 4.3 Zone stability (drift)
Centroids move only **0.5–1.0 km** between periods (Fig. 3). The largest drift is **MIDDAY ↔ NIGHT = 1.02 km** (midday commerce vs. night nightlife), the smallest PM_PEAK ↔ MIDDAY = 0.52 km. Zones *do* shift, but modestly.

### 4.4 Key OR result — static vs. adaptive routing
On the full 142M-trip population, with a fixed 20 zones, time-adaptive zoning barely beats static (Fig. 4):

| Period | adaptive (km) | static / AM zones (km) | gain |
|---|---|---|---|
| AM_PEAK | 0.576 | 0.576 | 0.0% (baseline) |
| PM_PEAK | 0.556 | 0.571 | +2.8% |
| MIDDAY | 0.579 | 0.571 | −1.4% |
| NIGHT | 0.616 | 0.625 | +1.4% |

**Average gain ≈ 0.9%.** One period is even slightly negative (within the noise of K-means minimizing squared distance in standardized space versus our mean-haversine metric). **The hypothesized large routing benefit of time-adaptive zoning does not materialize.** The structural reason is demand concentration: with pickups so dominated by the Manhattan core, any reasonable placement of 20 zones covers demand well, so the ~1 km of genuine zone drift is too small to change which zone is nearest for most trips.

### 4.5 Graph analytics
PageRank ranks the trip network's top hubs entirely within Midtown Manhattan — (40.76, −73.98) Times Square/Midtown, (40.75, −73.99) Penn Station/Herald Square (Fig. 5). This matches ground truth and validates the OD-graph construction.

### 4.6 Demand forecasting
A regularized **linear** model explains only **R²=0.055** (MAE≈390 trips); one-hot encoding the temporal features barely helps (R²=0.059). A **boosted tree** reaches **R²=0.871** (MAE≈92) (Fig. 6). The gap is itself the lesson: demand is a strongly *nonlinear* function of location (the tree splits on lat/lon) and exhibits the bimodal hourly pattern a linear term cannot capture. Tree feature importance is shared roughly equally across longitude, day-of-week, hour, and latitude.

---

## 5. Conclusion

We set out to confirm that urban demand zones should be time-adaptive and to quantify the routing gain. Instead, a rigorous, full-population analysis of 142M trips shows the opposite: **optimal zones are stable** (centroids drift <1 km between periods) and **time-adaptive zoning reduces dispatch distance by only ~1%**. For NYC yellow taxis, static zone decomposition is near-optimal because demand is too geographically concentrated for temporal shifts to matter at practical zone counts. This is a useful, cautionary result for time-varying VRP decomposition: the cost of adopting adaptive zoning may not be repaid in routing efficiency unless demand is far more spatially dispersed (e.g., last-mile delivery across a whole metro, or service in a polycentric city).

**Limitations & future work.** (a) The effect may differ at finer resolution (much larger k) or under a demand-weighted objective; (b) restricting to airport/outer-borough demand — which shifts more by time than the Manhattan core — may reveal where adaptivity does pay off; (c) a cross-year comparison (2014–2017) could track how the ride-hailing disruption reshaped these zones; (d) real-time adaptive zoning via streaming (Cloud Pub/Sub) would extend the dispatch application.

---

## References

[1] Bramel, J. & Simchi-Levi, D. (1997). *The Logic of Logistics.* Springer.
[2] Zaharia, M. et al. (2016). Apache Spark: A Unified Engine for Big Data Processing. *CACM* 59(11).
[3] NYC TLC Trip Record Data. https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
[4] Page, L. et al. (1999). The PageRank Citation Ranking. Stanford TR.
[5] Ester, M. et al. (1996). DBSCAN. *KDD-96.*
[6] Tibshirani, R. (1996). Regression Shrinkage and Selection via the Lasso. *JRSS-B* 58(1).
[7] Agatz, N. et al. (2012). Optimization for Dynamic Ride-Sharing. *Transportation Science* 46(3).
[8] Google Cloud BigQuery ML Docs. https://cloud.google.com/bigquery/docs/bqml-introduction
[9] Matter, U. (2024). *Big Data Analytics.* CRC Press.
[10] Rioux, J. (2022). *Data Analysis with Python and PySpark.* O'Reilly.

---

### Appendix — Figures
- **Fig. 0** `fig0_eda_overview.png` — hourly/DOW/monthly volume + pickup scatter by period
- **Fig. 1** `fig1_elbow_silhouette.png` — elbow (WSSSE) + silhouette vs k, per period
- **Fig. 2** `fig2_cluster_scatter_4panel.png` — 20 zones per period; **Fig. 2b** `fig2b_centroid_overlay.png` — all overlaid
- **Fig. 3** `fig3_zone_drift.png` — centroid drift heatmap
- **Fig. 4** `fig4_static_vs_adaptive.png` — routing: adaptive ≈ static
- **Fig. 5** `fig5_pagerank.png` — top OD hubs (Midtown)
- **Fig. 6** `fig6_demand_models.png` — BQML model comparison + tree feature importance
- **Interactive:** https://storage.googleapis.com/pstat135-taxi-shahil/viz/index.html

*Code: 03_eda.py · 04_temporal_kmeans.py · 04c_cluster_scatter.py · fig1_silhouette.py · 05_routing_plot.py · 06_zone_drift.py · 07_pagerank.py · 08_bqml_demand.sql · viz/index.html. Full numbers in RESULTS.md.*
