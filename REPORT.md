# Are Urban Demand Zones Stable? Distributed Spatial Clustering of 142 Million NYC Taxi Trips

**PSTAT 135 Final Project — Shahil Patel (shahil@ucsb.edu)**  
**Stack:** BigQuery · Dataproc/PySpark · BigQuery ML · NetworkX  
**Interactive map:** https://storage.googleapis.com/pstat135-taxi-shahil/viz/index.html  
**Code:** https://github.com/shahilpatel/NYC-TaxiAnalysis

---

## Abstract

Vehicle-routing problems are NP-hard, but a standard tractable heuristic decomposes a city into demand zones and routes within each. A natural hypothesis is that these zones should be time-adaptive — re-optimized for each operational period — because demand geography shifts between morning rush, midday, evening rush, and night. We test this empirically at scale: 142,567,774 cleaned 2015 NYC yellow-taxi trips clustered with distributed K-means (PySpark on Google Cloud Dataproc) into 20 zones per time period, with a full-population routing simulation comparing static vs. time-adaptive zoning. Contrary to the hypothesis, optimal zones are remarkably stable — centroids shift only 0.5–1.0 km between periods, and time-adaptive zoning reduces mean dispatch distance by only ~1%. We then extend the study to a controlled 5-arm longitudinal comparison (yellow and green taxis 2015, yellow 2024, Uber/Lyft 2019 and 2024) to ask whether the arrival of rideshare changed this result. The relationship is non-monotone: adaptive gain peaks at intermediate dispersion regimes (Yellow 2024: +9.1%, Green 2015: +7.5%), not at maximum dispersion (Uber/Lyft 2024: −1.5%). The driver is time-volatility of demand, not spatial spread — a cleaner decision rule than the original hypothesis predicted.

---

## 1. Introduction

Urban logistics and ride-dispatch operations rely on zone decomposition to make the vehicle-routing problem tractable: partition the service area into a small number of zones, assign vehicles to zones, and solve a far smaller routing problem within each. The quality of this decomposition depends on zone placement.

It is widely assumed that good zones must be time-adaptive — that the partition optimal for the 8 a.m. commute is wasteful at 2 a.m. when demand migrates to nightlife districts. If true, this motivates time-varying VRP decomposition and dynamic dispatch. This project asks whether that assumption holds for a real, large-scale demand dataset and quantifies the routing efficiency at stake.

Our contributions:
1. A reproducible, fully cloud-native pipeline that clusters 142M trips with distributed K-means.
2. A fair, full-population routing simulation measuring the dispatch-distance gain of adaptive vs. static zoning.
3. A counterintuitive finding: zones are stable and adaptivity buys almost nothing for concentrated demand.
4. A controlled 5-arm longitudinal study extending the finding to the rideshare era, identifying time-volatility — not spatial dispersion — as the key variable.

---

## 2. Data

**2015 baseline.** `bigquery-public-data.new_york.tlc_yellow_trips_2015`, the NYC TLC trip records. 2015 is the last full year of peak yellow-cab dominance before ride-hailing structurally reduced demand, and the last year with raw pickup/dropoff coordinates (later years publish only zone IDs). After filtering to NYC bounding box, fares $2.50–$100, and distance 0.1–50 mi, we retain **142,567,774 trips** (mean 2.97 mi, $12.79).

**5-arm extension.** For the longitudinal study we use:
- Green boro-taxi 2015: BigQuery public dataset (`tlc_green_trips_2015`), 19.2M trips
- Yellow taxi 2024: downloaded from NYC TLC, 41M trips
- Uber/Lyft 2019 (HVFHV): Feb–Mar 2019 snapshot, 44M trips (partial year due to TLC schema drift mid-2019)
- Uber/Lyft 2024 (HVFHV): full year, 240M trips

All arms are mapped to the same 263 TLC zone centroids, making zone counts and geographies directly comparable across modes and years.

**Time periods.** AM Peak (7–9 am), Midday (10 am–3 pm), PM Peak (4–7 pm), Night (8 pm–6 am). By volume: Night 52.3M, Midday 41.4M, PM Peak 30.5M, AM Peak 18.3M.

---

## 3. Methodology

**Distributed K-means (Dataproc/PySpark).** For each time period we standardize (pickup_lat, pickup_lon) and fit K-means, sweeping k ∈ {10, 15, 20, 25} and scoring silhouette on a sample. For the cross-period comparison we fix k=20 for every period — essential for a fair comparison, since different k per period trivially gives more centroids shorter nearest-centroid distances, confounding the result.

**Zone-stability metric.** For each pair of periods we compute a symmetric nearest-centroid displacement: for centroid sets C₁, C₂: ½ · (mean over C₁ of min haversine to C₂ + mean over C₂ of min haversine to C₁).

**Routing simulation.** For every one of the 142M trips we compute haversine distance to the nearest zone centroid under (a) adaptive zoning — that period's own centroids — and (b) static zoning — AM Peak centroids used all day. Implemented as a vectorized Spark `pandas_udf` broadcasting centroids and computing pairwise haversine inside each Arrow batch, scaling to the full population.

**5-arm analysis.** For the longitudinal study, demand-weighted K-means (k=20, pure numpy, 6 restarts) runs over 263 TLC zone centroids per arm per period. Drift and routing gain are computed identically to the 2015 analysis. The Manhattan-only re-run (restricting all arms to the common footprint) controls for coverage differences between modes.

**Graph analytics.** From the 2015 OD matrix (45,477 edges ≥20 trips) we build a weighted directed graph and compute PageRank (α=0.85).

**Demand forecasting (BigQuery ML).** Three models on hourly grid-cell demand: regularized linear regression (L1=L2=0.1), linear with temporal one-hot features, and a boosted tree.

---

## 4. Results

### 4.1 Exploratory analysis

Demand follows a bimodal weekday rhythm with AM and PM peaks, a Friday/Saturday weekly maximum, and mild seasonal variation. Pickups are overwhelmingly concentrated in Manhattan in every period (Fig. 0).

### 4.2 Temporal clustering

Per-period K-means produces sensible 20-zone partitions (Fig. 2). Overlaying all four periods' centroids shows them occupying nearly the same Manhattan core — a direct visual of stability.

### 4.3 Zone stability

Centroids move only **0.5–1.0 km** between periods (Fig. 3). The largest drift is Midday ↔ Night = 1.02 km (midday commerce vs. late-night nightlife districts), the smallest PM Peak ↔ Midday = 0.52 km.

### 4.4 Static vs. adaptive routing — the 2015 result

On the full 142M-trip population with k=20 fixed, time-adaptive zoning barely beats static (Fig. 4):

| Period | Adaptive (km) | Static — AM zones (km) | Gain |
|--------|--------------|------------------------|------|
| AM Peak | 0.576 | 0.576 | 0.0% (baseline) |
| PM Peak | 0.556 | 0.571 | +2.8% |
| Midday | 0.579 | 0.571 | −1.4% |
| Night | 0.616 | 0.625 | +1.4% |

**Average gain ≈ 0.9%.** The hypothesized routing benefit of time-adaptive zoning does not materialize. With pickups dominated by the Manhattan core, any reasonable placement of 20 zones covers demand well in every period, so the ~1 km of genuine zone drift is too small to change which zone is nearest for most trips.

### 4.5 Graph analytics

PageRank ranks the top hubs entirely within Midtown Manhattan — Times Square / Midtown, Penn Station / Herald Square — validating the OD graph and confirming Midtown as the network center.

### 4.6 Demand forecasting

A regularized linear model explains only R²=0.055 (MAE≈390 trips). Boosted tree reaches R²=0.871 (MAE≈92). The gap is the lesson: demand is a strongly nonlinear function of location and the bimodal hourly pattern that a linear term cannot capture. Tree feature importance is shared roughly equally across longitude, day-of-week, hour, and latitude.

### 4.7 The rideshare era — a controlled 5-arm study

The 2015 finding rests on demand concentration. Uber and Lyft fundamentally changed NYC's demand geography, spreading pickups across all five boroughs. We test whether this changes the stability result using a controlled design that separates mode from time.

**Study arms:**

| Arm | Mode | Year | Role |
|-----|------|------|------|
| A — Yellow 2015 | Yellow taxi | 2015 | Pre-rideshare baseline |
| B — Green 2015 | Green boro-taxi | 2015 | Outer-borough taxi |
| C — Yellow 2024 | Yellow taxi | 2024 | Mode control (same mode, 9 years later) |
| D — FHV 2019 | Uber/Lyft/Via | 2019 | Early rideshare |
| E — FHV 2024 | Uber/Lyft/Via | 2024 | Modern rideshare |

**Key comparisons:** A→C isolates the time effect within yellow taxis; C→E isolates the mode/coverage effect within 2024; D→E shows rideshare's own trend.

**Results (Fig. A–D):**

| Arm | Rides | Manhattan % | Radius (km) | Avg drift (km) | Adaptive gain | (Manhattan-only) |
|-----|-------|-------------|-------------|----------------|---------------|-----------------|
| Yellow 2015 | 142M | 92% | 3.10 | 0.70 | +0.18% | +2.11% |
| Green 2015 | 19M | 28% | 6.64 | 1.08 | +7.50% | −8.75% |
| Yellow 2024 | 41M | 89% | 3.89 | 1.28 | +9.12% | +12.70% |
| FHV 2019 | 44M | 44% | 7.83 | 1.67 | +4.29% | +2.77% |
| FHV 2024 | 240M | 39% | 8.39 | 1.48 | −1.53% | +2.06% |

**The relationship is non-monotone.** More spatial dispersion does not mean more adaptive gain. Uber/Lyft 2024 is the most dispersed arm but gains the least (−1.5%). Yellow 2024 is barely more dispersed than Yellow 2015 but gains 50× more (+9.1%).

**Decomposition:**
- A→C (time within yellow): gain +0.2% → +9.1%, radius 3.1 → 3.9 km. Post-COVID shift patterns made yellow taxi demand more time-volatile even as the geographic footprint barely changed.
- C→E (mode, same year): gain +9.1% → −1.5%. Rideshare's city-wide uniform spread means static zones already cover everywhere adequately.
- Manhattan-only control: FHV 2024 gain recovers to +2.1% within the common footprint, confirming the all-NYC result is partly a coverage artifact — but the direction holds.

**Decision rule.** Adaptive zoning pays off when demand is *time-volatile* — concentrated but shifting meaningfully through the day. It does not help when demand is either too concentrated (Yellow 2015) or too uniformly distributed (FHV 2024). The intermediate regimes (Yellow 2024, Green 2015) gain the most.

---

## 5. Conclusion

A rigorous, full-population analysis of 142M NYC yellow taxi trips shows optimal zones are stable (centroids drift <1 km) and time-adaptive zoning reduces dispatch distance by only ~1%. The structural cause is demand concentration in the Manhattan core.

Extending the analysis to five eras and modes reveals a non-monotone result: the decision to adopt adaptive zoning depends not on how dispersed demand is, but on whether it is *time-volatile*. Yellow taxi demand in 2024 — still Manhattan-heavy but with post-COVID behavioral shifts — gains 9% from adaptive zoning. Uber/Lyft 2024 demand, uniformly distributed city-wide around the clock, gains nothing. The practical decision rule is: adapt when demand is concentrated enough to matter but volatile enough to shift between periods.

---

## References

1. Bramel, J. & Simchi-Levi, D. (1997). *The Logic of Logistics.* Springer.
2. Zaharia, M. et al. (2016). Apache Spark: A Unified Engine for Big Data Processing. *CACM* 59(11).
3. NYC TLC Trip Record Data. https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
4. Page, L. et al. (1999). The PageRank Citation Ranking. Stanford TR.
5. Tibshirani, R. (1996). Regression Shrinkage and Selection via the Lasso. *JRSS-B* 58(1).
6. Agatz, N. et al. (2012). Optimization for Dynamic Ride-Sharing. *Transportation Science* 46(3).
7. Google Cloud BigQuery ML. https://cloud.google.com/bigquery/docs/bqml-introduction

---

## Appendix — Figures

| Figure | Description |
|--------|-------------|
| `figures/fig0_eda_overview.png` | Hourly volume, day-of-week, monthly trend, pickup scatter by period |
| `figures/fig1_elbow_silhouette.png` | WSSSE + silhouette vs k, per period — justifies k=20 |
| `figures/fig2_cluster_scatter_4panel.png` | 20 zones per period over pickup backdrop |
| `figures/fig3_zone_drift.png` | Inter-period centroid drift heatmap (0.5–1.0 km) |
| `figures/fig4_static_vs_adaptive.png` | Routing gain: adaptive ≈ static (~1%) |
| `figures/figA_era_demand.png` | Demand geography across all 5 arms — the dispersion shift |
| `figures/figB_era_drift.png` | Zone drift by era |
| `figures/figC_era_gain.png` | Adaptive gain by era — the 5-arm main finding |
| `figures/figD_gain_vs_dispersion.png` | Decision rule: gain vs. dispersion, all arms × periods |
