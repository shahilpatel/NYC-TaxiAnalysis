"""05_routing_plot.py -- Phase 5: plot the static-vs-adaptive routing result.
The distances were computed on the FULL population inside the Spark job
(04_temporal_kmeans.py); this just reads routing_summary.json from GCS and plots.
Run after the Dataproc job finishes."""
import os, json
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
    "/Users/shahil/Documents/UCSB/2025-2026/PSTAT135/pstat135-nyc-taxi-4db0653d3d93.json"
from google.cloud import storage
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BUCKET = "pstat135-taxi-shahil"
gcs = storage.Client()
blob = gcs.bucket(BUCKET).blob("results/temporal_kmeans/routing_summary.json")
data = json.loads(blob.download_as_text())
baseline = data["static_baseline"]
df = pd.DataFrame(data["results"])
order = ["AM_PEAK", "PM_PEAK", "MIDDAY", "NIGHT"]
df = df.set_index("period").loc[order].reset_index()
print(df.to_string(index=False))

fig, ax = plt.subplots(figsize=(10, 5))
x = np.arange(len(df)); w = 0.35
b1 = ax.bar(x - w/2, df["static_km"], w, label=f"Static Zones ({baseline} centroids)",
            color="#e74c3c", alpha=0.85)
b2 = ax.bar(x + w/2, df["adaptive_km"], w, label="Adaptive Zones (period-specific)",
            color="#2ecc71", alpha=0.85)
for bar, v in zip(b1, df["static_km"]):
    ax.text(bar.get_x()+bar.get_width()/2, v+0.003, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
for bar, v in zip(b2, df["adaptive_km"]):
    ax.text(bar.get_x()+bar.get_width()/2, v+0.003, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
ax.set_xticks(x); ax.set_xticklabels(df["period"], fontsize=11)
ax.set_ylabel("Avg Distance to Nearest Zone Centroid (km)")
ax.set_title("Static vs. Time-Adaptive Zone Dispatch Distance (k=20, 142M trips)\n"
             "Near-identical (avg gain ~1%) -> static zoning is near-optimal for "
             "Manhattan-concentrated demand", fontsize=12)
ax.legend()
for i, r in df.iterrows():
    if r["reduction_pct"] > 0.05:
        ax.annotate(f"-{r['reduction_pct']:.1f}%", xy=(i+w/2, r["adaptive_km"]+0.015),
                    ha="center", color="darkgreen", fontweight="bold", fontsize=10)
plt.tight_layout()
plt.savefig("figures/fig4_static_vs_adaptive.png", dpi=150)
print("\nSaved fig4_static_vs_adaptive.png")
print(f"\nHEADLINE: adaptive zones cut dispatch distance by "
      f"{df[df.period!=baseline]['reduction_pct'].mean():.1f}% on average "
      f"(excluding the {baseline} baseline).")
