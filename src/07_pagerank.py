"""07_pagerank.py -- PageRank on the NYC taxi origin-destination graph (Phase 7).
Uses the already-built od_matrix BigQuery table; independent of the Spark job."""
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
    "/Users/shahil/Documents/UCSB/2025-2026/PSTAT135/pstat135-nyc-taxi-4db0653d3d93.json"
from google.cloud import bigquery
import networkx as nx
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

client = bigquery.Client(project="pstat135-nyc-taxi")

df_od = client.query("""
    SELECT
      CONCAT(CAST(origin_lat AS STRING), ',', CAST(origin_lon AS STRING)) AS src,
      CONCAT(CAST(dest_lat   AS STRING), ',', CAST(dest_lon   AS STRING)) AS dst,
      origin_lat, origin_lon, trip_volume
    FROM `pstat135-nyc-taxi.taxi_analysis.od_matrix`
    WHERE trip_volume >= 50
""").to_dataframe()
print(f"Graph edges (trip_volume>=50): {len(df_od):,}")

G = nx.from_pandas_edgelist(df_od, source='src', target='dst',
                            edge_attr='trip_volume', create_using=nx.DiGraph())
print(f"Nodes: {G.number_of_nodes():,} | Edges: {G.number_of_edges():,}")

pr = nx.pagerank(G, weight='trip_volume', alpha=0.85, max_iter=100)
pr_df = (pd.DataFrame([{'node': k, 'pagerank': v} for k, v in pr.items()])
         .sort_values('pagerank', ascending=False))

coords = (df_od[['src', 'origin_lat', 'origin_lon']]
          .rename(columns={'src': 'node'}).drop_duplicates('node'))
pr_df = pr_df.merge(coords, on='node').head(25)

os.makedirs('data', exist_ok=True)
pr_df.to_json('data/pagerank_hubs.json', orient='records', indent=2)
print("\nTop 10 hubs (lat, lon | pagerank):")
for _, r in pr_df.head(10).iterrows():
    print(f"  ({r.origin_lat:.3f}, {r.origin_lon:.3f})  pr={r.pagerank:.5f}")

fig, ax = plt.subplots(figsize=(10, 6))
top = pr_df.head(15)
colors_pr = plt.cm.RdYlGn_r(np.linspace(0, 0.8, len(top)))
ax.barh(range(len(top)), top['pagerank'].values, color=colors_pr[::-1])
ax.set_yticks(range(len(top)))
ax.set_yticklabels([f"({r.origin_lat:.2f}, {r.origin_lon:.2f})" for _, r in top.iterrows()])
ax.set_xlabel('PageRank Score')
ax.set_title('Top 15 Trip Network Hubs - NYC 2015\n(PageRank on Origin-Destination Graph)',
             fontsize=13)
ax.invert_yaxis()
plt.tight_layout()
plt.savefig('fig5_pagerank.png', dpi=150)
print("\nSaved fig5_pagerank.png and data/pagerank_hubs.json")
