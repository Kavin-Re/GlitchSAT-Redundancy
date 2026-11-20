# P12 pre-registration: random-flip (binary symmetric channel) waterfall

Written 2026-11-20T05:10Z (UTC), BEFORE any Monte Carlo run and before my own enumerator was run. Nothing here is a result. This is a random-flip TEACHING model: not an attacker model, not a physical error rate, no bit-error-rate claim for silicon. Toy design, modelled bit flips only. Nothing established as new.

## Prior knowledge when writing (so these are not blind predictions)
- `research/c5/anchor/bf_*.json` (z3-free brute force, goal word, any wrong key): stored V2 min 3 flips with 182 attacking triples at T=3 and at T=4; apt-0.33 V2 min 2 with 3 attacking pairs at T=4. Those counts are over ANY wrong key (a set counts if at least one of the 255 wrong keys is accepted). The stored-V2 witness works on only 3 keys (first 0xC7), the apt witness on all 255.
- V0 and V1 have min 1; V2e (`rtl/v2e.v`, apt 0.33) has min 3 (P01).
- I have not computed per-key counts, V0/V1/V2e counts, or run any random-flip simulation.

## Model (fixed now)
- Designs and netlists: V0, V1, V2-stored = `reference/spike_netlists/v{0,1,2}.json`; V2-apt = `research/c4/b3_inputs/nl/v2_apt033.json`; V2e = `research/c6/p01/netlists/nl_apt_v2e.json`.
- Fault sites: every gate output and every flop Q (the anchor simulator's stem-flip sites), n per design. Horizon T = 4 cycles for every design. N = n x T site-cycles.
- Channel: every site-cycle flips independently with probability p (flip = value xor 1 in that cycle, seen by all fanout and the output port, same semantics as `anchor_sim.py`).
- False accept: `boot_word == 0x96` at some cycle t < 4, with the input `sig` held at one FIXED wrong key for the whole run. Known flop init.
- Which wrong key: per design, the wrong key with the largest number of attacking sets of the minimum size (ties: smallest key value). This mirrors the solver, whose model is free to choose the input; it is chosen from the exact enumerator, before any Monte Carlo. I will also report the any-key count (the anchor's 182 and 3) and the mean over the 255 wrong keys. Consequence fixed now: per-key A_d can be SMALLER than the any-key count, and the intercept prediction uses the per-key number.
- Exact enumerator: all flip sets of size d <= K (K = 3 for the V2 designs; K = 3 or more for V0, V1 if cheap), A_d = number that give a false accept at the fixed key. My enumerator must reproduce the anchor any-key counts (182 at d=3 stored T=4; 3 at d=2 apt T=4) or I stop.
- Monte Carlo: bit-parallel, 9 values of p log-spaced from 1e-3 to 1e-1 (4 per decade). Trial count per point fixed in advance from the truncated series (aim >= 200 hits; hard cap 4e9 trials per point; no stopping on the observed hits). Points with fewer than 20 hits are omitted from the figure and from every comparison; points with fewer than 100 hits are flagged. 95% interval: exact binomial (Clopper-Pearson). Seeds fixed in the script.

## Predictions
- P1 (slope). Least-squares slope of log10(estimate) against log10(p) over the points with p <= 3.2e-3 (the three lowest, where they have >= 20 hits) is within 0.35 of d_min: V0 1, V1 1, V2-stored 3, V2-apt 2, V2e 3. I expect the measured local slope to sit a little BELOW d_min for V0/V1 only if saturation begins, and at or slightly above for the V2 designs if higher-order sets already matter.
- P2 (series, as posed in the brief). The truncated series S_K(p) = sum_{d<=K} A_d p^d (1-p)^(N-d) lies inside the Monte Carlo 95% interval at every point where MC has >= 20 hits and the series predicts >= 20 hits.
  My expectation before running: P2 holds only where N x p is small. S_K is a strict LOWER bound on the true probability (it drops all sets larger than K). With N about 300 and p = 1e-3, N p is about 0.3, and if most supersets of an attacking set still attack, S_K is low by up to a factor (1-p)^(N-d_min), about 0.74. So I expect P2 to FAIL for the V2 designs at most or all plotted points, by undershoot, and to fail for every design at p >= 1e-2. I register it anyway as posed; a failure will be reported as a failure.
- P3 (leading term). A_dmin p^dmin is within a factor 2 of the MC estimate at the lowest plotted point for every design.
- P4 (bounds). No MC 95% interval lies entirely below S_K (S_K is a lower bound). Any such point means a bug in the simulator or the enumerator.
- P5 (ranking). At p = 1e-3 the order of P(false accept) is V0 >= V1 > V2-apt > V2-stored, and V2-apt sits one slope unit above V2-stored. I do not predict where V2e falls relative to V2-stored (same d_min; depends on the counts).

## Falsifiers
- P1: any design with a fitted slope outside d_min +/- 0.35.
- P2: any eligible point with S_K outside the MC interval.
- P3: ratio outside [0.5, 2].
- P4: any point with ci_hi < S_K.
- P5: any other order at p = 1e-3 (among points with >= 20 hits; if a design has no eligible point at 1e-3, P5 is "not testable" for it, not a pass).
- Enumerator check: any-key counts different from the anchor files.

All failed predictions will be reported at full prominence in `P12_REPORT.md`.
