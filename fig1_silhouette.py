"""fig1_silhouette.py -- Elbow (WSSSE) + silhouette curves per period (Phase 4 fig1).
Sweep values harvested from the Dataproc job logs (k in 10/15/20/25). These
justify the resolution choice; the final comparison uses a fixed k=20 for all
periods so static-vs-adaptive routing is fair."""
import matplotlib.pyplot as plt

K = [10, 15, 20, 25]
SIL = {  # silhouette score
    'AM_PEAK': [0.5556, 0.5256, 0.5568, 0.5373],
    'PM_PEAK': [0.5556, 0.5628, 0.5569, 0.5619],
    'MIDDAY':  [0.5413, 0.5418, 0.5129, 0.5248],
    'NIGHT':   [0.4960, 0.5950, 0.5635, 0.5701],
}
WSSSE = {  # within-cluster sum of squares (elbow)
    'AM_PEAK': [2609876.6, 1776910.2, 1095322.3, 966231.7],
    'PM_PEAK': [2942697.1, 1910530.5, 1397529.1, 1112734.3],
    'MIDDAY':  [4399943.9, 2931447.6, 2313491.7, 1751111.3],
    'NIGHT':   [7331141.0, 3998338.8, 3096341.8, 2355036.4],
}
COLORS = {'AM_PEAK': '#e74c3c', 'PM_PEAK': '#f39c12', 'MIDDAY': '#27ae60', 'NIGHT': '#5b8def'}

fig, (axL, axR) = plt.subplots(1, 2, figsize=(14, 5))
for p in SIL:
    axL.plot(K, WSSSE[p], 'o-', color=COLORS[p], label=p, linewidth=2, markersize=7)
    axR.plot(K, SIL[p], 'o-', color=COLORS[p], label=p, linewidth=2, markersize=7)
axL.set_title('Elbow: WSSSE vs k', fontsize=13)
axL.set_xlabel('k (number of zones)'); axL.set_ylabel('WSSSE (training cost)')
axL.set_xticks(K); axL.legend(); axL.grid(alpha=0.3)
axR.axvline(20, color='gray', ls='--', alpha=0.6, label='k=20 (chosen)')
axR.set_title('Silhouette vs k', fontsize=13)
axR.set_xlabel('k (number of zones)'); axR.set_ylabel('Silhouette score')
axR.set_xticks(K); axR.legend(); axR.grid(alpha=0.3)
plt.suptitle('K-means model selection per time period (NYC Yellow Taxi 2015)',
             fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('fig1_elbow_silhouette.png', dpi=150)
print("Saved fig1_elbow_silhouette.png")
