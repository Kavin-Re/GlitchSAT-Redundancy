# P14 report: burst events against random flips

License: UNDECIDED. Working title TBD. All burst numbers are SIMULATED (modelled events on toy netlists, T = 6 cycles, yosys 0.33). One modelled burst event = all state flops (or one copy group) inverted in one cycle, or a whole-design rail event; it is not a real overclock or voltage glitch. Textbook coding theory measured on toy designs; nothing established as new.

## Files
- `scripts/comms/burst_sweep.py`: generator calls (imports `distance_sweep.py` and the `glitchsat.py` netlist loader read-only), z3 event engine, z3-free brute force, sweep.
- `results/comms/burst.csv`: 32 rows = 16 codebooks x {plain, struct} netlists; predicted and measured in separate columns.
- `docs/comms/BURST_NOTES.md`, `tests/test_burst_sweep.py` (18 tests).
- `research/c6/p14/PREREG.md` (2026-11-20T05:10:46Z), `try1.log` (first run of 3 codebooks, 05:12:34Z), `sweep_run.log` (full run, 05:15:12Z to 05:25:07Z, 595 s), `recheck_control.py` / `.log`.
- Command: `PYTHONPATH=product/src python3 scripts/comms/burst_sweep.py --out results/comms/burst.csv --work <dir> --cli 'python3 -m faultbound_wt.cli' --reduce both` (run in a copy under /tmp/work_p14).

## Predictions against measurements (plain netlists; struct identical in every burst cell)

Cells are "predicted / measured". Minimum number of events; "none" = no attack with any subset of that kind's events within T = 6 (bounded, not a guarantee). Random = minimum single-flip events (flops only; all nets), MEASURED by the product CLI (P11 CSV for the first ten rows, this run for the last six).

| codebook (I, C, W, B) | random flops: pred / meas | random all nets: pred / meas | all flops | one group | rail 1->0 | rail 0->1 | 2x2 quadrant pred = meas? |
|---|---|---|---|---|---|---|---|
| 69_96_complement (69,-,96,69) | >6 / >6 (P11) | P11 / 3 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-robust, burst-fragile |
| C3_3C_complement (C3,-,3C,C3) | >6 / >6 (P11) | P11 / 3 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-robust, burst-fragile |
| A5_5A_complement (A5,-,5A,A5) | >6 / >6 (P11) | P11 / 3 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-robust, burst-fragile |
| F0_96_stored (F0,CC,96,69) | P11 / 4 | P11 / 2 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-robust, burst-fragile |
| 2B_95 (2B,69,95,6A) | P11 / 6 | P11 / 3 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-robust, burst-fragile |
| 00_1F_F8_E7 (00,F8,1F,E7) | P11 / 5 | P11 / 3 | none / none | none / none | none / none | none / none | yes: random-robust, burst-robust |
| A5_A6 (A5,66,A6,59) | P11 / 2 | P11 / 2 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-fragile, burst-fragile |
| fam_d2 (95,56,96,69) | P11 / 2 | P11 / 2 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-fragile, burst-fragile |
| fam_d4 (99,66,96,69) | P11 / 4 | P11 / 2 | 1 / 1 | 3 / 3 | none / none | none / none | yes: random-robust, burst-fragile |
| Bvar_one_copy (69,-,96,DF) | P11 / 3 | P11 / 1 | 1 / 1 | 1 / 1 | none / none | none / none | yes: random-fragile, burst-fragile |
| F0_96_B3C (F0,CC,96,3C) | 4 / 4 | <=3 / 3 | none / none | none / none | none / none | none / none | yes: random-robust, burst-robust |
| 2B_95_BEB (2B,69,95,EB) | 6 / 6 | <=3 / 3 | none / none | none / none | none / none | none / none | yes: random-robust, burst-robust |
| A5_A6_BBE (A5,66,A6,BE) | 2 / 2 | <=3 / 2 | none / none | none / none | none / none | none / none | yes: random-fragile, burst-robust |
| F0_96_BDF (F0,CC,96,DF) | 3 / 3 | <=3 / 1 | none / none | 1 / 1 | none / none | none / none | yes: random-fragile, burst-robust |
| 00_FF_C01_B02 (00,01,FF,02) | >6 / >6 | <=3 / 3 | 1 / 1 | 3 / 3 | none / none | 1 / 1 | yes: random-robust, burst-fragile |
| FF_00_CFE_BFD (FF,FE,00,FD) | >6 / >6 | <=3 / 1 | 1 / 1 | 3 / 3 | 1 / 1 | none / none | yes: random-robust, burst-fragile |

"P11" in a predicted cell means the value was already measured by P11 before my pre-registration, so it is not a prediction.

**Outcome: P1 to P7 all held; 0 mismatches in 32 rows x 4 burst kinds (column `pred_match`).** No falsifier fired. Read this soberly: the P2 to P4 rules are a few lines of XOR arithmetic, and the generated circuits hold their state in every word that is not an FSM arm, so agreement shows that these netlists implement the arithmetic and that the engine is consistent with it. It is a weak test of anything deeper.

## Failures and deviations (full prominence)
1. **One engine-control row did not complete.** 2B_95_BEB, structural netlist: my engine's any-net single-flip control returned z3 "unknown" (120 s timeout), so it could not be compared with the product CLI's 3. The row is flagged `ENGINE_CHECK_FAILED: control mismatch` in the CSV and is left that way. Its flop-flip control (6 = CLI 6), brute-force and reduce checks passed. A separate re-run of that one control with a 420 s limit returned 3 in 58.5 s, equal to the CLI's 3, and its witness replayed in the z3-free simulator (`recheck_control.log`). The CSV was not edited after the sweep, so the flag stays.
2. **I changed the integration step's prediction before running.** The plan said the all-flop burst "cannot reach non-complementary accept words". Reading the generator showed that most P11 codebooks, including the stored F0/96 one, use fail word B = ~W, so I pre-registered cost 1 for those. Measured: 1. The original wording would have been falsified on F0_96_stored, 2B_95, A5_A6, fam_d2 and fam_d4 if "non-complementary" is read as idle against accept.
3. **The plan's 2x2 could not be filled from the listed codebooks.** With P11's fail words, only 00_1F_F8_E7 is burst-robust. I added six codebooks (fixed in PREREG) whose fail word is not the complement.
4. **The any-net control's brute force is partial**: plain enumeration up to 2 flips only where z3 said 1 or 2, flop flips up to 2; larger cases rest on z3 against the product CLI. The burst kinds are checked exhaustively (state search over all event subsets).
5. Not done: no product flag (`--event-model burst`), no lint, no yosys 0.38 run, no per-cycle varying input, no burst restricted to one comparator's gates (only flop groups), T = 6 only.

## Surprises
- The stored design is itself in the "random-robust, burst-fragile" cell, through its fail word, not its idle word (witness: `flops_all@2`).
- FF_00_CFE_BFD has all-nets random minimum 1 (MEASURED, product CLI, both netlists; my control agrees). Consistent with P5 (<= 3) but I did not predict 1 and have not traced the net; not explained here.
- Group bursts need not share a cycle: witnesses such as `group_m1_92@2, group_m0_49@4, group_m2_24@4` work because the circuit holds any non-arm word, so partial inversions accumulate.

## What is and is not shown
- Shown (SIMULATED, bounded): on these 16 toy codebooks, one all-flop inversion event reaches accept exactly when a wrong-key run rests in the complement of accept; a one-group event set reaches it exactly when the difference is a union of copy groups; whole-design rail events reach only all-ones / all-zeros accept words.
- Not shown: any link to a physical burst, overclock or supply event; any probability; anything beyond T = 6, these events, this synthesis version. "none" and ">6" are bounded search results. No novelty: nothing established as new.

## Open questions
- Which net gives the 1-flip all-nets result for accept 0x00?
- Would a burst over one comparator's gates (not its flops) change the picture? Not modelled here.
- Product flag and encoding lint (all-ones difference, global or per group) remain for a later step.
