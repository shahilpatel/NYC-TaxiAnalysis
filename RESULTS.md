# Results — NYC Taxi Zone Stability Study

## Dataset

| Table | Rows | Notes |
|-------|------|-------|
| `cleaned_trips` | 142,567,774 | 2015 yellow taxi, full year, avg 2.97 mi / $12.79 |
| `trips_with_period` | 142,567,774 | adds time period + day type labels |
| `zone_demand` | 563,696 | hourly demand per ~1 km grid cell |
| `od_matrix` | 45,477 | origin→destination edges ≥20 trips |

Period distribution: Night 52.3M (37%), Midday 41.4M (29%), PM Peak 30.5M (21%), AM Peak 18.3M (13%).

---

## EDA (fig0)

| Period | Trips | Avg dist (mi) | Avg fare ($) |
|--------|-------|---------------|--------------|
| Night | 52,328,392 | 3.30 | 12.93 |
| Midday | 41,417,615 | 2.82 | 13.01 |
| PM Peak | 30,528,899 | 2.78 | 12.62 |
| AM Peak | 18,292,868 | 2.72 | 12.20 |

Night has the longest average trip — consistent with late-night airport and outer-borough runs.

---

## K-means — silhouette by k (fig1)

Sweep over k ∈ {10, 15, 20, 25} per period. Silhouette scores were stable (~0.51–0.60) across k values. k=20 fixed for all periods to enable a fair cross-period routing comparison.

---

## Zone drift — 2015 (fig3)

Symmetric nearest-centroid displacement between period pairs:

| Pair | Drift (km) |
|------|-----------|
| Midday ↔ Night | 1.017 |
| PM Peak ↔ Night | 0.755 |
| AM Peak ↔ Night | 0.751 |
| AM Peak ↔ Midday | 0.674 |
| AM Peak ↔ PM Peak | 0.607 |
| PM Peak ↔ Midday | 0.520 |

---

## Static vs. adaptive routing — 2015 (fig4)

Full 142M-trip population, k=20 fixed, static baseline = AM Peak zones.

| Period | Adaptive (km) | Static (km) | Gain |
|--------|--------------|-------------|------|
| AM Peak | 0.5760 | 0.5760 | 0.0% |
| PM Peak | 0.5555 | 0.5712 | +2.8% |
| Midday | 0.5788 | 0.5707 | −1.4% |
| Night | 0.6158 | 0.6246 | +1.4% |

**Average gain: ~0.9%.** Time-adaptive zoning does not materially improve dispatch efficiency. Zone drift is too small and demand too concentrated for the period-specific zone placements to change which zone is nearest for most trips.

---

## PageRank hubs

Top-5 by PageRank (α=0.85), weighted directed graph, 831 nodes, 31,480 edges:

| Rank | (lat, lon) | PageRank | Location |
|------|-----------|----------|----------|
| 1 | (40.760, −73.980) | 0.01566 | Times Sq / Midtown |
| 2 | (40.760, −73.970) | 0.01558 | Midtown East |
| 3 | (40.750, −73.990) | 0.01439 | Penn Station |
| 4 | (40.750, −73.980) | 0.01321 | Murray Hill |
| 5 | (40.760, −73.990) | 0.01095 | Hell's Kitchen |

---

## BigQuery ML demand forecast (fig6 removed — not in final figures)

| Model | R² | MAE (trips/hr) |
|-------|----|----------------|
| Linear, numeric features | 0.055 | 390 |
| Linear, temporal one-hot | 0.059 | 392 |
| Boosted tree | 0.871 | 92 |

Linear model explains ~6% of variance. Boosted tree reaches R²=0.87 by capturing nonlinear spatial signal and the bimodal hourly pattern.

---

## 5-arm longitudinal study — era comparison (figA–figD)

### Arm summary

| Arm | Rides | Manhattan % | Radius (km) | Drift (km) | Adaptive gain | Manhattan-only |
|-----|-------|-------------|-------------|-----------|---------------|----------------|
| Yellow 2015 | 142,505,668 | 92.4% | 3.10 | 0.70 | +0.18% | +2.11% |
| Green 2015 | 19,227,283 | 28.4% | 6.64 | 1.08 | +7.50% | −8.75% |
| Yellow 2024 | 41,028,021 | 88.7% | 3.89 | 1.28 | +9.12% | +12.70% |
| FHV 2019 | 44,120,902 | 44.0% | 7.83 | 1.67 | +4.29% | +2.77% |
| FHV 2024 | 240,111,310 | 38.8% | 8.39 | 1.48 | −1.53% | +2.06% |

### Decomposition

- **A→C (time within yellow):** gain +0.2% → +9.1%, radius 3.1 → 3.9 km. Post-COVID demand patterns made yellow taxi demand more time-volatile.
- **C→E (mode, same year):** gain +9.1% → −1.5%. City-wide uniform rideshare demand means static zones already work.
- **D→E (rideshare trend):** gain +4.3% → −1.5% as rideshare matured and spread more uniformly.
- **Manhattan-only control:** FHV 2024 gain recovers to +2.1% within the common footprint, confirming the direction but reducing the magnitude.

### Key finding

The relationship between dispersion and adaptive gain is **non-monotone**. Gain peaks at intermediate time-volatile regimes (Yellow 2024, Green 2015), not at maximum dispersion (FHV 2024). The decision rule: **adapt when demand is concentrated but shifts significantly between time periods**.

---

## Note on FHV 2019

Only Feb–Mar 2019 loaded (44M trips) due to mid-year TLC parquet schema drift (`airport_fee` INT→FLOAT, `wav_match_flag` INT→STRING). Treated as an early-rideshare snapshot rather than a full-year arm.
