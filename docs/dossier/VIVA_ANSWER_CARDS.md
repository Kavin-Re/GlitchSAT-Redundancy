# VIVA ANSWER CARDS (40 cards)
GlitchSAT. License: Apache-2.0. Study aid, not the owner's words: say only what you can explain; for anything you cannot, say "I do not know; here is what the file says". Full spoken answers, source tags and follow-ups: `research/c4/viva/VIVA_SIM_REPORT.md` (card id E1-1 etc. matches). All numbers are for modelled single-cycle flips in toy netlists, T=6, k<=3 unless stated; nothing physical, nothing new. Eight questions in the full report (E1-10, E1-11, E2-4, E2-9, E3-11, E3-12, E4-10, E4-11) have no card; read them there. Cards marked IDK: the honest reply is "I do not know / we did not test that". Cards marked OWNER cannot be answered by an agent.

## E1: ECE professor (derivations)
**E1-1. Why does V1 (two copies) fall to one flip?**
- Both compares m1, m2 feed one AND, `ok`; `ok` alone drives all 8 result bits.
- Flip `ok` for one cycle when the state is "compare": next state is the accept word 0x96.
- Fix direction: give each copy disjoint output bits (that is V2).
Number: **1** flip. File: `docs/OWNER_DERIVATION_SHEET.md` s1 (run `glitchsat check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6`). Trap: saying "two copies are redundant so it is safe".

**E1-2. Derive the 3 for V2, full word.**
- Wrong input gives word 0x69, the complement of 0x96: all 8 bits wrong.
- Copies own bit groups {0,3,6}, {1,4,7}, {2,5}; one flip of a copy's compare fixes its whole group; three copies = 3.
- Direct route (state flops): 0xF0 vs 0x96 and 0xCC vs 0x96 differ in 4 bits, so 4; minimum is 3.
Number: **3** (full word, stored netlist), apt-0.33 build **2**. File: `OWNER_DERIVATION_SHEET.md` s2. Trap: quoting 3 without "full word, inputs not attackable, known power-up".

**E1-3. Mask 0x0F and 0x4E: how many flips?**
- Rule: min of (direct bits differing from 0x96 in idle/compare states) and (flip a set of copies: one per copy plus one per masked bit no chosen copy owns).
- 0x0F: owners m0,m1,m2,m0; direct 2 -> answer 2. 0x4E: direct 3, copies 3 -> answer 3.
- Rule matches the solver on all 255 masks of the stored netlist only; fails (68 mismatches) on the apt-0.33 re-synthesis.
Number: **2 and 3** (0x03 gives 1, 0xFF gives 3). File: `research/c3/m1/m1_all_masks.csv` col 11. Trap: calling the rule a theorem. The consumer-mask rule is the minimum of Hamming distance to idle states and the number of comparator copies touched: known-style cut/Hamming reasoning, not a discovery; exact on spike V2 (255/255), 187/255 on apt (DA3).

**E1-4. Explain the SAT encoding.**
- Each gate: out = f(inputs) XOR flip; copy the circuit once per cycle (bounded model checking), link flops to next cycle.
- Goal clause: result word = 0x96 in some cycle while input != key; "at most K flips" is a cardinality constraint; z3 gives witness or UNSAT.
- Minimum: tighten K until UNSAT.
Number: **0, 1** (3-gate example: k=0 UNSAT, k=1 SAT on g3). File: `docs/dossier/worked_example.py`. Trap: OWNER must be able to read `build` in `scripts/glitchsat.py` line by line.

**E1-5. What does UNSAT at k=2 prove?**
- On THIS netlist file, THIS fault rule, goal and input rule: no set of <=2 flips in 6 cycles reaches the goal.
- Nothing about cycle 7, 3 flips, another netlist or another goal.
- So I never write "secure" for it.
Number: **k<=2, T=6**. File: `docs/dossier/VIVA_SHEET.md` FP12. Trap: "proved secure".

**E1-6. Hamming distance of the state code?**
- {F0, CC, 96, 69} has minimum distance 4; with only state-flop faults the minimum is 4.
- With all sites V2 costs 3 and V1 costs 1: the weak point is the decoder, not the code.
- 96 and 69 are complements; a flip-all event breaks every design; a non-complementary code was NOT tested (IDK).
Number: **4**. File: `docs/dossier/test_hamming.py` (args: copy dir, netlist, top). Trap: "the code makes V1 safe".

**E1-7. Stem versus fanout counting, 3-gate example.**
- g0 -> n -> {g1,g2,g3}: stem rule = 1 fault; per-fanout rule = 3.
- Over 32 V2 re-syntheses: stem min is 2 on 26 and 3 on 6; fanout min is 3 on all 32.
- Headline is stem (field convention); neither rule shown physical.
Number: **6 of 32 vs 32 of 32**. File: `research/c3/rep/rep_results.csv`. Trap: using 32/32 as the headline.

**E1-8. Why does merging identical compare cones give 1 flip?**
- The three compares are the same function of the same input; `opt_merge` keeps one and rewires.
- Then one net drives all 8 bits: V1 again.
- RTL unchanged; only the netlist differs, so a verdict belongs to one netlist hash.
Number: **180 / 60 / 24** (V2 min 1 / 2 / 3 over 264 configs; 94 / 38 / 20 over 152 distinct netlists). File: `research/c2/e2_variance/raw/matrix.csv`. Trap: "V2 is triplicated therefore 3".

**E1-9. SPICE: why do dips pull outputs low only; what did not happen?**
- My reading (inference): high outputs are held by pull-ups from the sagging rail; low outputs by pull-downs to ground, which the simulation did not dip.
- Data: 0 of 60 dip points flipped a flop Q (even 0 V for 3 ns); a clock runt >=1.3 V (tt) makes a flop capture D.
- ngspice on sky130 cells: simulation, not silicon; longest dip 3 ns.
Number: **0 of 60**. File: `research/c2/el1_spice/EL1_REPORT.md`. Trap: quoting volts or ps as attack parameters; "validated the glitch model".

**E1-12. Reproduce any number in front of me.**
- Pick the V1 one-flip result: it runs in under a second.
- Or V2: `--k 2` gives NO_ATTACK, `--k 3` gives min 3 in c0, c1, c2 (about 5 s).
- OWNER: name the derivation you have actually practised.
Number: **3** nodes, cycle 1. File: `docs/OWNER_DERIVATION_SHEET.md` (blanks). Trap: OWNER, the sheet is still blank.

## E2: VLSI engineer (layout and flow)
**E2-1. Is it a real chip layout?**
- No: a flow demonstration with open sky130 + OpenROAD on a 35-cell block.
- Never fabricated, no signoff.
- Purpose: show the V2 comparators remain separate cells.
Number: **35 / 36 cells** (V1/V2). File: `layout/v_designs/out_patched/RESULT.md`. Trap: "real layout", "tape-out ready".

**E2-2. DRC clean?**
- Router: 0 violations; magic top cell lists none after the patched rerun.
- Magic still reports rules inside library cell definitions (dfxtp_1: nwell.4, LU.2, LU.3).
- Reading: context false positives (tap + dfxtp_1 + tap flattened = empty list; one-cell test); not fixed; no foundry deck.
Number: **0** router violations. File: `layout/verify/VERIFY.md` s2. Trap: "DRC clean" or "verified".

**E2-3. LVS?**
- netgen: "Circuits match uniquely" for V1 and V2 after patches (422 vs 422 devices, 225 vs 225 nets for V1).
- Reference built from the same netlist plus PDK subcircuits; before the patches it failed; a separate door-lock design failed top-level LVS pin matching.
- So: layout matches the netlist, not the design intent.
Number: **422 vs 422**. File: `RESULT.md` table. Trap: "LVS passes, therefore correct".

**E2-5. Area/cells V0, V1, V2; why only +1 cell for V2?**
- V0 10 cells 89 um2; V1 35 / 358; V2 36 / 363 (yosys mapped).
- Reading of placed netlists (DA2): the three comparator cones are 3 cells each with 0 overlap, so copies are not merged.
- Why exactly +1: not decomposed (partial IDK).
Number: **36 vs 35**. File: `docs/dossier/PROJECT_DOSSIER.md` s7.9. Trap: "+1 cell means copies merged" or "means free redundancy".

**E2-6. Synthesis flow; did it merge your copies?**
- Yosys with keep_hierarchy compare modules, flatten, ABC gate list, techmap, JSON; no opt_merge after flatten in the stored flow.
- With opt_merge V2 costs 1.
- E2 matrix over builds: 180 / 60 / 24 (of 264 solved configs; 152 distinct netlists: 94/38/20 (DA3).
Number: **180/60/24 of 264 solved configs; 94/38/20 over 152 distinct netlists**. File: `scripts/synth.sh`, `research/c2/e2_variance/E2_REPORT.md`. Trap: "synthesis is a neutral step".

**E2-7. 85 gates (apt 0.33) vs 83 (conda 0.38)?** PARTLY KNOWN (corrected 2026-11-20)
- I do not know the exact tool change behind the gate counts.
- But the 2-vs-3 flips is not a version effect: the stored netlist is also Yosys 0.33; the cause is the encoding (see card ENC-1).
- Known: synthesis deterministic; compare cones disjoint in both; difference in next-state mapping (one MUX on conda).
Number: **85 vs 83; 2 vs 3 flips**. File: `docs/dossier/VIVA_SHEET.md` D-bonus. Trap: "caused by the Yosys version".

**E2-8. Mapped sky130 netlist V2 = 3, generic = 2?**
- Report: the 2-flip attack uses internal gates that are not separate sites after mapping.
- Project's own adapter; no second solver.
- I did not trace gates (IDK on detail).
Number: **3 vs 2**. File: `research/c2/el2_engineering/EL2_REPORT.md` (via dossier s7.9). Trap: "mapped netlist is verified secure".

**E2-10. Reset and power-up?**
- Layout has no reset; results assume a known power-up state.
- Arbitrary non-accepting power-up: V2 costs 1; arbitrary and no reset: every design costs 0.
- A design gap I name.
Number: **1 (arbitrary state), 0 (no reset)**. File: `research/c2/b2_scope/B2_REPORT.md`. Trap: "V2 survives any start state".

**E2-11. Did layout change the result?**
- Only as a modelling choice: copies 2-4 um apart, glitch radius 3.5 um reduces V2 to 1.
- No extracted power grid; not physics.
- So layout locality is a hypothesis, not a result.
Number: **3.5 um (assumed)**. File: dossier s7.9 / EL2 report. Trap: presenting the radius as measured.

**E2-12. Can I rebuild layout and SPICE from the repo?**
- Not fully: conda environments for layout, PDR, sby, SPICE are not rebuilt by the bundle.
- Solver, tests and V0-V2 sweeps work from apt yosys 0.33, iverilog, pip z3.
- Tool versions: OpenROAD f12e2f47, magic 8.3.464, netgen 1.5.272, klayout 0.30.13.
Number: **36/36** reproduce rows (apt flow only). File: `handoff/CONTINUATION/ENV_REBUILD.md`. Trap: "everything reproduces".

## E3: hardware security researcher (claim, novelty, fault model)
**E3-1. State the claim in one sentence.**
- "Three copies resist two faults" means nothing without: what is a fault, which output, how the chip starts, which netlist.
- I built a tool that reruns the question under each choice and shows which one decides.
- V2 is the example, not a recommendation; bounded toy simulation; nothing new.
Number: **1 / 2 / 3** (V2 range). File: `docs/dossier/ONE_PAGE_FOR_THE_OWNER.md`. Trap: leading with "V2 is secure/resists".

**E3-2. What is new? Does it break OpenTitan?**
- Nothing established as new: SYNFI, FIRMER already do formal netlist fault analysis; k-FRP is the closest and is unread.
- No analysis of OpenTitan or any product.
- Value: reproducible sensitivity analysis and teaching material.
Number: **0 novelty claims**. File: `docs/PRIOR_ART.md`. Trap: "first", "novel", "breaks"; OWNER open the 3 key papers.

**E3-3. Justify your fault model.**
- Chosen, not derived: a one-cycle XOR on a gate or flop output (formal-tool convention).
- Not covered: stuck-at, multi-bit/spatial, laser, EM, analog effects.
- EL1 suggests real events are correlated, directional, wrong-time captures.
Number: **1 cycle, 1 net per fault**. File: `docs/dossier/PROJECT_DOSSIER.md` s13. Trap: "a flip is what a glitch does".

**E3-4. Are independent single flips physical (EL1)?**
- Dips hit all high-output gates on a rail together, toward 0 only; no flop Q flip from a dip alone; clock runt = capture of D.
- So independent flips are the less supported model for dips.
- But: one tiny rail, one cell type, coarse grids, no extracted grid.
Number: **0 of 60**. File: `EL1_REPORT.md`. Trap: "SPICE validates (or refutes) the verdicts".

**E3-5. Does V2 survive rail-dip models (B3)?**
- Within T=6, <=3 events: no attack on V2, V5, V1 under whole-rail, hierarchy-half, fanout-cone dips; V0 falls to 1 under a cone dip.
- If one dip may choose which gates fall (dip_subset): V2 and V5 fall to 1 event with 3 gates, one per compare copy.
- Whether a real dip can be that selective, or rise instead of dip: not established either way (IDK). Under B3's 1-to-0-only rail model V1, V2 and V5 survive within the bound (V0 does not under a cone event), but a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too): survival depends on polarity, not on triplication; SPICE supports 1-to-0 for supply dips, EM literature reportedly describes set-to-1 (UNVERIFIED, snippet level); the domain is the netlist hierarchy, not a physical rail; physical track closed (no extraction, selectivity unproven; L2 spread layouts failed LVS 4/4 by a known filler flow bug).
Number: **>3 (1-to-0 rail) vs 1 (0-to-1 rail on the three copies; dip_subset, 3 gates)**. File: `research/c4/b3/B3_REPORT.md`, `research/c5/ledger/LEDGER_REPORT.md`. Trap: "V2 survives voltage glitches".

**E3-6. Which counting rule is correct; is 32/32 a rescue?**
- I headline stem=1 (field convention; one driver-node upset); 6 of 32 V2 builds hold against 2 flips.
- Fanout counting gives 32/32 but no source found supports it as physical: stress test only.
- I do not say any rule is physically right; partial-branch rule untested.
Number: **6/32 vs 32/32**. File: `research/c3/rep/REP_REPORT.md`, `research/c3/r22/R22_REPORT.md`. Trap: "stem is physically right".

**E3-7. V2=3 collapses to 1 under one change: what did you show?**
- That is the result: 3 holds in one cell (full word, inputs not attackable, known power-up, stored netlist).
- Goal `boot_ok`, input nets as sites, or arbitrary non-accepting start: 1 flip.
- So "resists two faults" is meaningless without qualifiers; I do not claim V2 is secure.
Number: **360 cells** in B2. File: `research/c2/b2_scope/B2_REPORT.md`. Trap: defending 3 as a general property.

**E3-8. The unbounded proof?**
- One tool-reported ABC-PDR PASS: one V2 netlist, word goal, k<=2; no certificate; no second engine.
- Controls: V1 at k=1 fails, so not vacuous; k-FRP unread.
- Not in the headline; I do not rely on it.
Number: **k<=2, 1 netlist**. File: `docs/dossier/VIVA_SHEET.md` D7. Trap: "formally proved secure for any T".

**E3-9. All cross-checks share your fault model; what is verified?**
- They check the encoding and the code, not the model: own simulator ~2.1M sets 0 disagreements; boolector; 13/13 replays; SymbiYosys 40 pairs; 2040 random runs vs brute force; REP 64/64.
- Would show me wrong: an independent simulator disagreeing with a stored witness (has not happened).
- uArchiFI (one third-party tool) gave the same minimum flips on 9 cells of three toy designs through an agent-written adapter: not a validation (RUN2). Untested: physical argument that voids the number; a second solver on the mapped netlist.
Number: **0 disagreements**. File: `validation/VALIDATION.md`. Trap: "independently validated".

**E3-10. Is the structural predictor validated? (No: 150 of 163 fresh cells exact, 92%; the 928/928 pooled figure is near-duplicate cells)**
- No. Lower bound sound (0 violations in 928+163+60 cells) and never called a 1-flip design safe.
- 76 fresh netlists: 92% exact overall (baselines: always 1 gives 62%, the sound lower bound alone 83%, DA3), but 58% (18 of 31) on cells needing >=2 flips; 7 under-predictions (fallback lb+1); runtime not faster; LEDGER: 71/71 on the E2 family sample, 4/6 on fresh RTLs (wrong on voter designs V2m, V5).
- A heuristic attack search plus lower bound; the SAT solver is the reference; not in the tool.
Number: **92% overall (always-1 62%, lower bound alone 83%) / 58% on 2+ flips**. File: `research/c4/ver/VER_REPORT.md`. Trap: saying "928/928" (near-duplicate cells).

## E4: industry hiring manager (so what, who, what did YOU do)
**E4-1. 30-second explanation for a non-expert.**
- Chips check a secret at boot; engineers copy the check so one disturbance cannot fool it.
- My program finds the fewest one-wire disturbances that fool a circuit: three copies needed 3, but one changed assumption gives 1.
- So a safety claim must state its assumptions; toy simulation, not a product.
Number: **3 -> 1**. File: `ONE_PAGE_FOR_THE_OWNER.md`. Trap: jargon; "it makes chips secure".

**E4-2. Who would use it?**
- Nobody yet: alpha command-line tool plus teaching material.
- A designer would run it on a post-synthesis netlist and read the answer as a lower bound under a stated model.
- Scope options (consumer bits, input sites, power-up modes, sweeps) are in `product/` since PS4/PS5; the branch counting rule and per-cycle input are not shipped (TODO).
Number: **324 passed** product tests (RECON, 2026-11-20 (RECON5); re-run it). File: `README.md` "Shipped tool vs research". Trap: "adoptable".

**E4-5. Whiteboard: the idea you understand best.**
- Draw m1, m2 -> AND `ok` -> 8 result bits; flip `ok`; accept.
- Then V2: three copies, each with its own bit group.
- OWNER: use only a derivation you have practised.
Number: **1 then 3**. File: `OWNER_DERIVATION_SHEET.md` s1-2. Trap: drawing without being able to say why 0x69 is the complement.

**E4-6. What went wrong; what would you not repeat?**
- Several claims died: supermarket monitor, a known headline, "V2 resists 2 flips"; the predictor looked 928/928 but is a heuristic.
- Lesson: every number carries its scope and a label.
- OWNER: add what you learned.

**E4-7. How reproducible, how long?**
- On a copy: headline commands seconds; `make reproduce` about 25 s; `make check-reproduce` vs 36 expected rows.
- Tied to apt Yosys 0.33; other builds may differ.
- Use a copy: make rewrites `results/`.
Number: **36 rows, ~25 s**. File: `START.md`. Trap: running make in the live tree.

**E4-8. How good is the testing?**
- Root tests all pass; docs say 30, my copy ran 98 this session (tests were added later) - re-run and quote your own.
- Mutation testing: about two thirds to three quarters of one-line breakages caught (root 72.5%, 50 of 69; product 67.6%, 50 of 74; reported, 10 product runs never run).
- Do not say "well tested"; all checks share the fault model.
Number: **189 passed, 2 skipped** (re-run it) / **72.5% root, 67.6% product** mutation score. File: `research/c3/t2/T2_REPORT.md`, `research/c4/t3/T3_REPORT.md`. Trap: repeating an old test count (the docs once said 30) without checking.

**E4-9. Does it scale?**
- Teaching scale: 2040-gate DMR S-box at 4 cycles, 2 flips, 46 s; 3 flips no result in 250 s.
- Only AND/OR/XOR/NOT/MUX/DFF; one goal port and one input; async reset refused.
- No boot ROM tried (IDK beyond that).
Number: **2040 gates, 46 s**. File: `research/c3/r20/R20_REPORT.md`. Trap: "scales to real chips".

**E4-12. Licence, third-party code, ethics?**
- Licence: Apache-2.0 (decided 2026-11-20). `third_party_derived/` holds adapted third-party code (CLEAVE no licence file; uArchiFI LGPL-2.1): keep out of any bundle (the Apache-2.0 licence covers only this project's own files).
- Responsible-use text drafted; nothing sent externally.

## Coding view and encoding root cause (added by agent INT, 2026-11-20; cards C-1 to C-8 from `research/c6/p13/P13_REPORT.md`)

**C-1. Is there any communications content in this project?**
- The state words are codewords of RM(1,3) [8,4,4], and the copied comparators are repetition codes.
- The measured flops-only cost equals the code distance; the all-nets cost is set by the decoder.
- It is textbook coding theory measured on toy designs, nothing new.
Number: **d=4, flops-only 4 on 4 of 4 netlists** (MEASURED). File: `docs/comms/CODING_VIEW.md`, `research/c6/p13/hamming_runs.txt`.

**C-2. Prove F0, CC, 96, 69 are RM(1,3) codewords.**
- Bit i = f(binary(i)); x2 = F0, x1 = CC.
- 69 = 0F+33+55 = 1+x0+x1+x2 and 96 is its complement x0+x1+x2.
- Also true if the byte is read MSB-first (bit reversal is an affine change of variables).
Number: **16 codewords, all 5 RTL words members** (FACT). File: `docs/comms/test_rm13.py`.

**C-3. What is the minimum distance and what does it guarantee?**
- Weight enumerator 1 + 14z^4 + z^8, so d=4.
- Detects any 3 bit errors, would correct 1 if a decoder corrected (none does).
- Guarantee holds for errors on the stored bits only.
Number: **d=4, detect 3, correct 1** (FACT). File: `research/c6/p13/test_output.txt`.

**C-4. If d=4, why does V1 fall to 1 flip?**
- The two copies are a [2,1,2] repetition code merged by `ok = m1 & m2` into one net.
- That net is a point where all codewords decode alike; flipping it at cycle 1 writes 96.
- A code protects the codeword, not the circuit that decodes it.
Number: **1 (`ok`@1), flops-only 4** (MEASURED). File: `research/c6/p13/cli_runs.txt`, `hamming_runs.txt`.

**C-5. Why is V2 3 on the stored netlist but 2 after re-synthesis?**
- Three copies with disjoint bit groups: a [3,1,3] repetition code used for detection, so 3 = its distance.
- CC xor 96 touches only two of three groups, so a netlist with one shared next-state net per group falls to 2 (card ENC-1).
- Re-encoded `rtl/v2e.v` gives 3 on 6 of 8 flows.
Number: **3 spike, 2 apt-0.33** (MEASURED; anchor brute force 182 triples / 3 pairs). File: `research/c5/anchor/ANCHOR_REPORT.md`, `docs/report/WHY_TWO_FLIPS.md`.

**C-6. What happens if the consumer reads only some bits?**
- It reads a punctured code: the distance on those bits only.
- For masks 0x03, 0x0F, 0x4E the masked distance from F0/CC to 96 is 1, 2, 3 and the CLI measures 1, 2, 3 with flop flips only.
- On all 255 masks the solver never exceeds the masked distance.
Number: **1/2/3; 255/255** (MEASURED). File: `research/c6/p13/cli_masks.txt`, `research/c3/m1/m1_all_masks.csv`.

**C-7. Is the complementary pair 96/69 a good choice?**
- Against independent flips yes: distance 8, the maximum.
- Against one event that inverts all 8 flops no: 69 xor FF = 96, and FAIL holds, so a later burst turns reject into accept.
- Interleaving or separating copies is the classic answer; not measured here.
Number: **distance 8; burst = 1 event** (ARITHMETIC; circuit run pending P14). File: `docs/comms/CODING_VIEW.md`.

**C-8. What may you not claim from the coding view?**
- No novelty; no claim that RM(1,3) was chosen on purpose.
- Modelled flips, T=6, four netlists: "matched in 4 of 4", not "always".
- No bit-error rates or physical glitch claims.
Number: **4 of 4** (MEASURED). File: `docs/comms/CODING_VIEW.md` "Limits".

**ENC-1. Why does V2 need 2 flips and not 3 on the apt 0.33 netlist?**
- The machine loads the armed word 0xCC at cycle 0; 0xCC xor 0x96 = 0x5A, bits {1,3,4,6}, owned by copies m1 and m0 only.
- On this netlist one net moves bits {1,4} and another moves {3,6}: two flips turn the load of CC into 96.
- Encoding sets the floor (2 copies touched => 2); the synthesis flow decides whether the floor is reached.
Number: **2 1 1 2 2 2 2 2 over 8 flows** (MEASURED, P01a; re-verified by the lead 2026-11-20). File: `docs/report/WHY_TWO_FLIPS.md`, `research/c6/p01/P01_REPORT.md`. Trap: "it is a Yosys version effect" (the stored netlist is also Yosys 0.33; that wording was an error, now corrected).

**ENC-2. Does re-encoding fix it?**
- Changing only the armed constant to 0xA5 (xor 96 = bits 0,1,4,5, all three copies) gives 3 on 6 of 8 flows.
- The two flows that merge the comparators (opt_merge, flatten before ABC) stay at 1: no encoding fixes merged copies.
- Conda 0.38 with 0xCC: 3 only on the plain flow; three other flows give 2.
Number: **v2e 3 1 1 3 3 3 3 3** (MEASURED, apt and conda). File: `rtl/v2e.v`, `research/c6/p01/sweeps/`. Trap: "v2e is secure" (bounded: T=6, k<=3, toy, modelled flips).
