# Council W2: chairman's report (22:00 UTC, 2026-11-19)

This is a simulated council: four members (A-D) and four peer reviews, all from the same model family as the work they review. It is not a human review.

Labels:
- [F: path] = the chairman checked the fact in that file this session.
- [M-x] = reported by member x, not re-checked by the chairman.
- [I] = inference.

Nothing was re-run: no solver, SPICE, LVS or tests.

Chairman spot-checks this session:
- B3_REPORT matrix and plain answers, l.20-45.
- README l.30-36.
- product/src/faultbound_wt/cli.py l.7.
- NUMBERS.md T.mut and T.root rows.
- T3_REPORT l.15.
- PROJECT_DOSSIER s17.

## 1. Consensus (5 lines)

1. P3 ("solver-backed scope reporter; predictor heuristic, not a validated linter") is honest. The measurement core is coherent. Roughly 5-6 of the 10 W1 items are closed [M-A,B,C,D].
2. The first thing a skeptical examiner would destroy is authorship. Dossier s17 is still empty [F: docs/dossier/PROJECT_DOSSIER.md s17 "Left empty on purpose"], and no owner derivation is recorded. Everything shipped tonight widens the surface the owner must defend.
3. The front door is stale against tonight's work, for example README "L2 in progress; faster encoding patch ... is not applied" [F: README.md l.36]. Stale lines must be fixed before anything new is added.
4. The physical track has reached rabbit-hole depth. Every "survives" verdict hinges on selectivity, which no model here settles. The L2 spread layouts fail LVS on 4/4 [M-A,B,C,D from L2_REPORT]. The die-wide selective event is still 1 [M-B,C,D].
5. Freeze the physical track. At most, run ONE pre-registered selectivity probe (SPICE or an RC estimate) and stop.

## 2. Disagreements and who was likely right

**Is the README rail-dip row meaningful?** Only D attacked it. D is right [F: B3_REPORT matrix l.26-28 and plain answers]:
- V1 (stem-flip cost 1) also scores >3 on rail_all, rail_half and rail_unions.
- B3 itself says the boot_ok result "is a consequence of directionality, not of any extra protection in V2/V5".
- So the row measures 1->0 polarity, not triplication.

All four peer reviewers ranked D first, mostly for this point.

**Was the A6 exit-code collision fixed?** D says there is no evidence. A says yes. A is right [F: product/src/faultbound_wt/cli.py l.7: `EXIT_ATTACK=1`, `EXIT_INTERNAL=4`]. No test asserting this was confirmed [I].

**Was the E2/DA reconciliation done?** B says it "looks done". A, C and D say it is not, and B's own risk 6 also says it is not. B is likely wrong. No reconciliation table was found by A, D or peer review 4 [M].

**Was the pre-registered predictor (W1 item 4) done?** B and C say it is not. A and D say it is done (PRE/TEST/VER, 150/163 against a 98% bar).
- A and D are right for item 4 as written: the predictor was pre-registered and reported as failing [F: README l.31].
- B and C are right that the W1 *extension* (state and next-state cones) was not pre-registered [M].

**What is the right mutation fix?** A proposes T2's figures (72.5% / 65.8%). These are already superseded for the product suite [F: T3_REPORT l.15]:
- tests/ is 50/69 = 72.5%.
- product is 50/74 = 67.6%. The denominator changed because 5 mutants are NOT_APPLIED after PS4.

NUMBERS still says 29/43 = 67% and 28/43 = 65% [F: docs/NUMBERS.md l.34-35]. The fix should quote T3, with its denominator.

**Is T.root.passed 98 or 99?** A says 99 (from T3). NUMBERS says 98 [F: NUMBERS l.27]. Unresolved. Re-measure it; do not pick one.

**Can the selectivity probe be done in 6 h?** C says no. A, B and D say about 1 hour, using the existing SPICE setup. A, B and D are more likely right [I]. A first-order RC estimate takes minutes (peer review 2).

**Where does the physical track go next?** Two options were proposed:
- C: demote it to a negative result.
- D: reframe it as a "redundancy survival ledger" built from measured geometry.

These are compatible. Keep the measured geometry facts (copy separation, single supply net). Drop rail-dip verdicts as headlines.

**Two micrometre figures.** D's 1.84 um (copy spacing, base layout) and the 2.95 um (selective-dip radius threshold) measure different things. Any slide that shows both must label each.

## 3. Blind spots all four members missed (from peer reviews and the chairman)

1. **Encoding regression.** T3 made the counter encoding the default *after* E2, DA/REP, M1, B2, B3 and L2 were produced. No one asked for a re-run diff of a sample of headline cells, or for NUMBERS to record which encoding produced each number. T3 cross-checked 40+150 netlists [F: T3_REPORT l.15], but that is not a headline-cell regression [I].
2. **No polarity control.** The rail models are 1->0 only. There is no symmetric 0->1 (VGND or ground-bounce) model, which is exactly what would reach the 1-event boot_ok attack [F: B3 plain answers].
3. **What triplication actually buys physically.** Under dip_subset, the smallest selective domain is 2 gates for V1 and 3 for V2/V5 [F: B3 l.34]. Triplication buys one extra gate of selectivity. Nobody framed the result this way.
4. **Bound adequacy.** No one checked whether ">3" at T=6, k<=3 on an 8-bit toy is informative, or whether T=8 changes any row.
5. **check_numbers.py limits.** It checks that documents agree with NUMBERS.md. It cannot detect that NUMBERS.md itself is stale. A clean run is not evidence of correctness.
6. **Downstream surfaces unchecked.** The deck, demo, report, edu kit and dashboard Scope tab were built before T3 and L2 landed. No member read them.
7. **No pre-registered threshold for "selective".** The SPICE probe needs one before it runs (droop difference vs cell switching threshold, pulse width). Otherwise it is one more post-hoc number.
8. **Possible disc-model bug.** In the L2 radius sweep, an all-or-nothing disc gives 3 at r=3, 2 at r=5 and >3 at r=10 [M-D, peer review 4]. That may be a model bug, for example a larger disc pulling in inverting gates. Nobody checked.
9. **Reproducibility.** B3, T3 and L2 scripts reference /tmp/work_* paths [M peer review 4]. Tonight's results may not re-run from the shipped tree.
10. **No owner fallback.** If the owner is unavailable before the 04:30 freeze, nothing has been prepared (only B suggested a README disclosure).
11. **Novelty.** "Nothing established as new" is asserted, not supported by a related-work check. Spatial TMR separation is standard rad-hard practice [I, general knowledge].

## 4. Top 5 risks (ranked)

1. **Authorship.** s17 is empty [F], and no owner re-derivation of V2=3 or mask 0x0F=2 exists [M]. Effect: the viva fails regardless of the quality of the work.
2. **Rail-dip row is non-discriminating.** "V2: no attack up to 3 events under rail dips" sits in a V2 table while V1 also scores >3 [F: B3 l.26-28]. Effect: an examiner sees directionality presented as security in one question, then distrusts the whole table.
3. **Stale front door and numbers.** Three places are stale:
   - README l.36 (L2 "in progress", patch "not applied") [F].
   - NUMBERS T.mut (67% / 65%, superseded by T3's 72.5% and 67.6%/74) [F].
   - T.root 98 vs 99, unresolved.

   The deck and dashboard are unchecked. Effect: one stale number discredits the rest.
4. **L2 die-cost and threshold numbers from layouts that fail LVS.** All 4 fail LVS; there are top-cell li1 DRC rules, the `_16_` output is unpinned, and the die-wide selective event is still 1 [M from L2_REPORT]. Effect: a VLSI examiner discounts the whole layout thread.
5. **Single-engine, bounded physical verdicts.** The B3 V2/V5/T=6 rows rest on z3 only. Brute force covered only V0/V1 at T<=4, with no witness replay [M-A,B]. The encoding has changed since then (blind spot 1). Effect: one encoding bug moves every "survives".

The predictor's 58% on cells needing 2+ flips is a close 6th. It is already disclosed in README l.31 [F], so its residual risk is wording only.

## 5. To-do list for the next six hours (ordered; each item small and checkable)

Agent types:
- OWNER = the human.
- DOCS = documentation and fact-sync agent.
- VER = verification agent (runs solvers and tests, no edits to the engine).
- PHYS = layout/SPICE agent.
- CHAIR = orchestrator.

| # | Item | Owner role | Done when |
|---|---|---|---|
| 1 | Run the three START.md commands, do derivations 1-2 of docs/OWNER_DERIVATION_SHEET.md on paper, and write s17 in the owner's own words. No agent writes s17. | OWNER (90 min) | s17 has owner text, or item 1b is done |
| 2 | Fact-sync pass, done once and batched:<br>- README l.36: T3 applied, default counter; L2 done, LVS FAILED 4/4.<br>- FINAL_STATUS: the same lines.<br>- NUMBERS T.mut: tests 50/69 = 72.5%; product 50/74 = 67.6% with a denominator note.<br>- T.root: re-measure.<br>- README "holds" wording. | DOCS + VER (re-measure only) | `grep -rn "in progress\|not applied\|29/43\|28/43"` across README, docs and FINAL_STATUS returns nothing stale |
| 3 | Add regexes for the stale values to check_numbers.py, run `--verify`, and attach the output. | DOCS | Clean output saved next to NUMBERS |
| 4 | Reword or remove the rail-dip row everywhere (README, deck, dashboard). Put V1 beside V2 with the sentence "V1 also shows no rail attack: this is 1->0 directionality, not a benefit of triplication." | DOCS | grep for "survives" and "rail" in README, docs, deck and dashboard shows the qualifier at every hit |
| 5 | Check the deck, demo, report, edu kit and dashboard Scope tab for stale lines and overclaims ("linter", "validated", "hardening works", L2 die cost). | DOCS (read and fix) | A list of hits with fixes, or "none found" with the files read |
| 6 | Encoding regression: re-run 10 headline cells (E2 V2 at min 1/2/3, M1 masks, B3 V2 rail_all and dip_subset, B2) on the T3 default encoding. Diff them against the stored values. | VER | Diff table with netlist hashes; every disagreement explained or flagged |
| 7 | Anchor (W1 item 5): run bf.py (no z3) on one E2 V2 netlist with min 2 and one with min 3 (T=4, k<=2). Replay 3 B3 V2 witnesses in bf_b3.py. | VER | One agree/disagree line each, with hashes |
| 8 | Commit the E2 structural confusion-matrix script and output (predicted <3: 204 rows / 192 correct; 48 of 252 missed), plus one table reconciling DA/REP with E2 on the apt-0.33 plain flow. | VER | Numbers match the W1 chair recount, or the mismatch is stated |
| 9 | Pre-register the selectivity probe before running it. Write a threshold file and hash it: the differential droop that counts as "selective" (e.g. > a stated fraction of the sky130 inverter switching threshold), the pulse width, and the sheet-resistance source. Then run either a first-order RC estimate or an ngspice RC ladder of the met1 rail and met4 strap from DEF geometry, with groups at 3 um and 15 um. Label it SIMULATED. Cap: 60 min. | PHYS | Hashed pre-reg file plus a result line, whichever way it falls; then the physical track is frozen |
| 10 | Freeze the physical story as one figure. Caption: B3 rail >3 vs selective 1 (3 gates V2/V5, 2 gates V1); LAYOUT copies 1.84 um apart on one supply net; L2 threshold moves to >8-15 um but die-wide selective is still 1; "L2: LVS FAILED 4/4, `_16_` unpinned". Move the L2 die-cost numbers to an appendix. | DOCS + PHYS | No L2 die-cost number on any first screen |
| 11 | Optional, only if items 1-10 are done: fix the L2 filler/li1 flow (VERIFY.md s3), pin `_16_`, and re-run LVS on ONE spread variant. | PHYS | LVS result line; if it fails, L2 stays in the appendix |
| 12 | Cancel the queued DA3, FP2, DS2 and persona waves. Keep only RT2, scoped to the code changed by T3, PS4 and PS5. | CHAIR | Queue shows only RT2 |

Do not start any new design variants, V-numbers, leaderboard or rewriter work.

## 6. Aim higher (one recommendation)

**Reframe the result as a "redundancy survival ledger".** This is D's idea, endorsed by all four peer reviews. It is one table: one row per flow stage, each with one independence metric, each cell MEASURED with a file path:

| Stage | Erosion | Source |
|---|---|---|
| Synthesis merges | V2 at 1 in 180 of 264 builds; opt_merge 85 gates/2 flips -> 63/1 | E2, G.v2.merge [M-D] |
| Consumer bits read | 3 -> 1 | M1 [M] |
| Placement | Copies 1.84 um apart, bbox gap 0 | LAYOUT, L2 base [M-D] |
| Power | All copies on one supply net fed at one column | LAYOUT [M-D] |

The honest headline: "A default open flow eroded the declared redundancy at every stage, and no stage warned." State "nothing established as new", since spatial TMR separation is standard practice [I].

Evidence needed before use:
- (a) Every ledger cell re-checked against its source file, with the netlist or DEF hash.
- (b) The logical rows re-run on the T3 default encoding (to-do item 6).
- (c) The placement figure confirmed from a flow whose base layout passes LVS. The base layout must be confirmed LVS-clean; only the spread variants are known to fail.
- (d) The rail-dip verdicts excluded from the ledger, because they do not discriminate (V1 = V2).
- (e) Ideally one design the project did not write, run through the shipped CLI with the scope tuple printed (C's adopter task).

## 7. Claims in member answers that need verification before use

| Claim | Status |
|---|---|
| D: "no evidence A6 fixed" | WRONG. EXIT_INTERNAL=4 is distinct from EXIT_ATTACK=1 [F: cli.py l.7]. A test asserting this is still unconfirmed. |
| B: "E2/DA reconciliation looks done" | Likely wrong. B contradicts itself in risk 6, and no table was found [M]. |
| A: "NUMBERS T.mut.prod should be 65.8%" | Superseded. T3 gives 67.6% over 74 runs [F: T3_REPORT l.15]. |
| A: "T.root.passed should be 99" | Unverified. NUMBERS says 98 [F]. Re-measure. |
| D: "V1 also >3 on every rail model" | Partly right. True for rail_all, half and unions. On rail_cone and rail_any V1 is >3 and V0 is 1 [F: B3 l.26-29]. Quote it as "V1 shows no rail attack", as B3 l.41 does. |
| D: "2.95 um exists only under SUB semantics" and the non-monotone disc (3/2/>3 at r=3/5/10) | Check against the L2 enumeration and sweep JSONs before quoting [M]. |
| D: "1.84 um copy spacing, bbox gap 0, one supply net fed at one column" | Check against L2_REPORT and LAYOUT_REPORT before putting it in the ledger [M]. |
| D: "R27 149 s -> 3.5 s at k=1" | Check against RUN_LOG l.192 and T3_REPORT [M]. |
| D: "V2 at 1 in 180 of 264 E2 builds"; "opt_merge 85/2 -> 63/1" | Check against NUMBERS E2.v2.min and G.v2.merge [M]. |
| All: "L2 LVS FAILED 4/4 (428 vs 430 devices), 15-24 DRC rules" | From L2_REPORT, not read by the chairman [M]. |
| A, B: "B3 brute force covered only V0/V1 at T<=4, no witness replay" | Check the B3 validation section [M]. |
| C: "product CLI accepts only attacker_model constant" | Consistent with README l.34 "per-cycle attacker input (TODO config.py)" [F]. |
| D: "rail droop differs by only millivolts over 3-15 um" | Inference. It is exactly what to-do item 9 tests. |
| Any "the predictor is 92%" quote | Always pair it with "58% on cells needing 2+ flips; heuristic" [F: README l.31]. |
