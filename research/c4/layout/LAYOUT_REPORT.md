# LAYOUT report: turning "selectivity" into layout facts (V2, V1)

Labels: MEASURED = read from the DEF / post-route netlist / LEF with plain Python; SIMULATED = z3 verdict of B3's fault model (bounded T=6, <=3 events) on layout-derived domains; INFERRED = my domain definition or reading, not extracted from a power-grid model; HYPOTHETICAL = what-if placement, routing/timing/DRC/LVS not redone. No silicon, no extracted parasitics, no EM model, no IR-drop solve. The layout is a flow demonstration with known DRC caveats (`layout/v_designs/out_patched/RESULT.md`: library-cell DRC errors inside magic remain, LVS only netlist-vs-extraction). V0 has no placed layout in the tree (only V1, V2), so V0 is not covered.

Inputs (read only): `layout/v_designs/out_patched/{v1,v2}.def`, `{v1,v2}_pnr.v` (post-route netlist), sky130_fd_sc_hd LEF (cell sizes), B3 engine `research/c4/b3/b3pack.py` (copied unchanged to /tmp/work_layout; `b3cell.py` here is the same file plus ONE patch: subset choice per placed cell).

## 1. Mapping gates to coordinates (MEASURED)
- `layout_extract.py` parses DEF placements (um) + LEF sizes. Cell position = cell centre. 8 rows (ROW_0..7, y = 5.44 + 2.72 k), 10 well-tap cells (`tapvpwrvgnd_1`, 9.7 um nominal pitch per row), 36 logic cells in V2 (28 gates + 8 dfxtp), 35 in V1. Coordinates for every cell, its row, VPWR/VGND rail y, nearest tap: `layout_geometry_{v1,v2}.json`.
- Rail rows: N rows have VGND at the bottom and VPWR at the top, FS rows the reverse, so one met1 rail serves two adjacent rows: VPWR rails y = 8.16 (rows 0,1; 12 cells), 13.6 (rows 2,3; 9), 19.04 (rows 4,5; 9), 24.48 (rows 6,7; 6); VGND rails y = 5.44 (6 cells), 10.88 (10), 16.32 (10), 21.76 (7), 27.2 (3).
- Compare copies: identified BY NAME (MEASURED): synthesis kept `(* keep_hierarchy *) cmp8`, so cells `c0/_2_,_3_,_4_` (nand4bb_1, nand2_1, nor4_1) etc. are the three copies; each copy is 3 cells and the cones of m0, m1, m2 are disjoint (also DA2). V1 has c1, c2. All other cells (`_NN_`) are FSM / output logic and flops.
- Gate-to-cell mapping for the solver: the B3 engine runs on generic gate netlists, not on this mapped netlist. I decomposed every placed sky130 cell into AND/OR/NOT/MUX primitives (cell functions taken from the liberty `function` strings) and named each primitive `<cell>::k`, so the engine's gates map one-to-one to placed cells (`nl/{v1,v2}_layout.json`). Check (MEASURED, `simcheck.py`): the decomposed layout netlist equals the B3 spike netlist on all 256 `sig` values over 5 cycles for both V1 and V2 (boot_word and boot_ok traces identical). Assumption: the flop init is F0 (the layout netlist has no reset; init copied from RTL, not carried by the flow).
- Modelling choice (labelled): a "cell dip" forces the placed cell's OUTPUT net to 0 (default `LAYOUT_NODES=out`). Forcing also the internal primitive nodes is run as a sensitivity (`*_allnodes.json`); the minimal attack sets are identical in both.

## 2. Geometry facts for V2 (MEASURED unless noted)
Minimal one-event attack sets (SIMULATED verdict, cell granularity, T=6, one dip event that may choose which cells fall; `minsets.py`, `minsets_v2.json`; enumeration <= 4 cells): there are exactly 4 minimal sets, all of 3 cells, all at cycle 1, for both goals (word, ok):

| set | min enclosing circle r (centres) | bbox w x h (um) | rows | VPWR rails | other cells inside the circle (flops) |
|---|---|---|---|---|---|
| c0/_2_, c1/_2_, c2/_2_ (the three nand4bb) | 2.95 um | 8.28 x 8.16 | 0,1,2 | 8.16 and 13.6 | 2 (0) |
| _16_, c0/_2_, c1/_2_ (inv `_16_` stands in for copy 2: word[5] = not m2) | 3.06 | 7.36 x 8.16 | 1,2,3 | 8.16, 13.6 | 2 (1) |
| c0/_3_, c1/_3_, c2/_3_ (the three nand2) | 3.29 | 7.36 x 5.44 | 0,1 | 8.16 only | 2 (1) |
| _16_, c0/_3_, c1/_3_ | 4.58 | 5.52 x 10.88 | 0,1,3 | 8.16, 13.6 | 4 (2) |

- Smallest radius that covers a sufficient set: 2.95 um (centre-to-centre; the cells are 1.4 to 5 um wide, so with cell extents the disc is somewhat larger). The earlier "3.5 um hits all three copies" statement is consistent: all four sets fit in 3.5 um except the last (4.58). Minimum rectangle: 7.36 x 5.44 um (nand2 triple, 40 um^2) or 8.28 x 8.16 (nand4bb triple). Inside the minimal circle only 2 other cells (0 or 1 flop); the whole V2 has 36 logic cells in a 30.6 x 30.6 um die.
- Over ALL 27 one-cell-per-copy triples the enclosing radius ranges 1.67 to 7.03 um (`geom_v2.json`); only 2 of the 27 triples (the nand4bb triple and the nand2 triple) are sufficient as a one-event all-or-nothing dip (SIMULATED, `results_domains_v2.jsonl`, copy_triples).
- Rail sharing (MEASURED): the nand2 triple sits on ONE VPWR rail (y=8.16: rows 0 and 1) but on three different VGND rails (5.44, 5.44, 10.88: c1,c2 row 0, c0 row 1); the nand4bb triple spans VPWR 8.16/13.6 and VGND 5.44/10.88. The copies are spread over rows: c0 all in row 1, c1 rows 0,0,2, c2 all in row 0. Copy-to-copy centre distances for the nand2 cells: 1.84 (c1-c2), 4.95 (c0-c1), 6.57 (c0-c2) um; for the nand4bb cells: 3.28, 4.95, 5.91 um.
- Nearest well tap (centre to centre, MEASURED): c0 nand4bb/nand2/nor4 2.30 / 5.06 / 2.76 um; c1 2.76 / 0.92 / 1.38; c2 2.30 / 0.92 / 3.68. Taps are placed per row about 9.7 um apart, so every cell is within about 5.1 um of a tap (`tapcell -distance 10`).
- Supply structure (MEASURED, DEF SPECIALNETS): met1 follow-pin rails per row (x 3.22 to 27.14, 0.48 um wide); ONE vertical met4 VPWR strap at x=9.22 and ONE vertical met4 VGND strap at x=19.22 (1.6 um wide, y 5.2 to 27.44); ONE horizontal met5 strap each (VPWR y=11.2, VGND y=21.2). All 4 VPWR rails connect to the met4 VPWR strap only at x=9.22 (via stacks), all 5 VGND rails only at x=19.22. There is no ring and no second strap. Consequence (INFERRED reading): electrically the design is one VPWR net fed at one column; "rail domains" below are my layout-derived guesses about where a local droop could be confined, not supported by a parasitic extraction.

## 3. Domain files and how to feed B3's engine
- `domains_{v1,v2,v2_wi}.json`: `families` -> family -> group name -> list of PLACED CELL names. Families: `row` (8 groups; cells of one placement row), `vpwr_rail` (4; cells touching the same VPWR met1 rail, i.e. two rows), `vgnd_rail` (5), `strap_branch` (VPWR rail x side of the met4 via column; INFERRED), `strap_far` (cells > or <= 5 / 10 um along the rail from the VPWR via column; INFERRED), `tap_nearest` (cells whose nearest tap is the same tap; INFERRED well proxy), `radius_{2.0,3.5,5.0,10.0}` (one disc per logic-cell centre, deduplicated; a cell is inside if its centre is within r), `rail_all`. MEASURED placement, INFERRED family definitions where stated.
- `domains_*_gates.json`: same groups as engine objects: `gates0` = primitive names whose output is a placed cell's output pin, `d0_flops` = flop cells. Feed into B3: `ev = bp.Event(name, gates0={net ids of gates0}, d0={Q net ids of d0_flops}, subset=False)` with net ids from `faultpack.Netlist('nl/v2_layout.json','v2').drivers` (the key `cellname` of each driver is the primitive name) and `bp.min_cost(nl, 6, events, cap=3, timeout_ms=60000, goal_out='boot_word', goal_value=0x96)` (ok: `goal_out='boot_ok', goal_value=1`). `run_domains.py` does exactly this (copy the B3 code to /tmp/work_layout first). `subset=True` makes an event choose any subset of its sites (B3 `dip_subset` restricted to the domain); `b3cell.py` makes that choice per placed cell.
- Run record: `results_domains_*.jsonl` (family x mode x goal), `sweep_*.json` (radius sweep 1 to 15 um), each cell-granular; `_allnodes` variants are the internal-node sensitivity.

## 4. Minimum event cost per domain family (SIMULATED, T=6, cap 3 events, no z3 unknowns; `>3` = no attack up to 3, not "secure")
AoN = every cell of the domain falls together (rail-like); SUB = ONE event picks which cells of the domain fall (selective). Entries are word / ok.

| family (V2 layout netlist) | AoN | SUB |
|---|---|---|
| rail_all (whole design) | >3 / >3 | 1 / 1 |
| row (8) | >3 / 3 | 2 / 2 |
| vpwr_rail (4) | >3 / >3 | 1 / 1 |
| vgnd_rail (5) | >3 / >3 | 2 / 2 |
| strap_branch, strap_far | >3 / >3 | 1 / 1 |
| tap_nearest | >3 / >3 | 2 / 2 |
| radius 2.0 um | 2 / 2 | 2 / 2 |
| radius 3.0 um | 3 / 3 | 1 / 1 |
| radius 3.5 um | 3 / 3 | 1 / 1 |
| radius 5.0 um | 2 / 2 | 1 / 1 |
| radius 10 um | >3 / 2 | 1 / 1 |
| radius 15 um | >3 / >3 | 1 / 1 |

V1 for comparison: any radius <= 4 um: 1 / 1 even all-or-nothing (a one-cell dip of `_29_` or the c1/c2 pair, 1.64 um apart); rows, rails, straps AoN >3 but SUB 1 / 1; radius 5 to 10 um AoN 2 / 2. V1 minimal sets: {`_29_`} alone, {c1/_2_, c2/_2_} (r 1.64), {c1/_3_, c2/_3_} (r 11.7), and for ok also {`_22_`, `_23_`}.

Readings: (a) rail-wide (rail_all) and whole row / rail / strap AoN domains do not break V2 within 3 events, matching B3 (rail_all/half/unions `>3`). (b) Disc domains do: two events, each a 2 um disc, break V2 (the c1/c2 nand2 pair is 1.84 um apart, c0's is 4.95 um away: one disc covers two copies, a second covers the third); a one-event all-or-nothing disc never works. AoN results are NOT monotone in r (2 -> 3 -> >3 -> 2) because a larger disc also drops unrelated cells (flops' D capture, FSM gates), which spoils the attack; this is a property of the all-or-nothing model, not noise. (c) The selective model is monotone: one event suffices once the disc is >= the smallest minimal-set radius (2.95 um; the sweep flips between 2.5 and 3.0), at any larger r too, and for row/vpwr_rail families with SUB.
- Consistency with B3: B3's `dip_subset` bound (V2: 3 gates, one per copy, 1 event) is reproduced at cell level with the same 3 sites; rail_all AoN `>3` agrees with B3's `rail_all`.

## 5. What the layout does and does not support (honest answer)
- Supports: the three copies are NOT spread over independent rails. For the sufficient triples all three cells lie within a 3 um radius (nand4bb triple 2.95 um, nand2 triple 3.29 um), the nand2 triple shares a single VPWR rail, and the nearest taps are 0.9 to 5 um away, so no well or tap separation exists between copies. The minimal circle contains only 2 other cells, so a localised domain that covers the three copies and almost nothing else exists geometrically.
- Does not support / does not show: a radius domain of 3 um does not by itself give cost 1 under rail-like semantics: if everything inside the disc falls together (AoN), the cheapest attack stays 2 to 3 events (the disc also contains the output inverter, flop D pins etc.). Cost 1 needs the event to choose WHICH cells fall (SUB). Whether a physical dip can choose, or what voltage threshold separates a nand2 from a neighbouring flop, is NOT in these data (EL1 saw a rail-wide correlated dip on a tiny circuit); an IR-drop / extraction run would be needed and was not done. Row, rail, strap and tap families as defined here cover 3 to 12 cells and 8 or more rows would be dipped together, which is rail-wide-like in effect for V2 (AoN `>3`). The single met4 via column per rail means that, if droop followed the PDN, the natural domain is the whole design, not a row; this is INFERRED from geometry only.
- So: no single physical domain (row, rail, strap, well) covers exactly the three copies; a small disc (2 to 3 um) does, but with collateral cells, and the verdict depends on the selectivity assumption, exactly as B3 said, now with numbers: selectivity radius threshold 2.95 um (MEASURED geometry, SIMULATED verdict).

## 6. What a designer could change in placement (measured by the same method)
HYPOTHETICAL what-if (`whatif.py`; V2 with three same-footprint cell swaps: `_18_`<->`c0/_3_`, `_19_`<->`c0/_2_`, `c1/_2_`<->`c2/_2_`; routing, timing, DRC and LVS not redone; `results_domains_v2_wi.jsonl`, `sweep_v2_wi.json`):
- Minimal-set radius rises from 2.95 to 4.58 um (nand4bb triple) and 6.13 (nand2 triple); the SUB threshold moves from between 2.5 and 3.0 um to between 4 and 5 um (sweep: SUB 2 up to 4 um, 1 from 5 um).
- Per-family verdicts after the swap: radius 2 to 4 um SUB cost 2 (before: 1 from 3 um); AoN radius 3.0: 2 (was 3), radius 3.5: 3 / 2. But the rail-type families stay at SUB 1 (vpwr_rail, strap_branch, strap_far, rail_all): a whole VPWR rail still contains a sufficient set, so a placement change within these slots only helps against local discs, not against a selective event on a rail.
- What would help more (not run; UNVERIFIED expectations): put the copies' cells on different VPWR rails and in different row pairs so that no rail contains a sufficient set (the nand2 triple is on one VPWR rail today; the what-if still has the nand4bb and nand2 triples on shared rails), separate the copies' wells (nearest-tap domains differ), and use a bigger / sparser floorplan (this die is 30.6 um on a side for 36 cells, utilisation 77 %, which is why everything is within a few um). The sparse-slot swap above reached only 4.6 to 6.1 um because the 30 um die and equal-footprint slots limit it. Each of these can be re-measured with `whatif.py` (swap list) -> `minsets.py` -> `radius_sweep.py` -> `run_domains.py`.
- Orthogonal point: the cheaper route is logic, not placement (a minimal set of three cells exists because the three nand2/nand4bb stages are logically symmetric; V2's cost 3 relies on the three copies being the only way to the word).

## Limits
Bounded T=6, <=3 events, init F0 assumed; no validation of my z3 runs against brute force on the layout netlists (only the functional equality check and agreement with B3's `rail_all` and `dip_subset` rows). Cell-output dip is one modelling choice; internal-node variants give the same minimal sets. Radius domains use cell centres, not cell extents. The V2 single-event verdicts are tied to the placed netlist (Yosys 0.38 / sky130 mapping), which differs from B3's generic gates (e.g. 7 generic gates per copy vs 3 cells), so the numbers are not interchangeable with B3's counts. The enumeration of minimal sets is limited to <= 4 cells. Nothing here is physical glitch evidence; nothing established as new.

## Files
`layout_extract.py` (DEF/netlist -> geometry, domains, decomposed netlist), `geom_report.py`, `minsets.py`, `radius_sweep.py`, `run_domains.py`, `whatif.py`, `export_gate_domains.py`, `simcheck.py`, `b3cell.py`; outputs `domains_*.json`, `domains_*_gates.json`, `layout_geometry_*.json`, `geom_*.json`, `minsets_*.json`, `sweep_*.json`, `results_domains_*.jsonl`, `whatif_v2_swaps.json`, `nl/*_layout.json`. Scripts expect work copies in /tmp/work_layout (B3 code + `nl/`), as run here.
