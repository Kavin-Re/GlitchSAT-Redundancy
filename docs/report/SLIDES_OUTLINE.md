# Slides outline (24 slides: 14 main + 10 appendix; slides 13 and 14 added by agent INT; slides 5, 6, 7, 10, 11 added and old slides 5 to 9 moved to appendix A6 to A10 by agent INT2a, 2026-11-20)
GlitchSAT. License: Apache-2.0. Generated from `docs/report/SLIDES.pptx` (built by `research/c4/pres/build_deck.py`); the speaker notes are the exact words to say. Every number is from `docs/NUMBERS.md` (2.95 um, 15 um and the L2 spread-layout facts are from `research/c4/layout/LAYOUT_REPORT.md` and `research/c4/l2/L2_REPORT.md`, not yet rows in NUMBERS.md). Faults are modelled bit flips on toy designs; nothing physical; nothing established as new.

## 1. GlitchSAT: How Many Glitches Does Redundancy Stop?   (about 41 words)
- Bounded SAT-Based Fault Analysis of Redundant Boot Checks.
- Given a netlist and the bits a consumer checks: how many modelled flips defeat a redundant boot decision, and which nets do the copies share?
- Three guards on one wire are really one guard.
- Speaker notes (say this):
  > SAY: Here is the whole project in one sentence. A boot check is often protected with redundant copies. I give a tool a gate-level netlist and the bits that the consumer actually reads. It tells me how many modelled single-cycle bit flips defeat the decision, which wires the supposed copies share, and how that answer changes when I change the synthesis build, the counting rule or the scope. And the sentence I want you to remember: three guards on one wire are really one guard. Everything today is a model of a toy circuit. Nothing physical, nothing claimed as new.

## 2. Three guards, one wire   (about 15 words)
- guard A
- guard B
- guard C
- one wire
- door
- guard A
- guard B
- guard C
- wire 1
- wire 2
- wire 3
- door
- flip opens the door
- flips needed
- Copies that all end in one wire act as one guard.
- ILLUSTRATIVE drawing (toy), not a measurement
- Speaker notes (say this):
  > SAY: Picture a door with three guards. Each guard checks the code. If the code is wrong, each says no. Now look at the left: all three answers travel down one shared wire to the door. If that one wire says yes for a single moment, the door opens, and the three guards were beaten by one flip. On the right, each guard has its own wire. Now the attacker needs to flip three wires. That is the whole idea.
  > SAY, honest part: the drawing is an illustration, not a measurement. The measured version is our toy design V1: two copies of the check that both end in one wire called ok. The solver finds that one flip of ok at cycle 1 opens it. And even in the three-wire design, the accept flag itself can fall to one flip, which I show two slides from now.

## 3. Our solver finds the minimum flips   (about 31 words)
- V0
- plain check
- V1
- two copies, one wire
- V2
- three copies, own bits
- Minimum flips found by z3. 6 cycles, at most 3 flips. MEASURED.
- Speaker notes (say this):
  > SAY: To turn the picture into a number I use a solver. Yosys turns the design into gates. The solver z3 chooses which wires to flip, and in which clock tick, and also the attacker's input. I keep lowering the flip limit until no attack exists. The last limit that still had an attack is the minimum.
  > SAY: Results on three toy designs, six clock ticks, at most three flips. The plain check V0 falls to one flip. V1, two copies that end in one wire, falls to one flip. V2, three copies each owning its own result bits, needs three flips. But careful: that three holds only in a narrow setting, and the next slide shows exactly which. Measured, by the command in my demo.

## 4. The answer depends on what is counted and checked   (about 37 words)
- Full word, stored netlist
- Other synthesis build
- Accept flag only
- Consumer reads 4 bits
- 1 to 3
- Input wires attackable
- Synthesis merges copies
- V2 minimum flips. Full word needs known power-up, inputs not attackable. Other build = apt Yosys 0.33. MEASURED: 6 cycles, at most 3 flips.
- Speaker notes (say this):
  > SAY: This is the main result. The same V2 design gives different minimum flips depending on what I count and what the consumer checks. If the consumer reads the full 8-bit word on the stored netlist, three. If the same source is re-synthesised with the apt Yosys 0.33, two. If the consumer reads only the single accept flag boot_ok, one. If the consumer reads four bits, between one and three; of 68 four-bit masks, 28 need one flip, 36 need two, 4 need three. If I let the input wires be fault sites, one. If synthesis merges the three identical copies into one, it is V1 again: one.
  > SAY: So 'V2 resists two flips' is only true in one narrow cell: full word, inputs not attackable, known power-up state, stored netlist. I never say it without those qualifiers. Measured by the 360-cell scope matrix and the 255-mask table; all bounded at six cycles and three flips.

## 5. One lock, four questions: 3, 2, 1, 0   (added by INT2a, 2026-11-20)
- Picture: `research/c6/p40/shots/1366_light_big.png` (screenshot of `docs/wow/dial.html`).
- Stored netlist, whole word: 3
- Re-built (plain recipe, same Yosys 0.33): 2
- Reader = accept flag: 1
- Any power-up state: 0
- Predict first: the room guesses before the digit shows.
- MEASURED: each digit copies one row (matrix.jsonl lines 241, 265, 277, 281). Screenshot: V2e build, also 3. 94 of 432 combinations measured; the rest say "not measured". docs/wow/dial.html; check_dial.py --browser 467 passed.
- Speaker notes (say this):
  > SAY: This is the Verdict Dial. The digit is the fewest modelled flips the solver needed to open the toy lock with a wrong key. Before each reveal I ask you to guess.
  > SAY: The stored netlist with the whole word read needs 3. I rebuild the same text with the plain recipe of the same Yosys version: 2. I let the next block read only the one-wire accept flag: 1. I let the lock wake up in any state: 0, because the toy has no reset.
  > SAY: Every digit is a copy of one measured row, and the source row is printed under it. Where nobody ran a combination, the dial says not measured. Toy design, modelled flips, 6 ticks, at most 3 flips, nothing physical.

## 6. See it happen: one flipped wire opens V1   (added by INT2a, 2026-11-20)
- Picture: `research/c6/int2a/img/theatre_step2_crop.png` (crop of `research/c6/p21/shots/step2_1366.png`, `docs/wow/theatre.html` step 2).
- V1: 1 flip, wire ok at tick 1, wrong key 0xC7; replayed: opens at tick 2.
- V2: no 1- or 2-flip attack within 6 ticks (456 sites); 3 flips, one wire per copy, opens.
- Caveat: reader = accept flag: 1 flip again.
- MEASURED (solver on the stored netlists) + SIMULATED (gate-level replay, iverilog). Schematics hand-drawn. docs/wow/theatre.html; check_theatre.py --browser 149 passed.
- Speaker notes (say this):
  > SAY: This is not an animation I drew. The solver names which wire to flip and when; a gate-level simulator replays that answer, and the strips are the recorded signals.
  > SAY: Left, the two-copy lock: both checks say no, but they meet on one wire, ok. One flip at tick 1 and the boot word reads open one tick later. On the three-copy lock the solver found no attack with one or two flips within 6 ticks; with three, one wire per copy, it opens.
  > SAY: One caveat I always show: if the next stage reads only the accept flag, it is one flip again. The small schematics are hand-drawn; the waveforms are from the simulation. Nothing touched hardware.

## 7. 264 builds of one design: 1, 2 or 3 flips   (added by INT2a, 2026-11-20)
- Picture: `research/c6/p24/shots/wall_1366_stage3_verdicts.png` (`docs/wow/wall.html`, step 3).
- 152 distinct netlists: 94 need 1 flip, 38 need 2, 20 need 3.
- Per setting (264 solved): 180 / 60 / 24.
- 120 of the 180 one-flip settings use opt_merge.
- Previously shown by SYNFI; E2 replicates it on a toy design.
- MEASURED: row counts of research/c2/e2_variance/raw/matrix.csv; one design, 6 cycles, at most 3 flips; settings not independent. docs/wow/wall.html; check_wall.py 42 passed.
- Speaker notes (say this):
  > SAY: I gave the same design file to 264 synthesis settings. They built 152 different netlists. Each tile is one netlist, and its colour, shape and digit say how many modelled flips it needs.
  > SAY: Twenty of 152 keep three. Thirty-eight drop to two. Ninety-four open with one. Most of the one-flip settings let the tool merge identical logic, so three copies become one. That is ordinary optimisation, and SYNFI showed this effect before us.
  > SAY: Limits: one toy design, the settings are not independent experiments, and a 3 means no attack found with fewer flips within 6 cycles, not safe.

## 8. Why 2 and not 3?   (added by INT)
- At cycle 0 the machine loads the armed word 0xCC. 0xCC xor 0x96 = bits {1,3,4,6}: they belong to only 2 of the 3 copies.
- So 2 flips of next-state nets can turn that load into 0x96. Not a Yosys-version effect: the stored netlist (3 flips) is also Yosys 0.33, another flow.
- Table, 8 synthesis flows, apt Yosys 0.33: v2 (armed 0xCC, 2 copies) 2 1 1 2 2 2 2 2; v2e (armed 0xA5, 3 copies) 3 1 1 3 3 3 3 3.
- The 1s are flows that merge the copies (opt_merge, flatten before ABC): no encoding fixes those.
- Encoding sets the floor; the synthesis flow decides whether it is reached.
- MEASURED by agent P01a, re-run by the lead 2026-11-20: `docs/report/WHY_TWO_FLIPS.md`, `rtl/v2e.v`. Stem rule, T=6, k<=3, toy design; conda 0.38 gives 3 only on its plain flow.
- Speaker notes (say this):
  > SAY: Earlier I blamed the Yosys version for V2 needing three flips on one netlist and two on another. That was wrong, and a fresh-eyes review caught it: both netlists come from Yosys 0.33.
  > SAY: The real reason is in the encoding. Before the key check, the machine loads the armed word CC. CC and the accept word 96 differ in four bits, and those four bits belong to only two of the three comparator copies. So an attacker does not need to fool all three copies: two flips at the moment CC is loaded are enough, if the netlist has one shared net per copy.
  > SAY: To test that, only the one constant was changed to A5, which touches all three copies. Over the same eight synthesis flows V2 gives 2, 1, 1, 2, 2, 2, 2, 2 and the re-encoded design gives 3, 1, 1, 3, 3, 3, 3, 3. The ones are flows that merge the copies, and no encoding fixes that. So: encoding sets the floor, the flow decides whether it is reached. Toy design, modelled flips, bounded at six cycles and three flips.

## 9. Redundancy is a code   (added by INT)
- Picture: `docs/comms/staircase.png` (flips needed against code distance; flops only and all nets).
- The state words are codewords of a textbook code (distance 4); the copies are a repetition code.
- Flops only: flips needed = distance to the nearest non-accept word (15 of 15 codebooks).
- All nets: about one flip per copy; 3 of 16 three-copy codebooks fall to 2 (my prediction failed).
- Modelled, toy, observed not a theorem. MEASURED: 19 codebooks, T=6, apt Yosys 0.33; `results/comms/distance_sweep.csv`, `docs/comms/CODING_VIEW.md`.
- Speaker notes (say this):
  > SAY: Here is a way a communications engineer would read the design. The state words of the boot machine form a small textbook code, a Reed-Muller code with distance four, and the copied comparators are a repetition code.
  > SAY: On this plot, the diagonal is what happens when only the state register may flip: in all 15 codebooks with distance up to six, the flips needed equal the distance to the nearest word that is not accept. When every net may flip, the curve stops at about one flip per comparator copy, so a bigger distance buys nothing past three.
  > SAY: Some of my predictions failed and I keep them visible. The flops-only count follows the nearest fail word, not the idle word. On the project flow 3 of 16 three-copy codebooks sit at 2, and the order of the words matters: F0 then CC gives 2, CC then F0 gives 3. I did not dissect why. This is modelled, on a toy design, observed and not a theorem, and nothing here is new coding theory.

## 10. Random flips: slope = flips needed, height = ways   (added by INT2a, 2026-11-20)
- Picture: `docs/comms/waterfall.png`.
- Low-p slopes: V0 0.98, V1 0.88, V2-stored 3.00, V2-apt 2.14, V2e 2.97 (min flips 1, 1, 3, 2, 3).
- V2e: 734 attacking triples vs 80 for stored V2, so about 9x more false accepts at low p.
- Higher adversarial cost does not mean a lower random rate: multiplicity matters.
- SIMULATED teaching model, not an attacker model or a physical error rate. T=4; results/comms/waterfall.csv. Failed prediction kept: the truncated series fit only 9 of 31 points (a lower bound).
- Speaker notes (say this):
  > SAY: Here every wire and flop is wrong with a small probability p in each clock cycle, independently, like line noise. I plot how often a wrong key is accepted. This is a teaching model, not an attacker and not a real error rate.
  > SAY: On log-log axes each design is a straight line. Its slope is the fewest flips needed: about 1, 1, 3, 2 and 3. Its height is how many ways there are. V2e and stored V2 both need three flips, but V2e has 734 attacking triples against 80, so it is about nine times more likely to false-accept at low noise.
  > SAY: One of my predictions failed and I keep it: the exact series cut at three flips matched the simulation at only 9 of 31 points. It is a lower bound, not an exact value.

## 11. Best against random flips, weakest against one burst   (added by INT2a, 2026-11-20)
- Complement pairs need more than 6 random flips, but one event that inverts all 8 state flops maps 0x69 to 0x96: 1 event.
- The stored code falls the same way: it rests in fail word 0x69, the complement of accept 0x96. Fail word 0x3C: no burst attack, random still 4.
- A burst limited to one comparator copy needs 3 events: interleaving helps.
- SIMULATED: one modelled burst = all state flops (or one copy group) inverted in one cycle; not a real overclock or voltage glitch. 16 codebooks, T=6, Yosys 0.33; results/comms/burst.csv, docs/comms/BURST_NOTES.md.
- Table row:  | burst-fragile (1 all-flop burst opens) | burst-robust (no burst attack within 6 cycles)
- Table row: random-robust (flops-only >= 4) | 69/96, C3/3C, A5/5A complements; stored F0/96 (fail word 0x69); 4 more | F0/96 with fail word 0x3C; 2 more
- Table row: random-fragile | 3 codebooks | 2 codebooks
- Speaker notes (say this):
  > SAY: Communications engineers separate random errors, one bit at a time, from burst errors, many bits at once. A code that is best against one can be poor against the other.
  > SAY: The complementary pair 0x69 and 0x96 differ in all eight bits, so random flips need more than six. But one modelled event that inverts all eight state flops turns 0x69 into 0x96 exactly: one event. Our stored design falls the same way, because it rests in its fail word 0x69. With the fail word changed to 0x3C, no all-flop burst reached accept, and random flips still needed four.
  > SAY: A burst here is an arithmetic event in the model, not a real glitch. Toy netlists, six cycles, no general rule about codes.

## 12. What is NOT proven   (about 24 words)
- Nothing physical: modelled flips.
- Toy designs, 6 cycles, 3 flips.
- Prior art covers the method.
- Predictor 92% exact (always-1: 62%, lower bound alone: 83%); solver judges.
- Predictor: VER audit, 150 of 163 fresh cells; 58% when 2 or more flips are needed.
- Speaker notes (say this):
  > SAY: Now what I do not claim. Nothing is physical: a flip is a modelling choice, and SPICE is simulation, not silicon. These are toy 8-bit designs, bounded at six cycles and three flips; greater than three means no attack found up to three, not secure. The base method is covered by earlier tools: SYNFI, FIRMER, k-FRP, CLEAVE, FIVER, uArchiFI. Nothing here is established as new, and I have not read the k-FRP full text. A predictor that guesses the answer without the solver was exact on 150 of 163 fresh toy cells, 92 percent (always guessing one gives 62 and the lower bound alone 83), and only 58 percent when two or more flips are needed; it is a quick pre-check and the solver stays the judge. And whether a real supply dip can choose which gates fall is open.

## 13. What I did   (about 16 words)
- Speaker notes (say this):

## 14. The sentence to keep   (about 30 words)
- 'Three copies resist two faults' means nothing without: what counts as a fault, which output, how the chip starts, which netlist.
- V2 is the example. Questions?
- Speaker notes (say this):
  > SAY: If you remember one thing: a claim like 'three copies resist two faults' means nothing unless it says what counts as a fault, which output is attacked, how the chip starts and which circuit file was tested. I built a small tool that re-runs the question under each choice and shows which choice decides the answer. V2 is the example, not a recommendation. Everything is a bounded simulation of a toy, and nothing is claimed as new. Questions, please.

## 15. A1. Counting rule: one flipped net is one fault   (about 70 words)
- Headline rule: flipping a net counts once, however many gates read it (matches FIRMER's per-gate counting).
- Stem rule: V2 needs 2 flips on 26 of 32 rebuilt netlists, 3 on 6.
- Fanout counting (a stress test): 3 flips on 32 of 32.
- Replicated on 64 of 64 rows with one reused recipe list, so not independent. Neither rule is shown physical.
- MEASURED: research/c3/rep/REP_REPORT.md; R22 (physical fault-model literature, snippets and fetched pages).
- Speaker notes (say this):
  > SAY: A flip of a net, called a stem, counts as one fault however many gates read it. That is the convention of the published tools; FIRMER counts per gate the same way. Counting a net read by f gates as f faults is a stress test, not a claim. Under the stem rule V2 needs only 2 flips on 26 of 32 rebuilt netlists and 3 on 6. Under fanout counting it needs 3 on all 32. A second agent replicated the numbers on 64 of 64 rows, but with one reused recipe list, so it is not independent. I do not claim either rule is physical; no source I found gives a physical 'right' rule.

## 16. A2. Predictor: a quick pre-check, not a verdict   (about 67 words)
- Fresh toy cells: exact on 150 of 163 (92.0%; always-1 62%, lower bound alone 83%); within one flip on 156 (95.7%). LEDGER: 71/71 on the E2 family sample, 4/6 on fresh RTLs (wrong on V2m, V5).
- When 2 or more flips are needed: exact on 18 of 31 (58%).
- Missed the pre-registered 98% bar; 1.4x slower than the solver.
- Lower bound never above the solver in 928 + 163 + 60 cells. The old 928/928 is an easy, near-duplicate corpus.
- MEASURED: research/c4/ver/VER_REPORT.md; docs/NUMBERS.md section 7.
- Speaker notes (say this):
  > SAY: I tested whether a structural rule could predict the minimum without the solver. On the first corpus it looked perfect, 928 of 928, but that corpus was easy and effectively three to five designs. An independent audit on 163 fresh cells from 76 new netlists found it exact on 150, 92 percent, within one flip on 156, and only 18 of 31, 58 percent, when two or more flips are needed. It missed the pre-registered 98 percent bar, and it was 1.4 times slower than the solver. What stays is a sound lower bound: in 928 plus 163 plus 60 cells the bound never exceeded the solver. So it is a pre-check, and the solver is the reference.

## 17. A3. The one unbounded proof (PDR)   (about 55 words)
- Stored V2 netlist, 2 or fewer flips: PASS for any number of cycles (ABC PDR, 0.83 s).
- Covers this netlist, this fault model, constant attacker input.
- With 3 flips an attack exists. Apt-built 85-gate netlist: PDR pass only at 1 flip. (Not a version effect: the stored netlist is also Yosys 0.33. Encoding sets the floor (idle word touches 2 of 3 copies => 2 flips); the synthesis flow decides whether the floor is reached (1 when a flow merges the copies). A build or flow difference changes the netlist, not the underlying weakness. See slide 'Why 2 and not 3?'.)
- No independent certificate; not replicated by a second tool.
- MEASURED by the lead, not re-run by RECON: formal/FORMAL.md section 4; docs/NUMBERS.md F.pdr.
- Speaker notes (say this):
  > SAY: There is exactly one unbounded result. With the ABC PDR engine in SymbiYosys, for the stored V2 netlist, no attack exists with two or fewer flips for any number of cycles. It passed in 0.83 seconds. It covers this netlist, this fault model and a constant attacker input only; with three flips an attack exists; the apt-built 85-gate netlist is covered only at one flip. There is no independent proof certificate and no second tool replicated it. So I use it as one data point, not as a claim that V2 is secure.

## 18. A4. Layout: what DRC and LVS do and do not say   (about 74 words)
- Original: router DRC 0, antenna 0, LVS match uniquely (430 vs 430), slack +7.035 ns (estimate).
- Magic errors in library cells are tap-dependent; tested in context for one cell only. Not claimed DRC-clean.
- 4 spread layouts: router and antenna clean, LVS failed in all 4 (filler flow bug, not fixed).
- Cost of spreading: wire length +29 to +50%, die area x1.26 to x2.5.
- MEASURED: research/c4/l2/L2_REPORT.md, layout/verify/VERIFY.md. No extraction, no IR-drop, no silicon.
- Speaker notes (say this):
  > SAY: The original V2 layout: router design-rule violations zero, antenna violations zero, LVS matches uniquely, 430 devices against 430, and slack about plus seven nanoseconds, which is an estimate from global-route parasitics, not signoff. Magic still lists errors inside the library cell definitions; they look tap-dependent, and I tested that in context for one cell type only, so I do not claim the layout is DRC-clean. The four spread layouts: router clean, antenna clean, but LVS failed in all four, for example 428 against 430 devices, because a signal wire on li1 touches a filler's ground in magic's view. That is a known flow bug and I did not fix it. Costs: wire length plus 29 to 50 percent, die area times 1.26 to 2.5. No extraction, no IR-drop, no silicon.

## 19. A5. Ledger: survival depends on polarity   (appendix, added by FIX3)
- Picture: `docs/report/ledger.png` (cells labelled MEASURED / SIMULATED / UNMEASURED).
- Under the 1-to-0 rail model V1, V2, V5 survive within the bound; a 0->1 event on the three compare copies breaks V2 and V5 with one event (V1 and V0 too). SPICE supports 1-to-0; selectivity unproven; the domain is netlist hierarchy.
- V1 and V2 tie in almost every row; triplication buys one extra gate under a selective event (2 vs 3 gates).
- SIMULATED / MEASURED as labelled: research/c5/ledger/LEDGER_REPORT.md; research/c5/anchor/RAIL_RECONCILIATION.md.
- Speaker notes: in the deck (slide 19 notes; slide 17 before INT added slides 13 and 14).
## 20. A6. The more bits the consumer reads, the more flips it takes   (about 32 words)
- 0 to 3
- V2, lowest n bits read. / n = 1 costs 0: the idle state already matches on that bit.
- MEASURED: --sweep-widths, 6 cycles, at most 3 flips.
- Speaker notes (say this):
  > SAY: Same V2 design, same netlist. I change only how many result bits the consumer reads: the lowest one bit, two bits, up to all eight. The minimum number of flips climbs: 0, 1, 1, 2, 2, 3, 3, 3. The zero at one bit is not a bug: the idle state already looks like acceptance on that single bit.
  > SAY: The lesson: a claim of protection has to say how wide the reader is. A reader that only checks four bits gets one or two flips, not three. You can reproduce this live with the sweep-widths command. Measured on the stored V2 netlist; modelled flips; 6 cycles, at most 3 flips.

## 21. A7. Same design, different build: 1, 2 or 3 flips   (about 24 words)
- 180 of 264 solved configs (94/38/20 over 152 distinct netlists)
- V2 settings need only 1 flip. / The build tool decides the answer.
- MEASURED: E2 matrix, 864 settings (792 solved in all, 264 for V2).
- Speaker notes (say this):
  > SAY: Now I keep the design and the scope fixed and change only how it is built. The solver was run on V2 across 864 synthesis settings; 264 of the V2 ones were solved. In 180 of them one flip is enough. In 60 it takes two. In only 24 does it take three. Counted per distinct netlist, 152 of them, the split is 94, 38 and 20. The reason is that the build tool can merge or reshape the three copies so they share logic.
  > SAY: I used to say two Yosys versions disagree. That was wrong: the stored netlist was made by the same Yosys 0.33. The real cause is the encoding, which I show on slide 'Why 2 and not 3?'. Encoding sets the floor; the synthesis flow decides whether the floor is reached. A build or flow difference changes the netlist, not the underlying weakness. This is measured, bounded, toy designs.

## 22. A8. Circuit simulation: a supply dip hits a whole rail   (about 28 words)
- 0 of 60
- Dip points that flipped a flop. / Dips pull high gates low, together. / Clock runt: wrong-time capture.
- SIMULATED (ngspice, sky130 cells). Not silicon. Plot: clock runt, red = flop captured D.
- Speaker notes (say this):
  > SAY: Is a flip a fair picture of a real disturbance? I asked a circuit simulator, ngspice with real sky130 cell models. This is simulation, not silicon.
  > SAY: Three things came out. One: when the supply dips, every gate with a high output on that rail sags together, and only from one to zero; low outputs stay low. So a dip is a rail-wide, one-way event, not one clean flip. Two: in 60 dip points, even down to zero volts for three nanoseconds, the stored flop value never flipped. Three: a short clock pulse, a runt, makes a flop capture its input at the wrong time, which is a wrong-time capture and not a free flip; the plot shows red where the flop captured wrongly. I do not quote voltages or timings as attack parameters, and I only tested dips up to three nanoseconds.

## 23. A9. Layout: a 2.95 um dip radius covers the three copies (outline section kept from the earlier title "Layout: the three copies sit within 2.95 um")   (about 35 words)
- 2.95 um
- Original: 3 copies, one supply net. / Spread 15 um or more: helps against local events only. / Die-wide selective dip: still 1. / Spread layouts failed LVS. / Rail polarity: 1-to-0 only survives; a 0->1 event on the three compare copies breaks V2 and V5 with one event.
- SIMULATED model on MEASURED placement. No extraction, no silicon.
- Speaker notes (say this):
  > SAY: I placed and routed the toy V2 with the open sky130 flow. This is a flow demonstration, nothing was made. I measured where the three comparator copies landed: the three cells that together are enough to break V2 sit within about 2.95 micrometres of each other, on one supply net. So a local disturbance could reach all three.
  > SAY: I then tried spreading the copies apart, to 15 micrometres or more. In the model that helps against local events, which then need more events. But a dip over the whole die that can choose which gates fall still costs one event, because the copies are still on the same supply net. And the honest part: all four spread layouts failed the LVS check because of a known flow bug, filler cells shorting a wire. So the spread layouts are an experiment, not a fix. No parasitic extraction, no IR-drop analysis.

## 24. A10. What we built   (about 26 words)
- 189
- main tests passed (2 skipped)
- 324
- product tests passed
- 72.5%
- mutation score, root 50 of 69
- Solver, and a product CLI with scope sweep, width sweep and timeout.
- Tests MEASURED on a clean copy (324 product tests, pyyaml installed). Mutation score REPORTED.
- Speaker notes (say this):
  > SAY: What exists is a toolkit. A solver that finds the minimum flips. A command-line product, faultbound-wt, that takes a netlist and says how many flips, which wires, and under which scope; it has a scope sweep, a width sweep and a timeout so it never hangs. There are 189 tests passing in the main suite, two skipped (no numpy, no browser in the clean install), and 324 in the product suite, counted on a clean copy. A mutation check killed 50 of 69 sabotaged versions of the main engine, about 72 percent, and 50 of 74 for the product, about 68 percent; those figures come from agent reports and I did not re-run them. Other tools and re-runs agree with the solver, but they share its fault model, so they check the code, not the physics.

