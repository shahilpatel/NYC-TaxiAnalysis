"""06_zone_drift.py -- Phase 6: zone-drift heatmap between time periods.
For each period pair, average centroid displacement (km) -- a Hausdorff-inspired
measure of how much the optimal zone layout moves. Reads the 4 centroids.json
files from GCS. Run after the Dataproc job finishes."""
import os, json
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
    "/Users/shahil/Documents/UCSB/2025-2026/PSTAT135/pstat135-nyc-taxi-4db0653d3d93.json"
from google.cloud import storage
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.spatial.distance import cdist

BUCKET = "pstat135-taxi-shahil"
TIME_PERIODS = ["AM_PEAK", "PM_PEAK", "MIDDAY", "NIGHT"]
gcs = storage.Client()


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1); dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat/2)**2
         + np.cos(np.radians(lat1))*np.cos(np.radians(lat2))*np.sin(dlon/2)**2)
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


centroids = {}
for p in TIME_PERIODS:
    d = json.loads(gcs.bucket(BUCKET).blob(
        f"results/temporal_kmeans/{p}/centroids.json").download_as_text())
    centroids[p] = pd.DataFrame(d["centroids"])
    print(f"{p}: {len(centroids[p])} centroids (k={d['k']})")

drift = pd.DataFrame(index=TIME_PERIODS, columns=TIME_PERIODS, dtype=float)
for p in TIME_PERIODS:
    drift.loc[p, p] = 0.0
pairs = [(a, b) for i, a in enumerate(TIME_PERIODS) for b in TIME_PERIODS[i+1:]]
for p1, p2 in pairs:
    c1 = centroids[p1][["centroid_lat", "centroid_lon"]].values
    c2 = centroids[p2][["centroid_lat", "centroid_lon"]].values
    dm = cdist(c1, c2, lambda u, v: haversine(u[0], u[1], v[0], v[1]))
    avg = (dm.min(axis=1).mean() + dm.min(axis=0).mean()) / 2
    drift.loc[p1, p2] = drift.loc[p2, p1] = round(avg, 3)
    print(f"  {p1} vs {p2}: {avg:.3f} km avg centroid drift")

fig, ax = plt.subplots(figsize=(7, 5))
sns.heatmap(drift.astype(float), annot=True, fmt=".2f", cmap="YlOrRd", ax=ax,
            linewidths=0.5, cbar_kws={"label": "Avg Centroid Drift (km)"})
ax.set_title("Zone Drift Between Time Periods\n(km avg centroid displacement)", fontsize=12)
plt.tight_layout()
plt.savefig("figures/fig3_zone_drift.png", dpi=150)
print("\nSaved fig3_zone_drift.png")
mx = max(pairs, key=lambda pr: drift.loc[pr[0], pr[1]])
print(f"Largest drift: {mx[0]} vs {mx[1]} = {drift.loc[mx[0], mx[1]]:.2f} km")
