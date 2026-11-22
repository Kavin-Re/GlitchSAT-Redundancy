# CE: external-reviewer questions and gap list
Read-only review; nothing was run or regenerated. Files read: README.md, docs/FINAL_STATUS.md, docs/report/PROJECT_REPORT.md, docs/report/review/R3_evaluator_panel.md (to avoid duplicating it, see "Overlap" at the end), dashboard/index.html text, layout/v_designs/out_patched/RESULT.md, validation/VALIDATION.md, formal/FORMAL.md (head), rtl/v0.v v1.v v2.v, layout/v_designs/flow_patched/pnr.tcl (clock/liberty lines), docs/PRIOR_ART.md and docs/report/FINAL_REVIEW.md (grep only). All numbers below are quoted from those files with their original labels; none is new.

"Best honest answer" = the best answer a student could give using only what the files support. "GAP" = no answer in files.

---
## Part 1. 25 review questions

### A. Digital design

**Q1. In V1 you `keep` the net `ok = m1 & m2`. Why is that net the single point of failure, and would a real designer ever build it that way?**
- Hard because: it tests whether the "result" is a property of the circuit or of a strawman. V1 is written (rtl/v1.v) so that the AND of the two compares is a named, preserved net. A competent designer would also duplicate the AND and the state register, or compare the sparse state against the two compares separately.
- Weak answer: "duplication is the textbook countermeasure so it should work, but the solver found it doesn't." (Treats V1 as representative.)
- Best honest answer: V1 is a deliberately minimal textbook design; the lesson is "copies feeding one shared net give no single-fault protection" (README, FINAL_STATUS). The rtl comment says `keep` stands in for a `dont_touch`. It is a teaching example, not a survey of real countermeasures. FILES DO NOT SHOW that any published design is built like V1; the claim "common textbook countermeasure" in rtl/v1.v is unsupported. Partial GAP.

**Q2. V2's boot_ok is `st == 8'h96`, an 8-input decode of the state register. Your lesson is "no single wire carries the decision". Does this wire not?**
- Hard because: rtl/v2.v ends with `assign boot_ok = (st == 8'h96)`, a shared AND tree downstream of the (unprotected) register. Your goal predicate is `boot_word == 0x96`, not `boot_ok`; a downstream consumer using boot_ok or a gate reading only a few bits of st sees a different attack surface.
- Weak answer: "boot_ok is just an output." (Ignores that a real consumer acts on it.)
- Best honest answer: the attack goal is defined on boot_word == 0x96 (PROJECT_REPORT sec. 3); the downstream decoder and the consumer of the word are out of the model. Nothing in the files argues how a real consumer would decode the word. GAP (scope of the security property is not justified).

**Q3. The state register `st` is an 8-bit one-hot-ish "sparse" encoding with Hamming distance between F0, CC, 96, 69. What are the pairwise Hamming distances, and what minimum distance is needed to detect/correct k flips? Why was 0x96/0x69 chosen?**
- Hard because: this is the coding-theory heart of a sparse FSM, and the only thing a flip-fault countermeasure can rely on. 0x96 and 0x69 are bitwise complements (distance 8); F0 vs 96 distance 4 (0xF0^0x96=0x66), CC vs 96 distance 4 (0xCC^0x96=0x5A, popcount 4), F0 vs 69 distance 4 (0xF0^0x69=0x99). So a 4-bit flip of the register could reach the target.
- Weak answer: "they are far apart."
- Best honest answer: NO ANSWER IN FILES = gap. The files never state a distance argument or check that st flips (flop Q at cycle t) stay detectable; there is no error-detection check on `st` at all (the FSM has `default: st <= st`, no error state). The model (single-cycle flip of flop Q, reg re-captured next cycle) also means flipping st is not persistent. GAP.

**Q4. The FSM has no error/lockout state and `default: st <= st`. What happens on an invalid state, and why does a fault-hardened design accept one cycle of evidence for boot?**
- Hard because: real secure-boot FSMs have an alert/terminal state; a bare hold hides a recovery question and omits redundancy on the state register.
- Weak answer: "toy design."
- Best honest answer: it is a toy 8-bit design (PROJECT_REPORT limitation 8). The files give no justification for omitting error states. GAP (design realism), cheap to state as a scope limit.

### B. Synthesis

**Q5. The same rtl/v2.v gives 85 gates under Yosys 0.33 and 83 under 0.38 and the security verdict flips (2-fault attack vs none). What is the mechanism, and is the verdict a property of your design or of ABC?**
- Hard because: it undermines the headline claim and the reviewer suspects a nondeterminism or a flow bug rather than a design property. Also, the stored "spike netlist" with MUX gates (68 gates + 8 flops) has unclear provenance.
- Weak answer: "different tool versions give different results."
- Best honest answer: "Why ABC differs between the two builds was not analysed" (PROJECT_REPORT 6.4). The honest statement is that the verdict attaches to a netlist, not to RTL, and that `keep_hierarchy` on cmp8 is the only thing preserving copies (validation/VALIDATION.md netlist B: stripped keep_hierarchy, abc merges the copies, V1 and V2 collapse). GAP for the mechanism; ANSWERED for "what to claim". The files also show the practical engineering remedy was not tried: no `keep`/`dont_touch` per output bit and no hash-pinned flow (future work 4).

**Q6. V2 costs 36 cells / 362.8 um^2 against V1's 35 / 357.8 (RESULT.md). Three comparators plus a split word cost +1.4% area. Does that not prove the redundancy was removed?**
- Hard because: three 8-bit equality comparators should be roughly +8 to +16 cells over one. Only +1 cell means either the comparators were merged in the layout flow or the netlist differs from what was analysed.
- Weak answer: "area overhead is small, which is good."
- Best honest answer: R3 raised the same suspicion. The files do not state which netlist (spike/0.33/0.38) was taken to layout, whether the three cmp8 copies survive in v2_net.v, or why the count is 36. NO ANSWER IN FILES = gap. A quick count of cmp8 instances in `layout/v_designs/out_patched/v2_pnr.v` would settle it. If merged, the layout V2 does not have the property the dashboard's Act 2 draws.

**Q7. What does `abc -g AND,OR,XOR,MUX` do to the netlist, and why is the solver's gate library (AND/OR/XOR/NOT/MUX/DFF) a legitimate model of a sky130 netlist (nand2, a21oi, dfxtp...)?**
- Hard because: the fault sites (gate outputs) of the generic netlist are not the nets or cells of the mapped sky130 netlist; a complex gate (a21oi, mux2) has internal nodes and a different number of fault sites.
- Weak answer: "same logic function."
- Best honest answer: FINAL_STATUS weak point 3 admits the solver ran on a different generic netlist from the layout. The files never map fault sites between the two. GAP: no fault-site equivalence between the model netlist and the mapped/placed one, so "the red box marks the single point of failure" is illustrative only.

### C. Timing (setup/hold, metastability)

**Q8. `sig` is an external input compared to the key and registered into `st`. Who drives it, what is its timing relative to clk, and what happens if it changes near the clock edge? Define metastability and compute a MTBF.**
- Hard because: the attack model holds `sig` constant for the whole run. A real attacker input arrives asynchronously, and an unsynchronised external signal into a flop is the textbook metastability case.
- Weak answer: "the flop will settle."
- Best honest answer: pnr.tcl uses `set_input_delay 2` against a 10 ns clock, i.e. the input is treated as synchronous; slack +7.05 ns setup / +0.519 ns hold (RESULT.md). There is NO discussion of asynchronous inputs, synchronisers, tau, T_w, or MTBF anywhere. NO ANSWER IN FILES = gap. Also the "input constant" assumption is listed as a limitation (PROJECT_REPORT 7.8) but not tied to metastability.

**Q9. Your hold slack is +0.519 ns at 10 ns. Which path, which corner, and why is hold positive with CTS but no hold buffers? What does fast-fast corner do?**
- Hard because: only tt_025C_1v80 is loaded (pnr.tcl line 5). Hold margin of about 0.5 ns on a flop-to-flop path in tt may vanish at ff, and "+7 ns setup" at 10 ns means the design has about 3 ns of logic, which carries no information about the failure margin.
- Weak answer: "slack is positive so timing is met."
- Best honest answer: RESULT.md says slack is a global-route parasitic estimate, not signoff. Single corner, single clock, 35 cells. Multi-corner not done. GAP.

**Q10. A clock glitch or a shortened pulse is the classic way to make a flop capture a wrong value. In your model a "flip" occurs on a gate output or flop Q for one cycle. How does a clock glitch map onto that, and which of your fault sites correspond to an overclocked/underpowered setup violation?**
- Hard because: a setup violation does not flip an arbitrary net, it makes a flop capture the previous (or a metastable) value on the paths with the longest delay. Those are specific nets, not all nets uniformly, and the fault is on the D-capture, not Q after the edge.
- Weak answer: "a flip is a fault."
- Best honest answer: NO ANSWER IN FILES. Faults are "modelled bit flips, not physical glitches" (README). No link between a timing violation and a chosen fault site; the model also does not include D-input faults (R3 change 7). GAP, and the single biggest electronics gap.

### D. CMOS / electronics

**Q11. Physically, what happens inside a CMOS NAND/AND gate and a D flop during a voltage-glitch or clock-glitch event? Draw the gate-level transient and say when the output flips, is missed, or is partially driven.**
- Hard because: this is the physical process the whole project names ("glitch"). The reviewer wants VTC, noise margin, propagation delay vs supply (alpha-power law), and the difference between a transient (SET) on a combinational node and an upset (SEU) of stored state.
- Weak answer: "the voltage drops so the gate outputs the wrong value."
- Best honest answer: NO ANSWER IN FILES. No SPICE of any kind, no delay-vs-VDD, no cell-level model. README and FINAL_STATUS say explicitly: "Faults are modelled bit flips, not physical glitches". The honest answer is "I did not study the physics; I modelled the logical effect." GAP, largest.

**Q12. For one sky130 cell (e.g. sky130_fd_sc_hd__and2_0 driving `ok`), what is its drive strength, delay and output capacitance, and what is the minimum glitch width/amplitude on its input that propagates (logical masking / electrical masking / latching-window masking)?**
- Hard because: electrical masking is why a one-cycle full-swing "flip" overstates what a real transient does, and latching-window masking decides whether the flop captures it. Together they decide the probability (not only the possibility) of the attack.
- Weak answer: "any glitch flips it."
- Best honest answer: NO ANSWER IN FILES. A Liberty file (sky130_fd_sc_hd__tt_025C_1v80.lib) is loaded for STA (pnr.tcl) but no cell delay/slew number is quoted or used. GAP.

**Q13. What is the difference between SEU, SET, a clock glitch, a voltage glitch, and laser fault injection, and which one is your "flip any gate output for one cycle" model closest to? What does it over- and under-approximate?**
- Hard because: the reviewer wants a justified threat model, not a name. A one-cycle full-cycle flip of any single net is an upper bound on a laser-style localised fault but is not a realistic outcome of voltage/clock glitching, which hits many nets and mostly the longest paths.
- Weak answer: "they are all glitches."
- Best honest answer: partial. PROJECT_REPORT sec. 7.8 lists absent models (stuck-at, multi-bit, clock, voltage). It does not argue which physical technique the model approximates. GAP in justification.

**Q14. What does an ESD/latch-up check or tap-cell spacing have to do with your DRC errors (nwell.4, LU.2, LU.3), and what physically is latch-up?**
- Hard because: the project explains its remaining magic errors as "missing tap" false positives; a reviewer asks you to say what latch-up is, why taps are needed, and why the rule is a real physical rule.
- Weak answer: "it's a design rule, fixed by adding taps."
- Best honest answer: VERIFY.md says the rules need a tap nearby and one cell (dfxtp_1) was re-tested with taps: no errors; other cells not re-tested; magic's count 21 vs rule-box sum unreconciled (R3 Q28). The physics (parasitic PNPN thyristor, well and substrate resistance, tap spacing) is not explained in the files. Partial GAP.

### E. Verification (SAT / BMC / PDR)

**Q15. State exactly what "no attack found for k<=2, T=6" means as a logical statement, and why is UNSAT a proof only for that unrolling? How does the BMC differ from the PDR result?**
- Hard because: bounded vs unbounded, the cost of fault-budget encoding (popcount in QF_BV), and the role of the attacker's constant input.
- Weak answer: "the solver says no, so it's safe."
- Best honest answer: good. PROJECT_REPORT 5/6.1/6.2, dashboard Act 3 and VALIDATION.md all state the bound: for T<=6 exhaustive pairs (46,056 at T=4; 103,740 at T=6); glitchsat to T=20 with k<=3 (474.9 s at 20 cycles); PDR gives "any number of cycles" for one netlist, k<=2. ANSWERED.

**Q16. Your PDR result is "PASS" from ABC with no certificate. Why should I trust it? How would you check the invariant independently? What property did the wrapper actually assert, and is it vacuous?**
- Hard because: a "proof" from one engine of a wrapper the same author wrote is only as good as (a) the wrapper's fidelity and (b) the engine. Non-vacuity requires a cover/witness at k=3.
- Weak answer: "sby printed PASS."
- Best honest answer: FORMAL.md: k=3 has an attack on the same wrapper (a sanity witness), k-induction inconclusive, no certificate exported, an error in a shared netlist-reading is not caught, yices missing, wrapper and glitchsat share semantics. Honest answer: "trusted on ABC's own check; independent re-check with a second unbounded engine (btormc/pono/yices-based k-ind) was not done." ANSWERED honestly, remedy listed as unfinished.

**Q17. Your validation simulator and the SBY wrapper were written to the same fault model by the same person/pipeline. What class of errors can they NOT catch, and give one concrete example from your design.**
- Hard because: separates "independent code" from "independent model". The strongest error class is model error: e.g. faults on the D input or on clock/reset; faults persisting longer than one cycle; faults on `sig`; faults on the observation net itself.
- Weak answer: "three methods agree."
- Best honest answer: VALIDATION.md "Honest limits": "this validates the encoding, not the fault model". Concrete example in the files: faults hit the observed net as well, and `sig` is held constant. ANSWERED.

**Q18. Mutation check: 2 of 3 RTL mutants of V2 were NOT caught (PROJECT_REPORT 5). What does that say about your verification method, and what is its coverage metric?**
- Hard because: mutation score 1/3 at RTL is a negative result about discriminating power; reviewers will ask why it is in the report and what was concluded.
- Weak answer: "the baseline was already weak."
- Best honest answer: report states "baseline already weak at 2" on the re-synthesised netlist (i.e. the mutants are indistinguishable from an already-broken design). That explanation is plausible but is a post-hoc reading; no mutation on the spike netlist at RTL level. Partial.

### F. Test / DFT

**Q19. Your designs have no scan chain. How would a scan chain change the attack surface and your result (scan-out of the key compare, scan-in forcing the state register)? What fault coverage (stuck-at / transition) do your three designs have under ATPG, and how does your fault list differ from a stuck-at list?**
- Hard because: for VLSI/DFT, the project's "fault" is a transient flip while DFT/ATPG use permanent stuck-at and transition faults. The comparison explains what the project is and is not (security fault vs manufacturing test).
- Weak answer: "DFT is a different topic."
- Best honest answer: NO ANSWER IN FILES = gap. Stuck-at is explicitly excluded (PROJECT_REPORT 7.8). No ATPG, no scan, no JTAG/test-mode discussion, no mention that scan is a known attack vector. Cheap to add with yosys + a small ATPG/fault-sim script or just the conceptual argument.

### G. Communication / coding theory

**Q20. Redundancy is error detection/correction by another name. Express V0, V1 and V2 as codes: what is the code, its distance, and why does triplication with a majority voter (TMR) need the voter to be fault-free? Is your V2 a TMR with a voter?**
- Hard because: V2 is a "triplicated compare with a split word", not majority voting; a single `ok` voter in TMR is exactly V1's flaw. A student who understands the coding view can state why bit-sliced consumption by 3 copies gives distance 2 against single faults but not 3-fault, matching the measured "min 3".
- Weak answer: "three copies are better than two."
- Best honest answer: NO ANSWER IN FILES = gap. The measured min-3 result is consistent with a distance-3-style argument but no document makes it. A short derivation (each of the three copies drives a disjoint subset of the 8 word bits; to reach 0x96 from 0x69 you need all three copies, or the word bits directly) would let the student predict 3 without the solver.

### H. Security

**Q21. State the threat model: what can the attacker control, observe, repeat? What is the attacker model's cost, and is "fewest flips" the right security metric (versus probability, number of attempts, required precision)?**
- Hard because: "minimum number of faults" ranks designs by attacker precision requirement, not by realism; a fault at a given cycle on a given net needs spatial and temporal precision a real injection tool might not deliver.
- Weak answer: "the attacker can flip anything."
- Best honest answer: the fault model is stated (PROJECT_REPORT sec. 3: one-cycle flip on any gate output/flop Q at any cycle, at most K total, attacker input free but constant, goal boot_word==0x96 with input != 0xC3). Not argued: why min-k is the metric, no cost, no repeatability. Partial GAP.

**Q22. What does your toolkit give that SYNFI/FIRMER/FIVER do not, and which claim in PRIOR_ART did you actually read in full?**
- Hard because: the project's own status says the method is covered by prior work and the full papers were not read.
- Weak answer: "mine is a SAT search, theirs is enumeration" (stated without having read FIRMER).
- Best honest answer: "nothing established as new"; README says "not a novel research result"; the possibly-new parts (minimum-fault search over several cycles with symbolic input, secure-boot case study) are unconfirmed; several prior-art claims are from abstracts/snippets (UNVERIFIED); SYNFI was run narrowly (one cycle, hand-chosen start state; two-cycle chain crashed). ANSWERED honestly. The research folder research/c2/r10_prior_art exists but was not part of this reading.

### I. Ethics

**Q23. If your tool found a real attack on an open-source design (say an OpenTitan block), what would you do, and who would you tell first? Is publishing a minimum-fault-set generator for a boot FSM dual-use?**
- Hard because: asks for a disclosure process and a dual-use judgement, not a platitude.
- Weak answer: "I would post it on GitHub."
- Best honest answer: docs/PRIOR_ART.md sec. 4 gives a process (private report via GitHub Security Advisories/security@opentitan.org, wait before publishing; policy page not opened, scope UNVERIFIED); real-design attempts found only generic upsets and "nothing to disclose" (FINAL_STATUS, REPORT sec. 6.6). Dual-use is not discussed. Partial; add one paragraph.

### J. Individual contribution

- Weak answer: "I led the project and the steps did the coding", or defending code the student cannot walk through.

**Q25. What did the tools do, and what did you decide? Name one result you did not expect and one decision you made against a tool's output.**
- Hard because: separates analysis from operating a toolchain. Yosys, ABC, z3, sby, OpenROAD, magic, netgen did the heavy work.
- Weak answer: "I ran the flow and it worked."
- Best honest answer: some decisions are recorded as the author's/integration step's: dropping the supermarket-attack thesis, the numerics/CertBound recommendation weakened by audit (FINAL_STATUS "What was dropped"), the 85-vs-83 finding, the filler-over-route flow bug (PROJECT_REPORT 6.5, workaround only). Whether these were the student's decisions is not recorded. Partial GAP.

---
## Part 2. Scores (0-10, harsh, individual ECE/VLSI project; evidence = files above)

| Criterion | Score | Why |
|---|---|---|
| Problem definition | 6 | One clear question; model stated precisely (PROJECT_REPORT sec. 3). Threat model and metric (min-k) not justified physically; goal predicate and observation net are author-chosen. |
| Electronics depth | 2 | No SPICE, no delay/VDD model, no glitch/metastability analysis, one Liberty corner used only through STA. R3 also gave 2. |
| VLSI depth | 5 | Real RTL->Yosys->OpenROAD->magic->netgen->antenna flow, LVS match, but a 35-cell block, one corner, no power/IR/CTS analysis, std-cell DRC unresolved, V2 layout may have lost the redundancy, no DFT. |
| Verification rigor | 7 | Three methods agree, exhaustive small-k, mutation, non-vacuity witness at k=3, one unbounded proof with limits stated. Held back by shared model, no PDR certificate, 85/83 unexplained. |
| Novelty | 2 | Self-declared none. A min-k loop around a SAT call; prior art not read. |
| Communication | 6 | Four-act dashboard, one-pager, slides, evidence labels; sprawl, repeated caveats, stale lines, internal process vocabulary. |
| Reproducibility | 5 | Core engine yes (make test/reproduce ~25 s); the headline V2 claim depends on a tool build; layout env 12 GB in /tmp; CI never run; no LICENSE. |

Overall: about 5/10 for an ECE/VLSI individual project, consistent with the project's own 6/10 self-score minus the electronics/defensibility risk.

---
## Part 3. The 10 largest gaps, ranked, with cheapest fix

| Id | Gap | Cheapest fix |
|---|---|---|
| CE-1 | Zero physical/electronics grounding of the central word "glitch": no SPICE, no VDD/clock-glitch transient, no mapping from a physical event to "flip net X in cycle t" (Q10-Q13). | ngspice (pip/conda, allowed) + sky130 models: one and2_0 and one dfxtp_1 testbench. Sweep (a) VDD dip depth/width, (b) clock pulse width, (c) input glitch width. Plot output vs time; report the threshold where output flips, is missed, or goes metastable. Label SIMULATED (circuit-level, not silicon). 1 to 2 days. |
| CE-3 | Headline result depends on an unexplained 85 vs 83 gate difference; layout V2 is +1 cell over V1, suggesting redundancy lost (Q5, Q6). | `grep -c cmp8` in `layout/v_designs/out_patched/v2_pnr.v` and v2_net.v; diff the two Yosys netlists; if copies merged, say the Act-2 drawing does not apply to the laid-out V2. Pin Yosys build plus netlist hash in synth.sh. Hours. |
| CE-4 | No timing-fault/metastability analysis; `sig` assumed constant and synchronous, one corner, hold margin unexamined (Q8-Q10). | From the existing OpenROAD run, report the critical path and the paths into `st`; run STA at ss and ff corners (liberty files already in the PDK); add a short MTBF derivation for an asynchronous `sig` with a 2-flop synchroniser (state tau, T_w as assumed ESTIMATED values). 1 day. |
| CE-5 | Fault-site mapping: solver's generic netlist differs from the placed sky130 netlist; "red box = single point of failure" is only illustrative (Q7). | Re-run the solver on the post-techmap sky130 netlist (yosys `read_liberty`/`dfflibmap`/`abc -liberty` then `write_json` or a cell-to-primitive wrapper), or at minimum state fault sites as cells, not nets. 1 to 2 days. |
| CE-6 | No coding-theory/hamming-distance argument for the sparse state and the split word; V2 vs TMR-with-voter not formalised; no predicted min-k (Q3, Q4, Q20). | Add a half-page derivation: pairwise distances of F0/CC/96/69, why a 3-copy bit-sliced word needs 3 faults, why 2 faults beat the re-synthesised netlist. Check the predicted minima against the measured ones. Hours. |
| CE-7 | No DFT/test content (scan, ATPG, stuck-at vs transient fault list) (Q19). | Run yosys `scan`-style insertion or a conceptual section plus a small stuck-at fault simulation using the existing netsim.py with a "stuck" mode; show scan as an attack path. 1 day. |
| CE-8 | Cost/benefit missing: V0/V1/V2 area, delay, power and fault resistance never tabulated together (RESULT.md quotes areas only; Q6). | One table from existing OpenROAD logs plus `report_power`, three designs, same die; add area/delay vs min-k. Hours. |
| CE-9 | Verification shares model/code; PDR uncertified; k>=4 and non-constant `sig` untested (Q16, Q17). | Re-run the k=2 proof with a second unbounded engine (btormc/pono or k-induction with an auxiliary invariant) or export ABC's invariant and check it with z3 on the transition relation; add a non-constant `sig` variant bounded to T=6. 2 days. |
| CE-10 | Threat model and ethics shallow: min-k not argued as a security metric, no mention of dual-use, only one disclosure paragraph (Q21, Q23). | One page: attacker capability table (voltage, clock, laser, EM), which model each approximates, and why min-k is a proxy for required precision; add a dual-use paragraph. Hours. |

---
## Part 4. Electronics and VLSI content that would most raise the score (concrete, ordered by return)

1. **SPICE glitch study of two cells (CE-1)** is the single biggest lift: Electronics 2 to about 6, Individual defensibility +1, Problem definition +1. Specifics: ngspice with sky130_fd_pr models or extracted v1_ext.spice sub-blocks (the project already has `v1_ext.spice` and `v1_top.spice` in layout/v_designs/out_patched/, extracted from layout, so a post-layout SPICE of the actual `_20_` and2_0 that drives `ok` is feasible). Measure: VDD droop depth x width map of when the `ok` net toggles; clock-high width at which dfxtp_1 fails to capture; capture of a glitch on D within the setup/hold window (and the resulting output, including a metastable-resolution time measurement). Feed the result back: pick the fault sites that are electrically reachable and show the attacker needs timing precision of X ns. That turns "bit flip" into a justified, parameterised fault model.
2. **Timing analysis at multiple corners (CE-4)**: ss/tt/ff STA of the three designs, path report to `st` bits, setup/hold slack vs clock period down to failure; an overclock sweep (reduce the period until setup fails) in gate-level sim with SDF back-annotation, showing which flops fail first. This is a physical-style fault injection that the existing flow can produce with iverilog + sdf from OpenROAD. Raises VLSI 5 to 6 or 7.
3. **Metastability and synchroniser calculation (CE-4)**: tau, T_w extracted from the SPICE flop (or quoted and labelled), MTBF for a 1- and 2-flop synchroniser on `sig`. Short, examinable, directly relevant to the input assumption.
4. **Post-synthesis, mapped-netlist fault model (CE-5)** run on the sky130 cells so the solver, the layout and the red box refer to the same objects; show whether redundancy survives mapping (CE-3).
5. **Power/area/delay cost table (CE-8)** and `report_power`/IR-drop of the PDN, to state the price of protection as an engineering trade-off.
6. **DFT view (CE-7)**: scan chain insertion as both a test method and an attack path.
These are all software-only with open tools already allowed by the rules (ngspice from conda/pypi, sky130 PDK already present in the layout env). Hardware-level glitching (ChipWhisperer or ring-oscillator droop on an FPGA) would add the most physical credibility but needs hardware and is out of scope.

---
## Overlap with R3
R3 (docs/report/review/R3_evaluator_panel.md) already lists 40 questions and a scorecard (overall about 6/10; electronics 2). This file adds: the V2 `boot_ok` decode and goal-predicate scope (Q2), Hamming-distance/coding view of the sparse state and TMR (Q3, Q20), the +1-cell V2 layout vs three comparators check as a concrete grep (Q6, CE-3), metastability/MTBF and corner/hold (Q8-Q9), electrical/latching-window masking (Q12), SET vs SEU vs laser model mapping (Q13), latch-up physics (Q14), DFT/scan (Q19), min-k as a security metric (Q21), dual-use (Q23), and concrete SPICE experiments reusing the existing extracted layout netlists. I did not run anything; scores are judgements on the files, and the claim in Q6 that V2 may have lost its redundancy in layout is an inference from RESULT.md cell counts, not a measurement.
