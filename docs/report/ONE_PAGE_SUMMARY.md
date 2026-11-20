# One-page summary

Licence: UNDECIDED. Title: working title TBD. Previous version: `research/c4/pres/backup/ONE_PAGE_SUMMARY.md.orig`. Numbers: `docs/NUMBERS.md`. Faults are modelled single-cycle bit flips on toy 8-bit designs; nothing is physical; nothing is established as new.

**The sentence.** Three guards on one wire are really one guard.

**The problem (working statement P3; the owner decides the wording).** Given a gate-level netlist and the bits a consumer actually checks, report how many single-cycle flips defeat a redundant boot decision, which nets the supposed copies share, and how that answer changes with synthesis build, counting rule and scope. The tool is a solver-backed scope reporter with a sound lower bound; it is not a validated linter.

**The story in plain words.** A lock has three guards, but their answers end in one shared decision wire. Our solver (z3, over a Yosys gate netlist) finds the fewest modelled flips that open it. Then the answer depends on what is counted and checked:

| V2 (three copies), minimum flips | Flips | Label |
|---|---|---|
| Full 8-bit word, stored netlist, inputs not attackable, known power-up | **3** | MEASURED |
| Same, re-synthesized with apt Yosys 0.33 | **2** | MEASURED |
| Accept flag `boot_ok` | **1** | MEASURED |
| Consumer reads 4 bits | 1 to 3 (28 / 36 / 4 of 68 masks need 1 / 2 / 3) | MEASURED |
| Input nets also fault sites, or arbitrary power-up | **1** (0 with no reset at all) | MEASURED |
| Synthesis merges the copies (opt_merge; effect previously shown by SYNFI, 3->2 and 4->2; our E2 replicates it on a toy design) | **1** | MEASURED (edu agent) |
| Over 264 synthesis settings | 1 in 180, 2 in 60, 3 in 24 (of 264 solved configs; 152 distinct netlists: 94/38/20 (DA3; not comparable with 6/32 of REP) | MEASURED |
| V0 and V1 (V1: two copies, one shared wire `ok`) | **1** | MEASURED |

Consumer-width curve (lowest n bits read, n = 1..8): 0, 1, 1, 2, 2, 3, 3, 3 (MEASURED; `faultbound-wt ... --sweep-widths`). The bound is always 6 cycles and at most 3 flips; ">3" would mean none found up to 3, not secure.

**Physical grounding, with its limits.**
- SPICE (SIMULATED, ngspice on sky130 cells, not silicon): a supply dip pulls every high gate on the rail low together; 0 of 60 dip points flipped a stored flop; a clock runt makes a flop capture at the wrong time. Do not quote voltages or timings.
- Rail-dip model (SIMULATED, B3 + LEDGER): Under B3's 1-to-0-only rail model V1, V2 and V5 survive within the bound (no attack up to 3 events, T=6; V0 does not under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication (LEDGER 0-to-1 control, `research/c5/ledger/`; whole-design `rise_all` stays >3 for the word goal). SPICE supports 1-to-0 for supply dips; EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here); the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug) (`research/c5/anchor/RAIL_RECONCILIATION.md`). V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates). Brute-force anchors now exist (agent ANCHOR, z3-free simulator, `research/c5/anchor/`): V2 spike stem flips (k<=2 none at T=4; 182 attacking triples at k=3), V2 apt pairs (3 attacking pairs at k=2), B3 rail models (32 rows, T=4, k<=2, all agree with z3) and selective sets (22 sets of size 3, none of size 1 or 2). Still z3-only: T=6 rail events at k=3, and V5.
- Layout (SIMULATED on a MEASURED flow-demo placement): the three copies sit within 2.95 um on one supply net. Spreading them to 15 um or more helps only against local events; a die-wide selective dip still costs 1. The spread layouts failed LVS (a known filler flow bug), so they are an experiment, not a fix.

**What we built.** The solver; a product CLI `faultbound-wt` with consumer bits, input sites, power-up modes, scope sweep, width sweep and timeout; a dashboard with a Scope tab; a classroom kit. Tests: 189 root passed (2 skipped), 324 product passed (MEASURED on a copy, 2026-11-20 (re-measured by RECON6 on the unpacked bundle); quote your own count). Mutation score 50 of 69 (72.5%) root, 50 of 74 (67.6%) product (REPORTED, T2/T3; earlier 67% / 65% was over the first 43 mutants only). Reproduce: `make reproduce` and `make check-reproduce` give 36 of 36 rows on a copy; do not run them in the live tree.

**What is NOT proven.**
- Nothing physical: no chip, hardware or glitch; SPICE is simulation.
- Toy designs, 6 cycles, at most 3 flips; the one unbounded proof (ABC PDR) covers one netlist and k <= 2, with no independent certificate.
- The prior art (SYNFI, FIRMER, k-FRP, CLEAVE, FIVER, uArchiFI) covers the base method; nothing is established as new; the k-FRP full text is unread.
- No counting rule is shown physical; stem = 1 is the field's convention. Under it V2 needs only 2 flips on 26 of 32 rebuilt netlists (3 on 6).
- The structural predictor is exact on 150 of 163 fresh toy cells (92%), against 62% for always predicting 1 and 83% for the sound lower bound alone (DA3; LEDGER: 71 of 71 on a stratified sample of the same E2 family, 4 of 6 on fresh RTLs (wrong on the voter designs V2m and V5); 58% on cells needing 2+ flips; it is a pre-check and the solver is the reference. The consumer-mask rule is the minimum of Hamming distance to idle states and the number of comparator copies touched: known-style cut/Hamming reasoning, not a discovery; exact on spike V2 (255/255), 187/255 on apt (DA3).

**Where to look.** Deck `docs/report/SLIDES.pptx` (12 slides plus 4 backup), demo `docs/report/DEMO_5MIN.md`, report `docs/report/PROJECT_REPORT.md`, dossier `docs/dossier/PROJECT_DOSSIER.md`, status `docs/FINAL_STATUS.md`, dashboard `dashboard/index.html`.
