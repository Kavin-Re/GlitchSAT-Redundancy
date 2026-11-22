# EL2: electronics-level view of the glitch-resistance results

by step EL2; for the author to edit. Every number has a label: MEASURED (a tool ran and printed it), SIMULATED / ESTIMATED (tool output under a stated modelling choice), UNVERIFIED. Faults are modelled bit flips. Nothing here is a statement about silicon, a physical glitch or a real attack. Nothing is established as new. License: UNDECIDED. Working title TBD.

Environment: conda env `eda` (Yosys 0.38+92, OpenROAD, OpenSTA inside it, sky130A PDK, `sky130_fd_sc_hd__tt_025C_1v80.lib`), apt Yosys 0.33, z3 (pip). All runs on copies under `/tmp/work_el2/`; `scripts/` and `layout/` untouched. Common solver setting: T = 6 cycles, k <= 3, attacker input `sig` free and constant, `!= 0xC3`, goal `boot_word == 0x96` at some cycle (the repo's setting).

## 1. Resistance versus cost

Three netlist kinds appear below, and the fault sites differ between them. Read the columns with that in mind.
- **generic** = `scripts/synth.sh` output (AND/OR/XOR/NOT/MUX gates) fed to the unmodified `scripts/glitchsat.py` (copy). A fault site is any generic gate output or flop Q.
- **mapped** = Yosys-mapped sky130 cells, my adapter `mapped_adapter.py`. A fault site is a standard-cell output or flop Q (one site per cell; transistor-internal nodes are not sites).
- Netlists: `apt-0.33` = apt Yosys 0.33; `conda-0.38` = Yosys 0.38 from env `eda`.

### 1a. Minimum number of flips (k <= 3, T = 6). MEASURED (solver verdicts, bounded)

| Design | generic apt-0.33 plain | generic apt-0.33 opt | generic conda-0.38 plain | generic conda-0.38 opt | mapped apt-0.33 (cells) | mapped conda-0.38 (cells) |
|---|---|---|---|---|---|---|
| V0 | min 1 | n/a | min 1 | min 1 | min 1 (`st[1]`) | min 1 |
| V1 | min 1 (`ok`, cycle 1) | n/a | min 1 | min 1 | min 1 | min 1 (`ok`, cycle 1) |
| V2 | **min 2**, none at k=1 | **min 2** | **min 3**, none at k=2 | **min 2** | **min 3**, none at k<=2 | **min 3**, none at k<=2 |
| V2 reference `reference/spike_netlists/v2.json` (generic, 68 gates) | min 3, none at k<=2 | | | | | |

Sources: `part1_apt.jsonl`, `part1_extra.jsonl`, `part1_cond038.jsonl` (run_part1.py), `run_part3.py` output. V0/V1 are broken by one flip in every netlist. V2 has no one-flip attack in any netlist. Whether V2 needs 2 or 3 flips depends on the synthesis run and on whether the fault site is a gate or a cell. Details:
- V2 generic apt-0.33 plain min-2 attack: flips `$abc$275$new_n74_` at cycle 0 and `$abc$275$new_n58_` at cycle 4. V2 conda-0.38 plain: no 2-flip attack; min 3 at k=3 (fault list in `part1_cond038.jsonl`). The reference spike netlist min-3 attack flips `word[0]`, `c1.$abc$251$new_n13_`, `c2.$abc$251$new_n10_`, all at cycle 1.
- Mapped V2, conda-0.38, min-3 attack: `c0/_1_`, `c1/_1_`, `c2/_1_` at cycle 1 (the nand2 in each compare copy). Mapped V2, apt-0.33, min-3 attack: `_18_`@0, `st[4]`@1, `st[1]`@1.
- A fault-free run with the legitimate key reaches the goal in every mapped netlist (`honest=true`).

### 1b. Cost columns (mapped netlists, same flow for all). MEASURED by Yosys stat / OpenROAD; power ESTIMATED

Flow: `synth.ys.tpl` (synth; dfflibmap; abc; liberty) then the repo's OpenROAD script with 10 ns clock, input delay 2, output delay 2, CTS, repair_timing, global + detailed route, global-route parasitics (`pnr_el2.tcl`, `runflow.sh`). conda-0.38 V1/V2 netlists are byte-identical to the repo's `layout/v_designs/out_patched/v?_net.v` (`cmp` same), and V1/V2 area/slack agree with its RESULT.md (+7.050/+0.519 and +7.035/+0.476 ns). The apt-0.33 netlists use `pruned.lib` (apt abc has no `-dont_use`; see limits), so cell choice differs.

| Netlist | cells (yosys) | logic area um2 (yosys stat) | placed design area um2 / util | worst setup slack ns (clk 10 ns) | worst-slack endpoint, required / arrival ns | worst hold slack ns | power uW (ESTIMATED) | P&R runtime s |
|---|---|---|---|---|---|---|---|---|
| V0 conda-0.38 | 10 | 88.8 | 115 / 51% (UTIL=30, see limits) | +7.050 | boot_word[0] 8.000 / 0.952 | +0.470 | 27.4 | 15.8 |
| V1 conda-0.38 | 35 | 357.8 | 399 / 77% | +7.050 | boot_ok 8.000 / 0.950 | +0.520 | 63.8 | 23.2 |
| V2 conda-0.38 | 36 | 362.8 | 399 / 77% | +7.035 | boot_ok 8.000 / 0.965 | +0.476 | 62.1 | 27.8 |
| V0 apt-0.33 | 10 | 88.8 | 115 / 51% | +7.050 | same netlist as conda | +0.470 | 27.4 | 13.5 |
| V1 apt-0.33 | 35 | 360.3 | 399 / 77% | +6.821 | `_46_/D` 10.127 / 3.306 | +0.480 | 63.6 | 29.2 |
| V2 apt-0.33 | 39 | 384.1 | 423 / 78% | +6.827 | `_47_/D` 10.120 / 3.293 | +0.490 | 61.9 | 25.4 |

Power: `report_power` with OpenSTA default activity (not a vector-based number), tt 1.8 V 25 C, uW totals (internal+switching+leakage); flops are about 58 % of it. Treat as relative only; V1 and V2 differ by under 3 %. V2 conda-0.38 vs V1: +1 cell, +5.0 um2 logic area (+1.4 %), worst setup slack 7.035 vs 7.050 ns (0.015 ns apart). Area and power are within a few percent of V1; V0 is 4x smaller but breaks at one flip.

Solver runtime (MEASURED, wall, k=3 incl. minimisation; synth excluded): generic V0 0.2-0.5 s, V1 0.4-1.3 s, V2 0.4-1.2 s on apt netlists, V2 conda plain 5.8 s (k=2 no-attack 4.3 s); mapped adapter 0.2-0.7 s for any k. The mapped model has fewer sites so it is faster.

**Reading the table (ESTIMATED, no cost claim beyond these figures):** going from the unprotected V0 to V2 costs about 4x cell count and area in this toy and raises the minimum modelled attack from 1 to 2 or 3 flips depending on the netlist. V1, the textbook duplicated compare, has nearly the same area and power as V2 and stays at one flip. Timing is not what is paid: all slack is above 6.8 ns because the 10 ns clock is loose for a 1-2 ns logic depth.

## 2. Slack-based plausibility (ESTIMATED slack, SIMULATED attacker)

Idea: a timing-violation-style attacker can only upset elements whose setup slack is small. Slack per cell = `slack max` of the cell's output pin vertex in OpenSTA after global-route parasitics (`CELLSLACK` lines in `logs/*_openroad.log`); flop D slack from the endpoint report. Sites are added in order of increasing slack and the solver asks the min flips (k <= 3, T = 6, cell-output flips). Data: `data_part2_*.json`; script `run_part2.py`.

Ranking of flop D endpoints, lowest slack first (ns, ESTIMATED):
- V2 conda-0.38: `_35_` 7.322, `_39_` 7.343, `_42_` 7.356, `_41_` 7.373, `_40_` 7.385, `_36_` 7.392, `_38_` 7.436, `_37_` 7.519 (spread 0.20 ns).
- V1 conda-0.38: `_46_` 7.079 ... `_41_` 7.352 (spread 0.27 ns). V2 apt-0.33: 6.827 ... 7.494.

| Netlist | cells sorted by slack: first prefix that allows an attack at k<=3 | min flips there | flops only (flop-Q flips, ranked by D slack), all 8 allowed |
|---|---|---|---|
| V0 conda-0.38 | 2 cells (slack <= 7.048 ns, includes `boot_ok` net) | 1 | attack with 1 flop `st[0]` (D slack 7.571) |
| V1 conda-0.38 | 6 cells (<= 7.079 ns), net `_15_` @0 | 1 | NO attack up to k=3 |
| V1 apt-0.33 | 4 cells (<= 6.821 ns), `_10_` | 1 | NO attack up to k=3 |
| V2 conda-0.38 | **22 of 36 cells** (<= 7.385 ns) | 3 (`word[5]`, `m0`, `m1` at cycle 1) | NO attack up to k=3 |
| V2 apt-0.33 | 18 of 39 cells (<= 7.099 ns) | 3 | NO attack up to k=3 |

What this says. With the allowed set restricted to the lowest-slack cells, V2 needs the attacker to reach 18 to 22 sites before any 3-flip attack exists, whereas V1 needs only the 4 to 6 lowest-slack cells, and one flip. The first 17-21 V2 cells (lowest slack first) give no attack at k <= 3. But the slack range across the whole design is narrow: 7.04 to 7.39 ns in V2, so the "restricted" set is nearly all of the design once the clock is overclocked by about 0.4 ns of margin spread. A "can only fault the weakest endpoint" attacker is therefore a weak restriction here, because there is no clearly weakest path (all paths are 1-2 ns on a 10 ns clock). Slack ranking is more informative on a design with a real critical path. Flip-flop-only faults (capture errors) never succeed at k <= 3 on V1 and V2 in the model, because 0xF0/0xCC to 0x96 needs more than 3 flop flips; V0 needs one.

One infinite-slack cell (`_20_` in apt-0.33 V2, sentinel 1e39 ns) has no constrained path; I list it last and do not interpret it.

### 2b. Overclock-style correlated variant (SIMULATED, a modelling choice)

One event at cycle t flips ALL cell outputs (flops included) with slack <= theta together, theta chosen per event, at most one event per cycle (`run_part2b.py`, `data_part2b_*.json`). Result: every netlist, V0, V1 and V2 (both toolchains), is broken by ONE event at k=1 (for example V2 conda-0.38: theta <= 7.160 at cycle 4; V2 apt-0.33: theta <= 7.540 at cycle 3). Cause: the encoded FAIL state 0x69 is the bitwise complement of the accept value 0x96, so an event that flips every state flop gives accept. That is a property of the chosen model plus the complementary encoding, not a physical finding: a real capture error would more likely retain the previous value than invert. It does show the logic: against a flip-everything event, the number of redundant compare copies is irrelevant, and the state encoding matters (a non-complementary accept/fail pair would remove this particular route; not run).

## 3. Mapped-netlist question: does the generic verdict carry over?

Adapter: `mapped_adapter.py` (does not touch `scripts/`). It parses Yosys `write_verilog` output of sky130 cells with hierarchy (`cmp8` x3), flattens it with aliasing of `assign` bit-vectors, reads each cell's `function` string from the liberty file (data), builds the same unrolled z3 model as `glitchsat.py` (cell output = one site, flop Q = one site, 6 cycles, same goal and attacker), and minimises. Flop initial values are not in the mapped Verilog (dfflibmap drops them); I supplied 0xF0 for V1/V2 and 0 for V0 from the RTL. All parsed liberty functions evaluate as total boolean functions of their inputs (self-test in the file). Fault-free key run reaches the goal (`honest=true`) on all six mapped netlists. It is a re-implementation, not an independent cross-check of the engine against another solver; its agreement with the generic engine on V0/V1/V2 verdicts is the only consistency check I ran.

Verdicts (MEASURED, k<=3, T=6; see 1a): V0 min 1, V1 min 1, V2 no attack at k<=2 and min 3 at k=3, for BOTH conda-0.38 and apt-0.33 mapped netlists. Does that match the generic verdict?
- V1: yes (min 1; the decision net `ok` is again a one-flip site in the conda mapped netlist, kept by `keep`).
- V2 conda-0.38: yes, the generic plain netlist and the reference spike netlist also give min 3 and "none at k=2".
- V2 apt-0.33: **no, not the same number**. The generic netlist gives min 2, the mapped netlist min 3. The min-2 attack uses two internal generic gates (`new_n74_`, `new_n58_`) that sit inside a larger sky130 cell after mapping and are no longer separate sites. So 2 versus 3 is partly an artefact of what counts as a fault site. A mapped cell is a bigger target than a generic gate; a transistor-level model would have even more sites and could give a lower minimum. I did not run one.

## 4. Locality experiment (SIMULATED, a modelling choice, not physics)

Placement: OpenROAD DEF (`/tmp/work_el2/lay/out/*.def`), die 30.6 x 30.6 um, logic cells about 8 to 27 um across. Cell centre = lower-left + width/2 (liberty area / 2.72 um row height). Model: one glitch at cycle t is a disc of radius r around the centre of any cell; it flips every cell output (and flop Q) whose centre is inside; overlapping discs at one cycle combine by XOR; up to k = 3 glitches, T = 6 (`run_part4.py`, `data_part4_*.json`). r = 0 equals the cell-output baseline.

Compare-copy geometry (um): V2 conda-0.38 copy centroids c0 (21.7, 9.5), c1 (19.4, 8.6), c2 (18.8, 6.8): pairwise centroid distances 2.5, 4.0, 1.9; V2 apt-0.33: 7.0, 9.4, 14.4. The three copies of V2 conda-0.38 sit within about 4 um of one another (the placer clustered them; the layout was not placed with any separation constraint).

Min glitches vs radius (MEASURED output of the model, k<=3, T=6), flops flippable / combinational cells only:

| r (um) | V2 conda-0.38, flops flippable | V2 conda-0.38, comb only | V2 apt-0.33, flops flippable | V2 apt-0.33, comb only | V1 conda-0.38 (either) |
|---|---|---|---|---|---|
| 0 | 3 | 3 | 3 | 3 | 1 |
| 1.5 | 3 | 3 | 3 | 3 | 1 |
| 2.5 | 2 | 2 | 3 | 3 | 1 |
| 3.5 | 1 | 1 | 2 | 2 | 1 |
| 5 | 1 | 1 | 2 | 1 | 1 |
| 7 | 1 | 1 | 2 | 1 | 1 |
| 10 | 1 | 2 | 2 | 1 | 1 |
| 15 | 1 | 1 | 1 | 2 | 1 |
| 25 | 1 | no attack | 1 | no attack | 1 (flops flip) / none (comb only) |

Reading it: for V2 conda-0.38 the minimum drops from 3 to 2 at r = 2.5 um and to 1 at r = 3.5 um, i.e. once a disc spans about the width of a compare cell plus its neighbour, because the three copies are placed within ~4 um. For the apt-0.33 placement (copies 7 to 14 um apart) r = 3.5 um already gives 2, and reaching 1 takes 15 um with flops flippable or 5 um with combinational cells only. The table is not monotone in r for the combinational-only column (e.g. V2 conda 10 um gives 2 after 7 um gave 1): the centres are only the cell centres, so the family of flip patterns is not nested in r. At r = 25 um one disc flips every cell, which defeats the compare logic only through the flops (complement encoding, as in 2b) and, with flops excluded, flips everything consistently so no attack results. The "flops flippable" rows at large r are therefore dominated by the 0x69 / 0x96 complement artefact.

Design lesson that holds inside the model: three independent copies protect only if a fault cannot hit more than one of them; the independence assumed by the k-flip count is a layout property. Placement-aware design (copies and result bits spaced apart, or interleaved with other logic) is the electronics counterpart of the solver's "no single net decides". Whether r of 2.5 to 3.5 um corresponds to anything a real fault could do is not established and I make no claim.

## What this says about electronics-level resistance

Within the stated model, the one-flip weakness of V1 (the single AND net that decides) and of V0 is a robust result: it appears in all 6 netlists and in the mapped cell-level model. V2 resists any single flip in every netlist, and resists two flips in 1 of 4 generic re-syntheses, in the reference spike netlist and in both mapped netlists. The minimum is not a property of the RTL alone: it moves between 2 and 3 with the synthesis tool version, the optimisation flow and whether the fault site is a gate or a cell. The cost of V2 over V1 is small (+1 to +4 cells and +1.4 % to +6.6 % logic area over V1; power within 3 %, ESTIMATED), and timing is not binding, so the design-level lesson is cheap here. Electronics-level facts the generic model hides: (i) copies that look independent in the netlist are placed within a few um and a correlated disc fault ignores the copy count; (ii) slack is nearly flat across the design, so an overclock-style restriction does not isolate a weak endpoint; (iii) the complementary accept/fail encoding makes a flip-all event an accept event. These are statements about modelled bit flips on a 36-cell toy.

## Limits and what was not done

- Bounded: k <= 3, T = 6 only; no unbounded argument is made here. Toy designs; nothing about silicon, voltage/clock/laser physics or real feasibility.
- Fault model by cell output is coarser than transistor level; generic gate model is finer than cells but not physical either. The 2-versus-3 difference for V2 apt-0.33 shows the verdict depends on this choice.
- The apt Yosys 0.33 abc has no `-dont_use`, so apt netlists were mapped with `pruned.lib` (lpflow/scan/latch/probe cells removed, `prune_lib.py`); this may differ from the integration step's intended apt flow. apt 0.33 mapped logic area is a few % higher (V2 384 vs 363 um2).
- V0 placement used 30 % utilisation (60 % fails global placement: GPL-0302), so its placed area / util are not comparable with V1/V2. V0's two flows give the same netlist apart from the header.
- Power is OpenSTA default-activity estimate, not simulation-based. Slacks are global-route-parasitic estimates, not signoff; the 10 ns clock leaves 7 ns slack everywhere.
- Slack-restricted and overclock models (section 2) and radius model (section 4) are modelling choices I made; the flop capture error is modelled as a Q flip, which over-approximates and differs from stale capture. DEF cell centres use area/2.72 um as width. CTS clock buffers are placed but not fault sites (clock faults are not modelled). Tap/fill cells ignored.
- The adapter was checked against the generic engine only by agreement on verdicts (V0, V1, V2 conda-0.38); no second solver, no mapped-netlist mutation test.
- Not done: SPICE-level or transistor-level fault sites; non-complementary encoding variant; placing copies far apart by constraint (die is 30 um); other corners (ss/ff) for slack.

## Commands (all on copies; paths as used)

```
# env: PATH=/tmp/mm_root/envs/eda/bin:$PATH for Yosys 0.38 / openroad; apt yosys is the default otherwise
# (1a) generic: python3 run_part1.py <label> rtl/<d>.v <d> plain|opt      # imports glitchsat from /tmp/work_el2/scripts (copy)
python3 run_part1.py v2_apt033 rtl/v2.v v2 plain      # apt 0.33;  same with PATH=eda for 0.38
python3 run_part1.py v2_spike_ref reference/spike_netlists/v2.json v2
# (1b) mapped netlists
yosys -q mapped/v2_033.ys                              # apt 0.33, pruned.lib (prune_lib.py)
yosys -q out/v2_038.ys                                 # conda 0.38, template layout/v_designs/flow_patched/synth.ys.tpl
./runflow.sh v2_038 out/v2_038_net.v v2                # openroad -no_splash -exit pnr_el2.tcl ; UTIL=30 for V0
python3 make_tables.py
# (3) python3 run_part3.py v2_cond038 layout/v_designs/out_patched/v2_net.v v2
# (2) python3 run_part2.py v2_038 v2 ; python3 run_part2b.py v2_038 v2
# (4) python3 run_part4.py v2_038 v2
```

Files in `research/c2/el2_engineering/`: `mapped_adapter.py`, `run_part1.py`, `run_part2.py`, `run_part2b.py`, `run_part3.py`, `run_part4.py`, `make_tables.py`, `pnr_el2.tcl`, `runflow.sh`, `prune_lib.py`, `data_part*.json`, `part1_*.jsonl`, `logs/` (OpenROAD logs with power, endpoints, per-cell slacks). Scripts reference `/tmp/work_el2/...` paths (netlists, liberty copy, DEFs), so they re-run only if that tree is rebuilt with the commands above.
