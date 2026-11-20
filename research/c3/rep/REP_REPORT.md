# REP_REPORT: independent replication of "V2 holds in 6/32 netlists (unit counting) vs 32/32 (fanout counting)"
License: UNDECIDED. Working title TBD. Written 2026-11-19 by agent REP. All faults are MODELLED single-cycle bit flips, toy 8-bit designs, N = 6 cycles. Nothing physical.

## Verdict: REPLICATED, 64 of 64 rows agree (MEASURED here). One caveat on independence below.

## 1. Origin (found)
- Single source: agent DA, `research/c2/devils_advocate/DA_CYCLE1.md` rows E1 and E3; raw data `experiments/results.txt` (unit weight) and `experiments/matrix.txt` (unit and fanout-weighted), generator `experiments/gen.sh`, weighted solver `experiments/weighted.py`. README line 5, `docs/FINAL_STATUS.md` ("not re-run by me") and `dashboard/build.py` repeat it. `research/c2/e2_variance/` (agent E2) has scripts only, no results, so it is not a second measurement.
- The original netlists (`/tmp/work_da/...`) no longer exist, so netlist hashes cannot be compared with the original; I compare gate counts and min-cost values per row instead.

## 2. The 32 netlists (V2; plus the 32 V1 companions, 64 total)
Design `rtl/v2.v` (triplicated check) and `rtl/v1.v` (duplicated). Variants: 2 Yosys builds (apt 0.33, conda `formal` 0.38+92) x 2 flows (`plain`: proc/techmap; `opt`: `synth -top; dffunmap`) x 8 ABC invocations (s0..s7: `abc -g AND,OR,XOR,MUX`; `-g AND,OR,XOR`; `-fast` with MUX; `-fast` without MUX; `-g AND,OR`; `-g AND,OR,MUX`; `-script +strash;dc2;map -g AND,OR,XOR`; `-g AND,OR,XOR,MUX -D 1000`), then the project's flatten/opt_clean/techmap/write_json tail (same as `scripts/synth.sh`). Hashes (sha256 first 16) of all 64 are in `rep_results.csv`.
Caveat on independence: I took the list of 8 ABC invocations and the synthesis tail from the original `gen.sh` (they define WHAT the 32 are); I wrote my own loop and all measurement code. My gate counts equal the original's on 64 of 64 netlists, so the netlists are almost certainly the same.

## 3. Counting rules (plain words), all with attacker input `sig` free, constant, != 0xC3, goal boot_word == 0x96 within 6 cycles
- `unit`: one flip of one net at one cycle = one fault, regardless of how many gates read that net (a stem flip = 1). This is glitchsat's own rule.
- `fanout_pins`: a flip of a net costs the number of gate-input pins, flop D pins and output-port bits it feeds (equivalent to flipping every branch separately). This is the original's rule.
- `fanout_gates`: same but output-port bits not counted (variant I added).
I did NOT test "per-branch with partial branch flips allowed" (cheaper than fanout-weighted; untested, so the 32/32 figure should not be read as covering it).

## 4. Method and commands
- Unit rule, documented CLI: `python3 scripts/glitchsat.py check net/<n>.json --top <v1|v2> --k K --cycles 6` for K = 1..4 until ATTACK_FOUND (`scripts/cli_check.sh`, 2m16s total for 64; output `cli_results.csv`).
- All three rules via z3: `scripts/rep_measure.py` imports `glitchsat.build()` from a copy (flip variable per (cycle, net), same semantics), adds my own weighted PbLe, increases budget 0..6 (`rep_raw_results.csv`; longest single solve 11.4 s; about 7 min total in background). Unit result from this path equals the CLI on every row.
- Netlists: `scripts/gen_rep.sh` (33 s). Work copy `/tmp/work_rep/`; project tree untouched.
- No UNKNOWN or timeout cells: all 192 minimisation cells returned a definite sat/unsat (timeout was 120 s per check, never hit).

## 5. Results (MEASURED; per-row table in `rep_results.csv`)
| Quantity | Original (DA) | REP | Agree |
|---|---|---|---|
| V2 unit min flips = 2 / = 3 | 26 / 6 | 26 / 6 | yes, same 6 rows (all `v2_plain_038_s0,s1,s4,s5,s6,s7`) |
| V2 holds against 2 flips, unit rule | 6 of 32 | 6 of 32 | yes |
| V2 fanout-weighted min | 3 on 32 | 3 on 32 (both fanout_pins and fanout_gates) | yes |
| V2 holds against 2 flips, fanout rule | 32 of 32 | 32 of 32 | yes |
| V1 unit min | 1 on 32 | 1 on 32 | yes |
| V1 fanout-weighted min | 2 on 32 | 2 on 32 | yes |
| per-row (64 rows) unit and fanout values and gate counts | | | 64/64 |

## 6. What this does and does not show
- Shows: the numbers are reproducible with an independent loop and independent weighted-cardinality code on the same recipe. The 6/32 versus 32/32 swing is a pure counting-rule effect (same 32 netlists).
- Does not show: that either rule is physical (that is BC row 3's objection and stays open); anything beyond N = 6, k <= 3, these two designs, these two Yosys builds; the original's own netlist hashes; the partial-branch rule. "Holds against 2 flips" is a BOUNDED statement for 6 cycles, not a proof.
- Wording suggestion for README line 5: "6 of 32 under stem=1, 32 of 32 under fanout-weighted counting (MEASURED by agent DA, independently replicated by agent REP, `research/c3/rep/`)", keeping the bound (N=6, k<=3).
