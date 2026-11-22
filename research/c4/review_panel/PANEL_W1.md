
Question: is the project (scope-and-model sensitivity method with V2 as specimen, consumer-mask rule, E2 synthesis-variance matrix, product CLI) defensible by one student alone and adoptable by others? Three biggest risks, the next six hours, and what would aim higher.

Inputs: member answers A-D, four peer reviews. Peer ranking was unanimous: D first (4 of 4), A second (4 of 4), B and C last.
Labels: **[F: file]** means I read it in that file this run. **[F-chair-run]** means I recomputed it from stored data this run. **[I]** means inference, not measured. **[M: x]** means the claim comes only from member or reviewer x and was not checked by me.
Chair checks run this run (read-only; no solver or synthesis was run):
- README.md line 5
- REP_REPORT verdict lines
- DA2_REPORT lines 45-48
- M1_REPORT lines 6 and 33
- PROJECT_DOSSIER s17
- a grep of product/src for scope flags
- config.py lines 74-78
- the E2 matrix.csv header, plus a recount of the V2 rows and the structural confusion matrix
- whether research/c4/bp/BP_REPORT.md exists

## 1. Consensus (5 lines)
1. Defensible only in a narrow form: a scoped sensitivity table (V2 min flips = 1/2/3 depending on goal, fault sites, init, counting rule and synthesis build), plus the consumer-mask rule labelled "exact on the spike netlist only". It is not defensible as "V2 resists 2 flips" [F: README l.5; F: M1_REPORT l.33; F-chair-run: E2 V2 SOLVED 264 = 180 at min 1, 60 at min 2, 24 at min 3].
2. The biggest single risk is authorship. Dossier s17 "My own contribution" is empty by design [F: PROJECT_DOSSIER l.141-142]. All code, runs and reviewers are step output [M: A, B, C, D; consistent with BC row 8].
3. Not adoptable today. The scope axes and goal masks are absent from product/src: a grep for input_sites, init_mode, goal_mask and free_in found 0 hits [F-chair-run]. Per-cycle attacker input is a TODO [F: config.py l.76]. The tool has toy-scale evidence only and the licence is undecided [M: B, C, D].
4. The front door (README l.5) is a one-sentence, roughly 120-word headline that still leads with the 2-flip question. It needs a short table with qualifiers attached [F: README l.5].
5. Counting rules need a physical-event column. Stop broad building and shrink the surface to a few core files [M: all four].

## 2. Disagreements, and who was likely right
- **Is the DA 6/32 vs 32/32 result unreplicated?** A, B and C say it is unreplicated, and their next-six-hours lists include replicating it.
  - **Reviewer 1 is right that it has been replicated.** REP_REPORT says "REPLICATED, 64 of 64 rows agree". REP used its own loop and its own measurement code but reused gen.sh's ABC recipe list [F: REP_REPORT l.4, l.12].
  - **Reviewer 1 is wrong that README l.5 contains no 6/32 or 32/32.** It does, labelled "MEASURED by that step, not re-run here" [F: README l.5].
  - Net effect: the README is stale on the replication status, and the replicate-DA items are already done.
- **Should the counting-rule table stay neutral?** A, B, C and D all say "endorse none".
  - Reviewer 1 points out that the repo already argues stem=1 is the physically defensible rule. Under that rule V2 holds on only 6 of 32 netlists, and the weighting rule must not be presented as a rescue [F: DA2_REPORT l.45, l.48].
  - Likely right: reviewer 1. The table can state the repo's own physical argument while saying that no rule is calibrated.
- **What the method's value rests on.**
  - A and C: merge the scope axes into the product.
  - B: prove the mask rule as a theorem.
  - D: the solver-free structural check is the generalisable asset.
  - D's direction won the peer vote, but the data only partly supports it. On the 264 solved V2 rows, the predictor "distinct_match_nets < 3 or shared_gates > 0" fires on 204 rows, and min is below 3 in 192 of them. It is silent on 60 rows, and 48 of those (12 at min 1, 36 at min 2) still break [F-chair-run, matching reviewer 1 exactly]. A compare-cone-only check misses 48 of the 252 breakable configs, so it must also cover state and next-state cones [I].
  - B's theorem goal is unrealistic for tonight. The rule already fails on apt-0.33 with 68 mismatches [F: M1_REPORT l.33].
- **Scaling limits.** D says "k=3 did not finish on 2040 gates". Reviewer 4 notes this was only a 250 s outer timeout [M: reviewer 4, R20 not read by me]. Use the wording "no result within 250 s".
- **Scores.** B's 5/10 and 6-7/10 are invented precision. Do not use them.

## 3. Blind spots all four members missed
1. **The replication is done.** REP replicated DA 64 of 64, so the work left is citing it with its independence caveat: same recipe list, rows matched by gate count rather than by hash [F: REP_REPORT].
2. **The physical argument is already on file.** It leans toward "V2 mostly does not hold" under stem=1 [F: DA2_REPORT l.45-48].
5. **The author's time is the binding constraint.** No plan says what ships if the author is absent tonight. The lists have 6-8 items each, with nothing cut [M: reviewers 2, 4].
6. **The review panel is not independent of its subject.** It uses the same model family, the same Yosys and the same z3 as the work it reviews, so its "replication" is not external evidence. Nobody proposed an exhaustive-simulation check of one E2 row as an anchor [M: reviewers 2, 3, 4].
7. **The two grids were never reconciled.** The DA/REP 32-netlist grid and the E2 864-config grid were never checked against each other where they overlap, for example the apt 0.33 plain flow [M: reviewer 1].
8. **Prior work was not read.** SYNFI, FIRMER, CLEAVE, k-FRP and FIVER coverage is asserted but not shown as read, so both "already covered" and "new" are unsupported [M: reviewer 3].

## 4. Top 5 risks, ranked
2. **The front door is stale and contradictory.** README l.5 calls DA "not re-run here", although REP replicated it [F]. It does not cite E2's 180/60/24 split [F-chair-run]. It also frames weighting-rule results alongside the stem=1 result, when DA2 calls stem=1 the realistic rule [F: DA2].
3. **The claimed contribution is not in the shipped tool.** The scope and mask axes exist only in research forks [F-chair-run grep]. "Adoptable" is therefore false for the method being sold.
4. **The surviving claim is post-hoc and thin.** "Depends on scope and counting" is close to a truism [F: DA2 l.45]. The mask rule is exact on one netlist only, brute-forced at T=4 and k<=2 [F: M1 l.6, l.33]. The structural shortcut misses 48 of 252 breakable configs [F-chair-run].
5. **Release blockers.** The licence is undecided, the third_party_derived/ code is unlicensed, the Dockerfile has not been built, and the red team found defects A1 (order-dependent multi-driver verdict) and A6 (crash exit code equals the attack exit code) [M: C, D; not read by me].

## 5. To-do for the next six hours (each small and checkable; no new work after 04:30 UTC)
| # | Item | Author role | Done when |
|---|------|-----------|-----------|
| 1 | Replace README l.5 with a short table: B2 scope row, E2 180/60/24 of 264 (file path plus hash), the M1 full-word and narrow-mask rows, and DA 6/32 vs 32/32 marked "replicated by REP, same recipe list". Name stem=1 as the rule DA2 argues is physical. Drop the word "holds". Cap the first screen at about 150 words. | Editor step (docs), reviewed by a reviewer step | README l.5 is no longer one sentence. Every number has a file path. A grep finds no "holds" on the first screen. |
| 2 | Write a counting-rule table with columns rule / physical event / V2 result / source, stating DA2's argument and "none calibrated". | Editor step | The table exists in FINAL_STATUS, and each row cites DA2, REP or E2. |
| 3 | Put the structural confusion matrix in an E2 addendum or new file (predicted <3: 204 rows, 192 correct; predicted 3: 60 rows, 12 correct). State that compare-cone-only structure misses 48 of 252. | Analysis step, read-only on matrix.csv | A script and its output are committed, and the numbers equal the chair's recount. |
| 4 | Pre-register predictions. Extend the predictor with state and next-state cone overlap. Write predictions for 5-10 configs not yet solved (the 72 ENGINE_UNSUPPORTED rows are not eligible). Hash the file and timestamp it, then solve and publish hits and misses unedited. | Analysis step writes the predictions; a separate solver step runs | The SHA-256 of the prediction file is recorded before any solver log exists, and the results table is published as is. |
| 5 | Anchor check: run M1's bf.py brute force (no z3) on one E2 V2 netlist at T=4, k<=2, and compare with matrix.csv min_flips. | Verification step | One row reports agree or disagree, with the netlist hash. |
| 6 | Author-defence sheet: three M1 masks worked by hand, giving 1, 2 and 3 flips, the V1 shared-net 1-flip case, and the solver command that confirms each. Leave s17 with empty slots only. | Teaching step writes the template; the **author** does the derivations | The sheet exists and contains no step-written first-person text. The author reproduces one derivation unaided, which is the only real evidence. |
| 7 | Add a scope tuple (goal, fault sites, init, attacker input, counting, build) printed in every product report, without porting the engines tonight. List the missing flags as "not in product". | Product step | The CLI output shows the tuple, the existing tests pass, and the README states that the scope axes are research-only. |
| 8 | Fix or document RT A1 and A6. At minimum make the crash exit code differ from the attack-found code. | Product step plus a test step | A test asserts the distinct exit code, and A1 is documented or rejected with an error. |
| 9 | Add START.md naming the 5-6 files that matter. Label everything else as archive and delete nothing. Mark third_party_derived/ NOT FOR RELEASE. | Editor step | The file exists, and the bundle manifest excludes third_party_derived/. |
| 10 | Refresh the stale statements: PROJECT_DOSSIER s15 (E2 status), the README replication status, and "BP absent" in any notes. | Editor step | A grep finds no "E2 has no numbers". |
If only two hours are usable, do items 1, 3, 6 and 9. Item 6 is the only one that raises the author's own defensibility.

## 6. Aim higher (one recommendation)
Build a **redundancy survival check that covers state as well as comparison logic**, scored on E2 as a fixed benchmark. It is a solver-free structural pass over a post-synthesis netlist that reports merged copies, shared stems, and nets that dominate every consumer bit across both compare and next-state cones. The solver serves only as a confirmation oracle, and the M1 rule is the hand-checkable theory of what the pass predicts [I].

Evidence needed before claiming it:
- (a) On the 264 solved V2 rows, the extended predictor beats the compare-cone baseline. The baseline misses 48 of 252 breakable configs [F-chair-run].
- (b) A pre-registered, hashed prediction set that is scored unedited (to-do item 4).
- (c) One design that is not a toy: an open, permissively licensed redundant FSM or comparator, run through a named default flow. The author decides on any outside report.
- (d) A read of SYNFI, FIRMER, k-FRP and FIVER before any novelty wording. Until then the status is "nothing established as new".

## 7. Claims in the answers that need verification before use
- **Confirmed:**
  - E2 V2 split 180/60/24 of 264 [F-chair-run].
  - Mask rule 255/255 on spike and 68 mismatches on apt-0.33 [F: M1].
  - config.py l.76 TODO [F].
  - No scope flags in product/src [F-chair-run].
  - s17 empty [F].
  - Reviewer 1's confusion matrix [F-chair-run].
- **Wrong or stale:**
  - "DA 6/32 vs 32/32 unreplicated" (A, B, C, D). REP replicated it [F].
  - "README l.5 has no 6/32" (reviewer 1). It does [F].
  - "BP_REPORT absent" (A, C). It exists [F].
- **Unverified, so do not use as fact:**
  - A's inference that fanout weighting cannot rescue the opt_merge netlists.
  - B's "475 s for k=3 at 20 cycles", "10k-gate user gets nothing", and the 5/10 scores.
  - B's "V2 costs 1 flip under boot_ok or free input" (check the B2 cell).
  - D's "k=3 did not finish on 2040 gates" (only a 250 s timeout, per reviewer 4).
  - D's "62 s for k=1".
  - The mutation scores 67%/65%.
  - RT A1 and A6.
  - "Dockerfile unbuilt".
  - "SYNFI, FIRMER and CLEAVE already cover the method".
  - The OpenTitan guidance claim (RUN_LOG 167).
  - "The spike netlist is not regenerable" (BC row 1 / QA Q20).
  - E2's "85 vs 83 gate cause not located".
- **Not checked by anyone:** whether the DA/REP grid and the E2 grid agree where they overlap.
