# DS REPORT: structured debate and dialectical synthesis
Read-only review; only this file was written. Working title TBD; licence UNDECIDED. I ran no solver and no make; every fact is read from a file (cited) and every judgement is marked [INF] (inferred). The debate voices are simulated personas written by me; they are not independent reviewers and nothing here is a human opinion.

Source files used: `README.md`, `docs/FINAL_STATUS.md`, `docs/dossier/PROJECT_DOSSIER.md` (s0-s4 only), `research/c2/b2_scope/B2_REPORT.md`, `research/c2/b1_faultmodels/B1_REPORT.md`, `research/c3/bc/BC_REPORT.md` (first part; the full file was truncated in my read), `compare/synfi_run/SYNFI_RESULT.md`, `compare/COMPARISON.md`, `handoff/CONTINUATION/CHECKPOINT.md`, `PROCESS_RULES.md`. `CHECKPOINT.md` exists only under `handoff/CONTINUATION/`.

## 0. Fact base the debaters may use (all MEASURED by other steps unless noted)
- F1. V0 and V1 break with 1 modelled flip in every cell tried (B2 matrix; B1 matrix; V1 breaks on the shared net `ok`, FINAL_STATUS).
- F2. V2, goal `boot_word==0x96`, input nets not fault sites, known power-up, constant non-key input: min 3 flips on the stored spike netlist and on conda 0.38 plain; 2 flips on apt 0.33 plain/opt and conda 0.38 opt (B2 matrix row "word noin known"). The unmodified CLI reproduces the baseline (B2 "Sanity").
- F3. Change any one assumption (goal `boot_ok`, input nets as fault sites, arbitrary non-accepting power-up state) and V2 costs 1 flip on every netlist (B2 matrix, columns `word +in`, `ok *`, `word noin nongoal`). With arbitrary power-up state and no reset every design costs 0 (B2 reading point 2).
- F4. B2's own conclusion: "V2 is NOT separable from V1 outside that one cell family" and "Never write 'V2 resists <=2 flips' without those five qualifiers."
- F5. Fault-model sweep (B1, spike netlist, V2 baseline 3): set_only, reset_only, branch_set, branch_reset stay 3; flop_hold and clock_skip_all give no attack up to 3; group models give 2; cone_flip_exact and hood_flip_exact and every input-fault model give 1. V1 rises 1 -> 2 under reset and branch models. Models are the step's modelling choices, not calibrated to any layout. Matrix gaps: branch_flip and input_branch_flip on V2 not finished (B1 "NOT covered").
- F6. 32-netlist re-synthesis: V2 min 2 flips on 26, 3 on 6; 6/32 hold against 2 flips; with fanout-weighted counting V2 needs 3 on all 32 and V1 needs 2 on all 32. This was MEASURED by step DA and "not re-run here" (README line 5; FINAL_STATUS "Synthesis recipe and counting rule"). Status: single-step, unreplicated.
- F7. V3 (B2, `rtl_v3.v`): in finished cells (boot_word goal) cost 3, including cells where V2 is 1. Many cells NOT RUN (`?`); the boot_ok goal is not like-for-like because V3's `boot_ok` is an 8-bit code; search capped at k<=3 so "3" is also V2's best case; arbitrary power-up: flipping `rst` in 3 reset cycles costs 3. B2: "does NOT show V3 secure".
- F8. Prior art: SYNFI already measured synthesis dependence (Yosys re-synthesis 3 -> 2) and a min-count by iterating the budget; FIRMER covers multi-cycle faults with per-cycle inputs; k-FRP and FIVER UNREAD; "nothing is established as new" (FINAL_STATUS "What this project is"; COMPARISON notes). SYNFI was run: it enumerates user-bounded fault sets, one-cycle, hand-chosen start state, two-cycle chain crashed, re-synthesized V2 not run (SYNFI_RESULT s1-2, and the note in COMPARISON).
- F9. Independent checks: second simulator and boolector agree on spike netlists at T=4 and T=6 but share the fault model (FINAL_STATUS; B1 validation: 36/36 rows agree, V2 only 2 of 17 models validated). One unbounded PDR proof, unreplicated (BC point 9, CT-5).
- F11. The pivoted claim was adopted after earlier claims were refuted (CHECKPOINT DECISION line; BC row 2).

## 1. The debate

Voices: THESIS (T, author's defender), ANTITHESIS (A, hostile reviewer), PRODUCT SKEPTIC (P), NON-TECHNICAL LISTENER (L), JUDGE (J). Each round: openings, rebuttals, concession list, judge's ruling. Rounds: 1 the V2 result, 2 the claim "verdicts depend on counting and scope", 3 the toolkit versus SYNFI/FIRMER, 4 V3 and what is left.

### Round 1: Does V2's result collapse?

**A opens.** The headline V2 number is a single cell of a 12-column table. Take B2's matrix: V2 costs 3 only under goal `boot_word`, input nets excluded, known power-up. Change one assumption and it is 1 flip, on all five netlists. Count the output net `boot_ok` as a fault site, which is the thing a boot ROM consumer actually reads, and one flip wins. The tool's own author wrote that V2 is not separable from V1 outside that cell family. So "triplication helps" is a statement about one cell, and the cell was picked before the table existed.

**T opens.** The cell is not hidden; it is the first sentence of README and FINAL_STATUS, with all four qualifiers written out, and the `boot_ok` 1-flip finding is stated next to it with the exact command (README; FINAL_STATUS "Scope"). The point of the project is the collapse: the same Verilog gives 1, 2 or 3 flips depending on netlist and scope (FINAL_STATUS "Three netlists, three minima"). I am not defending V2 as secure. V2 is the specimen.

**A rebuts.** Then say so first. Right now the README opens with V2 holding against 2 flips and a 119-word sentence of qualifiers (BC row 10). A reader takes "holds". Also "formal proof for any number of cycles" for the word goal is a PDR proof nobody replicated (BC row 9; CT-5), and the goal it proves is the weak one.

**T rebuts.** Agreed on ordering and on the proof. The collapse is not an embarrassment, it is the measurement: the matrix is a result about how sensitive the claim is, and each of the five qualifiers is something a vendor datasheet normally omits. The word-goal question is a legitimate one (can the stored state word be forced to the accept code), it is just not the accept-flag question.

**P interjects.** A designer adopting this wants to know whether their block passes. If the answer flips with the counting rule, what do I do with the output?

**L interjects.** So it's a lock with three keyholes, and if you can reach the door itself it doesn't matter?

**T.** Close enough: three checks do not help if one wire carries the final decision (V1 breaks with 1 flip on the shared net `ok`, F1). V2 triplicates the checks and the word, but the single accept flag at the end still falls to one flip (F3).

**Concessions R1.**
- T concedes: V2's "3" holds in one scope cell only; outside it V2 = V1 = 1 (F3, F4). "V2 resists" must never appear unqualified. The word-goal PDR proof is unreplicated and should leave the front door.
- A concedes: the collapse is documented by the project itself with commands, so it is not a concealed flaw; the single-cell dependence is the finding rather than a refutation of it. The unmodified CLI reproduces baselines (B2 Sanity), so the table is not an artefact of a modified engine.
- P concedes: V2 was never offered as a product.

**J rules R1.** A is right on substance and T has conceded it; A overreaches on "collapses" as an accusation, since the collapse is what the project reports. Outcome: the V2 result survives only as an exhibit of sensitivity, not as a result about triplication. Score: A 6, T 4 on content; T recovers on candour.

### Round 2: "Verdicts depend on how a fault is counted and on the exact netlist and scope"

**A opens.** This claim is true by construction. Change the metric and the number changes; a claim that no metric can falsify says nothing. The 6/32 versus 32/32 swing comes from "a flip of a fanout-f net costs f", a rule nobody has argued is physical (BC row 3). The 32-netlist matrix was produced and reported by one step and not re-run (F6). And B1's models are the step's choices, "none is calibrated to a layout, supply network or clock tree".

**T opens.** It is falsifiable in the plain sense: the matrix could have shown robustness and it did not. Under four of B1's models V2 stays at 3 (set, reset, branch_set, branch_reset), under two no attack up to 3, under the correlated and input models it falls to 1-2 (F5). So the verdict is stable under some model changes and not others, and the table says which. That is information a single-number tool report hides. Same for netlists: 1, 2, 3 on one source (FINAL_STATUS).

**A rebuts.** "Stable under some models" is not an argument for any model. Each row needs a physical event it represents. B1 admits the models are modelling choices. And SYNFI already measured the synthesis effect (3 -> 2, F8), so the netlist leg is not yours.

**T rebuts.** Correct on both: the netlist leg is prior art and the model rows are choices without calibration. What I claim is narrower: for this specimen the sign of the V2-over-V1 gap persists across all counting rules tried (V1 <= V2 in every row of B1 and in the 32 variants, FINAL_STATUS "ordering held in every variant"), while its size ranges 0-2 flips [INF from F5/F6: the gap is 0 under input faults, up to 2 under baseline]. That is a bounded, checkable statement. I cannot give the physical justification for fanout weighting, and I will not rank the rules without one.

**P.** Which rule do I pick on Monday?

**T.** The honest answer today: report the pair (unit-count, fanout-weighted) and the scope tuple, and do not pick. That is a deficiency, and it is why this is not a product.

**L.** Is it like measuring a wall's strength by how many bricks you have to remove, versus how many kicks?

**J asks T:** Is the 32-netlist result yours to rely on? **T:** It is one step's measurement and I should either re-run it or cite it as such.

**Concessions R2.**
- T concedes: the dependence on a counting rule is trivial unless a rule is argued physically; no such argument exists in the repo [INF from BC row 3 and B1 "NOT covered"]. The 32-netlist figures are unreplicated and must be labelled so. The netlist-dependence leg is already in SYNFI.
- A concedes: the project does show non-trivial structure (some models leave the verdict unchanged, some do not), and states its scope tuple explicitly, which is more than the compared tools' published headline results do [INF; not verified against those papers beyond COMPARISON].
- P concedes: a published list of "what verdict changes when" has value for reviewers even if no single rule is endorsed.

**J rules R2.** The claim as worded ("depends on counting") is a truism; the defensible version is the structured one: a scope tuple and a model list, with a table of which verdicts are stable. A wins on the unjustified weighting; T wins that the table is not vacuous. T must add the physical-event column BC asked for.

### Round 3: Does the toolkit add anything over SYNFI and FIRMER?

**A opens.** SYNFI enumerates fault sets and iterating the budget gives the minimum; it has already shown 3 -> 2 from re-synthesis. FIRMER does multi-cycle faults with an input sequence. You added: z3 search over any gate or flop and any cycle, a symbolic attacker input, a dashboard. Nothing is established as new; your own README says so. The 8-bit comparator is a 20-gate puzzle (BC row 4).

**T opens.** I do not claim novelty, and I did run SYNFI (SYNFI_RESULT). What is different in practice is measured: SYNFI needs hand-chosen locations and per-stage setup, ran only one cycle from a hand-chosen start state, a two-cycle chain crashed, and the re-synthesized V2 case was not run (F8). The glitchsat engine does unrolled multi-cycle minimum search from reset in about 25 s for the three designs (`make reproduce`, README), and the independent checker agreement is recorded (F9).

**A rebuts.** That is a comparison of ease of use on a toy, by the same step family that wrote glitchsat, with SYNFI run on newer unpinned dependencies because the pinned set would not install (SYNFI_RESULT s1). FIRMER and CLEAVE results (RUN1) are not in my fact base, k-FRP and FIVER unread. You cannot assert "adds nothing" or "adds something" with half the field unread.

**T rebuts.** Agreed; hence the wording "nothing established as new" and no comparison claims beyond the run SYNFI cells. The toolkit's justification for this project is as a teaching and cross-checking instrument, with B2's engine options (`input_sites`, `init_mode`, `free_in`) as the part that actually produced the scope matrix: a way to run one question under many assumptions and see which one carries the verdict. A single-shot tool report would not show the collapse.

**P.** Who adopts? A hardware security team has SYNFI inside the OpenTitan flow already. A student team might take this as a teaching kit. For anything beyond about 200 gates there is no scaling evidence (V2 k=3 at 20 cycles = 475 s on ~70 gates, BC row 7 citing QA).

**L.** So it's a practice gym, not a product?

**Concessions R3.**
- T concedes: no evidence it beats SYNFI or FIRMER on any axis other than convenience on a toy; no adoption evidence; scale is unmeasured beyond ~70-100 gates; comparison with half the field is unread.
- A concedes: the tool's output is reproducible by independent checks (F9), and the "scope matrix" workflow is a legitimate engineering contribution even if the individual ingredients exist.
- P concedes: the SARIF-like output and the "pick a rule" gap are fixable; as a teaching kit the barrier is low (README quickstart is a handful of commands).

**J rules R3.** A prevails on novelty and on any competitive claim. T prevails only on the narrow statement "reproducible, scriptable sensitivity analysis of one specimen". The project should never appear next to SYNFI as a competitor.

### Round 4: Is V3 any better?

**A opens.** V3 costs 3 where measured, which equals V2's best case (B2 limit a). Its table is mostly `?` (NOT RUN), the boot_ok column is not like-for-like because V3's `boot_ok` is an 8-bit code that merely moves the single-net problem to the consumer (limit c), and with arbitrary power-up the cheapest attack is flipping `rst` three times, again 3. A design that costs 3 where V2 costs 1 under input faults was built by a step that knew the V2 failure modes and designed against them; that is overfitting to the test. And it pays 6 comparators and 4 extra flops and 3 cycles of latency.

**T opens.** The claim for V3 is deliberately small and written in B2: in this model the cheapest attack moved from 1 to 3 in the scopes where V2 was 1, and V3 is not shown secure. What it demonstrates is the method working as a design-loop: find the lowest-cost assumption, harden it, re-measure under the same scope matrix. That is the practical use of the toolkit. V3 as a design is an exhibit, not a recommendation.

**A rebuts.** A design loop is only convincing if it ends. V3's `rst` flip at cost 3 shows the loop would continue forever; each fix exposes the next single net. And "3" is bounded by your search cap k<=3: "3 is the minimum" is true only because 2-flip attacks were refuted; nothing says 4 exists or not.

**T rebuts.** Fair on both: the loop does not terminate in this model, as there is always an output net, and that is itself an instructive limit (B2 limit e: a 1-bit `boot_ok` cannot be hardened at its own output net by upstream logic). V3's honest value is that it relocates the weakness to the interface contract, which is where the real-world argument belongs.

**P.** Then the deliverable to a customer is the sentence "your accept flag must be a multi-bit code checked by the consumer", which they could have read in any fault-injection guideline [INF].

**L.** So the lesson is "don't rely on one wire", and you needed a toolkit to say it?

**T.** The lesson is old; what the toolkit adds is a way to see which single wire a given netlist actually relies on, and how that moves when you resynthesise. I accept that this is modest.

**Concessions R4.**
- T concedes: V3 is no demonstrated advance beyond "cost 3, partly measured, bound-limited"; its boot_ok comparison is not like-for-like; its table has unrun cells; it must be presented as an exploratory attempt.
- A concedes: V3 does raise the minimum from 1 to 3 in every finished cell where V2 is 1 (F7), which is not nothing; the B2 write-up already carries its own limits.
- P concedes: the multi-bit-code advice is where a real adopter would get value.
- L concedes: it is understandable that "no single point of failure" is the story, and that it is simple.

**J rules R4.** V3 is no better than "a hardened exhibit under a capped bound". A wins on the claim that it is not a result; T wins that it is a faithful use of the loop and is honestly labelled in B2. Demote V3 to one paragraph in an appendix.

### Judge's overall verdict (INF)
The project cannot defend: "V2 is robust", "triplication helps" without qualifiers, "novel", "validated" in the independent-evidence sense, "V3 is better", or a product claim. It can defend: a reproducible scope-and-model sensitivity analysis showing that one small, fully specified redundancy claim changes from 1 to 3 flips depending on listed, checkable choices, with every choice made explicit and the engine's baselines reproducible.

## 2. Dialectical synthesis

**Thesis** (author): redundancy verdicts depend on how faults are counted and on netlist and scope, and the toolkit measures both. **Antithesis** (reviewer): that dependence is trivial, the V2 result is one cell, SYNFI/FIRMER exist, V3 is no better. **Synthesis**: the dependence is real but non-trivial only in its structure, and what survives is a method of reporting, a scope matrix, rather than any verdict about a design.

### 2.1 The strongest honest claim that survives

**One sentence.** For one small, fully specified toy design (V2), the minimum number of modelled bit flips needed to defeat its triplicated check ranges from 1 to 3 depending on a short list of explicit choices (which output is the goal, whether input nets count as fault sites, the power-up assumption, the netlist the synthesis flow produced), so a redundancy claim is only meaningful when stated with that scope (MEASURED, B2 matrix, 360 cells, 6 cycles, k<=3; modelled flips only; no novelty claim).

**One paragraph.** We took one toy secure-boot comparator in three versions and asked how few modelled single-cycle bit flips make it accept a wrong key. The unprotected and duplicated versions fall to 1 flip in every setting we tried. The triplicated version needs 3 flips (2 on some re-synthesised netlists) in exactly one setting: the goal is the internal result word, input wires are not fault sites, and the power-up state is known. In every other setting we tried (the accept flag as the goal, input wires as fault sites, an arbitrary power-up state) it needs 1, the same as the duplicated one. Across seventeen alternative fault models (B1) the picture is mixed: some leave the 3 unchanged, some give no attack at all, correlated and input-fault models give 1 or 2. The result is therefore not that triplication works or fails; it is that an unqualified "resists N faults" statement is not meaningful, and the checks needed to qualify it can be run in minutes with a script. This is a reproducible analysis of a toy under a modelled fault model; it has no hardware evidence, is not new relative to SYNFI and FIRMER, and does not show any real design secure or insecure. [All numbers B2/B1 MEASURED; wording INF]

**60-second spoken version.** "Imagine a secure-boot check that has to decide whether a key is right, and an attacker who can disturb one wire for one clock tick. We modelled that on a small circuit in three versions. The plain one and the one with two copies of the check both fail with a single disturbed wire. The one with three copies looks safe: you need three disturbances. But when we changed one assumption at a time, for instance letting the attacker disturb the final accept signal, or an input wire, or start from a different power-up state, that safety dropped back to a single disturbance. Even the same design source, run through different synthesis tools, needed one, two or three. So the lesson is not that three copies are good or bad. It is that a claim like 'resists two faults' means nothing unless you say what counts as a fault and which netlist you tested. We built a small tool that reruns the question under each assumption and shows which one carries the answer. All of it is simulation of a toy on a laptop; other published tools already do parts of this, and we are not claiming anything new or anything about real chips." (about 170 words, about 60 s) 

### 2.2 What the project IS and IS NOT

IS (each with source):
- A reproducible fault-injection analysis toolkit with a bounded z3 search, cross-checked by an independent simulator and boolector at T=4 and T=6 on the spike netlists (FINAL_STATUS; B1 validation).
- A set of measured sensitivity matrices: the 360-cell scope matrix (B2) and the 17-model fault-model matrix with gaps (B1).
- A teaching specimen: three small designs, a dashboard, open-source layouts as a flow demo (FINAL_STATUS "three gasp elements"; flow-level, not signoff).

IS NOT:
- Not novel: SYNFI already measured synthesis dependence; FIRMER covers multi-cycle inputs; k-FRP and FIVER unread (FINAL_STATUS).
- Not a security result about V2, V3 or any real design; no hardware, no physical glitches (README Rules).
- Not a product (no scale evidence, small cell library, no counting rule recommendation) (BC row 7).
- Not an independent validation: second implementation of the same fault model (FINAL_STATUS; BC row 12).
- Not a proof beyond bounds: PDR proof unreplicated; V3 capped at k<=3; 6 cycles.

### 2.3 Three decisions the author must make

1. **What is the claim: method or verdict?** Option A (recommended): the deliverable is the scope-and-model sensitivity method, V2 is an exhibit. Option B: keep "V2 holds against 2 flips" as the headline with qualifiers. B is the one every reviewer attacked (CT-1, CT-2, CT-3, BC row 1); A cannot be collapsed because it is the collapse. [INF recommendation]
2. **Which counting rule(s), and with what physical justification, or none?** Either (a) report unit-count and fanout-weighted side by side, label the 32-netlist matrix "one step's measurement, unreplicated", and refuse to rank; or (b) spend the remaining time giving each rule a physical-event column (stem fault, branch fault, coupling) as BC asked; or (c) re-run the 32-netlist experiment in a second step run. Without one of these the headline phrase "depends on how a fault is counted" is a truism (R2).

### 2.4 Recommended re-ordering of the story

Lead with (in this order):
1. The three-line question and the plain-language lesson: a claim like "resists 2 faults" is meaningless without its scope (the 60-second version).
2. One table: V2's minimum flips across the scope matrix (B2 columns reduced to 6) with V1 alongside, so the reader sees V2 = V1 outside one cell. Numbers labelled MEASURED with the command.
3. One table of fault-model rows (B1) with a physical-event column added; mark unfinished cells honestly.
4. The reproducible workflow: `make reproduce`, `check-reproduce`, plus the scope options used (`input_sites`, `init_mode`, `free_in`).
5. What is not claimed (novelty, hardware, product, independence).

Demote (move to appendix or archive, keep in tree):
- "V2 resists 2 flips" as a headline, and the formal unbounded proof (unreplicated).
- The 32-netlist figure (6/32 vs 32/32) from the first sentence to a footnote labelled "one step, not re-run".
- V3 to one paragraph labelled exploratory, bound-limited, boot_ok column not like-for-like.
- Dashboard "break it / fix it" language, since it frames faults as attacks and V2 as a fix (BC row 6); keep the game but with the disclaimer.
- Layout work: label "flow demo, not signoff", off the critical path.
- The README line 5 119-word sentence (BC row 10): replace by two sentences plus the table.
Add a pivot-history paragraph stating that the claim was changed after earlier claims were refuted (CHECKPOINT DECISION; BC row 2), so the reviewer hears it from the author first.

## 3. Defence script: the 10 hardest questions

Answers are the best truthful ones from the files; [INF] marks inference. "I" is the author speaking; wording is a draft for the author to edit.

**Q1. Your headline V2 result flips to 1 under any one assumption change. So what did you actually show?**
A. That is the result, not an objection to it. I show the minimum number of flips for V2 under a table of settings: 3 in one setting, 1 in the others (B2 matrix, 360 cells). V2 is not separable from V1 outside that setting (B2). The finding is that an unqualified "resists 2 faults" statement is not meaningful; I do not claim V2 is secure.

**Q2. Isn't "depends on how you count" just a truism?**
A. As a bare sentence, yes. The content is which models change the verdict and which do not: set/reset/branch models leave V2 at 3, hold models give no attack to 3, correlated and input models give 1-2 (B1 matrix). I cannot yet give a physical justification for fanout weighting, and I do not recommend one rule (BC row 3).

**Q3. What does your tool do that SYNFI and FIRMER do not?**
A. Nothing I can claim as new; the repo says nothing is established as new (FINAL_STATUS). I ran SYNFI: it enumerates user-bounded fault sets with a SAT check and I got one-cycle results from a hand-chosen start state; a two-cycle chain crashed and re-synthesised V2 was not run (SYNFI_RESULT). My engine searches multi-cycle from reset. I did not read k-FRP or FIVER, so I make no comparison claim against them.

**Q4. Is the V2 triplication result a hardware result?**
A. No. Faults are modelled single-cycle bit flips of gate outputs and flop outputs in a netlist model. No chip, glitcher or physical measurement was involved (README Rules). The SPICE bridge is circuit-level simulation of a gate, not silicon.

**Q5. Why should I believe your solver?**
A. A second simulator and boolector agree on spike netlists, exhaustively for all single-fault sites and all 2-fault sets of V2 at T=4 and 6 (FINAL_STATUS); B1's checker agreed on 36/36 rows at T=4. Limit: they share my fault model, so they check the encoding, not the model; and for V2 only 2 of 17 B1 models were validated (B1 "Validation"). B2's engine reproduces the CLI baselines (B2 Sanity).

**Q6. The 6/32 versus 32/32 figure: did you measure it?**

**Q7. You said you have an unbounded proof. Show me.**
A. One PDR proof for one netlist and the word goal, tool-reported; the technical reviewer did not replicate it (CT-5, BC row 9). I would not lean on it. My bounded results are 6 cycles, k<=3, with deeper sweeps to 20 cycles for k<=3 (FINAL_STATUS, DEEP_RESULTS). "No attack up to 3" is not security.

**Q8. Why did the claim change during the project?**
A. Because earlier claims were refuted. The supermarket-monitor idea was dropped when research showed the real incidents were IT-layer (dossier s2); CertBound's headline was already known; the V2 headline was cut down by reviewers (CT-1..3). The current claim, redundancy verdicts depend on counting and scope, is the one that survived; I know that makes it look like a rescue, so I list the pivots here and say which numbers were measured before the claim was chosen [INF on which are pre-registered: not established in the files; BC row 2 recommends declaring the counting rules before re-running].


**Q10. Is V3 better than V2, and is V3 secure?**
A. V3 is not shown secure. In every finished cell where V2 costs 1, V3 costs 3 under goal boot_word (B2). Its 8-bit `boot_ok` moves the single-net problem to the consumer, many cells are NOT RUN, the search is capped at k<=3, and flipping `rst` three times costs 3 from arbitrary power-up. It costs 6 comparators, 4 flops and 3 cycles of latency. It is an exploratory hardened exhibit.

**Bonus (if time): Why is the 85-gate vs 83-gate difference between Yosys 0.33 and 0.38 netlists not explained?** Not explained (D1-1; BC row 9); the 0.33 netlist shares logic across the result word, giving the 2-flip attack (FINAL_STATUS). I can state what we know, what we do not, and that conda 0.38 'opt' also gives 2 (B2).

## 4. Open items and limits of this review
- The BC report was only partly read (about 9 KB of 20 KB; the rest was truncated by the tool); rows 13+ are not used here.
- I did not read RUN1/RUN2 (FIRMER, CLEAVE, uArchiFI, k-FRP, FIVER) outputs, EL1 SPICE, E2 variance matrix, or the CT/CE/CC reviewer files; the debate does not use them.
- The debate is a structured simulation by one step; the judge's scores are my judgement [INF], not measurement.
- Nothing in this file was run; all numbers are quoted from the named reports.
