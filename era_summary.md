# Era comparison — controlled 5-arm summary

| arm | n (trips) | Manhattan % | radius km | drift km | adaptive gain % | (Manh-only gain %) |
|---|---|---|---|---|---|---|
| Yellow '15 | 142,505,668 | 92.4% | 3.10 | 0.70 | +0.18 | +2.11 |
| Green '15 | 19,227,283 | 28.4% | 6.64 | 1.08 | +7.50 | -8.75 |
| Yellow '24 | 41,028,021 | 88.7% | 3.89 | 1.28 | +9.12 | +12.70 |
| FHV '19 | 44,120,902 | 44.0% | 7.83 | 1.67 | +4.29 | +2.77 |
| FHV '24 | 240,111,310 | 38.8% | 8.39 | 1.48 | -1.53 | +2.06 |

## Decomposition (separating mode from time)
- A->C time-within-yellow: gain +0.2% -> +9.1% (radius 3.1->3.9km)
- C->E mode/coverage (same year): gain +9.1% -> -1.5%
- D->E rideshare's own trend: gain +4.3% -> -1.5%
- Manhattan-only control: FHV'24 gain stays +2.1% even within the common footprint (vs -1.5% all-NYC).
