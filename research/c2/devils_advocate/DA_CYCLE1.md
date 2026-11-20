# DA_CYCLE1: devil's advocate review of the current direction

License: UNDECIDED. Working title TBD. Written 2026-11-19 by the devil's-advocate agent. Labels: MEASURED = I ran it in this session (command/file given); UNVERIFIED = not tested; ESTIMATED = my reasoning/cost guess.
All experiments ran on a COPY: /tmp/work_da/project (apt Yosys 0.33; conda Yosys 0.38+92 from env `formal`, binary /tmp/mm_root/envs/formal/bin/yosys; z3 5.4.1). Scripts and raw outputs are copied to `research/c2/devils_advocate/experiments/`. Nothing in results/ or any project file was touched. All faults are modelled bit flips on toy 8-bit designs; N = 6 cycles unless stated; nothing physical.

## 0. Experiment results first (they change the argument)

| # | Question | Result (MEASURED) | Files / command |
|---|---|---|---|
| E1 | Does the V2 verdict depend on the synthesis recipe more than on the Yosys version? | Yes. 32 V2 netlists (2 Yosys builds x {plain, opt} x 8 ABC scripts): unit-weight min flips = 2 in 26 of 32, = 3 in 6 of 32 (all six are 0.38 + plain flow + an ABC script that maps the same way). So "V2 holds against 2 flips" is the MINORITY outcome (19 percent). V1: min = 1 in 32 of 32. Ordering V1 (1) < V2 (>=2) holds in 32 of 32 pairs. | `experiments/gen.sh`, `experiments/run_abc_matrix.py`, `experiments/results.txt` |
| E2 | Do redundant copies get merged by synthesis for V1 too? | Not with the project's own flow (keep_hierarchy until after abc): V1's two compare cones are 9 gates each with 0 shared gates, in 0.33 and 0.38, plain and opt (`experiments/cones.py`). BUT with a flat flow (keep_hierarchy removed, `synth -flatten`) the copies are merged: with `abc -fast -g AND,OR,XOR` V1 and V2 become the SAME netlist (85 gates each, identical cell counts 39 AND/30 OR/16 NOT, both builds) and both have min flips 2; with `abc -g AND,OR,XOR,MUX`, V1 = V2 = 51 gates (0.33) or 59 gates (0.38) and both break with ONE flip. So redundancy erasure is not specific to V2; a flat flow can make "duplicated" and "triplicated" designs indistinguishable. | `experiments/run_flat.py` (flat netlists were in /tmp/work_da/x3; regenerate with the command line in section 5) |
| E3 | Is the "net-build dependence" dominated by the unit weight of a stem flip? | Yes. Re-solving with a stem flip costing its fanout (= flipping every branch) gives V2 min = 3 on ALL 32 netlists (V1 = 2 on all 32). Forbidding every net with fanout >= 2 gives the same (V2 3, V1 2) on the 7 netlists I tried. So the 2-flip attacks on V2 exist only because one flip of a net with fanout 2 or 3 is counted as one fault. The 0.33/0.38 "contradiction" is a consequence of the fault-model weighting, not a deep tool effect. | `experiments/weighted.py`, `experiments/matrix.py`, `experiments/matrix.txt` |
| E4 | Does a simple structural check (no solver) find the weak spots? | Partly. Unit-capacity min vertex cut from `sig` to `boot_word` (my own 40-line max-flow, `experiments/cut.py`): V1 = 1, V2 = 3 on all 64 netlists. It reproduces the ranking and V1's single point of failure (min flips 1), and equals the fanout-weighted V2 value (3) but NOT the unit-weight solver answer on 26 of 32 V2 netlists (solver 2). It is not a sound bound (flipped nets still carry sig-dependence the attacker can exploit by choosing sig; the 2-flip attacks are not cuts). Verdict: a structural check catches "one shared wire decides" instantly and finds V1's problem; it does not replace the solver for the V2 case. | `experiments/cut.py` |
| E5 | Does a time-varying attacker input change the minimum? (A4 item 1) | No change at N = 6 for V0, V1, V2 plain/opt 0.33 and 0.38 (mins 1,1,2,3,2 as in the constant-input runs); V2 plain 0.38: min 3 at N = 8 and N = 10 with per-cycle free input vs. (constant input) no attack at k=2 for N = 8 and 10. Patched copy of glitchsat, not independently validated; V2 plain 0.38 only beyond N = 6. | `experiments/glitch_tv.py`, `experiments/run_timevarying.py` |
| E6 | Is a solver needed at all at this scale? | Each k<=3, N=6 solve took under 1 s here. UNVERIFIED claim that brute force suffices; the project's own `validation/` already enumerated all 2-flip sets exhaustively (46,056 at T=4, 103,740 at T=6, per STATE.md). The solver's real value starts at k>=3 and N>=8 (475 s at N=20, k=3 for V2 spike). | STATE.md (not re-run by me) |
| E7 | Which fault nets are the 2-flip attacks on V2? | Nets with fanout 2 or 3 (ABC-introduced shared AND/OR stems, e.g. fanout 2 `$abc$275$new_n74_`, fanout 3 `$abc$275$new_n58_` in 0.33 plain). The attack is not on a net named in the RTL. | `experiments/names.py` output, section E1 run |

Caveats on all of the above (ESTIMATED importance): the same three project-authored designs; only N = 6 for most; two Yosys builds; my fanout weighting counts output-port uses as fanout; I did not test stuck-at, flop-hold or clock-glitch models; I did not test the sky130-mapped netlist; I did not re-check the PDR proof.

## 1. Alternative directions (at least four)

### ALT-A. Synthesis-provenance linter ("did my redundancy survive synthesis?")
- What changes: the product stops being "find the min flips" and becomes a diff/lint: given RTL plus a synthesis recipe, report (i) whether duplicated/triplicated logic survives as disjoint gate cones (structural cone-overlap, 20 lines, E2 `cones.py`), (ii) the structural min vertex cut (E4), (iii) the solver min only when asked. Output: "intended redundancy 3, structural 3, effective under unit-weight flips 2, tool build and recipe recorded".
- Evidence that would favour it: E1/E2 (verdict depends on recipe and flatten setting, V1 and V2 become identical netlists under a flat flow); SYNFI paper's own motivation that synthesis optimises redundancy away (R1, OPENED); cone overlap and cut are fast and need no solver.
- Cheapest experiment (<=1 h, mostly DONE): E2 + E4. Remaining 30 min: run the linter on a 4th design (e.g. a majority-voted 3-copy compare with a real voter) and see whether cut/overlap predicts solver min on it.
- Cost: LOW (about 1 day to productise). Risk: "lint for redundancy removal" is plausibly known (SYNFI paper, fault-resistant partitioning); novelty still NOT established.

### ALT-B. Fault-model sensitivity as the headline (replace "shared-wire lesson" by "the lesson depends on how you weight a stem flip")
- What changes: the central claim becomes: the minimum-flip number is a function of the fault model's counting rule; under stem-flip = 1 fault V2 is netlist-fragile (2 or 3); under stem-flip = fanout (branch faults) V2 is robustly 3 and V1 is 2 on all 32 variants. Report both columns always; compare with stuck-at/flop-hold models.
- Evidence that would favour it: E3 (26 of 32 V2 verdicts change with weighting alone; netlist variance vanishes). Favoured further if a third model (flop-hold on clock glitch) also reorders the designs.
- Cheapest experiment (<=1 h): extend `weighted.py` with a flop-hold fault (flop keeps previous Q in cycle t) and a "k faults must be in the same cycle" variant; rerun matrix. Cost LOW-MEDIUM (a day in the engine). This is the strongest answer to A4 item 4 and to the panel's "is a flip what a glitch does" question.
- Risk: moves the project from "tool + lesson" to "model-sensitivity study"; weaker as a product, stronger as an ECE/VLSI viva story.

### ALT-C. Education tool only (drop product face and layout)
- What changes: ship the dashboard plus a 3-design lab sheet ("break V0, V1, V2 in your browser/CLI, then re-synthesize with one changed ABC flag and watch V2 break") with expected answers from E1/E2 as the exercise; remove SARIF/JUnit/pip-CLI/threat-config items and layout work from the plan.
- Evidence that would favour it: R1 says the strongest demand evidence is education (UNSW labs use Yosys JSON; OPENED/SNIPPET per R1); no practitioner demand evidence found (R1 caveat); examiner weighting in A4 item 6; E1/E2 give a ready-made exercise whose answer a student can verify in 10 minutes.
- Cheapest experiment (<=1 h): hand the 1-page lab to one person unfamiliar with the project (the owner or a colleague) and time how long reproduce-and-explain takes; UNVERIFIED whether the owner has a test subject. Cost LOW (reuses existing artefacts); product value is deliberately small.
- Risk: gives up the pip-CLI / CI product ambition the owner stated ("like a product as well").

### ALT-D. Smaller sharper claim: "ordering holds, thresholds do not"
- What changes: stop claiming any binary "V2 resists 2 flips"; claim only: across 64 synthesis variants the ranking V0 <= V1 < V2 never reversed (E1: 32 of 32) while the absolute threshold moved between 2 and 3; give the matrix as the central table. Treat the PDR proof as a footnote about one netlist.
- Evidence that would favour it: E1, E3 (min V2 under stem weighting is 3 everywhere, 2 under unit weighting in 26/32).
- Cheapest experiment (<=1 h): extend the matrix to 3 more designs (e.g. V1 with 3 copies and a majority voter, V3 = parity-protected state, V0 with sparse state) and see whether the ordering survives. Cost LOW. Risk: with only project-authored designs the ordering claim is weak evidence (confirmation bias in design choice).

### ALT-E. Different fault model as the headline (time, clock, correlated)
- What changes: replace single-cycle flips on one net by (a) multi-net correlated flips (a voltage glitch hitting several nets in one cycle), (b) flop-hold (clock glitch), (c) stuck-at-0/1 for one cycle.
- Evidence that would favour it: A4 item 4; panel Q2/Q3; E3 shows the verdict hinges on the counting rule so the model matters more than the tool. Disfavoured by E5: time-varying input did NOT change the minima, so that sub-direction is low-yield.
- Cheapest experiment (<=1 h): add flop-hold sites (`D <- Q` for one cycle) as extra F variables in a patched `build`, rerun V0/V1/V2. Cost MEDIUM (model design plus validation of the new encoding by a second implementation). Risk: no physical evidence to justify any choice of model; "SPICE bridge" cannot settle it.

### ALT-F (for completeness). Switch project identity to the CMSIS numerics audit ("CertBound")
- Not recommended: the headline finding (sqrt_q15 7.15 LSB) is already known upstream (STATE.md), the audit is a generic-C build, and the owner never chose it. Listed only because the lead made a reversible decision about it.

## 2. The 10 most damaging attacks on the current claims and plan (ranked)

1. **The central lesson is partly an artefact of the fault-model weighting (A4 item 4, now MEASURED).** E3: under "stem flip costs its fanout" V2 is min 3 on all 32 netlists and the 0.33/0.38 "tool dependence" disappears. The README sentence "held against 1 and 2 flips on one netlist and not on another, so the answer depends on the exact synthesized netlist" is only true for the unit-weight model. A reviewer with this experiment can say the headline is a counting convention. Severity: highest. Fix: report both weightings next to every verdict.
2. **"Shared wire does not help" is not what breaks V2.** V2 has no shared RTL wire among result bits; the 2-flip attacks use ABC-introduced stems (E7). The lesson as stated in the README ("copies that share one wire do not help") is true of V1 (the kept `ok` net) but the V2 behaviour is a different mechanism (stem sharing created by logic optimisation after the copies). Two mechanisms are folded into one sentence. Severity: high.
3. **The V2 "hold" is the minority synthesis outcome and the "fix" is fragile (E1: 6/32).** Presenting V2 as "fix it" in act 2 and the PDR proof in act 3 both lean on one netlist that appears in 19 percent of my variant matrix. Severity: high. The ordering claim (V1 < V2) survives; the absolute claim does not.
4. **The flat-flow collapse (E2) is not in any document.** A natural, mainstream synthesis flow (flatten, no keep_hierarchy) turns V1 and V2 into the same netlist. The project's flow is the one that preserves copies by construction (keep_hierarchy, mapping before flatten) so the "ordinary" outcome is hidden by script choice; the `opt` flow of synth.sh still goes through keep_hierarchy. Severity: high. This is also the strongest support for ALT-A.
5. **Novelty and prior-art claims rest on abstracts (PRIOR_ART, R3 Q8, Q9).** uArchiFI (Yosys + SMT + BMC + counterexample, per R2) is described as the main overlap risk; full papers for SYNFI/FIRMER/FIVER unread. "Minimum-fault search with a symbolic input" may simply be uArchiFI's iterator loop or FIRMER's min/max fault count. Severity: high for any claim beyond "reproduces and teaches". The current docs already hedge; the risk is the product face implying differentiation.
6. **Product face has no demand evidence (A4 item 6; R1 caveat) and lowers the individual-project value.** SARIF/JUnit/pip CLI/threat config cost the same hours as ALT-B/ALT-D, which answer examiner questions directly. A SARIF report of a toy 8-bit design has no consumer. Severity: medium-high.
7. **Validation shares the model and netlist reader (R3 Q13/Q14; STATE.md).** The independent simulator, boolector and sby all encode the same flip model and read the same Yosys JSON. E3 shows the model's counting rule moves answers; none of the validation touches that. Also the PDR certificate is ABC's own (R3 Q19). Severity: medium-high.
8. **Solver not needed at the scale shown (E6).** All headline minima (k<=3, N=6) solve in under a second and were exhaustively enumerable; the solver adds value only past N=8, but those deep runs only exist for the spike V2 netlist and have no independent check above 6 cycles. A skeptic says a 60-line brute force would have produced the same table. Severity: medium (UNVERIFIED that brute force reaches N=6 in Python; validation reports it done).
9. **Solver netlist vs layout netlist mismatch (A4 item 3, still unanswered).** Four-act story implies one design. E1 shows the verdict moves with the ABC script; the sky130 mapped netlist is another ABC script again. Without running the solver on the mapped netlist the "lay it out" act supports nothing about the attack. Cheap to settle (see recommendations); not yet done. Severity: medium.
10. **Constant attacker input in the headline proof (A4 item 1) is NOT the damaging problem I expected.** E5 (MEASURED, patched copy) found no change for the five netlists tested; the attack here consumes the input at one cycle. I rank it 10 because the plan puts 4 hours on it; one hour suffices to close it with this experiment plus a PDR re-run with a free per-cycle input (UNVERIFIED: the PDR wrapper was not modified). The residual risk: a design that re-samples input after a state-reset glitch.

(Not ranked but note: the electronics bridge is a score-2 item and A4 item 5 says to keep it labelled SIMULATED; SPICE cannot choose among fault models, so it should not be sold as validation. Layout polish: agree with A4 item 8, stop.)

## 3. PIVOT or STAY? Recommendation: STAY on the project, PIVOT the claim and de-prioritise the product face.

Reasoning:
- The engine, tests, reproduction and validation are sound enough (many re-runs by others) and do not need replacing. A different project would restart at zero for the same 6/10 ceiling (novelty 3 is a ceiling set by prior art, not by direction).
- What the evidence says is wrong is the framing, not the tool: the headline "copies sharing one wire do not help; V2 holds or not depending on the tool build" is, per E1-E3, better stated as: (a) the number of flips needed depends on synthesis recipe AND on how a stem flip is counted; (b) the ordering V0 <= V1 < V2 was robust in all 64 netlist variants; (c) a flat flow can erase redundancy entirely. That is a sharper, more defensible, more viva-friendly claim (ALT-D + ALT-B + ALT-A in one table).
- Product face: keep only what is nearly free (pip install, JSON report, one CLI that records tool build and recipe). Cut SARIF/JUnit/threat-model breadth until a named consumer exists; spend the hours on the weighting-sensitivity table (new column in every verdict), flop-hold fault model, and the sky130-mapped netlist solve (A4 items 3, 5, 6).
- Layout: stop polishing; reuse existing layout only as the "resistance versus area" row.

What would change this recommendation to PIVOT: (i) if a 4th and 5th design (voted copies, parity state) show the ordering V1 < V2 failing under both weightings, then drop "ranking" and keep only provenance (ALT-A as the whole product); (ii) if the owner (not agents) says the project is graded mostly on teaching, go ALT-C; (iii) if the full-paper read finds that uArchiFI/FIRMER already report min-fault attack sets with synthesis-sensitivity, drop any differentiation claim and describe the work purely as an independent reproduction with a teaching goal.

Cheapest actions to carry out (each <=1 h, ESTIMATED): add the fanout-weighted second column to `reproduce` output; run the solver on the sky130-mapped V2 netlist; add the flat-flow netlists to the expected-results table and state the collapse; re-word the README sentence as two mechanisms (kept shared net in V1; optimiser-created shared stems in V2); keep "for a constant attacker input" on the PDR proof but note E5.

## 4. What I could not do / UNVERIFIED
- Did not run SYNFI, the PDR proof, the layout flow or the sky130 netlist (UNVERIFIED for my claims about them).
- E3's fanout weighting is one modelling choice of mine; the right physical weighting is unknown and cannot be decided by simulation alone.
- E5 patch (`experiments/glitch_tv.py`) was not cross-validated by a second implementation; beyond N=6 only V2 plain 0.38 tested.
- E1 used the project's designs and two Yosys builds only (0.33 apt, 0.38+92 conda); I did not find why 0.38 differs in the plain flow (cause not isolated; both differ at the abc step because the netlists differ only after abc, MEASURED in cones/CSE counts, but the ABC internal reason is UNVERIFIED).
- I did not validate that all solver verdicts in the 64-netlist matrix agree with an independent simulator.
- Wall times ignore parallelism; all runs were single-process, each under 1 s except where timeouts were set.

## 5. How to reproduce (copies only; do not run in the project tree)
```
cp -r /home/user/project /tmp/work_da/project   # tar --exclude=handoff --exclude=layout was used
cd /tmp/work_da/project
bash ../x4/gen.sh                    # (= experiments/gen.sh) 64 netlists, two Yosys builds
python3 ../x4/run.py                 # (= experiments/run_abc_matrix.py) unit-weight min flips
python3 ../x5/matrix.py              # fanout-weighted min flips (experiments/matrix.py, weighted.py)
python3 ../x5/cut.py <netlist.json>  # structural min vertex cut
# flat flow: yosys -p "read_verilog rtl/v1.v; hierarchy -top v1; setattr -mod -unset keep_hierarchy *; synth -flatten -top v1; dffunmap; abc -fast -g AND,OR,XOR; opt_clean; techmap; opt_clean; write_json out.json"
```
