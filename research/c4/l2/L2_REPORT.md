# L2 report: spreading the three V2 comparator copies in a real sky130 OpenROAD run

Layout flow demonstration only: **no parasitic extraction, no IR-drop analysis, no silicon**. The dip/droop is a modelled threat (B3's bit-flip fault model, z3, T=6, <=3 events), not a physical measurement. Nothing established as new.

Tools (MEASURED, `openroad -version`, `yosys -V`, magic, netgen in env `eda`): OpenROAD 8.3.464 / f12e2f47, Yosys 0.38+92, magic 8.3.464, netgen 1.5.272, sky130A PDK sky130_fd_sc_hd. z3 5.4.1 (system python). Workdir `/tmp/work_l2` (large files stay there).

## What was run
Same netlist as the original V2: re-synthesis of `rtl/v2.v` with `flow_patched/synth.ys.tpl` gives a byte-identical `v2_net.v` (MEASURED, diff). The original flow (`flow_patched/pnr.tcl`) was copied to `pnr_l2.tcl` with only these changes: (1) utilisation is a parameter; (2) before `tapcell`, the 9 cells of c0/c1/c2 (`_2_` nand4bb, `_3_` nand2, `_4_` nor4 of each copy) are placed by hand on chosen rows/x positions and set `FIRM` (fixed for the placer); (3) `check_antennas -report_file` added. Everything else (tapcell distance 10, PDN, global/detailed placement, CTS, repair_timing, global+detailed route, filler, magic GDS+DRC, flat extraction, netgen) is unchanged (`run_var.sh`). Domain families, minimal sets and the radius sweep use LAYOUT's scripts copied to `/tmp/work_l2/lay/code` (paths parametrised only) and B3's `b3pack.py`/`faultpack.py` unchanged (`dom.sh`).

Variants (anchors are fractions of the core; each copy's 3 cells sit side by side in one row):
- `base`: original flow rerun, util 60, no pinning. Placement is identical to the committed `out_patched/v2.def` (COMPONENTS md5 equal); routing geometry differs in detail from the committed DEF (router output not byte-identical), timing/area/LVS equal.
- `v8` (util 45): c0 bottom-left, c1 bottom-right, c2 top-middle.
- `s8` (util 25): c0 bottom-left, c1 bottom-right, c2 top-left (a corner layout; named s8 on disk, it is a ">=15 um" case).
- `v15` (util 20): same anchors as v8, larger core.
- `rr` (util 25): c0, c1, c2 on rows 0, 6, 12 along the diagonal: three different VPWR/VGND rail pairs, taps between them (the "different rails" variant).

## Results table (MEASURED unless noted; DEF/odb in `/tmp/work_l2/out_<var>/`)
| | base (orig.) | v8 | s8 | v15 | rr |
|---|---|---|---|---|---|
| die side (um) / die area (um^2) | 30.6 / 936 | 34.4 / 1183 | 44.1 / 1944 | 48.6 / 2362 | 44.1 / 1944 |
| OpenROAD cell area (um^2) / util | 399 / 77% | 400 / 58% | 414 / 31% | 427 / 26% | 414 / 31% |
| components (taps+CTS+fill included) | 72 | 102 | 199 | 243 | 195 |
| min copy-to-copy distance, centres / bbox gap (um) | 1.84 / 0 | 9.2 / 5.98 | 17.9 / 14.7 | 23.5 / 20.2 | 16.3 / 13.6 |
| min MEC radius of one cell per copy (um), 27 triples | 1.67 | 11.5 | 18.6 | 19.7 | 18.4 |
| rows of the copies | c0:1 c1:0,2 c2:0 | 0 / 0 / 8 | 0 / 0 / 12 | 0 / 0 / 13 | 0 / 6 / 12 |
| a VPWR rail holding cells of all 3 copies | y=8.16 (yes) | none | none | none | none |
| met4 VPWR straps in design / copies' nearest | 1 / all 9.22 | 2 / see data | 2 / c0 9.22, c1 29.22, c2 9.22 | see data | see data |
| wire length, detailed route sum (um) | 949 | 1223 (+29%) | 1241 (+31%) | 1419 (+50%) | 1290 (+36%) |
| setup / hold slack (ns, clk 10 ns, global-route est.) | 7.035 / 0.476 | 7.056 / 0.479 | 7.056 / 0.478 | 7.054 / 0.474 | 7.043 / 0.479 |
| router DRC violations (final) | 0 | 0 | 0 | 0 | 0 |
| antenna (`check_antennas`) | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| magic DRC, top cell | none listed | 15 (li.3, licon.2, met3.6, ...) | 20 (li.3 x53 boxes, ...) | 24 (li.3, met3.6, ...) | 18 |
| netgen LVS | match uniquely (430/430 dev, 226/226 nets) | **FAIL** pin matching (428 vs 430, 220 vs 226) | **FAIL** (427/430, 219/226) | **FAIL** (425/430, 219/226) | **FAIL** (427/430, 221/226) |

Delay cost: the timing slack does not change measurably (+0.0 to +0.02 ns; the 10 ns clock and the tiny design make the added wire irrelevant; no parasitic extraction, estimate only). Wire length cost +29 to +50 %, die area cost x1.26 to x2.5 (die area; cell area only +0 to +7 %: the extra cells are taps, fill and CTS).

**DRC/LVS honesty.** The routed designs are clean by the router (0 violations, empty report) and antenna check, but **LVS FAILS in all four spread variants**, and magic lists top-cell DRC rules that the original does not. Cause (MEASURED, magic extraction warnings in `out_<var>/v2_magic.log`): "Ports FILLER_x.VNB and VGND / sig[2] / sig[3] / sig[4] are electrically shorted" (rr: `c2/_4_.VNB` with sig[3]), i.e. a long signal wire routed on li1 across a row boundary touches the VGND rail of a filler/cell in magic's view. This is the same flow bug VERIFY.md section 3 found for the triage design (fillers inserted after routing, li1 invisible to OpenROAD); the original V2 only passes because its short wires happen not to hit it. Longer `sig` fan-in wires from the central logic to the far-apart copies trigger it. I did NOT fix or suppress it. Tried: skipping `filler_placement` (`*_nf` runs): LVS then still fails (even for `base_nf`: "Netlists do not match", nets 227 vs 226), so that is not a valid fix and I report it only as a negative result. So the hardened placements are not LVS-clean with this flow; fixing needs the flow change named in VERIFY.md (keep li1 off row boundaries / fill before routing), not done here.

## Security-model results (SIMULATED on MEASURED placement; T=6, cap 3 events; `>3` = no attack found up to 3, not "secure")
Smallest sufficient one-event cell set (minimal-set enumeration <=4 cells, `data/minsets_<var>.json`), radius of the minimal enclosing circle of the set's cell centres:

| | base | v8 | s8 | v15 | rr |
|---|---|---|---|---|---|
| min MEC radius of a sufficient set (um) | 2.95 | 11.15 | 17.91 | 15.16 | 15.30 |
| that set | c0/c1/c2 `_2_` | `_16_`+c0/_3_+c1/_3_ | `_16_`+c0/_2_+c1/_2_ | `_16_`+c0/_3_+c1/_3_ | `_16_`+c0/_3_+c1/_3_ |
| selectivity threshold from the sweep, SUB cost 1 first at r (um) | between 2.5 and 3.0 | between 8 and 10 | > 15 (SUB 2 at 15) | 15 (SUB 2 at 10) | 15 (SUB 2 at 8, 10) |

The original 2.95 um is reproduced exactly by the rerun (base). The hardened thresholds are x3 to >x5 larger. Caveat: the enumeration stops at 4 cells so its minimal radius is an upper bound; the sweep (primitive-level subset, any size) is authoritative and shows SUB 1 already at r=10 for v8 while the 4-cell enumeration gives 11.15, so v8's threshold is in (8, 10], not 11.15. Also: in the spread variants the cheapest set uses the output inverter `_16_` as stand-in for copy 2, so the threshold depends on where the placer put the output logic (a fully hardened placement would also pin `_16_`/`_18_`/`_19_` away); this was not done.

Radius sweep (cost word/ok; AoN = all cells of the disc fall together, SUB = one event picks which cells fall; full table `data/sweep_<var>.json`):
| r (um) | base AoN / SUB | v8 AoN / SUB | s8 AoN / SUB | v15 AoN / SUB | rr AoN / SUB |
|---|---|---|---|---|---|
| 3 | 3/3 , 1/1 | 3/2 , 3/2 | 3/2 , 3/2 | >3/3 , 3/3 | 3/2 , 3/2 |
| 5 | 2/2 , 1/1 | >3/2 , 3/2 | 3/2 , 3/2 | >3/2 , 3/2 | 3/2 , 3/2 |
| 10 | >3/2 , 1/1 | >3/2 , 1/1 | >3/2 , 3/2 | >3/2 , 2/2 | >3/2 , 2/2 |
| 15 | >3/>3 , 1/1 | >3/2 , 1/1 | >3/2 , 2/2 | >3/2 , 1/1 | >3/2 , 1/1 |
(Each cell: word/ok. For the "ok" goal an attacker can use cheaper collateral paths, hence the many 2 entries; word and ok are both listed in the JSON.) For small discs (<= 2 um) cost is 2 to 3 in all variants (one disc per copy).

**Rail-level selective event (`data/fam_<var>.jsonl`, SUB cost word/ok):** whole-die rail (`rail_all`, one event, selectable cells): 1/1 in ALL variants, so hardening by distance does not remove a die-wide selective dip (the three copies are still on the same two supply nets; the PDN is one VPWR net). VPWR rail families: base 1/1; v8 2/2; s8 2/2; v15 2/2; rr 3/2. Strap-branch: base 1/1, v8 2/2, s8 and v15 3/3, rr 3/2. VGND rail 2/2 everywhere. Rows: 2/2 (rr 3/2). All-or-nothing rail/row/strap families stay `>3` (or 2 to 3 for the ok goal), as in the original. So spreading and putting the copies on distinct rail pairs (rr) makes any single rail- or row-level event insufficient (cost 2 to 3), but the rail families here are only 1 to 2 of rows wide and a global selective event (rail_all) is unchanged; it requires a dip that can pick the three specific copies out of a 100+ um^2 die, which is the modelling assumption (selectivity), now needing reach of 10 to >15 um instead of 3 um.

## Cost of the hardening
Die area x1.26 (v8) to x2.5 (v15); cell area +0.3 % to +7 % (taps/fill/CTS); detailed wire length +29 % to +50 %; slack unchanged within 0.02 ns (estimate); utilisation 77 % -> 58 / 31 / 26 / 31 %. LVS fails in this flow once wires get long (above), so the real cost includes a flow fix. Router-DRC and antenna still clean.

## Not done / limits
- No parasitic extraction, no IR-drop, no EM, no real power-grid model; domains are geometric (radius / row / rail), a modelled threat. The "well/tap separation" idea is only reflected via rows/rails (taps are placed every 10 um in every variant).
- `_16_` and other output-logic cells were not pinned; thresholds are limited by them. Only 4 anchor patterns and one seed per variant; B3 numbers are bounded (T=6, <=3 events, init F0 assumed, z3 60 s timeout, no unknowns observed in the logs I read).
- Simcheck: the decomposed layout netlists of all variants equal the original on all 256 sig values over 5 cycles (`lay/<var>/sim.log`, MEASURED, 0 of 256 differ), so function is unchanged at netlist level (same netlist).
- LVS failures not resolved (see above); magic DRC counts of std-cell definitions are the known context-dependent false positives, but the top-cell rules listed for the spread variants are real li1 layout conflicts caused by the same fill/li1 problem (not investigated further).
- Rail-row variant with taps between: rr places copies on rows 0/6/12 (three distinct rail pairs, taps from the standard tapcell step); not a dedicated well-isolation structure.

## Files
Tracked here: `pnr_l2.tcl`, `run_var.sh`, `dom.sh`, `metrics.py`, `data/` (metrics_<var>.json with every copy cell position/row/rails, summary_flow.json with all flow numbers, sweep_*.json, minsets_*.json, fam_*.jsonl). Large artefacts under `/tmp/work_l2/out_<var>/` (v2.def, v2_routed.odb, v2.gds, v2.mag, logs, lvs rpt), GDS e.g. `/tmp/work_l2/out_v15/v2.gds`. Commands: `./run_var.sh <var> <util> 1 ax0 ay0 ax1 ay1 ax2 ay2` then `python3 metrics.py <var>` and `./dom.sh <var>`; variant arguments listed above.
