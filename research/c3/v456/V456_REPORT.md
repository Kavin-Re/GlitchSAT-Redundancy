# V456: countermeasure example designs V4, V4b, V5, V6 (build and measure)
Step V456, 2026-11-19. License: UNDECIDED. Title: working title TBD. Faults are modelled single-cycle bit flips of gate outputs and flop Q (glitchsat model), T=6 cycles, k<=3, goal observed at any cycle; toy designs; no hardware claim; nothing established as new. "MEASURED" = solver output of the command below; ">3" never occurred in any cell. Work dir `/tmp/work_v456/`; copies of tools in `tools/`, raw rows in `data/`.

## 1. Designs (RTL in `rtl/`, same interface and security setting as `rtl/v2.v`: KEY 0xC3, `sig` constant attacker input != KEY, accept word 0x96, power-up via `initial` values, no reset pin)
| file | idea | note |
|---|---|---|
| `rtl/v4.v` | sparse 16-bit accept code {st,stn}=9669 plus complement rail, ONE shared compare | `boot_word`=st (8-bit goal), `boot_word16`={st,stn}, `boot_ok` checks 16 bits |
| `rtl/v4b.v` | as V4, complement rail has its own compare copy | |
| `rtl/v5.v` | 3 compares, per-bit 2-of-3 voter built twice (AND-OR and mux form, `keep_hierarchy` per bit), disagreement detector `dis`, sticky `alert`, both gate accept; hold CC on alert | `boot_ok = st==96 & ~alert` |
| `rtl/v6.v` | sparse sequence F0->CC->3C->96, 69 sink, invalid->69; two compares on `s1<=sig`, `s2<=s1` (R21 sketch, s2 = DELAYED COPY of s1) | s1,s2 init 0 (x not allowed by the hardened engine) |
| `rtl/v6b.v` | as V6 but `s2<=sig` (fresh second sample) | extra, not requested |
| `rtl/v6h.v`, `rtl/v6bh.v` | V6 / V6b with the absorbing states 96 and 69 HOLDING (`st<=st`) instead of loading constants | added after V6 measured 1 flip |
Reset behaviour: no reset input (as V2); defined power-up by `initial`; V5 `alert` starts 0 and is never cleared. All netlists load in the H1-hardened `scripts/glitchsat.py` Netlist (no multi-driver, no x, no async flops): checked (`gs_base.Netlist`, 40 netlists).
Simulation (MEASURED, iverilog, `rtl/tb.v`, 256 DUT copies, one per `sig`, 10 cycles): `iverilog -g2005 -DDUT=v5 -o x tb.v v5.v; vvp x`. All eight designs (and V2): boot_ok=0 at power-up, honest key reaches boot_word 0x96 with boot_ok=1 (cycle 2 for V2/V4/V4b/V5, cycle 3 for V6 family) and holds it, 255 wrong keys never give boot_ok=1 or word 0x96 (0 violations). Verilator `--lint-only`: 0 errors on v4 v4b v5 v6 v6b. In the solver, honest_boots (fault-free, key fixed) was True in all 360 cells.

## 2. How measured
Engine = `tools/gs.py` = B2's extended copy of `scripts/glitchsat.py` (input_sites, init_mode known|free_nongoal) plus a goal_mask arg (unused here); validated against the same V2 numbers B2 reported (control row below reproduces 3 and 2). Per cell: k=0..3 non-minimising solves, 90 s per solver call (flows batch: 60 s), unknown cells would be marked UNKNOWN: **0 unknown in 360 cells** (`data/all_rows.json`). Cell = (design, netlist, goal, input nets as sites yes/no, init known / free_nongoal = arbitrary power-up from which the fault-free run never accepts).
Command: `python3 tools/run.py out.jsonl <designs> <netlists> <ms>`. Flows: "spike-style" = conda yosys 0.38 plain (`tools/synth_any.sh`; B2 showed this reproduces the stored spike V2 = 3; I did NOT use the stored spike netlists because V4-V6 have none), "apt-0.33" = `scripts/synth.sh plain`; extra: conda opt, apt opt, and `apt033_flat` = `tools/synth_flat.sh` (flatten BEFORE opt, keep_hierarchy stripped: worst-case merging, my own flow, not a project flow).
Goals: word = boot_word==0x96 (8 bit), ok = boot_ok==1, word16 = {st,stn}==9669 (V4/V4b only).

## 3. Result: minimum flips (MEASURED, T=6, k<=3)
Cells show noin-known / noin-arbitrary / in-known / in-arbitrary (in = input nets are sites). Goal = 8-bit word unless stated.
| design | spike-style (conda 0.38 plain) word | apt-0.33 plain word | boot_ok goal (both flows) | word16 goal (both flows) | input sites / arbitrary power-up |
|---|---|---|---|---|---|
| V2 (control) | **3** | **2** | 1 | n/a | 1 / 1 in all three scope changes |
| V4 shared compare | 1 | 1 | 1 | 1 | 1 |
| V4b separate compares | 1 | 1 | 1 | **2** (noin-known) | word16: 1 in the other three scopes |
| V5 voter+alert | **3** | **3** | 1 | n/a | 1 / 1 / 1 (word and ok) |
| V6 (sketch) | 1 | 1 | 1 | n/a | 1 |
| V6b fresh sample | 1 | 1 | 1 | n/a | 1 |
| V6h hold fix | 1 | 1 | 1 | n/a | 1 |
| V6bh | 1 | 1 | 1 | n/a | 1 |
Every cell not in the "word, noin, known" column is 1 for every design including V2 and V5, except V4b word16 noin-known = 2. Full 360-cell table: `data/all_rows.json` (fields design, netlist, goal, input_sites, init, min, faults, status). Other flows (word goal, noin, known): conda opt / apt opt: V2 2/2, V4 1, V4b 1, V5 3/3, V6 family 1. `apt033_flat`: V2 1, V5 1, V4b word16 1 (copies merged, see section 4).

Witnesses (MEASURED): V4 = the single shared compare node at cycle 1. V4b word16 = the two compares' internal nodes at cycle 1 (2 flips); V4b word = `c0.m` (1 flip, the 8-bit goal only depends on one rail). V5 = 3 flips: two of three compare copies plus one of {the alert-path/`dis` net, the final gate} (e.g. `$0\alert`, c1, c2 on apt; net n75, c0, c2 on conda). V6 / V6h / V6bh: ONE flip at cycle 0 inside the next-state logic (a decode/select net) takes F0 straight to 96 at cycle 1 with sig=0x00; I re-simulated this witness independently with `tools/wit.py` (own simulator over the netlist JSON, all 255 sig): reproduces for V6, V6h, V6bh on both flows (e.g. st = F0, 96, 96, ...). I did not trace the exact gate function; the cause is generic: the sparse code gives register-bit distance, but the next-state muxing/decode nets are single points whose flip loads any constant of the FSM, and abc/procmux sharing makes these nets few. Holding states (V6h) did not fix it.
Control: V2 reproduces B2 exactly (conda plain 3, apt 2, apt opt 2, boot_ok 1, input sites 1, arbitrary 1).

## 4. Does synthesis merge the redundant copies? (MEASURED, `tools/cnt.py`, `data/compare_net_counts.txt`)
Method: exhaustively evaluate every gate net over the 256 values of its 8-bit source and count nets whose function equals (src==0xC3) that have no such net as fanin ("distinct compare roots"). Counts (roots):
| design | conda plain | apt plain | conda opt | apt opt | apt flat (worst case) |
|---|---|---|---|---|---|
| V2 | 3 | 3 | 3 | 3 | 1 |
| V4 | 1 | 1 | 1 | 1 | 1 |
| V4b | 2 | 2 | 2 | 2 | 1 |
| V5 | 3 | 3 | 3 | 3 | 1 (and the whole alert logic is optimised away: 8 flops, no `alert` flop; boot_ok cost 1, word cost 1) |
| V6 (s1,s2 delayed) | 1+1 (two samples, 24 flops) | same | same | same | same |
| V6b (fresh `s2<=sig`) | 24 flops, 1+1 | 24 flops | **16 flops** (s1 and s2 merged into one register; compare roots 2 on the same flops) | 16 flops | 16 flops, 1 root |
So the project flow (per-module abc, hierarchy flattened after, no opt_merge) and conda/apt `synth` without -flatten keep the keep_hierarchy compares apart; only my forced-flatten flow merges them, and V5's voter/alert redundancy then vanishes (V5 -> 1). V6b's "independent second sample" is merged by `synth` (opt) into one register, so it would not give temporal independence under that flow. Counted only compare roots; voters stay instantiated (16 voter cells) in V5 under non-flat flows.

## 5. Full-mask consumer matrix (MEASURED, conda 0.38 plain, T=6, 60 s per call, `tools/mat.py`, `data/mask_*.jsonl`; collisions (0) = idle states already match on masked bits)
Min flips, count of masks per popcount (V2 spike for reference from M1: popcount 8 -> 3, 6 -> 2:11 3:17):
- V4b: 255/255 masks done, 0 unknown. pop1 0:6 1:2; pop2 0:11 1:17; pop3 0:8 1:48; pop4 0:2 1:68; pop5 1:56; pop6 1:28; pop7 1:8; pop8 1:1. Every non-colliding mask is 1 flip (same as V1).
- V6h: 222/255 done (killed at the 480 s cap; not complete), 0 unknown among done: all non-colliding done masks are 1.
- V5: only 82/255 done (cap), 1 unknown: pop1 1, pop2 1 (one 2), pop3 1:17 2:10, pop4 1:6 2:13, pop5 2:5 3:1. So for consumers of up to 4-5 bits V5 is mostly 1 to 2; only wide consumers (full word) reach 3. Remaining V5 masks (pop 5-8 mostly) NOT RUN; the 8-bit full word is 3 from section 3.

## 6. Reading (what raises the cost, what does not)
- Only in the scope word / input nets not sites / known power-up (the scope where V2 itself is 3 or 2) does anything differ. In every other scope all designs, including V2 and V5, are 1: boot_ok goal (one net), input nets as sites, arbitrary power-up state. So none of V4, V4b, V5, V6 raises the cost in those scopes.
- V5 (hardened voter + sticky alert): 3 in both flows on the full word, equals V2's spike value and exceeds V2 apt (2) by one. This is the only design above V2 in the apt-0.33 flow. It is fragile to synthesis: forced flatten (opt_merge) collapses it to 1. And for narrow consumers it is mostly 1 to 2 (partial matrix).
- V4: complement rail with a shared compare = 1 as predicted (negative demo). V4b: its separate compare raises the 16-bit goal to 2, but an 8-bit consumer of one rail sees 1, and any other scope is 1; so separate compare copies only help a consumer that checks both rails.
- V6 sparse sequence FSM: 1 flip in every measured cell, worse than V2. Prediction in R21 (2) was refuted: the sparse state code protects register bits but not the select/decode nets. Two sampled compares did not help (constant `sig`; also V6b is merged by `synth`).
- Plainly: no design beats V2 apart from V5 on the full-word goal in apt flow (3 vs 2), no design beats V2 spike (3). None raises cost under goal boot_ok, input-as-sites or arbitrary power-up.

## 7. Not done / caveats
- Only T=6, k<=3; "1" cells are exact minima, "3" cells mean k<=2 unsat and a 3-flip attack found. Input sites: one shared site per input bit. Arbitrary power-up = free_nongoal only (plain "free" gives 0 for all designs, not run). Free per-cycle attacker input (B2 `free_in`) NOT run, so temporal-diversity benefit of V6b under time-varying input is untested (R21's point).
- V6's one-flip witness cause not traced to a specific gate. Mask matrices for V5 and V6h incomplete (cap). Yosys apt 0.33 and conda 0.38 only; the stored spike netlists were not used for V4-V6 (no such files), so "spike-style" means conda 0.38 plain.
- My `apt033_flat` flow is not a project flow. Compare-root counting only recognises exact (src==C3) functions.
- Faults are modelled bit flips in toy netlists; nothing here is a statement about hardware.

## Files
`V456_REPORT.md`; `rtl/{v4,v4b,v5,v6,v6b,v6h,v6bh,tb}.v`; `tools/{run.py,gs.py,cnt.py,wit.py,mat.py,synth_flat.sh,synth_any.sh}`; `data/{res_core,res_core2,res_flows}.jsonl, all_rows.json, compare_net_counts.txt, mask_*.jsonl, mask_summary.txt`. Note: `mat.py` imports `gs_mask` from /tmp/work_v456 (copy of `research/c3/m1/gs_mask.py`).
