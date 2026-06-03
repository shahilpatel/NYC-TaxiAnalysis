#!/usr/bin/env python3
"""
5-arm longitudinal study: yellow/green 2015, yellow 2024, Uber/Lyft 2019 and 2024.

Reads era_zone_period.csv, fits weighted k-means (k=20) over 263 TLC zones per arm/period,
and computes zone drift, static-vs-adaptive dispatch gain, and dispersion metrics.
Runs twice: all-NYC and Manhattan-only (coverage control).
"""
import os, json, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "era_zone_period.csv")
FIGS = os.path.join(ROOT, "figures")
os.makedirs(FIGS, exist_ok=True)
PERIODS = ["AM_PEAK", "MIDDAY", "PM_PEAK", "NIGHT"]
PERIOD_LABEL = {"AM_PEAK": "AM Peak", "MIDDAY": "Midday", "PM_PEAK": "PM Peak", "NIGHT": "Night"}
ARMS = ["yellow_2015", "green_2015", "yellow_2024", "fhvhv_2019", "fhvhv_2024"]
ARM_LABEL = {"yellow_2015": "Yellow '15", "green_2015": "Green '15", "yellow_2024": "Yellow '24",
             "fhvhv_2019": "FHV '19", "fhvhv_2024": "FHV '24"}
ARM_COLOR = {"yellow_2015": "#f1c40f", "green_2015": "#27ae60", "yellow_2024": "#e67e22",
             "fhvhv_2019": "#9b59b6", "fhvhv_2024": "#2980ff"}
K = 20
BASELINE = "AM_PEAK"
RNG = np.random.default_rng(42)
LAT0, LON0 = 40.75, -73.95

def to_km(lat, lon):
    return np.column_stack([(lon - LON0) * 111.32 * math.cos(math.radians(LAT0)),
                            (lat - LAT0) * 110.57])
def km_to_ll(x, y):
    return (LAT0 + y / 110.57, LON0 + x / (111.32 * math.cos(math.radians(LAT0))))
def haversine(la1, lo1, la2, lo2):
    R = 6371.0; p = math.pi / 180
    dla = (la2 - la1) * p; dlo = (lo2 - lo1) * p
    a = np.sin(dla/2)**2 + np.cos(la1*p)*np.cos(la2*p)*np.sin(dlo/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def kpp_init(X, w, k):
    n = len(X); C = [X[RNG.choice(n, p=w/w.sum())]]
    for _ in range(1, k):
        D = np.min(((X[:, None, :] - np.array(C)[None, :, :])**2).sum(2), axis=1)
        pr = D * w; s = pr.sum()
        C.append(X[RNG.integers(n)] if s == 0 else X[RNG.choice(n, p=pr/s)])
    return np.array(C, dtype=float)

def wkmeans(X, w, k, iters=80, restarts=6):
    best = None; k = min(k, len(X))
    for _ in range(restarts):
        C = kpp_init(X, w, k); a = None
        for _ in range(iters):
            a = ((X[:, None, :] - C[None, :, :])**2).sum(2).argmin(1)
            newC = C.copy()
            for j in range(k):
                m = a == j
                if m.any():
                    newC[j] = (X[m] * w[m][:, None]).sum(0) / w[m].sum()
            if np.allclose(newC, C):
                C = newC; break
            C = newC
        inertia = (w * ((X - C[a])**2).sum(1)).sum()
        if best is None or inertia < best[0]:
            best = (inertia, C.copy(), a.copy())
    return best[1], best[2]

def analyze(df):
    """Return centroids/zones/metrics/drift for one (already-filtered) dataframe."""
    centroids, zones, metrics = {}, {}, {}
    drift = {}
    for era in ARMS:
        centroids[era], zones[era], metrics[era] = {}, {}, {}
        for per in PERIODS:
            g = df[(df.era == era) & (df.period == per)]
            if g.empty:
                continue
            lat = g.lat.to_numpy(float); lon = g.lon.to_numpy(float); w = g.trips.to_numpy(float)
            zones[era][per] = g[["lat", "lon", "trips", "borough"]].reset_index(drop=True)
            C, a = wkmeans(to_km(lat, lon), w, K)
            lat_c, lon_c = km_to_ll(C[:, 0], C[:, 1])
            tc = np.array([w[a == j].sum() for j in range(len(C))])
            centroids[era][per] = list(zip(lat_c.tolist(), lon_c.tolist(), tc.tolist()))
            tot = w.sum(); man = g[g.borough == "Manhattan"].trips.sum(); p = w / tot
            cm_lat = (lat * w).sum()/tot; cm_lon = (lon * w).sum()/tot
            metrics[era][per] = {
                "trips": int(tot), "manhattan_share": float(man/tot),
                "entropy": float(-(p*np.log(p+1e-12)).sum()/math.log(len(w))) if len(w) > 1 else 0.0,
                "mean_radius_km": float((w*haversine(lat, lon, cm_lat, cm_lon)).sum()/tot),
            }
    for era in ARMS:
        if BASELINE not in centroids.get(era, {}):
            continue
        base = np.array(centroids[era][BASELINE])
        for per in PERIODS:
            if per not in zones[era]:
                continue
            z = zones[era][per]
            lat = z.lat.to_numpy(float); lon = z.lon.to_numpy(float); w = z.trips.to_numpy(float)
            def md(C):
                C = np.array(C)
                return float((w*haversine(lat[:, None], lon[:, None], C[None, :, 0], C[None, :, 1]).min(1)).sum()/w.sum())
            ad = md(centroids[era][per]); st = md(base)
            metrics[era][per].update(adaptive_km=ad, static_km=st,
                                     gain_pct=((st-ad)/st*100 if st else 0.0))
    def sym(C1, C2):
        C1 = np.array(C1); C2 = np.array(C2)
        d = haversine(C1[:, None, 0], C1[:, None, 1], C2[None, :, 0], C2[None, :, 1])
        return 0.5*(d.min(1).mean()+d.min(0).mean())
    for era in ARMS:
        D = np.full((4, 4), np.nan)
        for i, pi in enumerate(PERIODS):
            for j, pj in enumerate(PERIODS):
                if pi in centroids.get(era, {}) and pj in centroids[era]:
                    D[i, j] = sym(centroids[era][pi], centroids[era][pj])
        drift[era] = D
    return dict(centroids=centroids, zones=zones, metrics=metrics, drift=drift)

def arm_avg(res, era, key):
    vals = [res["metrics"][era][p][key] for p in PERIODS
            if p in res["metrics"].get(era, {}) and key in res["metrics"][era][p]]
    return float(np.mean(vals)) if vals else float("nan")
def arm_drift(res, era):
    D = res["drift"].get(era)
    return float(np.nanmean(D[np.triu_indices(4, 1)])) if D is not None else float("nan")
def arm_manshare(res, era):
    num = sum(res["metrics"][era][p]["manhattan_share"]*res["metrics"][era][p]["trips"]
              for p in PERIODS if p in res["metrics"].get(era, {}))
    den = sum(res["metrics"][era][p]["trips"] for p in PERIODS if p in res["metrics"].get(era, {}))
    return num/den if den else float("nan")

def main():
    df = pd.read_csv(CSV)
    df = df[df.period.isin(PERIODS)].copy()
    res_all = analyze(df)
    res_man = analyze(df[df.borough == "Manhattan"].copy())

    for era in ARMS:
        for per in PERIODS:
            if per not in res_all["centroids"].get(era, {}):
                continue
            d = os.path.join(ROOT, "results", "era_compare", era, per); os.makedirs(d, exist_ok=True)
            cs = [{"cluster_id": i, "centroid_lat": la, "centroid_lon": lo, "trip_count": int(tc)}
                  for i, (la, lo, tc) in enumerate(res_all["centroids"][era][per])]
            json.dump({"era": era, "period": per, "k": len(cs), "centroids": cs},
                      open(os.path.join(d, "centroids.json"), "w"))
        if res_all["centroids"].get(era):
            os.makedirs(os.path.join(ROOT, "viz", "era"), exist_ok=True)
            ez = {per: [[round(r.lat, 5), round(r.lon, 5), int(r.trips)]
                        for r in res_all["zones"][era][per].itertuples()]
                  for per in PERIODS if per in res_all["zones"][era]}
            json.dump({"era": era, "label": ARM_LABEL[era],
                       "centroids": {p: res_all["centroids"][era][p] for p in PERIODS if p in res_all["centroids"][era]},
                       "zones": ez}, open(os.path.join(ROOT, "viz", "era", f"{era}.json"), "w"))

    metrics_out = {"all": {}, "manhattan": {}}
    for scope, res in [("all", res_all), ("manhattan", res_man)]:
        for era in ARMS:
            metrics_out[scope][era] = {
                "manhattan_share": arm_manshare(res, era), "mean_radius_km": arm_avg(res, era, "mean_radius_km"),
                "avg_drift_km": arm_drift(res, era), "avg_gain_pct": arm_avg(res, era, "gain_pct"),
                "per_period": res["metrics"].get(era, {})}
    json.dump(metrics_out, open(os.path.join(ROOT, "era_metrics.json"), "w"), indent=2, default=float)

    make_figures(res_all, res_man)
    write_summary(res_all, res_man)
    print("done. arms:", [e for e in ARMS if res_all['centroids'].get(e)])

def make_figures(res_all, res_man):
    arms = [e for e in ARMS if res_all["centroids"].get(e)]
    n = len(arms); fig, ax = plt.subplots(1, n, figsize=(3.4*n, 5.4), squeeze=False); ax = ax[0]
    for k, era in enumerate(arms):
        agg = {}
        for per in PERIODS:
            if per in res_all["zones"].get(era, {}):
                for r in res_all["zones"][era][per].itertuples():
                    agg[(r.lat, r.lon)] = agg.get((r.lat, r.lon), 0)+r.trips
        if not agg:
            continue
        la = np.array([p[0] for p in agg]); lo = np.array([p[1] for p in agg]); tr = np.array([agg[p] for p in agg], float)
        ax[k].scatter(lo, la, s=4+200*np.sqrt(tr/tr.max()), c=np.sqrt(tr), cmap="inferno", alpha=0.85, edgecolors="none")
        ax[k].set_title(f"{ARM_LABEL[era]}\nManh {arm_manshare(res_all, era)*100:.0f}%  r={arm_avg(res_all, era,'mean_radius_km'):.1f}km", fontsize=10)
        ax[k].set_xlim(-74.05, -73.7); ax[k].set_ylim(40.55, 40.92); ax[k].set_xticks([]); ax[k].set_yticks([])
    fig.suptitle("Pickup demand geography by mode & year (same 263 zones) — the dispersion shift", fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(FIGS, "figA_era_demand.png"), dpi=130); plt.close(fig)

    x = np.arange(len(arms)); wbar = 0.38
    fig, axB = plt.subplots(figsize=(9, 5))
    axB.bar(x-wbar/2, [arm_drift(res_all, e) for e in arms], wbar, label="all NYC", color="#4c8dff")
    axB.bar(x+wbar/2, [arm_drift(res_man, e) for e in arms], wbar, label="Manhattan only", color="#b9c8e8")
    axB.set_xticks(x); axB.set_xticklabels([ARM_LABEL[e] for e in arms]); axB.set_ylabel("avg inter-period zone drift (km)")
    axB.set_title("Do zones move more in the dispersed modern regime?", fontweight="bold"); axB.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIGS, "figB_era_drift.png"), dpi=130); plt.close(fig)

    fig, axC = plt.subplots(figsize=(9, 5))
    axC.bar(x-wbar/2, [arm_avg(res_all, e, "gain_pct") for e in arms], wbar, label="all NYC", color="#27ae60")
    axC.bar(x+wbar/2, [arm_avg(res_man, e, "gain_pct") for e in arms], wbar, label="Manhattan only", color="#a9dfbf")
    axC.axhline(0, color="#888", lw=0.8)
    axC.set_xticks(x); axC.set_xticklabels([ARM_LABEL[e] for e in arms]); axC.set_ylabel("avg adaptive-zoning gain (%)")
    axC.set_title("Does time-adaptive zoning pay off? (controlled across mode/year)", fontweight="bold"); axC.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIGS, "figC_era_gain.png"), dpi=130); plt.close(fig)

    fig, axD = plt.subplots(figsize=(9, 6.5))
    for res, mk, sc in [(res_all, "o", "all NYC"), (res_man, "s", "Manhattan only")]:
        for era in arms:
            xs = [res["metrics"][era][p]["mean_radius_km"] for p in PERIODS
                  if p in res["metrics"].get(era, {}) and "gain_pct" in res["metrics"][era][p]]
            ys = [res["metrics"][era][p]["gain_pct"] for p in PERIODS
                  if p in res["metrics"].get(era, {}) and "gain_pct" in res["metrics"][era][p]]
            axD.scatter(xs, ys, marker=mk, s=70, color=ARM_COLOR[era], edgecolors="k", alpha=0.85,
                        label=ARM_LABEL[era] if mk == "o" else None)
    axD.set_xlabel("demand dispersion — mean radius from centre of mass (km)")
    axD.set_ylabel("adaptive-zoning gain (%)")
    axD.set_title("Decision rule: adaptive zoning pays off as demand disperses\n(circles = all NYC, squares = Manhattan-only control)", fontweight="bold")
    axD.grid(alpha=0.3); axD.legend(title="arm", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIGS, "figD_gain_vs_dispersion.png"), dpi=130); plt.close(fig)

def write_summary(res_all, res_man):
    arms = [e for e in ARMS if res_all["centroids"].get(e)]
    lines = ["# Era comparison — controlled 5-arm summary\n",
             "| arm | n (trips) | Manhattan % | radius km | drift km | adaptive gain % | (Manh-only gain %) |",
             "|---|---|---|---|---|---|---|"]
    for e in arms:
        ntot = sum(res_all["metrics"][e][p]["trips"] for p in PERIODS if p in res_all["metrics"].get(e, {}))
        lines.append(f"| {ARM_LABEL[e]} | {ntot:,} | {arm_manshare(res_all,e)*100:.1f}% | "
                     f"{arm_avg(res_all,e,'mean_radius_km'):.2f} | {arm_drift(res_all,e):.2f} | "
                     f"{arm_avg(res_all,e,'gain_pct'):+.2f} | {arm_avg(res_man,e,'gain_pct'):+.2f} |")
    def g(res, e): return arm_avg(res, e, "gain_pct")
    dec = ["", "## Decomposition (separating mode from time)"]
    if all(a in arms for a in ["yellow_2015", "yellow_2024"]):
        dec.append(f"- A->C time-within-yellow: gain {g(res_all,'yellow_2015'):+.1f}% -> {g(res_all,'yellow_2024'):+.1f}% "
                   f"(radius {arm_avg(res_all,'yellow_2015','mean_radius_km'):.1f}->{arm_avg(res_all,'yellow_2024','mean_radius_km'):.1f}km)")
    if all(a in arms for a in ["yellow_2024", "fhvhv_2024"]):
        dec.append(f"- C->E mode/coverage (same year): gain {g(res_all,'yellow_2024'):+.1f}% -> {g(res_all,'fhvhv_2024'):+.1f}%")
    if all(a in arms for a in ["fhvhv_2019", "fhvhv_2024"]):
        dec.append(f"- D->E rideshare's own trend: gain {g(res_all,'fhvhv_2019'):+.1f}% -> {g(res_all,'fhvhv_2024'):+.1f}%")
    dec.append(f"- Manhattan-only control: FHV'24 gain stays {g(res_man,'fhvhv_2024'):+.1f}% even within the common footprint "
               f"(vs {g(res_all,'fhvhv_2024'):+.1f}% all-NYC).")
    open(os.path.join(ROOT, "era_summary.md"), "w").write("\n".join(lines + dec) + "\n")
    print("\n".join(lines + dec))

if __name__ == "__main__":
    main()
