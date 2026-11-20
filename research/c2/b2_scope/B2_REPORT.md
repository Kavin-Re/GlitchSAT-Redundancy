# B2 report: claim-scope sensitivity of "V2 resists <=2 flips" and a V3 attempt
All numbers MEASURED unless marked; faults are modelled single-cycle bit flips, not physical glitches. Toy designs, 6 cycles, k<=3 (a cell ">3" means no attack with <=3 flips; it is bounded, not a proof beyond that).

## What was run
- Engine: `gs.py` in this folder = COPY of `scripts/glitchsat.py` (original untouched) with four added options: `input_sites` (each input bit net is a flip site, shared by all its fanouts, equivalent to adding an input buffer), `init_mode` (`known` = netlist init values; `free` = any power-up state; `free_nongoal` = any power-up state from which the fault-free run never reaches the goal), `free_in` (attacker input fresh every cycle, != key every cycle), `ctrl` (platform-driven input schedule, used for V3 `rst`), `goal_from` (goal only observed from a cycle on, used for V3 after reset).
- Sanity: the unmodified CLI reproduces the baselines (`cli_baseline.txt`; e.g. `python3 glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6` -> NO_ATTACK_UP_TO_BOUND for boot_word, and `--goal-out boot_ok --goal-value 1` -> ATTACK_FOUND, 1 flip `boot_ok`@1; V2 RTL via apt 0.33 `--k 2` -> ATTACK_FOUND, 2 flips).
- Netlists: `spike` = `reference/spike_netlists/{v0,v1,v2}.json`; `apt033_plain/opt` = `scripts/synth.sh` flows with apt Yosys 0.33; `conda038_plain/opt` = same script logic with `/tmp/mm_root/envs/eda/bin/yosys` 0.38 (`synth_any.sh`). Command: `python3 run_matrix.py /tmp/work_b2/nl` (360 cells, raw rows in `matrix.jsonl`).
- Cell format `const/free` = minimum #flips with the attacker input held constant / fresh each cycle. Columns: goal (`word` = boot_word==0x96, `ok` = boot_ok==1), input nets as fault sites (`noin` / `+in`), init (`known`, `nongoal` = arbitrary non-accepting power-up state, `free` = arbitrary).

## Matrix (MEASURED)
| design | netlist | word noin known | word noin nongoal | word noin free | word +in known | word +in nongoal | word +in free | ok noin known | ok noin nongoal | ok noin free | ok +in known | ok +in nongoal | ok +in free |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v0 | spike | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v0 | apt033_plain | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v0 | apt033_opt | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v0 | conda038_plain | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v0 | conda038_opt | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v1 | spike | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v1 | apt033_plain | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v1 | apt033_opt | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v1 | conda038_plain | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v1 | conda038_opt | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v2 | spike | 3/3 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v2 | apt033_plain | 2/2 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v2 | apt033_opt | 2/2 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v2 | conda038_plain | 3/3 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v2 | conda038_opt | 2/2 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 |
| v3 | apt033_plain | 3/3 | 3/3 | 3/3 | ?/? | ?/? | ?/? | ?/? | ?/? | ?/? | ?/? | ?/? | ?/? |
| v3 | apt033_opt | 3/3 | 3/3 | 3/3 | 3/3 | 3/? | ?/? | ?/? | ?/? | ?/? | ?/? | ?/? | ?/? |
| v3 | conda038_plain | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/? | ?/? | ?/? | ?/? | ?/? | ?/? |

## Reading the V0-V2 matrix
1. Only ONE cell family keeps V2 above 1 flip: goal boot_word, input nets NOT fault sites, known init state. There V2 costs 3 (stored spike netlist and conda 0.38 plain), 2 (apt 0.33 plain, apt 0.33 opt, conda 0.38 opt). Constant vs free input per cycle makes no difference (E1 reproduced: 3/3 and 2/2).
2. Change any one assumption and V2 drops to 1: goal boot_ok (single flip of the `boot_ok` net, found by the unmodified CLI too), input nets as fault sites, or arbitrary non-accepting power-up state (state register one flip from the accept code). Arbitrary power-up state with no reset costs 0 for every design (the accept code can be the power-up value); that is a design gap, not a tool finding.
3. V0 and V1 are cost 1 in every cell with a known init, and 0 with arbitrary init; V2 is NOT separable from V1 outside that one cell family. The "V2 > V1" statement holds only inside it.
4. Synthesis flow matters inside that family (3 vs 2) and nowhere else.

## V3 (rtl_v3.v, in this folder; not in rtl/)
Mechanisms: (1) sig sampled into a 3-deep shift register and compared in three different cycles, so one input-net flip fools only one sample; (2) six compare copies, each result bit needs 4 of 6 matches; (3) sticky error flag on copy disagreement; (4) synchronous reset (`rst`, platform-driven 1,1,1,0,0,0) holding `st` and `err`; (5) `boot_ok` is an 8-bit code (0xFF) built bit-by-bit from the result register, not one net (interface change: V0-V2's boot_ok is 1 bit, so the boot_ok column is NOT like-for-like). Honest key boots fault-free on every netlist run (`honest_boots` rows). Goal observed from cycle 3 on (after reset); cost 3 for free-init rows.
Command: `KMAX=3 python3 run_v3.py v3_<netlist>.jsonl <netlist>` (rows in `v3_*.jsonl`; table above, rows marked `?` did not finish inside the 45-minute cap and are NOT RUN).
What the finished V3 cells show (boot_word goal only; the boot_ok/8-bit-code columns are almost entirely NOT RUN, 1 cell finished: cost 3 on conda 0.38 plain, known init): cost 3 where measured, including cells where V2 is 1 (input nets as fault sites, arbitrary power-up state). Where the table has a number, V3 is >=V2 in that scope, with cost 3 reached by 3 flips (e.g. the same input bit's history flops at cycles 2,3,4, or compare-input nets). Honest limits: (a) 3 is not a high bar (it equals V2's best case) and was not shown to exceed 3: the search was capped at k<=3, so the true minimum in each cell is exactly 3 only because 2-flip attacks were proved absent (minimization unsat) and a 3-flip attack exists; (b) V3 trades area (6 comparators, 3+1 extra flops) and 3 cycles of latency; (c) the 8-bit `boot_ok` just moves the single-net problem to the consumer that must check all 8 bits; (d) with arbitrary power-up state the cheapest attack is flipping the `rst` net in all 3 reset cycles (3 flips), so the reset only helps if `rst` is not a flip site or is held longer; (e0) `rst` is assumed platform-driven and itself a flip site only in `+in` columns; (e) 1-bit boot_ok cannot be hardened at its own output net by any logic upstream (the output net is a flip site by definition of the model).
The V3 result does NOT show V3 secure; it shows that, in this fault model, the cheapest attack moved from 1 to 3 flips in the scopes where V2 was 1.

## Required wording for any V2 claim
"In the glitchsat model (modelled single-cycle bit flips of gate outputs and flop Q, 6 cycles), with the attack goal boot_word == 0x96 (NOT the boot_ok output, which one flip reaches), with input nets NOT counted as fault sites, a known power-up state (the layout has no reset), the stored spike netlist, V2 needs at least 3 flips (MEASURED, k<=2 unsat); on netlists re-synthesised from rtl/v2.v with apt Yosys 0.33 (and conda 0.38 'opt') it needs 2. Under any one of the changed assumptions (boot_ok goal, input nets as fault sites, arbitrary power-up state) V2 costs 1. Toy design; not a security result; no claim about hardware."
Never write "V2 resists <=2 flips" without those five qualifiers.

## Not done / caveats
- Input-site model = one shared flip site per input bit; per-fanout-branch input faults were not modelled.
- `free_nongoal` requires only that the fault-free run from that state never accepts; other plausible power-up constraints were not tried.
- "Free input" = different value each cycle, all != key; a weaker "differs in at least one cycle" attacker was not run.
- Cells with `?` for V3: not run (time cap). Files: matrix.jsonl, v3_*.jsonl, gs.py, run_matrix.py, run_v3.py, mk_tables.py, synth_any.sh, rtl_v3.v, cli_baseline.txt.
