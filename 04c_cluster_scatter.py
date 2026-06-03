"""04c_cluster_scatter.py -- fig2: zone geography per period (4-panel) + overlay.
Shows each period's 20 k-means centroids over a faint pickup-density backdrop.
Directly visualizes the stability finding: the zones barely move across periods."""
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
    "/Users/shahil/Documents/UCSB/2025-2026/PSTAT135/pstat135-nyc-taxi-4db0653d3d93.json"
from google.cloud import bigquery, storage
import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt

bq = bigquery.Client(project="pstat135-nyc-taxi")
gcs = storage.Client()
BUCKET = "pstat135-taxi-shahil"
PERIODS = ["AM_PEAK", "MIDDAY", "PM_PEAK", "NIGHT"]
COLORS = {"AM_PEAK": "#e74c3c", "MIDDAY": "#27ae60", "PM_PEAK": "#f39c12", "NIGHT": "#5b8def"}
TITLES = {"AM_PEAK": "AM Peak (7-9am)", "MIDDAY": "Midday (10am-3pm)",
          "PM_PEAK": "PM Peak (4-7pm)", "NIGHT": "Night (8pm-6am)"}

# faint pickup backdrop (small sample per period) + centroids
samples, cents = {}, {}
for p in PERIODS:
    samples[p] = bq.query(f"""
        SELECT pickup_lat, pickup_lon FROM `pstat135-nyc-taxi.taxi_analysis.trips_with_period`
        WHERE time_period='{p}' AND RAND()<0.0005 LIMIT 8000
    """).to_dataframe()
    d = json.loads(gcs.bucket(BUCKET).blob(
        f"results/temporal_kmeans/{p}/centroids.json").download_as_text())
    cents[p] = pd.DataFrame(d["centroids"])

XLIM, YLIM = (-74.02, -73.93), (40.70, 40.82)

# 4-panel
fig, axes = plt.subplots(2, 2, figsize=(13, 12))
for ax, p in zip(axes.flat, PERIODS):
    ax.scatter(samples[p].pickup_lon, samples[p].pickup_lat, s=2, alpha=0.07, c='gray')
    ax.scatter(cents[p].centroid_lon, cents[p].centroid_lat, s=120, marker='X',
               c=COLORS[p], edgecolors='black', linewidths=0.8, zorder=5)
    ax.set_title(f"{TITLES[p]} - 20 zones", fontsize=13)
    ax.set_xlim(*XLIM); ax.set_ylim(*YLIM)
    ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
plt.suptitle('Time-Adaptive Demand Zones (k=20 centroids per period)\n'
             'NYC Yellow Taxi 2015 - zones shift only ~0.5-1 km between periods',
             fontsize=15, fontweight='bold', y=1.0)
plt.tight_layout()
plt.savefig('fig2_cluster_scatter_4panel.png', dpi=150, bbox_inches='tight')
print("Saved fig2_cluster_scatter_4panel.png")

# overlay: all periods' centroids on one map -> shows them sitting together
fig2, ax = plt.subplots(figsize=(9, 11))
for p in PERIODS:
    ax.scatter(cents[p].centroid_lon, cents[p].centroid_lat, s=110, marker='X',
               c=COLORS[p], edgecolors='black', linewidths=0.6, alpha=0.8, label=TITLES[p])
ax.set_xlim(*XLIM); ax.set_ylim(*YLIM)
ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
ax.set_title('All four periods overlaid (k=20 each)\nzones cluster in the same Manhattan core',
             fontsize=13)
ax.legend(); ax.grid(alpha=0.25)
plt.tight_layout()
plt.savefig('fig2b_centroid_overlay.png', dpi=150)
print("Saved fig2b_centroid_overlay.png")
