"""
Time-stratified distributed K-means on NYC yellow taxi 2015 (PySpark / Dataproc).

Submit:
    gsutil cp 04_temporal_kmeans.py gs://pstat135-taxi-shahil/scripts/
    gcloud dataproc jobs submit pyspark gs://pstat135-taxi-shahil/scripts/04_temporal_kmeans.py \
        --cluster=pstat135-cluster --region=us-central1 --project=pstat135-nyc-taxi

Phase 1 clusters each time period, sweeping k and selecting by silhouette.
Phase 2 computes adaptive vs static routing distance on the full population.
"""
from pyspark.sql import SparkSession
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.sql import functions as F
from pyspark.sql.functions import pandas_udf
import numpy as np
import pandas as pd
import json, subprocess

BUCKET = "pstat135-taxi-shahil"
INPUT  = f"gs://{BUCKET}/data/trips_with_period/*.parquet"
OUTPUT = f"gs://{BUCKET}/results/temporal_kmeans"
K_VALUES = [10, 15, 20, 25]
# FIXED_K: use the SAME number of zones in every period. Required for a fair
# static-vs-adaptive routing comparison -- otherwise more centroids trivially
# means shorter nearest-centroid distance and the comparison is confounded by k.
# Set to None to fall back to per-period best-silhouette k (NOT comparable).
FIXED_K = 20
TIME_PERIODS = ["AM_PEAK", "PM_PEAK", "MIDDAY", "NIGHT"]
STATIC_BASELINE = "AM_PEAK"        # zones a fixed design would use all day
LABELED_SAMPLE_FRAC = 0.05         # fraction of labeled trips written for viz/BQ
SWEEP_MAXITER = 15
FINAL_MAXITER = 30

spark = (SparkSession.builder.appName("TemporalKMeans")
         .config("spark.executor.memory", "6g")
         .getOrCreate())
spark.sparkContext.setLogLevel("WARN")


def make_nearest_km_udf(centroid_latlon):
    """Vectorized UDF: distance (km) from each point to its NEAREST centroid in a
    broadcast set. Centroids (<=25 pts) are tiny, so we broadcast and do a numpy
    pairwise haversine inside each Arrow batch -- scales to 142M rows."""
    bc = spark.sparkContext.broadcast(np.asarray(centroid_latlon, dtype=float))

    @pandas_udf("double")
    def _udf(lat: pd.Series, lon: pd.Series) -> pd.Series:
        c = bc.value                                   # (k, 2)
        latr = np.radians(lat.to_numpy()); lonr = np.radians(lon.to_numpy())
        clat = np.radians(c[:, 0]);        clon = np.radians(c[:, 1])
        dlat = latr[:, None] - clat[None, :]           # (n, k)
        dlon = lonr[:, None] - clon[None, :]
        a = (np.sin(dlat / 2) ** 2
             + np.cos(latr)[:, None] * np.cos(clat)[None, :] * np.sin(dlon / 2) ** 2)
        d = 2 * 6371.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        return pd.Series(np.nanmin(d, axis=1))
    return _udf


def already_done(period):
    """True if this period's centroids.json was already written to GCS."""
    r = subprocess.run(["gsutil", "-q", "stat", f"{OUTPUT}/{period}/centroids.json"])
    return r.returncode == 0


def load_centroids(period):
    txt = subprocess.run(["gsutil", "cat", f"{OUTPUT}/{period}/centroids.json"],
                         capture_output=True, text=True).stdout
    return json.loads(txt)


df_all = spark.read.parquet(INPUT).select(
    "pickup_lat", "pickup_lon", "pickup_hour", "pickup_dow",
    "trip_distance", "fare_amount", "time_period")
print(f"Total rows loaded: {df_all.count():,}")

evaluator = ClusteringEvaluator(featuresCol="features", metricName="silhouette")
all_results = {}        # period -> list of {k, silhouette, wssse} (only newly run)
best_k_by_period = {}
centroids_geo = {}      # period -> [(lat, lon), ...] geographic centroids

# Phase 1: cluster
for period in TIME_PERIODS:
    print(f"\n{'='*55}\nCLUSTER period: {period}")

    if already_done(period):
        d = load_centroids(period)
        # Only reuse if it already matches the target k (else recompute below).
        if FIXED_K is None or d["k"] == FIXED_K:
            centroids_geo[period] = [(c["centroid_lat"], c["centroid_lon"])
                                     for c in d["centroids"]]
            best_k_by_period[period] = d["k"]
            print(f"  SKIP (already done): loaded {len(centroids_geo[period])} "
                  f"centroids, k={d['k']}")
            continue
        print(f"  RECOMPUTE: existing k={d['k']} != FIXED_K={FIXED_K}")

    df_period = df_all.filter(F.col("time_period") == period)
    n = df_period.count()
    print(f"  Rows in period: {n:,}")

    assembler = VectorAssembler(inputCols=["pickup_lat", "pickup_lon"],
                                outputCol="raw_features")
    scaler = StandardScaler(inputCol="raw_features", outputCol="features",
                            withMean=True, withStd=True)
    df_a = assembler.transform(df_period)
    scaler_model = scaler.fit(df_a)
    df_scaled = scaler_model.transform(df_a).cache()

    if FIXED_K is not None:
        # Comparison mode: one fit at the shared k, no sweep.
        best_k = FIXED_K
        period_results = []
        print(f"  FIXED_K mode: clustering at k={best_k} (no sweep)")
    else:
        df_eval = df_scaled.sample(False, 0.05, seed=42).cache()
        period_results = []
        for k in K_VALUES:
            km = KMeans(featuresCol="features", k=k, seed=42, maxIter=SWEEP_MAXITER)
            model = km.fit(df_scaled)
            sil = evaluator.evaluate(model.transform(df_eval))
            wssse = model.summary.trainingCost
            period_results.append({"k": k, "silhouette": sil, "wssse": wssse})
            print(f"    k={k:2d} | sil={sil:.4f} | wssse={wssse:.1f}")
        df_eval.unpersist()
        best = max(period_results, key=lambda r: r["silhouette"])
        best_k = best["k"]
        print(f"  -> best k for {period}: {best_k} (sil={best['silhouette']:.4f})")
    best_k_by_period[period] = best_k

    km_final = KMeans(featuresCol="features", k=best_k, seed=42, maxIter=FINAL_MAXITER)
    model_final = km_final.fit(df_scaled)
    df_labeled = model_final.transform(df_scaled).select(
        "pickup_lat", "pickup_lon", "pickup_hour", "pickup_dow",
        "trip_distance", "fare_amount", "time_period",
        F.col("prediction").alias("cluster_id"))

    # Full-population cluster stats (cheap aggregate) ...
    stats = (df_labeled.groupBy("cluster_id").agg(
        F.count("*").alias("trip_count"),
        F.avg("trip_distance").alias("avg_distance"),
        F.avg("fare_amount").alias("avg_fare"),
        F.avg("pickup_lat").alias("centroid_lat"),
        F.avg("pickup_lon").alias("centroid_lon"),
    ).orderBy("cluster_id"))
    stats.write.parquet(f"{OUTPUT}/{period}/cluster_stats/", mode="overwrite")

    # ... but only a SAMPLE of labeled trips (full 142M-row write is wasteful)
    (df_labeled.sample(False, LABELED_SAMPLE_FRAC, seed=42)
     .write.parquet(f"{OUTPUT}/{period}/labeled_trips/", mode="overwrite"))

    centroids = stats.select("cluster_id", "centroid_lat", "centroid_lon",
                             "trip_count").collect()
    centroid_list = [{"cluster_id": int(r.cluster_id),
                      "centroid_lat": float(r.centroid_lat),
                      "centroid_lon": float(r.centroid_lon),
                      "trip_count": int(r.trip_count)} for r in centroids]
    centroids_geo[period] = [(c["centroid_lat"], c["centroid_lon"])
                             for c in centroid_list]
    with open(f"/tmp/centroids_{period}.json", "w") as f:
        json.dump({"period": period, "k": best_k, "centroids": centroid_list},
                  f, indent=2)
    subprocess.run(["gsutil", "cp", f"/tmp/centroids_{period}.json",
                    f"{OUTPUT}/{period}/centroids.json"])

    df_scaled.unpersist()
    all_results[period] = period_results
    print(f"  done clustering {period} -> written to GCS")

# Phase 2: routing simulation
print(f"\n{'='*55}\nROUTING simulation (full population)")
static_set = centroids_geo[STATIC_BASELINE]
static_udf = make_nearest_km_udf(static_set)
routing_results = []
for period in TIME_PERIODS:
    dfp = df_all.filter(F.col("time_period") == period).select(
        "pickup_lat", "pickup_lon")
    adaptive_udf = make_nearest_km_udf(centroids_geo[period])
    if period == STATIC_BASELINE:
        # adaptive zones ARE the static baseline -> identical, one pass
        agg = dfp.select(F.mean(adaptive_udf("pickup_lat", "pickup_lon")).alias("a"),
                         F.count("*").alias("n")).first()
        adaptive_km = static_km = float(agg["a"]); nrows = int(agg["n"])
    else:
        agg = dfp.select(
            F.mean(adaptive_udf("pickup_lat", "pickup_lon")).alias("a"),
            F.mean(static_udf("pickup_lat", "pickup_lon")).alias("s"),
            F.count("*").alias("n")).first()
        adaptive_km = float(agg["a"]); static_km = float(agg["s"]); nrows = int(agg["n"])
    reduction_pct = (static_km - adaptive_km) / static_km * 100 if static_km else 0.0
    routing_results.append({"period": period, "adaptive_km": adaptive_km,
                            "static_km": static_km, "reduction_pct": reduction_pct,
                            "n": nrows})
    print(f"  {period:<10} adaptive={adaptive_km:.4f}km | "
          f"static({STATIC_BASELINE})={static_km:.4f}km | gain={reduction_pct:.1f}%")

# ------------------------------------------------------------------ summaries
print("\n\nROUTING DISTANCE: ADAPTIVE vs STATIC ZONES (full population)")
print(f"{'Period':<12} {'adaptive_km':>12} {'static_km':>12} {'gain_%':>8} {'n':>14}")
for r in routing_results:
    print(f"{r['period']:<12} {r['adaptive_km']:>12.4f} {r['static_km']:>12.4f} "
          f"{r['reduction_pct']:>8.1f} {r['n']:>14,}")
with open("/tmp/routing_summary.json", "w") as f:
    json.dump({"static_baseline": STATIC_BASELINE, "results": routing_results},
              f, indent=2)
subprocess.run(["gsutil", "cp", "/tmp/routing_summary.json",
                f"{OUTPUT}/routing_summary.json"])

if all_results:
    with open("/tmp/silhouette_summary.json", "w") as f:
        json.dump({"results": all_results, "best_k": best_k_by_period}, f, indent=2)
    subprocess.run(["gsutil", "cp", "/tmp/silhouette_summary.json",
                    f"{OUTPUT}/silhouette_summary.json"])

spark.stop()
print("\nAll done!")
