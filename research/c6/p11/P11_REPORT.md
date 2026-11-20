# P11 report: code distance as fault budget, decoder as ceiling

Every number is MEASURED unless marked; command: `python3 scripts/comms/distance_sweep.py --out results/comms/distance_sweep.csv --cli faultbound-wt` (product CLI `faultbound-wt analyze`, stem rule, goal `boot_word == W`, `sig != 0xC3`, known init, T = 6, k <= min(d(I,W), 6); flops-only = `[faults] kinds = ["flop"]`; apt yosys 0.33). Faults are modelled single-cycle bit flips on a toy design. Bounded results (T = 6, k <= 6); `>6` means no attack found up to 6, not "safe". No physical claim. Nothing established as new: this is known minimum-distance / cut reasoning (M1 rule) applied to more constants.

## FAILED or partly failed predictions (full prominence)
1. **FAILED: "on the apt-0.33 plain netlist the plateau is 2 for complement pairs".** Measured: all three complement pairs (69/96, C3/3C, A5/5A) give 3 on the plain netlist. The value 2 appears only for three of the four distance-4 two-step codebooks (F0/96 stored, A5/96, fam_d4); CC/96, with the same words as the stored design in swapped order, gives 3. My pre-registered guess of where ABC sharing bites was wrong.
2. **FAILED as literally posed by the lead (predicted to fail in PREREG): "flops-only == d(I,W)".** For the two B-variant codebooks d(I,W) = 8 but flops-only = 3 and 6 = distance from the FAIL word to W. The governing quantity is d_min (nearest non-accept word visited), not d(I,W).
3. **FAILED in part: "saturates at 3 for the 3-copy design"** on the project flow: 3 of 16 three-copy codebooks sit at 2 (item 1). It holds on the no-ABC structural netlist (never above 3 anywhere).
4. **Could not be done as asked: "stored-style netlist".** The stored spike flow is not reproducible here, so the rule was tested on a no-ABC structural flow (proc; techmap; flatten) as a stand-in. This is a substitution, declared in PREREG before running.

## Predictions vs measured (kept separate)
| # | Prediction (PREREG.md, 05:02Z, before any run) | Measured (sweep 05:03Z, re-run identical) | Verdict |
|---|---|---|---|
| a | flops-only == d_min where d_min <= 6 | 15 of 15 equal; plain and no-ABC netlists agree on all 19 | held |
| a' | where d_min > 6: no attack up to 6 | 4 of 4 (`>6`: 69/96, C3/3C, A5/5A, fam_d7) | held (bounded) |
| a-literal | flops-only == d(I,W); predicted to fail for the 2 B-variants only | fails for exactly those 2 (3 and 6 vs 8) | literal form FAILED (as predicted) |
| b1 | all-nets <= flops-only, all codebooks | 19 of 19, both flows | held |
| b2 | no-ABC structural netlist: all-nets == rule | 19 of 19 | held |
| b3 | apt-0.33 plain: all-nets <= rule, equality not guaranteed | 16 equal, 3 lower (2 vs 3) | held |
| c | plateau 3 (three copies), 2 (two), 1 (one copy / one-copy grouping) on structural netlist | 3 / 2 / 1 as predicted; max over all cells = 3 | held |
| c-plain | plain plateau 2 or 3, "2 more likely for complement pairs" | complement pairs = 3; 2 only at three d=4 codebooks | FAILED (the "which" part) |
| d | complement pairs have the largest gap d - all-nets | gap >= 5 (8 vs 3) for the three pairs; next: fam_d7 4, Bvar_two 4 (by d_min) | held; note Bvar_one_copy has d(I,W)=8 and all-nets 1 (gap 7 in d(I,W) terms, 2 in d_min terms) |
| neg | generator controls rejected before any solver run | both rejected by the iverilog check (wrong key boots; power-up accepted) | held |

## Measured table (yosys 0.33; "plain" = scripts/synth.sh plain; "no-ABC" = structural stand-in)
| codebook | I | C | W | B | d(I,W) | d_min | copies | rule | flops plain | all plain | flops no-ABC | all no-ABC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F0_96_stored | F0 | CC | 96 | 69 | 4 | 4 | 3 | 3 | 4 | 2 | 4 | 3 |
| CC_96 | CC | F0 | 96 | 69 | 4 | 4 | 3 | 3 | 4 | 3 | 4 | 3 |
| 69_96_complement | 69 | - | 96 | 69 | 8 | 8 | 3 | 3 | >6 | 3 | >6 | 3 |
| 2B_95 | 2B | 69 | 95 | 6A | 6 | 6 | 3 | 3 | 6 | 3 | 6 | 3 |
| C3_3C_complement | C3 | - | 3C | C3 | 8 | 8 | 3 | 3 | >6 | 3 | >6 | 3 |
| A5_5A_complement | A5 | - | 5A | A5 | 8 | 8 | 3 | 3 | >6 | 3 | >6 | 3 |
| A5_96 | A5 | 66 | 96 | 69 | 4 | 4 | 3 | 3 | 4 | 2 | 4 | 3 |
| A5_A6 | A5 | 66 | A6 | 59 | 2 | 2 | 3 | 2 | 2 | 2 | 2 | 2 |
| 00_1F_F8_E7 | 00 | F8 | 1F | E7 | 5 | 5 | 3 | 3 | 5 | 3 | 5 | 3 |
| fam_d1 | 97 | 16 | 96 | 69 | 1 | 1 | 3 | 1 | 1 | 1 | 1 | 1 |
| fam_d2 | 95 | 56 | 96 | 69 | 2 | 2 | 3 | 2 | 2 | 2 | 2 | 2 |
| fam_d3 | 91 | 76 | 96 | 69 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| fam_d4 | 99 | 66 | 96 | 69 | 4 | 4 | 3 | 3 | 4 | 2 | 4 | 3 |
| fam_d5 | 89 | 6E | 96 | 69 | 5 | 5 | 3 | 3 | 5 | 3 | 5 | 3 |
| fam_d6 | A9 | 6A | 96 | 69 | 6 | 6 | 3 | 3 | 6 | 3 | 6 | 3 |
| fam_d7 | E9 | 68 | 96 | 69 | 7 | 7 | 3 | 3 | >6 | 3 | >6 | 3 |
| Bvar_one_copy | 69 | - | 96 | DF | 8 | 3 | 1 | 1 | 3 | 1 | 3 | 1 |
| Bvar_two_copies | 69 | - | 96 | 4D | 8 | 6 | 2 | 2 | 6 | 2 | 6 | 2 |
| ctrl_one_copy_grouping | F0 | CC | 96 | 69 | 4 | 4 | 1 | 1 | 4 | 1 | 4 | 1 |
| NEG_fail_equals_accept | F0 | CC | 96 | 96 | 4 | - | - | - | rejected, not run | - | - | - |
| NEG_idle_equals_accept | 96 | CC | 96 | 69 | 0 | - | - | - | rejected, not run | - | - | - |

## Surprises
- Word ORDER matters on the ABC netlist: F0 then CC gives 2, CC then F0 gives 3, same code, same distances. Witness for F0/96: two ABC-created nodes, one at cycle 0 and one at cycle 4 (`$abc$275$new_n74_@0, $abc$275$new_n58_@4`, column `witness_all`). I did not dissect the mechanism; "shared next-state logic" is INFERRED, not shown.
- Flops-only was identical on both netlists for all 19 codebooks, so the register budget did not depend on synthesis here.
- The netlist hash depends on the directory yosys runs in (source paths are written into the JSON). The generator now synthesises with relative names so `netlist_sha256` is repeatable; the first run (absolute paths) had the same minima and different hashes (`sweep_run.log`).

## Not done / limits
- 19 measured codebooks, one consumer (full word), one counting rule, T = 6 only, k <= 6, input nets not sites, known init. `>6` cells are unknown above 6 (d = 7 and 8 could not be confirmed as 7 or 8).
- No brute-force cross-check of these cells (z3 via the product only). conda yosys 0.38 not run. The glitchsat CLI was not needed: the product's `kinds` config key gives flop-only sites (there is no command-line flag for it, only the TOML key).
- No timeouts occurred (0 unknown cells from timeouts).

## Runtime
Full sweep: 12 to 15 s wall on 4 cores (`sweep_run.log`: 14.7 s and 12.1 s), 76 solver runs, 21 functional checks. Tests: `pytest tests/test_distance_sweep.py` 12 passed in about 3 s (work copy, venv with the product CLI).

## Files
`scripts/comms/distance_sweep.py`, `scripts/comms/plot_staircase.py`, `results/comms/distance_sweep.csv`, `docs/comms/staircase.png`, `docs/comms/STAIRCASE_NOTES.md`, `tests/test_distance_sweep.py`, `research/c6/p11/PREREG.md`, `P11_REPORT.md`, `sweep_run.log`.
