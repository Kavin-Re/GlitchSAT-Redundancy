# Project report: which redundant copies really protect a decision?


## Abstract
Designers add redundant copies of a boot check and say the check "resists k faults". We ask what such a statement needs in order to mean anything. We built a solver (z3 over a Yosys gate netlist, unrolled over clock cycles) that finds the fewest modelled flips that make a toy boot check accept a wrong key, and a command-line tool that reruns the question under different scopes. On three toy designs (V0 plain, V1 two copies feeding one wire, V2 three copies with split result bits), bounded at 6 cycles and at most 3 flips: V0 and V1 fall to 1 flip; V2 needs 3 flips only in one narrow scope (full 8-bit word, inputs not attackable, known power-up, stored netlist) and 2 on an apt Yosys 0.33 re-synthesis; it needs 1 flip if the consumer reads only the accept flag, if input nets are fault sites, or if synthesis merges the copies (previously shown by SYNFI: 3->2 and 4->2 faults after FSM recoding and register merging, `set_dont_touch` restored 4; our E2 replicates it on a toy design); a consumer reading its lowest n bits needs 0, 1, 1, 2, 2, 3, 3, 3 flips; over 264 synthesis settings V2 needs 1, 2 or 3 flips in 180, 60 and 24 (of 264 solved configs; 152 distinct netlists: 94/38/20 (DA3). A circuit-level simulation (SIMULATED) and a layout study (SIMULATED on a flow-demo placement) show why one clean flip is a simplification: a supply dip hits a whole rail, and the three copies sit within 2.95 um on one supply net. The base method is covered by earlier tools; nothing is established as new. Nothing physical was tested.

## 1. Problem
Plain words: a lock has three guards, but all three answers can end in one shared wire. Flip that wire for one clock tick (a modelled flip, not a real glitch) and the lock may open. The quotable sentence: **three guards on one wire are really one guard.**

Working statement P3 (the owner decides the wording; evolution in `docs/dossier/PROBLEM_STATEMENT_EVOLUTION.md`): given a gate-level netlist and the bits a consumer actually checks, report how many single-cycle flips defeat a redundant boot decision, which nets the supposed copies share, and how that answer changes with synthesis build, counting rule and scope. After the predictor audit (section 3.7) P3 is stated at the smaller level: a solver-backed scope reporter with a sound lower bound, not a validated linter.

## 2. Method
- Designs: V0 plain compare; V1 two compare copies and a sparse FSM, both copies feeding one net `ok`; V2 three compare copies, each owning its own result bits (`rtl/`, stored netlists in `reference/spike_netlists/`). Key 0xC3, accept word 0x96.
- Fault model: one fault is one flip of one net (gate output or flop Q) for one cycle, any cycle, at most k flips in total; the attacker input is free and held constant; a net counts once however many gates read it (stem rule, the convention of SYNFI and FIRMER; fanout counting is run as a stress test). Verdicts are bounded: 6 cycles and k <= 3 unless stated; `>3` means no attack found up to 3, never "secure".
- Solver: `scripts/glitchsat.py` (Yosys netlist, z3, cardinality bound tightened until UNSAT; witness replay in iverilog). Product CLI `faultbound-wt` (`product/`): consumer bits, goal output, input sites, power-up modes, scope sweep, width sweep, wall-clock timeout; not shipped: the branch counting rule and per-cycle attacker input.
- Every product report prints its scope block (goal, inputs, init state, counting rule, bounds, netlist SHA-256) and "bounded result under this model; not a proof of security".

## 3. Results, each with its scope
Scope of every V2 "3" below: stored spike netlist, goal = 8-bit result word, input nets not fault sites, known power-up state, constant non-key attacker input, 6 cycles, k <= 3.

### 3.1 Engine results (MEASURED; `results/reproduce_summary.json`, 36 rows)
V0: 1 flip on every netlist. V1: 1 flip (net `ok`, cycle 1). V2 stored netlist: no attack with 1 or 2 flips, 3 flips needed. V2 re-synthesized with apt Yosys 0.33: 2. V2 on validation flow B (hierarchy stripped): 1 (4 of 378 single-flip sites).

### 3.2 Scope matrix (B2, 360 cells, MEASURED)
V2 minimum flips: full word 3 (stored); 2 (apt re-synthesis); accept flag `boot_ok` 1; input nets as fault sites 1; arbitrary non-accepting power-up 1; no reset at all 0 (a design gap). V0 and V1: 1 in every known-init cell. "V2 resists 2 flips" is true in exactly one narrow cell; never quote it without the qualifiers.

### 3.3 Consumer width (M1, MEASURED)
Lowest n bits read, V2 stored netlist: 0, 1, 1, 2, 2, 3, 3, 3 for n = 1..8 (product `--sweep-widths`). Four-bit masks: 28 / 36 / 4 of 68 need 1 / 2 / 3. All 255 masks: 88 / 96 / 44 need 1 / 2 / 3, plus 27 that already accept with 0 flips. The mask rule is exact on the stored netlist (255 of 255) and fails on the apt re-synthesis (68 mismatches). Rechecked by M1b with two engines: 0 of 1785 cells changed (`research/c4/m1b/M1B_REPORT.md`).

### 3.4 Synthesis variance (E2, MEASURED)
864 configurations (792 solved; 264 for V2): V2 needs 1 flip in 180, 2 in 60, 3 in 24 (of 264 solved configs; 152 distinct netlists: 94/38/20 (DA3; 6/32 (REP, one recipe family) and E2's 180/60/24 are counts in different grids, not comparable rates (ANCHOR N5: on 24 REP/E2 netlist pairs the minimum flips agree 24 of 24)); V1 233 / 31 / 0; V0 264 / 0 / 0. Baseline: apt Yosys 0.33 gives 85 gates and 2 flips, conda 0.38 gives 83 gates and 3 flips; why the builds differ was not analysed. When synthesis merges identical copies (opt_merge, 63 gates) V2 needs 1. SYNFI previously showed the same effect (3->2 and 4->2; `set_dont_touch` restored 4); E2 replicates it on a toy design across 864 configs plus a keep-attribute axis.

### 3.5 Counting rule (DA, REP, R22)
Stem = 1: V2 needs 2 flips on 26 of 32 rebuilt netlists and 3 on 6. Fanout counting: 3 on 32 of 32. REP replicated all 64 rows, but with one reused recipe list (not independent). No source found gives a physical "right" rule; neither is shown physical (R22, SOURCED).

### 3.6 Bounded and unbounded checks (MEASURED)
Independent simulator, a second solver and SymbiYosys agree with the solver (about 2.1M fault sets x 255 inputs, 0 disagreements; 13 of 13 witnesses replay; 40 of 40 sby pairs) but share the fault model, so they check the encoding, not the physics. One unbounded result: ABC PDR, stored V2 netlist, k <= 2, any number of cycles, PASS in 0.83 s; one netlist, constant attacker input, no independent certificate; 3 flips break it. Depth sweep to 20 cycles never lowered the V2 stored-netlist minimum below 3.

### 3.7 Structural predictor (PRE, TEST, VER)
A pre-registered predictor scored 928 of 928 on its first corpus (easy, near-duplicate cells; effective sample 3 to 5 designs). An independent audit on 163 fresh cells found it exact on 150 (92.0%; always predicting 1: 62%, sound lower bound alone: 83%, DA3), within one flip on 156 (95.7%), 18 of 31 (58%) when 2 or more flips are needed, and 1.4x slower than the solver; it fails the 98% bar. Its lower bound was never above the solver in 928 + 163 + 60 cells. Use: quick pre-check; the solver is the reference.

### 3.8 Physical grounding (SIMULATED)
- SPICE (EL1, ngspice, sky130 cells; not silicon): a supply dip pulls every high gate on the rail low together (1 to 0 only); 0 of 60 dip points flipped a stored flop (down to 0 V for 3 ns; longer dips unmapped); a clock runt makes a flop capture its input at the wrong time. Do not quote voltages or timings as attack parameters.
- Rail-dip model (B3 + LEDGER, T = 6, <= 3 events): Under B3's 1-to-0-only rail model V1, V2 and V5 survive within the bound (no attack up to 3 events, T=6; V0 does not under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication (LEDGER 0-to-1 control, `research/c5/ledger/`; whole-design `rise_all` stays >3 for the word goal). SPICE supports 1-to-0 for supply dips; EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here); the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug) (`research/c5/anchor/RAIL_RECONCILIATION.md`). V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates). Brute-force anchors now exist (agent ANCHOR, z3-free simulator, `research/c5/anchor/`): V2 spike stem flips (k<=2 none at T=4; 182 attacking triples at k=3), V2 apt pairs (3 attacking pairs at k=2), B3 rail models (32 rows, T=4, k<=2, all agree with z3) and selective sets (22 sets of size 3, none of size 1 or 2). Still z3-only: T=6 rail events at k=3, and V5.
- Layout (LAYOUT, L2; OpenROAD, magic, netgen, sky130; flow demonstration, no extraction, no IR-drop): the three sufficient cells lie within 2.95 um on one supply net. Four spread layouts (the smallest sufficient set then needs a circle of radius 11 to 18 um) raise the cost against local events; a die-wide selective dip still costs 1; die area x1.26 to x2.5, wire length +29 to +50%; router DRC 0 and antenna 0, but LVS FAILED in all four (known filler flow bug, not fixed). The original layout: router DRC 0, LVS matches uniquely (430 vs 430), slack +7.035 ns (estimate); magic errors in library cells are tap-dependent and tested in context for one cell only, so it is not claimed DRC-clean.

**What triplication bought (V1 two copies vs V2 three copies; every cell is a ledger cell, `research/c5/ledger/ledger.csv`, word goal, T = 6, at most 3 events; M = MEASURED, S = SIMULATED; `>3` = no attack found up to 3, not "secure").**

| Ledger row | V1 | V2 | Reading |
|---|---|---|---|
| Stem flips, stored spike netlist, hierarchy kept | 1 (M) | 3 (M) | V2 gains 2 |
| Stem flips, apt 0.33 plain / opt | 1 / 1 (M) | 2 / 2 (M) | V2 gains 1 |
| Stem flips, conda 0.38 plain / opt | 1 / 1 (M) | 3 / 2 (M) | V2 gains 2 / 1 |
| Stem flips, apt plain + `opt_merge` (register merging) | 1 (M) | 1 (M) | tie |
| Consumer checks only 4 bits (0x0F) | 1 (M) | 2 (M) | V2 gains 1 |
| Consumer checks the accept flag `boot_ok` | 1 (M) | 1 (M) | tie |
| Fanout-branch counting (stress rule) | 2 (M) | 3 (M) | V2 gains 1 |
| Rail event 1->0 (whole design) | >3 (S) | >3 (S) | tie |
| Rail event 0->1 (negative control; netlist hierarchy, not a physical rail) | 1 (S) | 1 (S) | tie |
| Selective event that may pick its gates | 1 event (S) | 1 event (S) | tie in events; the smallest selective set is 2 gates for V1 and 3 for V2 (one per compare copy; LEDGER_REPORT s2): V2 gains one gate |

So V2 gains over V1 only in the stem-flip and fanout-count rows (hierarchy kept, one netlist family); in every rail-event row they tie, and where register merging collapses the copies V2 falls to V1's number. Physical track closed: no extraction, selectivity unproven. No new numbers; a copy of ledger cells.

### 3.9 Other checks
Six real-design wrappers (R20): only a DMR AES S-box needs 2 flips; the rest 1; generic upsets, no finding. SYNFI was run on the toy designs (narrow; its verdicts agree with ours on V0, V1, V2).

## 4. What was built, and checked
Solver, product CLI, dashboard (with a Scope tab), classroom kit, explainer page and game, layout flow demos. Tests: 189 root passed (2 skipped); 324 product passed (MEASURED, clean copy, 2026-11-20 (re-measured by RECON6 on the unpacked bundle)). Mutation score 50 of 69 (72.5%) root, 50 of 74 (67.6%) product (REPORTED, T2/T3; 10 product mutant runs never run, so the product figure is over the runs that exist; earlier 67% / 65% was over the first 43 mutants only). `make reproduce` and `make check-reproduce`: 36 of 36 rows on a copy (CI on another Yosys build may differ). Run them only on a copy.

## 5. Limits (read these)
1. Nothing physical: no chip, hardware or glitch; SPICE and layout are simulations or flow demonstrations.
2. Toy 8-bit designs; bounds 6 cycles, k <= 3; attacker input constant in the engine (a free per-cycle input checked only for the stored V2 netlist).
3. The prior art covers the base method (section 6); nothing is established as new.
4. No counting rule is shown physical.
5. The one unbounded proof covers one netlist; the predictor is a heuristic pre-check.
6. Whether a real dip can choose which gates fall is open; spread layouts failed LVS; layouts are not DRC-clean as a whole; no parasitic extraction.
8. CORRECTED (2026-11-20; the earlier item, now superseded, said the V2 verdict depends on the Yosys version, an error found by a fresh-eyes review and measured by P01a, `docs/report/WHY_TWO_FLIPS.md`): the stored netlist is also Yosys 0.33 (68 gates, another flow); the 85 vs 83 gates (apt 0.33 vs conda 0.38; 0.52 like 0.38 on the plain flow, H5) are flow/build differences in the netlist. The cause of 2 flips is the encoding: 0xCC xor 0x96 touches only two of three copies; `rtl/v2e.v` (0xA5) gives 3 1 1 3 3 3 3 3 over 8 flows (v2: 2 1 1 2 2 2 2 2); conda 0.38 gives 3 only on the plain flow. Encoding sets the floor (idle word touches 2 of 3 copies => 2 flips); the synthesis flow decides whether the floor is reached (1 when a flow merges the copies). A build or flow difference changes the netlist, not the underlying weakness.

## 6. Prior art and references
Related tools that already cover the base method: SYNFI, FIRMER, k-FRP, CLEAVE, FIVER, uArchiFI (`docs/PRIOR_ART.md`). No novelty claim. Labels: SOURCED means a research agent fetched the page or read search-result text; I (PRES) did not read any of these papers, and for k-FRP the full text is still unread (access blocked, not worked around). RUN2 later ran uArchiFI (same minimum flips in 9 of 9 cells, one tool, three toy designs, not a validation) and built k-FRP (different question); FIVER was not built (`research/c5/run2/RUN2_REPORT.md`, measured).
- SYNFI: Nasahl et al., arXiv 2205.04775. Full text read by agent R10 (`research/c2/r10_prior_art/R10_PRIOR_ART_FULL.md`).
- FIRMER: arXiv 2307.00561, TCHES 2024 issue 4. Page read by R23 (first 100k characters); full text read by R10.
- k-FRP: Tollec et al., TCHES 2024(4) 179-204, eprint 2024/247. Abstract only (SOURCED, R23); full text unread.
- CLEAVE (Springer chapter, doi path in R23) and FIVER (TCHES 2021, article 9072): abstract or snippet only.
- OpenTitan hardware implementation guidelines, https://opentitan.org/book/doc/security/implementation_guidelines/hardware/index.html (page fetched by R21): sparse FSM encoding, redundant copies, synthesis-proof primitives.
- Fault-model literature (R22, snippets and keyword searches; not read end to end): SoK of fault injection attacks, arXiv 2509.18341; Roscian et al., FDTC 2013 (laser, SRAM, set/reset); Moro et al., 2013 (EM on a Cortex-M3); Ordas et al., 2017 (fetch blocked; snippet only).


## 8. Reproduce and where to look
Demo: `docs/report/DEMO_5MIN.md` (commands verified on a copy). Deck: `docs/report/SLIDES.pptx` (12 slides plus 4 backup; outline `SLIDES_OUTLINE.md`). One page: `ONE_PAGE_SUMMARY.md`. Dossier `docs/dossier/PROJECT_DOSSIER.md`, Q&A cards `QA_ANSWER_CARDS.md`, status `docs/FINAL_STATUS.md`, dashboard `dashboard/index.html`.
