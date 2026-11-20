# VIVA_SIM_REPORT: four mock examiners, 48 questions, weakest 10, 5-minute outline, one-command falsifiers

Source tags used below (the file the fact comes from):
- [ONE_PAGE] docs/dossier/ONE_PAGE_FOR_THE_OWNER.md; [B2] research/c2/b2_scope/B2_REPORT.md; [M1] research/c3/m1/M1_REPORT.md; [E2] research/c2/e2_variance/E2_REPORT.md and raw/matrix.csv; [REP] research/c3/rep/REP_REPORT.md; [R22] research/c3/r22/R22_REPORT.md
- [EL1] research/c2/el1_spice/EL1_REPORT.md; [B3] research/c4/b3/B3_REPORT.md; [VER] research/c4/ver/VER_REPORT.md; [CO] research/c4/council/COUNCIL_W1.md
- [LAY] layout/verify/VERIFY.md and layout/v_designs/out_patched/RESULT.md; [README] README.md

Format: each question has the spoken answer (target <= 45 s, about 110 words), sources, then follow-ups (F1..F3) only where the first answer was weak.

---
## 1. E1: ECE professor ("show me what YOU understand, derive it, do not cite it")

**E1-1. On the board: why does V1, two compare copies, fall to one flip?**
"V1 compares the input with the key twice, m1 and m2, but accepts through one AND gate, ok = m1 AND m2, and that one net drives all eight result bits. With a wrong input both compares are zero, so ok is zero and the state goes idle, compare, fail. If I flip the net ok to one for one cycle, at the cycle where the state is compare, the next state is the accept word. The two compares never get a vote. So duplication helps only if the copies do not end in one wire."
Sources: [ODS] 1, [DOS] 5. [RE-RAN] `glitchsat check v1.json --k 1` gives ATTACK_FOUND, net `ok`, 8 of 8 bits.
F1 "What would make one flip not enough?" -> "Give each copy its own disjoint output bits. That is V2: m0 owns bits 0,3,6; m1 owns 1,4,7; m2 owns 2,5." [ODS] 2.

**E1-2. Derive the "3" for V2 on the full word.**
"With a wrong input all three compares are zero and the result word is 0x69, which is the bitwise complement of the accept word 0x96, so all eight bits are wrong. Each compare copy owns a group of bits, so one flip of a copy's compare output repairs all of that copy's bits at once. Three copies, three flips. The other route is flipping state flops directly: idle 0xF0 against 0x96 differs in four bits, the compare state 0xCC also in four. So the cheapest is three. This is for the full word only."
Sources: [ODS] 2; [DOS] 7. [RE-RAN] k=2 gives NO_ATTACK_UP_TO_BOUND, k=3 gives min 3 (one node in each of c0,c1,c2, cycle 1).
F1 "Why is 0xF0 xor 0x96 four bits?" -> "0xF0 is 1111 0000, 0x96 is 1001 0110; xor is 0110 0110, four ones." F2 "So is 3 a property of V2?" -> "No, of V2 plus this netlist plus the full-word goal; see E1-3 and E3-7."

**E1-3. A consumer reads only some bits. What do masks 0x0F and 0x4E cost?**
"I use the rule from the M1 report: minimum is the smaller of two things. One, the direct route: the number of bits that differ from the accept word in the idle or compare state, inside the mask. Two, flip a set of copies and pay one per copy plus one per masked bit that no chosen copy owns. For 0x0F, bits 0 to 3, owners m0, m1, m2, m0: direct costs 2 from either state, all copy routes cost 3, so the answer is 2. For 0x4E, bits 1,2,3,6, direct costs 3, copies cost 3, so 3. Checked by the solver on all 255 masks, but only on the stored netlist."
Sources: [M1] s3, [ODS] 3. [RE-RAN] m1_all_masks.csv column 11: 0x03 -> 1, 0x0F -> 2, 0x4E -> 3, 0xFF -> 3.
**[IDK] part:** "The rule fails on the apt-0.33 re-synthesis, 68 masks mismatch. I do not have a rule that covers that." Say: "It is an exact rule for one netlist, not a theorem."

**E1-4. Explain your SAT encoding from first principles.**
"Each gate becomes an equation, out equals f of its inputs. A fault gives each gate output a free switch: out equals f of inputs XOR flip. I copy the circuit T times, one per clock cycle, and connect flop outputs to the next cycle's inputs: that is bounded model checking. The goal clause says the result word equals 0x96 in some cycle while the input is not the key. 'At most K flips' is a cardinality constraint on all the switches. z3 either gives a witness or says unsatisfiable. I find the minimum by tightening K."
F1 "Show the 3-gate example." -> g1 = a AND b, g2 = a AND b, g3 = g1 AND g2, key a=b=1, goal g3=1 with (a,b) not (1,1). k=0 unsat; k=1 flip g3; this is V1 in miniature. [RE-RAN] worked_example.py prints k=0 None, k=1 SAT.

**E1-5. What exactly does UNSAT at k=2 prove?**
"On this netlist file, with this fault rule, this goal and this input treatment, no set of at most two single-cycle flips within six cycles reaches the goal. It says nothing about cycle seven, three flips, another netlist, or another goal. I never write 'secure' for it."
Sources: [VS] FP12, [DOS] 4.

**E1-6. Hamming distance: your state code {F0, CC, 96, 69} has distance 4. What does that buy?**
"If the attacker may flip only the eight state flops, the minimum is four, equal to the code distance. [RE-RAN] state-flop-only gives 4. But with all sites V2 costs 3 and V1 costs 1, because the weak point is the decoder, the shared net. A code protects the codeword, not the circuit that decodes it. And 96 and 69 are complements, distance 8, so a flip-all event breaks every design; I did not test a non-complementary encoding."
Sources: [DOS] 12, [VS] FP19. **[IDK]**: non-complementary encoding untested; say "that is the first thing I would test next".

**E1-7. Stem versus fanout counting, with three gates.**
"Net n is the output of g0 and feeds g1, g2, g3. Under the stem rule flipping n is one fault because the disturbance sits at the driver. Under the per-fanout rule I charge one fault per reader pin, so three. An attacker who benefits from a high-fanout net pays one under the first rule and three under the second. On my 32 re-synthesised V2 netlists the minimum is 2 on 26 and 3 on 6 under stem counting, and 3 on all 32 under fanout counting."
Sources: [ODS] 5, [REP] s5. [RE-RAN] rep_results.csv: rep_unit_cli 2 x26, 3 x6; rep_fanout_pins 3 x32.
F1 "Which rule is physical?" -> see E3-6. I do not claim one is.

**E1-8. Why does merging identical compare cones drop V2 to one flip?**
"The three compares are the same function of the same input. If synthesis merges identical cells, the three become one net, and that one net drives all eight bits: that is V1 again, so one flip. The RTL is unchanged; only the netlist differs, so a verdict belongs to one netlist hash. In the E2 matrix, V2 rows with opt_merge give 1."
Sources: [ODS] 4, [E2]. OpenTitan guideline R21 (agent snippet) says synthesis may optimise redundancy away [DOS] 11 (SNIPPET).

**E1-9. In your SPICE runs a supply dip only pulls outputs low. Why, and what did NOT happen?**
"My reading, not a measurement: a high gate output is held up by the pull-up transistors from the rail, so when the rail sags the output sags with it; a low output is held by pull-downs to ground, and in the simulation ground is not dipped, so low stays low. What the data say: in 60 dip points the stored flop value never flipped, even at 0 V for 3 ns; a clock runt of 1.3 V in the typical corner made the flop capture its input. It is ngspice on sky130 cells, simulation, not silicon."
Sources: [EL1] A, B. The physical explanation is INFERRED (EL1 states what, not why).
**[IDK]**: "dips longer than 3 ns, other cells, extracted grids: not mapped." Say: "My longest dip was 3 ns; retention for longer dips is unmapped."

**E1-10. Setup time: what did experiment C show?**
"I moved the data change relative to the clock edge on a 25 ps grid. In the typical corner at 1.8 V the latest change that is still captured is about 50 to 75 ps before the edge, and at 1.2 V about 100 ps, so setup scales with supply and corner. After the edge the old value was held. No undefined output on a 25 ps grid. A late-data fault is a wrong-time capture, not a free flip."
Sources: [EL1] C. Do not quote these as attack parameters (EL1 says so).

**E1-11. Why T = 6 cycles and k <= 3?**
"The designs are a small state machine: idle, compare, accept or fail, so most attacks sit at cycle 1. Six cycles is the solver's default. I also swept longer: V2 at k=3 over 20 cycles took 475 seconds. Beyond k=3 the solver time grows. A result of 'greater than 3' means no attack up to 3, not secure."
Sources: [VS] FP20, [DOS] 7.6. The 475 s is from docs/DEEP_RESULTS.md, quoted by [DOS]; I did not re-run it.

**E1-12. Pick any number in your report and derive or reproduce it in front of me.**

---
## 2. E2: VLSI engineer ("what is real: DRC, LVS, flow")

**E2-1. Is the layout a real chip layout?**
"No. It is a flow demonstration: the open sky130 flow with OpenROAD placement, clock tree and routing, run on a 35-cell block. It was never fabricated and there is no signoff. I use it to show that the three comparators of V2 stay as physically separate cells, not to claim anything about chips."
Sources: [DOS] 7.9, [LAY]. Layout needs a separate EDA install and is not in CI ([README]).

**E2-2. DRC: clean or not?**
"Three separate statements. The router reports 0 violations. Magic DRC lists no rule on the top cell of either design after the patched rerun. But magic still reports errors inside the library cell definitions, for example dfxtp_1: nwell.4 and the latch-up rules LU.2 and LU.3. I tested one flip-flop between two tap cells flattened and the DRC list was empty, so I read these as context-dependent false positives of checking a cell alone, not geometry errors. I did not fix them and I did not have a foundry deck."
Sources: [LAY] s2 and RESULT.md. Evidence for the 'false positive' reading: one cell context test only (tested on dfxtp_1; other cells 'show the same rules' per VERIFY).
**[IDK]**: "I cannot prove the same for every cell." Say: "one cell context test, others share the same three rules".

**E2-3. LVS?**
"After my patch run, netgen reports 'Circuits match uniquely' for V1 and V2, 422 versus 422 devices and 225 versus 225 nets for V1. Two limits: the reference netlist was built from the same synthesized netlist using PDK subcircuits, so it checks that the layout matches that netlist, not that the netlist matches the design intent. And before patches the match failed, and for a separate door-lock design the top-level LVS failed on pin matching; I do not claim that one."
Sources: [LAY] RESULT.md, [DOS] 7.9.

**E2-4. Timing: +7 ns slack. So what?**
"It is an estimate from global-route parasitics at 10 ns on a 35-cell block, not signoff, with hold slack about +0.5 ns. It tells me nothing about glitch tolerance. I quote it only to say the flow ran end to end."
Sources: [DOS] 7.9 (ESTIMATED), [LAY].

**E2-5. Area and cell count: V0, V1, V2?**
"After yosys mapping: V0 10 cells, 89 square microns; V1 35 cells, 358; V2 36 cells, 363. V2 is only one cell more than V1, which could mean the copies merged, so I checked the placed netlists: the three comparator cones are 3 cells each with zero overlap."
Sources: [DOS] 7.9 (DA2 read the pnr netlists; I did not re-read them).
F1 "Why only one cell more?" -> "the voting logic is tiny; the extra comparator copies replaced shared logic; I have not decomposed it further." **[IDK]** partially.

**E2-6. Which synthesis flow, and did the tool merge your copies?**
"Yosys with keep_hierarchy on the compare modules, then flatten, ABC with a gate list, techmap, and a JSON netlist. In the stored flow there is no opt_merge after the flatten, so the copies stay separate. If I add opt_merge V2 costs one flip. Across 264 solved V2 configurations in the E2 matrix, 180 need 1, 60 need 2, 24 need 3."
Sources: scripts/synth.sh header, [ODS] 4, [E2]. [RE-RAN] counts 180/60/24 from raw/matrix.csv.

**E2-7. Why 85 gates with apt Yosys 0.33 and 83 with conda 0.38?**
**[IDK]** "I do not know the exact cause. Synthesis is deterministic, the three compare cones are disjoint in both, and the difference is in the next-state mapping, one MUX on the conda build. The apt build's 2-flip attack uses an AND with fanout 3 and an OR with fanout 2. I am not saying the Yosys version is the cause; it is a correlate."
Sources: [VS] D-bonus, FP14 (E2).

**E2-8. On the sky130-mapped netlist V2 costs 3, generic costs 2. Explain.**
"I only know what the report says: the 2-flip attack on the generic netlist uses internal gates that are not separate sites after mapping. The mapped result came from the project's own adapter; there is no second solver on it."
Sources: [DOS] 7.9, [VS] FP15. **[IDK]** on the exact gates; say "the mapped netlist hides those gate boundaries; I did not trace it gate by gate".

**E2-9. Antenna and manufacturing grid?**
"OpenROAD check_antennas: 0 pin and 0 net violations for both designs; no off-grid geometry in the GDS, checked with klayout over all polygon vertices. The tool reports a missing antenna cell warning, so no diodes exist. Not a foundry signoff."
Sources: [LAY] s1.

**E2-10. Reset and power-up in the layout?**
"The layout has no reset. My result depends on a known power-up state: with an arbitrary non-accepting state V2 costs 1, and with arbitrary state and no reset every design costs 0. That is a gap I name, not hide."
Sources: [B2], [VS] FP7, [DOS] 13.9.

**E2-11. Did layout change the security result?**
"Only as a modelling experiment. I put the copies 2 to 4 microns apart and assumed a 3.5 micron glitch radius, a modelling choice, not physics: that reduces V2 to one flip, because one event reaches all three. I did not extract a power grid, so I cannot say what a real dip would hit."
Sources: [DOS] 7.9 (SIMULATED modelling choice).

**E2-12. Can I rebuild your layout and SPICE from the repo?**
"Not fully. The layout, PDR proof, SymbiYosys runs and SPICE use conda environments that the bundle does not rebuild; the solver, tests and the V0 to V2 sweeps work from apt yosys 0.33, iverilog and pip z3. Tools used: OpenROAD f12e2f47, magic 8.3.464, netgen 1.5.272, klayout 0.30.13."
Sources: [DOS] 13.10, [LAY], handoff/CONTINUATION/ENV_REBUILD.md (named in [DOS]).

---
## 3. E3: hardware security researcher ("attack the claim, novelty, fault model")

**E3-1. State your claim in one sentence.**
"A claim like 'three copies resist two faults' means nothing unless it says what counts as a fault, which output is attacked, how the chip starts and which circuit file was tested. I built a small tool that reruns the question under each choice and shows which one decides the answer; V2 is the example, not a recommendation. Everything is a bounded simulation of a toy, nothing is claimed as new."
Source: [ONE_PAGE] 'The sentence to defend'; [VS] s0.

**E3-2. What is new? Does this break OpenTitan?**
"Nothing is established as new. SYNFI and FIRMER already do formal fault analysis on netlists; SYNFI even measured synthesis dependence itself. The closest paper, k-FRP, I have not read; its full text was blocked. And no, it says nothing about OpenTitan or any product: I analysed toy netlists and a few wrapped public blocks."
F1 "So why is it worth anything?" -> "Reproducible sensitivity analysis and teaching material; the counting rule as a variable of the minimum-fault question: I found no paper treating it that way, but absence of hits is not evidence of absence."

**E3-3. Your fault model is a clean XOR for one cycle. Justify it.**
"I cannot derive it; I chose it. It is the convention of formal tools: one gate output or flop output flips for one cycle. The SPICE work suggests real glitches are different: correlated, one-directional on a rail dip, and wrong-time capture on a clock glitch. Not covered at all: stuck-at, multi-bit spatial faults, laser or EM injection. So 'one clean flip' is an abstraction."
Sources: [DOS] 13.2, [EL1], [R22] via [VS] s4.

**E3-4. Are single independent flips even physical? What does EL1 say?**
"In my circuit simulation a supply dip hit every high-output gate on the rail together and only toward 0; no flop output flipped from a dip alone; a clock runt made a flop capture its input. So independent single flips are the less supported model for dips. But it is one small cell, coarse grids, no extracted power grid, so it cannot show what a real chip does."
Sources: [EL1]. Do not quote volts or picoseconds.

**E3-5. You built a rail-dip model (B3). Does V2 survive it?**
"Within the model and the bound of 3 events, 6 cycles: yes. Under a whole-rail dip, a half-design dip by hierarchy, or a fanout-cone dip, I find no attack up to 3 on V2, V5, V1; V0 falls to 1. The word goal is also not reachable by wrong-time capture. But the verdict depends entirely on selectivity: if one dip event may choose which gates fall, V2 and V5 fall to one event, with three gates, one per compare copy. EL1 saw all high gates drooping together, so that selective event is not what my SPICE supports, but one tiny rail cannot show a real dip cannot be selective."
Sources: [B3] matrix and 'Plain answers'. **[IDK]**: "whether a real dip can be selective: not established either way." B3 checks: 16 pytest passed, brute-force check only on V0/V1 at T<=4, k<=2; V2 relies on the z3 engine.

**E3-6. Which counting rule is correct? Isn't 32/32 a rescue?**
"I headline the stem rule, one flipped gate output is one fault, because it is the published tools' convention (FIRMER counts per gate) and matches one driver-node upset. Under it V2 holds against 2 flips on only 6 of 32 builds. Fanout counting makes it 32 of 32, but I found no source that supports it as physical, so I show it as a stress test and never as the result. I do not say any rule is physically right. I also did not test per-branch with partial flips."
Sources: [R22], [REP] s3, s6, [CO] s2. Do NOT say "stem=1 is physically right" ([VS] s3 row 4).

**E3-7. Your headline V2 = 3 collapses to 1 if I change any one thing. What did you show?**
"That is the result, not an objection to it. V2 costs 3 in one cell: full word, inputs not attackable, known power-up, stored netlist. Change the goal to the accept flag, or allow input nets, or an arbitrary non-accepting power-up, and it is 1. So 'resists two faults' is not a meaningful sentence without those qualifiers. I do not claim V2 is secure."
Sources: [VS] D1, [B2] 360 cells, [README] one-glance table. [RE-RAN] boot_ok k=1 gives ATTACK_FOUND on net `boot_ok`.

**E3-8. You claim an unbounded proof?**
"I do not lean on it. One tool-reported PASS from ABC's PDR for one V2 netlist, word goal, k <= 2. No certificate, not replicated by a second engine, and k-FRP, which may cover this, is unread. Controls show it is not vacuous: V1 at k=1 fails. It is not in the headline."
Sources: [VS] D7, FP13; [DOS] 7.7. Never say "formally proved secure for any number of cycles".

**E3-9. Every cross-check shares your fault model. So what is verified?**
"Right: they check my encoding and code, not the model. Own simulator against the solver on about 2.1 million fault sets, 0 disagreements; boolector; 13 of 13 witnesses replayed; SymbiYosys depth 6; 2040 random runs against brute force; replication by REP, 64 of 64. What would show me wrong: an independent simulator disagreeing with a stored witness. That has not happened. A physical argument that makes V2's number meaningless is untested."
Sources: [VS] D5, FP30, [DOS] 7.7, 8.

**E3-10. You have a solver-free structural predictor with 928 of 928 right. Is that validated?**
"No, and I would not say 928 of 928. The audit found no leakage, and its lower bound was never violated in 928, 163 and 60 cells, and it never called a one-flip design safe. But those cells are near-duplicates of a few designs. On 76 fresh netlists it matched the solver on 92 percent of cells, but only 58 percent of cells that need two or more flips (18 of 31), and in 7 cells it said an attack exists where the solver found none up to 3. It is a heuristic attack search with a sound lower bound; the SAT solver remains the reference. It is not part of the tool."
Sources: [VER] s3-5. [RE-RAN] raw `heldout.csv` pred==solver string comparison gives a lower count than VER's table (150/163), which uses the corrected x-init reruns and treats '>3' as 4; reconciled by FIX3: raw match count 144, 148 with '>3' as 4, 150 after two x-init corrections (NUMBERS.md).

**E3-11. The claim changed several times. Isn't the final one a post-hoc rescue?**
Sources: [VS] D8, FP28, [DOS] PROBLEM_STATEMENT_EVOLUTION.

**E3-12. Dual use and what you do NOT claim?**

---
## 4. E4: industry hiring manager ("so what, who uses it, what did YOU do")

**E4-1. Explain it in 30 seconds to me, not an expert.**
"Chips often check a secret key at boot, and engineers add copies of the check so that one disturbance cannot fool it. I made a small program that takes the circuit and asks the fewest one-wire disturbances needed to fool it. The lesson: three copies looked safe, needing three disturbances, but changing one assumption, such as which output you look at, brings it back to one. So the safety claim must state its assumptions. It is a toy simulation, not a product and not a hardware test."
Sources: [ONE_PAGE], [VS] s0.

**E4-2. Who would use this?**
"Honestly: nobody uses it yet. It is an alpha command-line tool plus teaching material. A designer would run it on their own post-synthesis netlist and read the answer as a lower bound on attacker effort under the stated model. The scope options that make the project's point are not yet in the shipped tool, only in research scripts, and per-cycle input is a TODO."
Sources: [DOS] 9, [CO] risk 3, README 'Not in the shipped tool'. R24 (agent searches) found hardware projects mostly gate on scripts; I did not read it.



**E4-5. Show me on a whiteboard the one idea you understand best.**
Source: [ODS] 1 to 2, [RE-RAN] worked_example.

**E4-6. What went wrong? What would you not do again?**
Sources: [VS] D8, [VER] s5, [CO] s2.

**E4-7. How long to run, how reproducible?**
"Quickstart on a copy: the three headline commands take seconds, `make reproduce` about 25 seconds, `make check-reproduce` compares with an expected table of 36 rows. Verdicts are tied to apt Yosys 0.33, so another Yosys build may not reproduce the expected file. Use a copy because make rewrites results/."
Sources: README, [DOS] 8 (RA). [RE-RAN] START.md commands.

**E4-8. How good is the testing?**
Sources: [DOS] 8 (MT); [RE-RAN] `python3 -m pytest -q tests`: all root tests passed in 26.6 s (count then lower than now). Later note (RECON3, 2026-11-20): current counts 133 root, 310 product.

**E4-9. Does it scale to real chips?**
"Teaching scale. A 2040-gate DMR AES S-box wrapper at 4 cycles found a 2-flip attack in 46 s; at 3 flips it gave no result in 250 s. The toy at 20 cycles for 3 flips takes minutes. The engine supports only AND, OR, XOR, NOT, MUX and flops, one goal port and one attacker input per design; I have not tried a boot ROM."
Sources: [DOS] 7.6, [VS] FP23. **[IDK]** beyond that.

**E4-10. What would you do with one more month?**
"Test a non-complementary state encoding; read k-FRP and the other papers fully before any novelty wording; re-derive the 32-netlist matrix with a fresh synthesis recipe; add the scope options to the shipped tool; get three real people to read the web pages, since no real person has."
Sources: [VS] s4, [CO] s5-6.

**E4-11. Which skills does this show on a CV?**
Source: file inventory; no claim on the owner's ability.

**E4-12. Licence, third-party code, ethics?**

---
## 5. The weakest 10 answers: where the owner is most exposed, and what to do before presenting
Ranked by (likelihood examiners ask) x (damage if the owner cannot answer unaided). Each has one action: practise a derivation, learn a number, or drop a claim.

2. **E1-1, E1-2, E1-12 unaided derivations.** Exposure: derivations sheet is blank; E1 will ask for the board. *Action (practise):* derivation 1 (V1 shared `ok`) and derivation 2 (V2 = 3 via complements and three bit groups; direct route 4). Number: **3** (V2 full word), **4** (direct route).
3. **E3-6 / E1-7 counting rule.** Exposure: the 6/32 versus 32/32 swing looks like a rescue; no rule is shown physical. *Action (claim to drop):* never say 'stem is physically right' or 'V2 holds in 32/32'. Number: **6 of 32 vs 32 of 32**, same netlists, only the rule differs. Practise the 3-gate fanout example.
4. **E3-10 the structural predictor (928/928).** Exposure: README/other pages may still carry the clean figure; VER shows 18 of 31 exact on multi-flip cells, 7 unsafe-direction misses, no runtime advantage. *Action (claim to drop):* do not present the predictor as validated or faster; if mentioned, say 'heuristic attack search with a sound lower bound; the solver is the reference'. Number: **92 percent overall, 58 percent when 2+ flips are needed**. Reconciled (FIX3): raw 144, 148 with '>3' read as 4, 150 after the two x-init corrections (NUMBERS.md); quote 150/163 with baselines always-1 62% and lower bound alone 83% (DA3).
5. **E2-7 / E3 "85 versus 83 gates".** Exposure: honest answer is 'unknown'. *Action:* learn the sentence 'deterministic, cones disjoint in both, difference in next-state mapping, I do not know the exact change; merging gives 1'. Number: **85 vs 83**, 2 vs 3 flips. Do not say 'caused by the Yosys version'.
6. **E1-9 / E3-4 SPICE physics.** Exposure: electronics content scored lowest by the panel (4/10 estimate); the physical 'why' of 1-to-0 sag is my inference, not in EL1. *Action (practise):* read EL1 fully and be able to say pull-up/pull-down in two sentences; rehearse 'one gate and flops, not silicon; longest dip 3 ns; never quote volts'. Number: **0 of 60** dip points flipped a flop.
7. **E2-2, E2-3 DRC/LVS honesty.** Exposure: 'magic reports errors in library cells' sounds like unclean layout; the LVS reference is built from the same netlist; the door-lock design failed top-level LVS. *Action (claim to drop):* never say 'DRC clean' or 'verified'; say 'router 0; top cell lists none; cell-definition rules are context false positives from one flip-flop test'. Number: **422 vs 422** devices (V1, netgen match). File: layout/verify/VERIFY.md.
8. **E3-5 B3 rail-dip result.** Exposure: 'V2 survives rail dips' sounds like a security result; it flips to 1 if one event can choose gates (3 gates, one per copy). *Action (claim to drop):* do not say 'survives rail dips' without 'bounded, whole-rail/hierarchy/cone domains only, selectivity unknown'. Number: **>3 under rail models; 1 under dip_subset (3 gates)**. Also not brute-force validated for V2/V5. UPDATE (FIX3): wording now carries the polarity result: under B3's 1-to-0-only rail model V1, V2 and V5 survive within the bound (V0 does not under a cone event), but a rail-wide 0-to-1 event on the three copies costs 1 event on V2 and V5 (and on V1, V0): survival depends on polarity, not on triplication; SPICE supports 1-to-0 for supply dips, EM literature reports set-to-1; selectivity is unproven; the domain is netlist hierarchy, not a physical rail. V2/V5 rail rows now have T=4, k<=2 brute-force anchors (ANCHOR); T=6 k=3 and V5 are still z3 only.
9. **E3-8 / E3-9 'independent validation' and the unbounded proof.** Exposure: it is tool-reported, uncertified, one netlist; cross-checks share the model. *Action (claim to drop):* remove 'unbounded proof' and the word 'independent' from your talk. Number: **k <= 2, one netlist, no certificate**.
10. **E3-2 novelty and prior-art.** Exposure: prior-art text was written by agents from snippets; k-FRP and FIVER unread; an examiner who knows SYNFI will ask what is different. *Action:* open SYNFI and FIRMER abstracts and one k-FRP summary yourself and learn what each does in one sentence; keep 'nothing established as new'. Number: **0 papers claimed new**; name 3 tools (SYNFI, FIRMER, k-FRP).
Near misses: E4-8 test count is stale in the docs (30 vs 98 on my copy): re-run and quote your own; E2-12 several environments are not rebuildable from the bundle.

## 6. 5-minute spoken outline (total 300 s; reads about 700 words)
| t | Seconds | Say | Evidence on screen |
|---|---|---|---|
| 0:00 | 30 | Question: if a secure-boot check is copied, does that help against a disturbed wire? Define a fault: one flipped wire for one clock tick, in a model. | docs/wow/explainer.html hero (screenshot) |
| 0:30 | 45 | V0 and V1 fall to one flip: V1's two copies end in one shared wire `ok`. Derive on the board (E1-1). | worked 3-gate picture |
| 1:15 | 75 | V2 with disjoint output bits needs 3 flips: derive (complement 0x69, three groups). Then the catch: change the goal to the accept flag, or allow input faults, or arbitrary start state and it is 1. | B2 scope table; command `glitchsat check v2.json --k 2` then `--k 3` (or screenshot) |
| 2:30 | 45 | Width of the consumer: 4-bit reader typically 1 or 2; mask 0x0F is 2, 0x4E is 3. Same design, different build: 1, 2 or 3 (180/60/24). Say you do not know the exact 85 versus 83 cause. | M1 CSV rows; E2 counts |
| 3:15 | 40 | Counting rule: stem rule 6 of 32, fanout rule 32 of 32, same netlists; I headline stem, and do not say any rule is physical. | REP table |
| 3:55 | 30 | How checked and what is not claimed: other tools agree but share the model; rail-dip, SPICE, layout are simulations and a flow demo; no hardware, no novelty, V2 not recommended. | EL1 plot / B3 matrix |

## 7. Claims in the repo an examiner could falsify with one command
Run on a copy only: `mkdir /tmp/c && cd /home/user/project && tar --exclude=handoff --exclude=layout --exclude=research --exclude=.git -cf - . | (cd /tmp/c && tar xf -)`, then `cd /tmp/c`. (`make reproduce` and `make test` rewrite results/ and tb/.) Results marked [RE-RAN] I ran this session; others UNVERIFIED by me.
| # | Claim (where) | Command (from the copy unless a research path) | Expected | Status |
|---|---|---|---|---|
| 1 | V1 falls to 1 flip on `ok` (README) | `python3 scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6` | ATTACK_FOUND, net `ok` | [RE-RAN] matches |
| 2 | V2 has no 2-flip attack, 3-flip min 3 (README) | `python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6` and `--k 3` | NO_ATTACK_UP_TO_BOUND; then min 3 in c0,c1,c2 | [RE-RAN] matches (1.6 s, 5.4 s) |
| 3 | `boot_ok` falls to 1 flip (README) | `python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1` | ATTACK_FOUND on `boot_ok` | [RE-RAN] matches |
| 4 | E2: V2 over 264 configs = 180/60/24 (README) | `python3 -c "import csv,collections as c;r=[x for x in csv.DictReader(open('research/c2/e2_variance/raw/matrix.csv')) if x['design']=='v2' and x['status']=='SOLVED'];print(len(r),c.Counter(x['min_flips'] for x in r))"` (from the project root) | 264, 180/60/24 | [RE-RAN] matches |
| 5 | REP: V2 stem min 2 x26, 3 x6; fanout 3 x32 (README) | `python3 -c "import csv,collections as c;r=[x for x in csv.DictReader(open('research/c3/rep/rep_results.csv')) if x['netlist'].startswith('v2')];print(c.Counter(x['rep_unit_cli'] for x in r),c.Counter(x['rep_fanout_pins'] for x in r))"` | {2:26,3:6}, {3:32} | [RE-RAN] matches (reads stored CSV, does not re-solve) |
| 6 | M1 mask values (ODS) | `grep -E "^0x(03\|0F\|4E\|FF)," research/c3/m1/m1_all_masks.csv \| cut -d, -f1,11` | 1,2,3,3 | [RE-RAN] matches |
| 7 | Hamming: state-only min 4, all sites 3 (DOS s12) | `python3 docs/dossier/test_hamming.py /tmp/c reference/spike_netlists/v2.json v2` | 4 and 3 | [RE-RAN] matches |
| 8 | 3-gate example: k=0 unsat, k=1 sat (DOS s5) | `python3 docs/dossier/worked_example.py` | k=0 None, k=1 SAT | [RE-RAN] matches |
| 9 | Old root-test count in README, ONE_PAGE, RUBRIC (the docs then said 30) | `python3 -m pytest -q tests` | docs said an older count | [RE-RAN] FALSIFIED as a count: all root tests passed, the tests directory had grown since the docs were written. Verdict (all pass) holds; the number in the docs was out of date (history at FIX3 time: 99 root and 139 product + 1 skipped; current 133 and 310 per NUMBERS.md). |
| 10 | 36/36 reproduce rows (DOS s8) | `make reproduce && make check-reproduce` then `python3 ci/check_reproduce.py --rerun` | 36/36 | UNVERIFIED by me this session |
| 11 | Predictor 92% exact on fresh cells (VER) | `python3 -c "import csv;h=list(csv.DictReader(open('research/c4/ver/heldout.csv')));print(sum(x['pred']==x['solver'] for x in h),len(h))"` | VER: 150 of 163 | [RE-RAN] the raw string comparison gives a lower count than VER's (VER applies the corrected x-init reruns, rerun_x.py, and caps >3 at 4). RECONCILED (FIX3, 2026-11-19): raw match count 144; with '>3' read as 4: 148; plus the 2 x-init corrections: 150 (NUMBERS.md, `heldout` check). Quote 150/163 (92%) with baselines always-1 62% and lower bound alone 83% (DA3). |
| 12 | Predictor lb sound; no false-safe (VER s3.1) | `cd research/c4/ver && python3 -I resample.py` (about 30 min of solver time per VER) | 60/60 reproduce | UNVERIFIED by me, too slow |
| 13 | B3: V2/V5 survive rail models, break with dip_subset (B3 report) | `python3 -c "import json;[print({k:v for k,v in r.items() if k in ('design','model','goal','min','status')}) for r in map(json.loads,open('research/c4/b3/matrix_T6.jsonl'))]" \| head -50` (key names UNVERIFIED: print one row first) | >3 for rail models, 1 for dip_subset | UNVERIFIED by me; rows are stored data, solver scripts `research/c4/b3/run_cells.py` need a work dir `/tmp/work_b3` |
| 14 | V0 falls to 1 with a rail_cone dip (B3) | same file as 13 | rail_cone V0 = 1 | UNVERIFIED |
| 15 | Layout: LVS matches uniquely, router 0 DRC | read `layout/v_designs/out_patched/RESULT.md` (it lists tool outputs; re-running needs the conda EDA env) | as table | not rebuildable from bundle |
| 16 | EL1: 0 of 60 dip points flip a flop Q | `python3 -c "import json;d=json.load(open('research/c2/el1_spice/fault_windows.json'));print(list(d))"` then inspect key `A_supply_dip` | held in all 60 | UNVERIFIED by me; needs ngspice to regenerate |
| 17 | Unbounded PDR proof (VS D7) | needs conda env with ABC and yosys-abc; not in bundle | PASS k<=2 | not reproducible from the bundle: examiner may call it unsupported |
| 18 | Fuzzing "0 mismatches in about 6,700 programs"; CMSIS issues | none | n/a | NOT reproducible from the repo (RA). Drop from the talk. |
| 19 | "V1 needs 2 in 31 of 264 re-synthesis configs" (README) | same one-liner as #4 with `x['design']=='v1'` | 264 solved, 233 at 1, 31 at 2 | [RE-RAN] matches |
Examiners will most easily find: #9 (stale count), #11 (two different figures), and the claims they cannot rerun (#15 to #18). Say beforehand that #17 and #18 are not in the repo bundle.

## 8. What I could not do / limits
- Did not read PROJECT_DOSSIER sections 14 to 19, THREAT_MODEL_ONE_PAGE, SE_REPORT, R22, DS or FP reports in full; the facts about them come from the viva sheet and dossier summaries. Layout facts: read VERIFY.md and RESULT.md heads only.
- Did not re-run make reproduce, PDR, sby, SPICE, layout, B3 or VER resample (time and conda envs).
- Spoken answers are my wording from the files, not rehearsed; word counts are estimates (about 110 words per 45 s).
- The physical reason for 1-to-0 sag (E1-9) and the 'false positive' reading of magic's library-cell errors (E2-2, from VERIFY.md's own conclusion) are explanations to check with the owner's electronics knowledge.
