"""08_bqml_figures.py -- Phase 8 figures: model R2 comparison + feature importance.
Reads ML.EVALUATE / ML.FEATURE_IMPORTANCE from the three trained BQML models."""
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
    "/Users/shahil/Documents/UCSB/2025-2026/PSTAT135/pstat135-nyc-taxi-4db0653d3d93.json"
from google.cloud import bigquery
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

client = bigquery.Client(project="pstat135-nyc-taxi")
M = "pstat135-nyc-taxi.taxi_analysis"

comp = client.query(f"""
  SELECT 'Linear\\n(numeric)' AS model, r2_score, mean_absolute_error FROM ML.EVALUATE(MODEL `{M}.demand_forecast`)
  UNION ALL SELECT 'Linear\\n(categorical)', r2_score, mean_absolute_error FROM ML.EVALUATE(MODEL `{M}.demand_forecast_cat`)
  UNION ALL SELECT 'Boosted\\nTree', r2_score, mean_absolute_error FROM ML.EVALUATE(MODEL `{M}.demand_forecast_bt`)
""").to_dataframe()
order = ['Linear\n(numeric)', 'Linear\n(categorical)', 'Boosted\nTree']
comp = comp.set_index('model').loc[order].reset_index()

fig6 = client.query(f"""
  SELECT feature, importance_gain FROM ML.FEATURE_IMPORTANCE(MODEL `{M}.demand_forecast_bt`)
  ORDER BY importance_gain DESC
""").to_dataframe()

fig, (axL, axR) = plt.subplots(1, 2, figsize=(14, 5))

# Left: R2 comparison
bars = axL.bar(comp['model'], comp['r2_score'],
               color=['#c0392b', '#e67e22', '#27ae60'], alpha=0.88)
for b, v, mae in zip(bars, comp['r2_score'], comp['mean_absolute_error']):
    axL.text(b.get_x()+b.get_width()/2, v+0.02, f"R²={v:.3f}\nMAE={mae:.0f}",
             ha='center', va='bottom', fontsize=10)
axL.set_ylim(0, 1.0); axL.set_ylabel('R² (test)')
axL.set_title('Demand Forecast: Model Comparison\n(zone_demand, 563,696 cells)', fontsize=12)

# Right: boosted-tree feature importance
labels = {'lon_bucket': 'Longitude', 'lat_bucket': 'Latitude', 'pickup_dow': 'Day of week',
          'pickup_hour': 'Hour', 'pickup_month': 'Month'}
fig6['lab'] = fig6['feature'].map(labels).fillna(fig6['feature'])
axR.barh(fig6['lab'][::-1], (fig6['importance_gain']/1e6)[::-1], color='#2980b9', alpha=0.85)
axR.set_xlabel('Importance (gain, millions)')
axR.set_title('Boosted-Tree Feature Importance\n(what drives hourly zone demand)', fontsize=12)

plt.tight_layout()
plt.savefig('fig6_demand_models.png', dpi=150)
print(comp.to_string(index=False))
print("\nSaved fig6_demand_models.png")
