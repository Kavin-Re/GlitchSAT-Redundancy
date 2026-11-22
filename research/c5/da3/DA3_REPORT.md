# DA3 report: Devil's advocate + inversion, wave 2
Step DA3, 2026-11-19. Nothing in the tree was edited; all re-runs on copies in `/tmp/work_da3/` (tree copy `p/`, scripts `a.py c.py g.py gs_alt.py`, B3 copy `b3/`). Labels: **VERIFIED** = I ran or recomputed it this run (command named); **READ** = taken from a project file, not re-run; **INFERRED** = my reasoning. All solver numbers are bounded (T=6 cycles, k<=3), modelled bit flips on toy designs; nothing physical. Wave-1 items (DA2: decoder width, PDR vacuity, SYNFI agreement, layout merge, product probes, counting-as-tautology) are not repeated.

## Part 1. Attacks on the current claims

### A1. Consumer-mask rule is just Hamming distance plus min-cut restated  -> ATTACK LANDS (strongest finding)
- Attack: the rule `min( min_s popcount((s xor 0x96)&mask), min_S |S| + popcount(~bits(S)&mask) )` is "Hamming distance to the nearest idle state, or flip the shared comparator output of each copy you need". If the second term collapses to "number of copies the mask touches", the rule is a textbook distance/cut bound with one netlist-specific table (bit -> copy).
- Test: `python3 -I /tmp/work_da3/a.py` (reads `research/c3/m1/m1_all_masks.csv`, imports M1's `pred.py`). I compared against the solver column `v2_spike_min_flips` for all 255 masks.
- Result (VERIFIED, MEASURED data): the M1 rule matches 255/255 (reproduced). So does the one-liner **min(Hamming-to-idle, number of copies whose bits the mask touches) = 255/255**, no subset search. Hamming alone: 251/255. Copies-touched alone: 80/255. Permuting the bit-to-copy grouping (wrong grouping) still gives 253/255, so on 255 masks the data barely tests the grouping. On the apt re-synthesis the same one-liner is right on 187/255, identical to M1's 68 mismatches.
- Verdict: **the rule is Hamming + min-cut (cut size = copies touched), not a new rule.** It is a correct explanation of V2-spike, with no content beyond "read the netlist and count which comparator copies feed the consumed bits". It does NOT survive as a method claim; it survives only as a review-level explanation ("why does width matter: the attacker flips each copy's shared output, 1 flip per copy, or the bits directly"). The dossier/README should say "this is a Hamming distance + cut-size bound; exact on one netlist, fails on re-synthesis" and never "rule" as if general. Also: 255 masks of ONE netlist is one data point about the netlist, not 255 independent tests (INFERRED).

### A2. E2 merely rediscovers SYNFI  -> PARTLY (already conceded in PRIOR_ART; sharper form below)
- Attack: SYNFI (SOURCED in SWEEP_S2; `docs/PRIOR_ART.md` line 19) already showed synthesis cuts the fault count (3->2, 4->2) and `set_dont_touch` restores it. E2's "synthesis changes the verdict" is the same observation; the grid is a parameter sweep; counts inflate independence.
- Test: `python3 -I /tmp/work_da3/c.py` on `research/c2/e2_variance/raw/matrix.csv`, V2 SOLVED rows.
- Result (VERIFIED): 264 solved V2 configs but only **152 distinct canonical netlists**; verdicts never disagree within a canonical netlist (0 of 152), so synthesis flags only matter through the netlist they produce. Per distinct netlist: min 1 / 2 / 3 = 94 / 38 / 20 (vs headline 180/60/24 per config). Dropping the duplicate conda build (same git sha, README admits non-independent): 80 / 32 / 12 over 124. Also `opt_merge` (merge column) alone explains most of the 1s: with merge, 120 of 132 are 1 and 12 are 2, never 3; 3 appears only in `plain` flow, no merge (24 configs, 20 netlists) and in 18+6 of them only on conda 0.38. The E2 text says the opt_merge collapse and "the three copies collapse to one match net" which is exactly SYNFI's "merged duplicate registers".
- Verdict: **E2 does not add a new phenomenon; it adds a quantified map on one design with 3 builds.** Safe form: "consistent with SYNFI's 3->2 and 4->2; here is how often, in a small Yosys grid on one 8-bit toy". Quote counts per distinct netlist (94/38/20), not per config. The unidentified 0.33 vs 0.38 cause remains a correlate. SYNFI's remedy (dont_touch) is the tested fix; the project's `keep` attribute changed no verdict in 432 pairs (READ, E2), so the project did NOT reproduce SYNFI's fix result; say so.

### A3. Product scope sweep is a thin wrapper  -> ATTACK LANDS on implementation, PARTLY on value
- Attack: `--scope-sweep` is a nested for-loop around `analyze()`.
- Test: read `product/src/faultbound_wt/runner.py` lines 291-380 (VERIFIED by reading); ran it on a copy: `analyze reference/spike_netlists/v2.json --top v2 --scope-sweep --sweep-masks 0xF,0x69` (VERIFIED, 4 goal rows x 4 scope columns in ~0.6 s total). Output at max_flips=1: full word `>1` for known init with input nets not sites, 1 with input sites, 0 with arbitrary init; boot_ok 1 / 0.
- Result: the sweep is: build goal list (config goal + extra masks + `boot_ok`), loop {init} x {input-sites}, call `analyze`, `deepcopy` config. ~80 lines, no new analysis. Gaps that make it thinner than the problem statement P3: it sweeps neither **synthesis build/flags** (the E2 axis) nor **counting rule** (`--count-rule branch` exits 3) nor per-cycle attacker input; the "scope" it reports is goal x input sites x init. Two of its four columns (init=arbitrary) print 0 for every design (a documented design gap, not a result). A user must pass `--max-flips 3` to see the interesting full-word cell (default shows `>1`).
- Verdict: **thin as code, valuable only as a reporting convention** (one table that keeps the qualifiers attached to the number). Call it that; do not call it "the method in the tool". P3's own sentence includes "synthesis build, counting rule": two of its four axes are not in the product. Be ready to say so at the review.

### A4. B3 survival depends on a model that forbids the obvious attack (0->1 events)  -> PARTLY: the survival is real but non-discriminating
- Attack: rail dip is 1->0 only, flop Q never flipped by a dip alone, so reaching `boot_word=0x96` (which has ones) is nearly impossible by construction; "V2 survives" says nothing about V2.
- Tests (VERIFIED, copy `/tmp/work_da3/b3/`, B3's own `run_cells.py`, T=6, cap 3, z3 60 s): V0 (the naive single compare) under `rail_all` word: **>3, same as V2**. stem_flip: V0 1, V2 3. rail_cone: V0 1, V2 >3. dip_subset: V0 1, V2 1. Extra variant I added (event also forces every flop Q to 0 for the cycle; `/tmp/work_da3/b3/q.py`): `rail_all_plusQ` word >3 on V0, V1, V2; with a selectable subset it is 1 on all three.
- Result: the whole-rail result does not separate V0 from V2. The only discriminating row is rail_cone (V0 breaks, V1/V2 do not), and the selective row (all designs 1). The 0->1 attacker is not "forbidden": the project already has it as `stem_flip`/`set_only`/`branch_set` (V2 3, 3, 3, B1/B3 tables, READ), so 0->1 events cost what they always cost; B3 states this itself ("directionality, not extra protection"). What is not covered: a combined event (1->0 on some gates plus 0->1 on others, i.e. a real supply bounce) is not in the model (INFERRED; not run).
- Verdict: **survives as an honest bounded negative result; fails as evidence of protection by V2.** README row "no attack up to 3 events" must carry "also true for the unprotected V0 under the whole-rail model" or it will be read as a V2 virtue.

### A5. L2 spread-placement threshold (2.95 um -> 11 to 18 um)  -> PARTLY; one sharper attack from the table
- Attack (a): thresholds are measured on layouts that fail LVS in 4 of 4 spread variants (READ, L2). (b) the cheapest set uses output inverter `_16_` as stand-in for a copy, so the threshold measures where the placer put `_16_`, not the copy spacing (READ, L2 admits it; `research/c4/l2/data/minsets_*.json`). (c) **the all-or-nothing model is the one the SPICE basis supports; under it the original layout already survives at r >= 10 um**: L2 table, AoN word at r = 10 and 15 is `>3` for base. The 3x to 5x "improvement" exists only under the selective (SUB) model, which EL1 contradicts and which `rail_all` SUB (cost 1 in every variant) shows spacing cannot remove.
- Test: re-read `L2_REPORT.md` radius sweep table and `data/minsets_*.json` (READ, not re-run; EDA tools not installed here).
- Result: spacing only matters for a selective dip of limited reach; the claim "spreading raises the threshold" is true inside that assumption and meaningless outside it; sample = 5 layouts, 1 seed each, no extraction.
- Verdict: **partly.** Keep it as a "flow demonstration plus what-if", never as hardening evidence. Say the dependence on selectivity first.

### A6. T3 speedup  -> PARTLY (a rediscovery of a standard encoding, but the baseline is not a z3 strawman)
- Attack: replacing z3 `PbLe` by a Sinz sequential counter (2005) is textbook; the "28x to 107x" compares against a naive baseline and uses timeouts as lower bounds.
- Test (VERIFIED, copy `/tmp/work_da3/gs_alt.py`, only change: third mode using z3 built-in `AtMost`; `python3 -I /tmp/work_da3/g.py`, V2 spike, 60 s timeout): T=6,k=3: counter 0.32 s, PbLe 6.12 s, AtMost 4.02 s. T=12,k=2: counter 0.60 s, PbLe 58.9 s, AtMost 59.3 s (about 100x). T=20,k=2: counter 2.5 s, PbLe and AtMost both timeout at 60 s (>=24x).
- Result: the speedup is real on the project's own V2 spike (19x at T=6, 100x at T=12) and not an artefact of PbLe being unusually bad (z3 AtMost is as slow). But the technique is standard (the project itself cites R27/Sinz) and, for the reproduce rows, the end-to-end gain is 3.4x (14.4 s -> 4.2 s, READ T3) on runs that already take seconds. At the 150 s cap legacy times out so ratios are lower bounds (READ).
- Verdict: **survives as an engineering improvement to the tool's runtime, not as a research claim.** Do not put it on a headline slide.

### A7. Predictor 92%  -> ATTACK LANDS on the number as evidence of skill
- Attack: 92% on a sample where most cells are trivial; compare against trivial baselines.
- Test (VERIFIED, `research/c4/ver/heldout.csv`, 163 cells, python recount; `lb` is the sound structural lower bound; `>3` coded 4): "always predict 1" = 101/163 (62%); the sound lower bound alone = 136/163 (83%); on the 30 cells needing >=2 flips, lower bound exact in 4/30 and the heuristic `est` in 24/30 by my recount of the `est` column (VER reports 18/31 for the predictor; I did not reconcile the 24 vs 18 and 155 vs 150 totals: I used the `est` column, VER used the `pred` fallback rules; INFERRED reason). VER itself notes 124 of 163 cells are trivially 0 or 1 and the predictor was 1.4x slower than the solver (READ).
- Verdict: **92% beats "always 1" by 30 points and a free lower bound by about 9, on 65 of 76 netlists from four generated families; it failed its own 98% pre-registered bar.** Honest line: "a sound lower bound is exact in 83% of fresh cells; the heuristic adds about 9 points; the solver stays the reference". Drop "92%" from any front-door table without those baselines.

### A8. P3 / "verdict belongs to (netlist, consumer, counting rule, scope)"  -> PARTLY a truism; a falsifiable core exists
- Attack: a statement that a minimum depends on its definition parameters cannot be false. The counting-rule evidence is one recipe list (REP: 64/64 rows but one reused recipe list).
- Test: reasoning over the data above (INFERRED) plus A1/A2 numbers.
- Result: the non-trivial parts are (i) size of the effect (V2: 3 -> 2 -> 1 across three single changes), (ii) which parameter dominates. A1/A2 say: the consumer-mask effect is Hamming + cut (predictable by one line), and the synthesis effect is mostly `opt_merge`/ABC merging (SYNFI's finding). So what remains of P3 is the *reporting discipline* (print the qualifiers next to the number) plus a measured table, not a claim that could be refuted. BC2 recommended a falsification paragraph; it still helps: "the mask rule predicts X on held-out netlists; it fails on apt re-synthesis (68/255), so it is not general".
- Verdict: **partly.** State P3 as "a scoped report, with measured examples", not as a finding.

### Summary table
| # | Claim | Attack lands? | Survives as |
|---|---|---|---|
| A1 | consumer-mask rule | YES | Hamming + cut explanation of one netlist (255/255 by `min(ham, copies touched)`) |
| A2 | E2 synthesis variance | PARTLY | quantified SYNFI-consistent map; report 94/38/20 per distinct netlist |
| A3 | product scope sweep | YES (code), PARTLY (value) | reporting table; 2 of 4 P3 axes not shipped |
| A4 | B3 rail-dip survival | PARTLY | bounded negative; V0 survives whole-rail too |
| A5 | L2 spread threshold | PARTLY | what-if valid only for a selective dip; LVS fails |
| A6 | T3 speedup | PARTLY | real (19-100x on V2), standard encoding |
| A7 | predictor 92% | YES | sound lb 83%, heuristic +9 points, failed own bar |
| A8 | P3 verdict-belongs-to | PARTLY | reporting convention, not a refutable finding |

## Part 2. Inversion: how to guarantee the author fails the review tomorrow
Status: YES following now, PARTLY, NO. Evidence in the right column is VERIFIED unless marked READ/INFERRED.

| # | Recipe | Now | Evidence | Fix tonight |
|---|---|---|---|---|
| 1 | Go in unable to re-derive anything (s17 "My own contribution" empty; author has not re-derived) | YES | `PROJECT_DOSSIER.md` l.170 "author to write"; README says author has not reviewed | Do ONE unaided derivation (the mask rule in the form `min(Hamming, copies touched)` on a 4-bit mask, 15 min on paper) and write 5 lines in s17 about it. This is the single highest-value action. |
| 2 | Recite "the mask rule" as a discovery | YES (README/dossier call it "rule", "exact 255/255") | A1 | Rehearse the answer: "it is a Hamming distance plus a cut count, exact on one netlist, fails on re-synthesis (68/255)". Edit wording in the Q&A sheet. |
| 3 | Quote 92% and "180/60/24" without baselines | YES | A2, A7; README table | Quote 94/38/20 per distinct netlist; quote "always-1 gets 62%, lower bound alone 83%". |
| 4 | Let the reviewer find a claim that is truer for the unprotected design (B3) | PARTLY | A4: V0 also `>3` under rail_all | Add "V0 also survives whole-rail" to the B3 row; never say "V2 resists dips". |
| 5 | Present L2 as hardening | PARTLY | README "L2 in progress" is stale (L2 is finished; dossier has it) | Replace the README line; lead with "valid only if a dip can pick gates; LVS fails". |
| 6 | Claim novelty or "validated against SYNFI" | NO | rules and PRIOR_ART wording ("nothing established as new") | Keep; add: "E2 is consistent with SYNFI's 3->2 and 4->2; we did not reproduce its dont_touch fix". |
| 7 | Say "product implements the method" | PARTLY | A3: synthesis and counting axes not shipped | Say "scope sweep over goal, input sites, init; synthesis and counting are done by research scripts". |
| 8 | Blur model and physics (glitch, dip, "attack") | PARTLY | many tables say "flip", B3/L2 say "dip" | One spoken sentence: "bit flips in a netlist; a dip is a modelled event set; nothing measured on a chip". |
| 9 | Not know the weakest slide (one netlist, T=6, k<=3, `>3` is not secure; PDR proof is one netlist, k<=2, not replicated) | PARTLY | README lists them but they are paragraphs | Memorise 4 limits: toy 8-bit, T=6/k<=3, one PDR netlist, no physical test. |
| 10 | Cannot demo or reproduce live | PARTLY | START.md commands work on a copy; commands rewrite `results/`, `tb/` | Pre-run the three START.md commands on a fresh copy tonight, keep the output on screen; never run `make reproduce` in the tree. Have `scope-sweep` output (A3 command above) ready as the 4x4 table. |

Count: YES 3 (1, 2, 3), PARTLY 6, NO 1. If the author does fixes 1 to 3 only, the review risk drops most (INFERRED).

## Not done / limits
- Did not re-run L2/OpenROAD or SPICE (tools not in this env); A5 is read-only evidence.
- A4 combined 0->1 plus 1->0 supply-bounce event not modelled; I did not add it.
- A7 recount uses the `est` column, VER's 150/163 uses `pred`; unreconciled.
- A6 timeouts at 60 s (not the 150 s used by T3), so ratios are lower bounds.
- All counts bounded (T=6, k<=3), modelled flips, toy designs; nothing physical; nothing here is claimed as new.
