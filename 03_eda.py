"""04 EDA overview — reads cleaned_trips and trips_with_period from BigQuery."""
import os
from google.cloud import bigquery
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

client = bigquery.Client(project="pstat135-nyc-taxi")
T = "pstat135-nyc-taxi.taxi_analysis"

summary = client.query(f"""
    SELECT time_period, COUNT(*) AS trips,
      ROUND(AVG(trip_distance),2) AS avg_dist, ROUND(AVG(fare_amount),2) AS avg_fare,
      ROUND(STDDEV(fare_amount),2) AS fare_std
    FROM `{T}.trips_with_period` GROUP BY time_period ORDER BY trips DESC
""").to_dataframe()
print(summary.to_string(index=False))

hourly = client.query(f"SELECT pickup_hour, COUNT(*) AS trips FROM `{T}.cleaned_trips` GROUP BY pickup_hour ORDER BY pickup_hour").to_dataframe()
dow = client.query(f"SELECT pickup_dow, COUNT(*) AS trips FROM `{T}.cleaned_trips` GROUP BY pickup_dow ORDER BY pickup_dow").to_dataframe()
dow['day'] = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
monthly = client.query(f"SELECT pickup_month, COUNT(*) AS trips FROM `{T}.cleaned_trips` GROUP BY pickup_month ORDER BY pickup_month").to_dataframe()
sample = client.query(f"""
    SELECT pickup_lat, pickup_lon, time_period
    FROM `{T}.trips_with_period` WHERE RAND() < 0.001 LIMIT 100000
""").to_dataframe()

fig = plt.figure(figsize=(16, 10))
gs = gridspec.GridSpec(2, 2, figure=fig)

ax1 = fig.add_subplot(gs[0, 0])
ax1.bar(hourly['pickup_hour'], hourly['trips'] / 1e6, color='steelblue')
ax1.set_title('Hourly Trip Volume (2015)', fontsize=13)
ax1.set_xlabel('Hour of Day'); ax1.set_ylabel('Trips (millions)')
for period, (s, e, c) in {'AM Peak': (7, 9, 'red'), 'PM Peak': (16, 19, 'orange'), 'Night': (20, 23, 'navy')}.items():
    ax1.axvspan(s, e, alpha=0.15, color=c, label=period)
ax1.legend(fontsize=9)

ax2 = fig.add_subplot(gs[0, 1])
ax2.bar(dow['day'], dow['trips'] / 1e6, color=['#e74c3c' if d in ['Sat', 'Fri'] else 'steelblue' for d in dow['day']])
ax2.set_title('Trip Volume by Day of Week', fontsize=13); ax2.set_ylabel('Trips (millions)')

ax3 = fig.add_subplot(gs[1, 0])
ax3.plot(monthly['pickup_month'], monthly['trips'] / 1e6, 'go-', linewidth=2, markersize=8)
ax3.set_title('Monthly Trip Volume (2015)', fontsize=13)
ax3.set_xlabel('Month'); ax3.set_ylabel('Trips (millions)')
ax3.set_xticks(range(1, 13))
ax3.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], rotation=30)

ax4 = fig.add_subplot(gs[1, 1])
cmap = {'AM_PEAK': 'red', 'PM_PEAK': 'orange', 'MIDDAY': 'green', 'NIGHT': 'navy'}
for period in sample['time_period'].unique():
    m = sample['time_period'] == period
    ax4.scatter(sample.loc[m, 'pickup_lon'], sample.loc[m, 'pickup_lat'], alpha=0.15, s=1,
                c=cmap.get(period, 'gray'), label=period)
ax4.set_title('Pickup Locations by Time Period', fontsize=13)
ax4.set_xlabel('Longitude'); ax4.set_ylabel('Latitude'); ax4.legend(markerscale=8, fontsize=9)
ax4.set_xlim(-74.05, -73.90); ax4.set_ylim(40.65, 40.85)

plt.suptitle('NYC Yellow Taxi 2015 - Exploratory Data Analysis', fontsize=15, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig('fig0_eda_overview.png', dpi=150, bbox_inches='tight')
print("Saved fig0_eda_overview.png")
