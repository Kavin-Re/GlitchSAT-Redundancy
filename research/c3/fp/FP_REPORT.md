# FP REPORT: First-principles rebuild + 30 Socratic questions
Read-only review; only this file was written. Working title TBD; licence UNDECIDED. Nothing was run: I read files only.
Labels: [S] = sourced from our files (file named); [I] = inferred by me (general textbook physics/logic or my reasoning, NOT measured in this project). Files read [S]: AGENT_RULES.md, CHECKPOINT.md, README.md, docs/FINAL_STATUS.md, docs/dossier/PROJECT_DOSSIER.md (parts 0-9 and the brief's tail), docs/dossier/VIVA_SHEET.md, research/c3/bc/BC_REPORT.md (pass 1), research/c2/b1_faultmodels/B1_REPORT.md. NOT available when I read: reports of E2 (variance), B2 (scope), EL1 (SPICE); they had only scripts or raw data, so any statement about them is "unknown to me".

---
# PART 1. FIRST PRINCIPLES

## 1.1 What a fault is, and why a glitch flips a bit  [I unless noted]
A digital circuit is a set of wires carrying voltages that are *read* as 0 or 1 only at one moment per cycle: the clock edge, when each flip-flop (flop) samples the wire at its D input. For the sample to be right, the wire must have settled to its correct level a little before the edge (setup time) and hold it a little after (hold time). Between edges the wires are allowed to be wrong.
So a "fault" at gate level is: *at the moment a flop samples, some wire does not carry the value the logic says it should.* Four physical ways to cause that (textbook; none was done or measured here):
- Supply: lower the supply voltage briefly (droop). Transistors switch slower, a signal path takes longer than the clock period, and the flop samples the old or a half-changed value. The wrong value is usually a stale one, not a random one.
- Clock: shorten one clock period (or add an extra edge). Same effect: the edge arrives before the data has settled. Also a flop may miss an edge (the project's `flop_hold` and `clock_skip_all` models).
- Electromagnetic (EM): a nearby coil induces a current/voltage in a wire or the power grid; a short pulse may appear on a wire, and if it overlaps the sampling window the flop captures it.
- Laser: light makes a transistor junction conduct, which injects charge and creates a short pulse (a "single-event transient") on that node. Same latch condition as EM.
Common thread [I]: the physical event is an analog disturbance; it becomes a *bit* error only if it overlaps a sampling window or is long enough to propagate. Supply and clock glitches hit *many* wires at once (they are global); EM and laser can be local. The "flip one wire for one cycle" fault of this project is a deliberate, clean abstraction: the pulse is assumed to be captured and to be the exact opposite of the right value [S: VIVA Q3; docs/report/PROJECT_REPORT.md s7 item 1 as cited there]. No mapping from physics to that abstraction was built [S: VIVA Q3]. EL1 (SPICE, in flight) is the intended bridge, result not read by me.

## 1.2 What "minimum fault set" means  [S for definition; I for the graph picture]
Ask: "what is the smallest number K of wire-flips, placed anywhere in any of T cycles, with the attacker also choosing the input, that makes the boot word equal 0x96 while the input is not the key?" [S: PROJECT_DOSSIER s1]. K=0 is the fault-free chip: it must not accept a wrong key, so K>=1 always. The minimum is a property of (circuit, fault rule, goal, input rule), not of the circuit alone.
Picture [I]: every wrong-key input is blocked by some logic. A fault set "defeats" the blocking logic when, after the flips, the output equals 0x96. A set of wires that *every* path to the output passes through is a single point of failure (graph term: a cut), so K=1 if such a wire exists. The minimum is roughly "how many independent wires must be corrupted so all blocking paths are broken", reduced further by logic masking (some flips are cancelled by later gates) and increased by timing (a flip is only a flip if it exists at a clock edge).

## 1.3 Why redundancy helps or does not  [S for results, I for explanation]
Redundancy helps only to the extent that the copies are *independent in the way the attacker acts*. Three ways it fails:
1. Common-mode wire: two copies feed one AND that decides the state. Flip that AND's output and both copies are bypassed. That is V1: break with 1 flip [S: README; worked example dossier s5: "every 1-flip attack uses f3 (the shared wire)"]. This is pure logic, true on any netlist that has that shared wire, independent of physics.
2. Synthesis merges the copies: a logic optimizer sees two identical comparators and may share gates; redundancy written in Verilog is not necessarily redundancy in gates. This is a plausible reading of why V2 held on some netlists and not others [S: FINAL_STATUS: "synthesis shares logic across the result word"; the exact cause inside Yosys/ABC is NOT located, VIVA Q19]. My reading that sharing creates the 2-flip attack's shared stems matches DA_CYCLE1 (attacks use shared stems of fanout 2 or 3 introduced by ABC) [S via FINAL_STATUS, DA-agent MEASURED, not re-run].
3. Correlated physical faults: a global glitch (supply, clock) hits all copies at once, so counting copies assumes an independence the physics may not give [S: VIVA Q21; B1: cone_flip_exact and hood_flip_exact make spike V2 fall with 1 event].
Why it can help: if each copy drives its own output bits and no single wire decides, the attacker must corrupt the output bits of enough copies separately, so K rises (V2: 3 flips on the spike netlist) [S].
Note on V2 [S: dossier s6]: V2 has no vote. It is "three comparators writing their own bits", not classical TMR (majority voting). So "V2 shows redundancy helps" is a narrower statement than "TMR works".

## 1.4 What a bounded SAT/BMC verdict really says versus a proof  [S for facts, I for plain wording]
- SAT: the solver found a concrete fault set (nets, cycles, input). This is an *existence proof by example*, checkable by replay in a simulator [S: 13/13 witnesses replayed]. Strong, but only inside the model.
- UNSAT at bound (k<=2, T cycles): it is a *proof of a narrow statement*: "on this netlist file, with this fault rule, this goal, this input rule, no set of <=2 flips within T=6 cycles reaches the goal". It says nothing about cycle 7, 3 flips, another netlist, another goal or another fault type [S: glitchsat NOTE; dossier s4]. The proof's correctness also rests on the encoding being right (cross-checked by own simulator, boolector, sby: "checks the encoding, not the model") [S: VIVA Q11-12].
- PDR "PASS" (unbounded): ABC searched for an inductive invariant, so no time bound. Same narrowness in model/netlist/goal. Not independently checked: ABC checks its own invariant, no certificate exported, k-induction inconclusive, not replicated by the critic [S: VIVA Q17; FINAL_STATUS CT-5].
- Neither is a statement about silicon. The word "proved" is only legitimate with the solver output and its bound attached [S: AGENT_RULES].

## 1.5 Derived from basics vs chosen by us  [S where file cited; I for judgement]
| Item | Derived (logic/physics gives it) | Or a convention WE chose | Evidence |
|---|---|---|---|
| Shared decision wire is a single point of failure | DERIVED (logic; any netlist with it) | | dossier s5 worked example |
| SAT answer given the model, bounds, netlist | DERIVED (mathematics; cross-checked by 4 routes) | | VALIDATION.md |
| Hamming distance of {F0,CC,96,69} = 4 so 4 flips on state-flop Q only | DERIVED (arithmetic) | | dossier s11 |
| Fault = XOR flip of a gate output or flop Q for one cycle | | CHOSEN (abstraction of a pulse that is captured) | glitchsat docstring; VIVA Q3 |
| One stem flip = ONE fault, whatever the fanout | | CHOSEN counting rule. The rival rules (fanout-weighted, branch-only) give different V2 verdicts | DA_CYCLE1 E3; B1 |
| Goal = 8-bit word `boot_word == 0x96` (not the flag `boot_ok`) | | CHOSEN goal; with the flag goal V2 breaks with 1 flip | README (CT-1) |
| Input `sig` free but constant, != key; not a fault site | | CHOSEN input treatment; E1 extends to free per-cycle input under "key never presented"; the weaker spec breaks every design with 0 flips | E1 via FINAL_STATUS; B1 input rows |
| Known power-up state | | CHOSEN | README scope |
| Clock and reset have no fault sites | | CHOSEN | B1 "NOT covered" |
| Accept code 0x96 and fail code 0x69 are bit-complements | | CHOSEN encoding; flip-all breaks every design because of it | BC row 5 (EL2-3) |
| Netlist = the synthesized file (tool build, recipe) | | CHOSEN/ACCIDENTAL: Yosys 0.33 vs 0.38 vs 8 ABC scripts change the gate list | FINAL_STATUS |
| T=6 cycles, cap k<=3 | | CHOSEN (solver cost: V2 k=3 at T=20 = 475 s) | DEEP_RESULTS via VIVA Q5 |
| "V2 verdict depends on netlist and counting rule" | PARTLY DERIVED, PARTLY BY CONSTRUCTION: different counting rules are different metrics, so different numbers are guaranteed; the finding has content only if one rule is justified physically (BC row 3) | | BC_REPORT |
Counting-rule reading [I]: a physical glitch on a wire's driver reaches every branch of that wire, so "one stem flip = one fault" matches a driver/node upset; "flip one branch pin" needs a defect at the receiver or a very local pulse; "cost = fanout" is stricter than either for a node upset. B1 shows V1 rises 1 to 2 under reset/branch models and V2 stays 3 [S]. I could not find in our files an argument ranking these rules; neither can the owner say aloud which is "right".

## 1.6 ONE-PAGE "WHAT IS ACTUALLY TRUE HERE" (owner to say aloud; edit into your own words)
1. "I modelled a glitch as a clean one-cycle flip of one wire. A real glitch is analog and often hits many wires; I built no map from physics to my model. Nothing here used hardware."
2. "Given that model, the question 'how few flips make the toy boot circuit accept a wrong key' is pure logic, and I get exact answers with a SAT solver: a flip set if one exists, or a statement that none exists up to a stated number of flips and cycles."
3. "Copies of a check that end in one shared wire do not help: flip that wire. That follows from logic, not from my tool. V0 and V1 break with 1 flip."
4. "The triplicated design V2 needs 3 flips on the stored netlist, but the same Verilog synthesized with Yosys 0.33 needs only 2, and across 32 re-synthesis recipes an agent measured 2 in 26 and 3 in 6. So V2 is a specimen showing a verdict belongs to a netlist, not a design, and not a recommended fix."
5. "Part of that spread is my counting rule: I count a flip of a shared wire as one fault. If a wire with fanout f counts as f faults, V2 needs 3 on all 32 agent-built netlists. I chose the rule; I cannot yet say which is physically right. I show both." (DA agent's numbers, not re-run by me.)
6. "What I checked: a second simulator, a second solver and SymbiYosys agree with my solver on the same model, and the sweep reproduces 36 of 36 rows. That checks my encoding, not the model."
7. "One unbounded proof exists, for V2 k<=2 on one netlist, from ABC's PDR. It is tool-reported, not independently certified, and I do not rest the project on it."
8. "Limits: toy 8-bit design, known start state, constant (or one-spec free) input, accept flag itself falls to 1 flip, clock and inputs not fault sites in the main model, sky130 layout never analysed by the solver."

---
# PART 2. 30 SOCRATIC QUESTIONS (6 groups x 5)
Format: Q, answer, source/label. FLAG = owner currently cannot answer (8 flags: Q4, Q7... see list at end). "WE DO NOT KNOW" is an honest answer.

## A. Definitions
**Q1. What exactly is a fault in your tool?** A one-cycle XOR on the output of a gate or a flop Q (the flop Q flip is transient on its output and does not overwrite stored state). [S: dossier s4; FORMAL.md s2 as cited]
**Q2. What is a "minimum fault set"?** The smallest K with a satisfying assignment of flips (cycle and net) plus input; found by tightening the cardinality bound until UNSAT. [S: dossier s5]
**Q3. What does "break" mean?** `boot_word == 0x96` observed at some cycle while `sig != 0xC3`. Not the flag `boot_ok`: that falls to 1 flip on V2. [S: README, CT-1] Owner can say this.
**Q4. What counts as ONE fault; which counting rule is correct? FLAG 1.** We have three rules: one stem flip (our default), cost = fanout, per-branch flip. They change V2 from 6/32 to 32/32 holding. No file argues which matches a physical event. [S: DA_CYCLE1 via FINAL_STATUS; BC row 3; B1] I (inferred): node-upset matches stem=1, but this is not argued in our files.
**Q5. What does "redundancy helps" mean as a number?** The minimum K rises. Ordering V0 <= V1 < V2 held in every variant tried. [S: FINAL_STATUS] It does not mean "secure".

## B. Assumptions
**Q6. Why is the attacker input constant; real boot data changes?** The main solver and PDR hold `sig` constant; E1 (reported, not re-run by lead) shows the same V2 k<=2 result with a fresh non-key value every cycle, under the spec "key is never presented"; under a weaker spec every design breaks with 0 flips. [S: FINAL_STATUS E1]
**Q7. Why a known power-up state; what if flops power up random? FLAG 2.** We chose it; I find no run with arbitrary initial state. WE DO NOT KNOW whether V2 k<=2 survives. [S: README scope "known power-up state"; no counter-file seen]
**Q8. Why are inputs and clock/reset not fault sites?** A modelling choice. With input flips every design needs 1 event (B1) but that mostly reflects the spec issue (flip makes input equal the key); CT-2 says input buffers as sites also give min 1. Clock/reset sites: none; `flop_hold`/`clock_skip_all` give no attack up to 3. [S: B1; README]
**Q9. Are faults independent single events?** The main model says yes. Correlated models: one event flipping a whole fanout cone or neighbourhood breaks spike V2 with 1 event; group models give 2. Groups come from netlist graph, not layout. [S: B1 matrix]
**Q10. Is "attacker omniscient" realistic?** No: it picks cycle, net and input perfectly; it gives a worst-case bound for design checking, not attack cost. [S: VIVA Q6; BC row 6]

## C. Evidence
**Q11. Why trust the solver?** Own gate simulator (about 2.1M fault sets, 0 disagreements), boolector, 13/13 replays, SymbiYosys BMC (40 pairs), `make check-reproduce` 36/36 re-run by D1. All share the fault model. [S: VIVA Q11-12]
**Q12. What does UNSAT at k=2 prove?** Only the narrow statement of 1.4. [S: glitchsat NOTE]
**Q13. Is the unbounded proof right? FLAG 3.** ABC's own invariant, no certificate, not replicated by the critic, k=3 PDR re-run returned NOSTATUS. Owner can say only "tool-reported". [S: VIVA Q16-17, FINAL_STATUS CT-5]
**Q14. Why do apt Yosys 0.33 (85 gates, 2-flip attack) and conda 0.38 (83 gates, none) differ? FLAG 4.** WE DO NOT KNOW the cause inside Yosys/ABC. Hypotheses only; E2 variance study result not read by me. [S: VIVA Q19; FINAL_STATUS]
**Q15. Does the attack exist in the sky130-mapped netlist? FLAG 5.** Unknown; the red box is matched by net name only; CT-6 found no attack at k<=2, T=6 in a separate critic simulation (not our solver). [S: FINAL_STATUS weak point 3, CT-6]

## D. Alternatives
**Q16. Why your own solver, not SYNFI/FIRMER?** They exist; SYNFI enumerates chosen fault sets and already measured synthesis dependence; FIRMER covers multi-cycle with per-cycle inputs. Our SYNFI run was thin (one cycle, hand-picked start, chain crashed). [S: FINAL_STATUS; VIVA Q26-27] Not new.
**Q17. Why not simulate the electronics, what does SPICE show? FLAG 6.** An EL1 SPICE bridge was in flight; I have not seen a report; earlier a DFF sweep was "started, not analysed". The owner cannot currently state a SPICE result. [S: VIVA Q24; CHECKPOINT; research/c2/el1_spice has scripts only]
**Q18. Why not a real majority voter (TMR)?** V2 has no vote; I find no voted design analysed. WE DO NOT KNOW whether a voted version resists more flips or just moves the shared wire into the voter (inference: the voter output is a shared wire). [S: dossier s6; I]
**Q19. Would a different state encoding change results?** Likely: accept/fail are complements, so flip-all breaks every design. A non-complementary encoding test is a proposed 1-line follow-up, not done. [S: BC row 5]
**Q20. Why cap at k<=3, T=6?** Solver cost (V2 k=3 at T=20 took 474.9 s); nothing at k>=4 beyond T=4,6 (k=4,5 run only at T=4,6). So ">3" is not "secure". [S: FINAL_STATUS, B1]

## E. Consequences
**Q21. Is V2 a design someone should adopt?** No. Specimen only. [S: BC row 1; I own reading]
**Q22. What should a designer do with the tool?** Run it on their own post-synthesis netlist, name the tool build and counting rule, treat the answer as a lower bound on attacker effort under the model. [I; consistent with VIVA "verdicts need provenance"]
**Q23. Does it scale to real designs? FLAG 7.** WE DO NOT KNOW. Largest real design tried was a 6-gate comparator; V2 k=3 at T=20 costs 475 s on about 70 gates; only AND/OR/XOR/NOT/MUX/DFF supported (async reset raised KeyError). [S: VIVA Q5; BC row 7]
**Q24. Is "2 versus 3 flips" security-relevant?** The number is not a probability or cost: it assumes the attacker can place any flip exactly. Converting to real difficulty needs fault-rate data we do not have. [I]
**Q25. What changes the headline?** A physical argument selecting one counting rule; a layout-aware correlation model; netlist-level re-check on sky130 netlist; an arbitrary-init run. Any of these could move V2 either way. [I]

## F. Meta
**Q27. What is new?** Nothing established as new. [S: FINAL_STATUS]
**Q28. Each pivot followed a finding that killed the last claim; is the surviving claim unfalsifiable?** Partly fair: "verdicts depend on counting rule and netlist" is partly true by construction (different metrics give different numbers). It is falsifiable in one place: the claim that across plausible synthesis recipes the verdict spreads (6/32 vs 32/32). A pre-registered list of counting rules before final numbers is the fix. [S: BC row 2-3]
**Q29. Which numbers did you re-run yourself?** Re-run by D1/lead: `make test` 10 passed, check-reproduce 36/36, PDR k=2 PASS, boot_ok 1 flip, 85/83 gate counts. Agent-reported, not re-run: the 32-netlist matrix, E1 free-input result, B1 matrix (36 rows checked vs independent simulator at T=4 only), the SYNFI run, fuzzing (data not in repo). [S: FINAL_STATUS, dossier s8, B1]
**Q30. What would show you the project is wrong?** If an independent simulator disagreed with a stored witness; if the PDR proof failed under a second engine; if the layout netlist gave a different min; if V2's 3-flip result vanished under a counted-by-physics rule. The first two have not happened; the last two have not been tested. [I]

## Owner cannot answer today (8 flagged)
Q4 counting rule justified; Q7 arbitrary power-up; Q13 reliability of the unbounded proof; Q14 why 0.33 differs from 0.38; Q15 sky130 netlist; Q17 SPICE result; Q23 scaling; Q26 own contribution.
Suggested cheapest remedies [I]: write a one-paragraph justification of stem=1 vs weighted (Q4); run V2 with free initial state for k<=2 (Q7); say "tool-reported, unreplicated" and move the proof to an appendix (Q13); give the 3-step "what we know" answer (Q14); run the solver on the mapped netlist or say "unknown" (Q15); read the EL1 report before the viva (Q17); state "teaching-scale only" (Q23); fill the 10-line "what I decided" list (Q26).

## What I could not do
No solver, no commands, no web. Did not read E2, B2, EL1 results (not written at my read time); did not open CRITIQUE.md in full or BC pass 2/3; section 1.1 physics is general knowledge, not from our files and not measured here.
