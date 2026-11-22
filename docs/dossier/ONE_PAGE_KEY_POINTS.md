# ONE PAGE FOR THE AUTHOR (plain words)
GlitchSAT. License: Apache-2.0. Read this first, then `PROJECT_DOSSIER.md`. Everything below is something you must be able to say aloud. If you cannot, cut it.

## What the project is

## What is proven (inside the model, with numbers; each is a bounded result: 6 clock ticks, up to 3 flips)
- V0 and V1 fall to 1 flip. V1's two copies end in one shared wire, so one flip beats both. This follows from logic.
- V2 needs 3 flips (or 2 on some rebuilds of the same design) only under a narrow setting: the attacker aims at the 8-bit result word, input wires are not attackable, the chip starts in a known state. Change any one of those and V2 needs 1 flip, like V1. (360-case table, `research/c2/b2_scope/B2_REPORT.md`.)
- It also depends on how wide the part that reads the result is (full word 3 or 2; a 4-bit reader usually 1 to 2; the single accept flag 1) (`research/c3/m1/`), and on which program built the circuit (the same design needed 1, 2 or 3 flips: 1 in 180, 2 in 60, 3 in 24 of 264 solved configs out of 864 build settings; 152 distinct netlists: 94/38/20) (`research/c2/e2_variance/`), and on how one flip is counted (`research/c3/rep/`).
- Other tools and re-runs agree with the solver, but they all share the same fault model, so they check the code, not the physics. The tests pass (189 main tests, 324 product tests, on a copy, 2026-11-20 (re-measured by RECON6 on the unpacked bundle); run `make test` and quote your own count). Mutation score of those tests (REPORTED, not re-run): root 72.5% (50 of 69 runs), product 67.6% (50 of 74). One unlimited-time proof exists for one case; no one has independently replicated it.

## What triplication bought
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

## What changed in the last wave (C4)
- The check "does a predictor tell you the answer without the solver" was run: on fresh netlists it was exact 92% of the time (always predicting 1 gives 62%, the free lower bound 83%; 58% when 2 or more flips are needed) and not faster; so it is a rough pre-check, the solver stays the judge.
- Rail dips (model, bounded, SIMULATED): Under B3's 1-to-0-only rail model V1, V2 and V5 survive within the bound (no attack up to 3 events, T=6; V0 does not under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication (LEDGER 0-to-1 control, `research/c5/ledger/`; whole-design `rise_all` stays >3 for the word goal). SPICE supports 1-to-0 for supply dips; EM literature reportedly describes set-to-1 (UNVERIFIED, search-snippet level, not checked here); the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug) (`research/c5/anchor/RAIL_RECONCILIATION.md`). If one dip could pick its gates it takes 1 event on V2 (3 gates; V1 2: V1 and V2 tie in every rail-event ledger row and differ only in the stem-flip and fanout-count rows (table 'What triplication bought', `docs/report/PROJECT_REPORT.md`); triplication buys one extra gate under a selective event (2 vs 3 gates)). The layout puts the three sufficient cells within 2.95 um of each other on one supply net. 2.95 um holds under the selective force-to-0 (supply-dip) model. Under the bit-flip model a sufficient triple {c0/_2_, c1/_4_, c2/_4_} lies within 1.665 um; placed V2 has 22 flip triples, all in cycle 1; one shot opens V2 from 1.75 um (centre rule) or 0.25 um (overlap rule, ASSUMED); with set0 and no selection no single shot works. Whether a real dip can choose is the open question.
- The mask rule: The consumer-mask rule is the minimum of Hamming distance to idle states and the number of comparator copies touched: known-style cut/Hamming reasoning, not a discovery; exact on spike V2 (255/255), 187/255 on apt (DA3).
- Product safety: RT2 (`research/c5/rt2/RT2_REPORT.md`, MEASURED) found a HIGH command-execution bug (the top name or Verilog path was pasted into a Yosys command). H2 and H3 fixed it in the product, `scripts/synth.sh` and `glitchsat.py check`; the integration step re-tested it with a canary file on 2026-11-19 22:42 UTC (rejected, exit 3, no file created; MEASURED). The GitHub Action's two shell steps were run locally in a clean venv (MEASURED at integration, 2026-11-20; the `uses:` steps and the SARIF upload cannot run off GitHub, so nothing ran on GitHub), and the Dockerfile was built and run locally only after adding the sandbox proxy's CA to a COPY of it (shipped Dockerfile unchanged; not built on a normal network). Third-party tools (RUN2): uArchiFI run on 9 of 9 cells, same minimum flips as ours (one tool, three toy designs; not a validation; counting unit matters); k-FRP built but answers a different question; FIVER not built or run (RUN2, measured). Yosys itself is not sandboxed. Until a human has reviewed the fix, still do not run the Verilog path or the Action on untrusted input. Other findings: `docs/dossier/CRITIQUE.md` (RT2-N1 to RT2-N14).
- Other designs: only V5 beats V2, and only on one setting; V6 was worse. The command-line tool now offers consumer bits, input sites, power-up modes and scope sweeps; a classroom kit and a dashboard Scope tab exist.
- Consumer-mask numbers: rechecked by M1b with two engines: no cell changed (0 of 1785; research/c4/m1b/M1B_REPORT.md).

## What is NOT proven
- Nothing about real chips, real glitches or any real product. A "flip" is a modelling choice. There is no hardware.
- Nothing is new: SYNFI and FIRMER already do this kind of analysis; one closer paper (k-FRP) was never read.
- The predictor is not validated and not faster (92% exact, against 62% for always-1 and 83% for the lower bound alone; 58% on multi-flip cells; 4/6 on fresh RTLs); the 928/928 figure is near-duplicate cells.
- Not shown: that a real supply dip can choose which gates fall (B3, LAYOUT), or any layout-based security claim (no IR-drop or extraction).
- Not shown: that V2 or V3 is secure; that the counting rule we use is the physically right one (it is the field's convention); the exact tool change behind 85 vs 83 gates (unknown). Corrected 2026-11-20: the 2-vs-3 flips is not a version effect but the encoding (`docs/report/WHY_TWO_FLIPS.md`).
- The circuit-level (SPICE) simulation is of one gate and flops, not silicon. It says a supply dip hits many wires at once and only pulls them low, and a dip alone never flipped a stored bit; so "one clean flip" is a simplification. Do not quote voltages or timings.

## The sentence to defend
"A claim like 'three copies resist two faults' means nothing unless it says what counts as a fault, which output is attacked, how the chip starts and which circuit file was tested. I built a small tool that reruns the question under each choice and shows which one decides the answer. V2 is the example, not a recommendation. Everything is a bounded simulation of a toy; nothing is claimed as new."

## The 3 decisions only you can make
1. **What is the claim: the method or a verdict?** Recommended: the method (scope-and-model sensitivity), V2 as the exhibit. The verdict version ("V2 resists 2 flips") is what every reviewer broke.
2. **Which counting rule goes on the front page, and what do you say about it?** Recommended default: headline "one flipped gate output = one fault" (the convention of the published tools), show the other rules beside it, and never say any is "physically right".

## How to present it in 5 minutes
1. (30 s) The question: copies of a check; do they help? Show the three-guards-one-wire picture (`docs/explainers/explainer.html`, hero button).
2. (60 s) V0 and V1 fall to 1 flip. Say why: one shared wire.
3. (90 s) V2 needs 3, but change one choice and it drops to 1: show the scope table (B2) and the 4-bit-reader row (M1). This is the main result.
4. (45 s) The same design needed 1, 2 or 3 flips depending on the build and the counting rule. Say you do not know the exact cause of the Yosys difference.
5. (30 s) How it was checked (other tools, same model; 150 tests; re-run on a copy) and what is not claimed (hardware, novelty, security).
Do not run `make` in the live tree; use screenshots or a copy. Read `research/c2/el1_spice/EL1_REPORT.md` before showing the SPICE plots.

## Before you present
Re-run `make test` and `make check-reproduce` yourself on a copy (`/tmp/<yourname>`; `make reproduce` overwrites `results/`). Re-derive `docs/dossier/worked_example.py` by hand. Read the 8 hardest questions in `QA_SHEET.md` s3 aloud.
