# P12 report: random-flip waterfall

2026-11-20. Random-flip teaching model; not an attacker model and not a physical error rate. Toy design, modelled bit flips, no silicon claim, nothing established as new. All numbers SIMULATED: exact counts from `bsc_channel.py enum` (`enum.json`, `enum.log`), Monte Carlo from `bsc_channel.py mc` (`mc.log`, `results/comms/waterfall.csv`), comparisons in `analysis.out`. Pre-registration: `PREREG.md` (written before the enumerator and before any Monte Carlo run).

## FAILED prediction first
**P2 (truncated series inside the Monte Carlo 95% interval at every eligible point): FAILED.** Eligible points (MC hits >= 20 and series predicts >= 20 hits): 31. Inside the interval: 9. Outside: 22, all by undershoot.
- Inside: V0 and V1 at p = 1e-3, 1.8e-3, 3.2e-3; V2-apt at 1e-3 and 1.8e-3; V2-stored at 1e-3 only.
- V2e fails at every eligible point, including the lowest (series/MC = 0.80 at p = 1e-3).
- Cause, as anticipated in the pre-registration: the series stops at sets of 3 flips and is a lower bound. With N = 304 to 388 site-cycles, N x p is 0.3 to 0.4 already at p = 1e-3, so larger sets carry 14% to 20% of the probability for the 3-flip designs. At p = 0.1 the series is low by more than ten orders of magnitude and is useless there.
- The brief's sentence "the exact series matches the Monte Carlo" therefore holds only at the bottom edge of the plotted range, and not at all for V2e. A fair test needs either K >= 4 in the enumerator or p below 1e-3; neither was run.

## Predictions against measurements
| # | prediction | measured | verdict |
|---|---|---|---|
| P1 | low-p slope (three lowest points) within 0.35 of min flips 1, 1, 3, 2, 3 | V0 0.984, V1 0.881, V2-stored 3.003, V2-apt 2.137, V2e 2.971 | holds |
| P2 | truncated series inside the 95% interval at all eligible points | 9 of 31 | **FAILS** |
| P3 | A_dmin x p^dmin within a factor 2 of MC at p = 1e-3 | ratios 1.02, 1.04, 1.16, 1.01, 1.17 | holds |
| P4 | no MC interval entirely below the series | 0 of 45 | holds |
| P5 | at p = 1e-3: V0 >= V1 > V2-apt > V2-stored | 1.08e-2, 9.6e-4, 2.98e-6, 6.9e-8 | holds |
| check | any-key counts equal the anchor files | 182 triples (stored, T=4), 3 pairs (apt, T=4) | equal |

The slope guide was also my prior sub-expectation "at or slightly above d_min for the V2 designs": V2-apt 2.14 is above, V2-stored 3.00 and V2e 2.97 are not distinguishable from 3.

## Exact counts (T = 4, K = 3)
| design | netlist sha256 (12) | sites x T = N | key | A_1, A_2, A_3 at key | any wrong key | mean over 255 wrong keys |
|---|---|---|---|---|---|---|
| V0 | 103ad03e40a5 | 20 x 4 = 80 | 0xC7 | 11, 730, 23561 | 15, 999, 32244 | 8.2, 581, 19988 |
| V1 | 84730fa7b5e3 | 66 x 4 = 264 | 0x00 | 1, 211, 21794 | 1, 243, 28033 | 1, 209, 21388 |
| V2-stored | 289355dc483b | 76 x 4 = 304 | 0xC7 | 0, 0, 80 | 0, 0, 182 | 0, 0, 6.2 |
| V2-apt | 031980732ade | 93 x 4 = 372 | 0x00 | 0, 3, 1341 | 0, 3, 1777 | 0, 3, 1349 |
| V2e | 005b02a5d7a7 | 97 x 4 = 388 | 0xC7 | 0, 0, 734 | 0, 0, 1065 | 0, 0, 543 |

Key = the wrong key with the most minimum-size sets (ties: smallest value). Every one of the 255 wrong keys reaches the minimum in every design, but for V2-stored the count depends strongly on the key (80 at 0xC7, mean 6.2), so the plotted V2-stored curve is that design's worst fixed key, about 13 times above its key-average.

## Monte Carlo at the lowest and highest p (full table: the CSV, 45 rows)
| design | p = 1e-3: hits / trials, estimate [95%] | series | p = 0.1 estimate |
|---|---|---|---|
| V0 | 45282 / 4194304, 1.080e-2 [1.070e-2, 1.090e-2] | 1.086e-2 | 0.382 |
| V1 | 4022 / 4194304, 9.59e-4 [9.30e-4, 9.89e-4] | 9.48e-4 | 9.6e-3 |
| V2-stored | 172 / 2500853760, 6.88e-8 [5.89e-8, 7.99e-8] | 5.92e-8 | 6.0e-3 |
| V2-apt | 200 / 67108864, 2.98e-6 [2.58e-6, 3.42e-6] | 3.00e-6 | 8.0e-3 |
| V2e | 171 / 272629760, 6.27e-7 [5.37e-7, 7.29e-7] | 4.99e-7 | 8.6e-3 |

Every one of the 45 points has at least 171 hits, so none is omitted or flagged.

## What surprised me
- V2e, built to restore 3 flips, is about 9 times MORE likely to false-accept than V2-stored under random flips at low p (734 against 80 triples), and from p = 1.8e-2 it is level with or above V2-apt, which needs only 2 flips. Random-flip rate and adversarial minimum rank these designs differently.
- At p = 0.1 the three V2 netlists (0.6% to 0.9%) are within a factor 1.6 of V1 (1.0%): the redundancy advantage is a low-noise property in this model.
- V1's curve flattens near 0.7% from p = 1e-2 to 3e-2; I did not investigate why (presumably the single attacking site saturates while extra flips spoil it).

## Deviations from the pre-registration
- Trial counts were fixed in advance from the leading term A_dmin x p^dmin (target 200 hits, minimum 4 x 2^20 trials, cap 4e9), not from the truncated series as written: the series collapses at high p and would have demanded impossible trial counts. Still no stopping on observed hits. Two points ended slightly under 200 hits (172, 171) because the leading term overestimates.
- "Flagged below 100 hits" never applied.

## Not done / limits
- K = 4 enumeration and p below 1e-3 (needed to test P2 fairly); key-averaged or uniformly random key Monte Carlo; other horizons than T = 4; V5; any design beyond the five netlists; any independent re-implementation of the Monte Carlo (the enumerator and the Monte Carlo share one gate simulator, so P4 and the low-p agreement test the sampler and the counting, not the gate semantics; the gate semantics are checked only through the match with the anchor counts 182 and 3).
- One seed set, one run. Runtime: enumeration 23 s, Monte Carlo about 2 min on 4 cores.
- Tests: `python3 -m pytest -q tests/test_waterfall.py`, 13 passed.

## Files
`scripts/comms/bsc_channel.py`, `results/comms/waterfall.csv`, `docs/comms/waterfall.png`, `docs/comms/WATERFALL_NOTES.md`, `tests/test_waterfall.py`, `research/c6/p12/{PREREG.md, P12_REPORT.md, enum.json, enum.log, mc.log, analysis.out}`.
