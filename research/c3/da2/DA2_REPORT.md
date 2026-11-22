# DA2 report: Devil's advocate + inversion
Step DA2, 2026-11-19 evening UTC. Working copy: `/tmp/work_da2/p` (copy of the tree without handoff/layout/third_party_derived); nothing in the project was edited. Labels: **VERIFIED** = I ran or read it in this run (command given); **INFERRED** = my reasoning, not tested. Rows already in `docs/dossier/CRITIQUE.md` (CT-1..15, DA-1..4, K-1..6, CE-*, E1-*, EL2-*) are not repeated except where I add a new measurement.

## Part 1. Six central claims, attacked

### C1. "V2 holds against 2 flips" (scoped resistance)
- Attack (new, generalises CT-1): the claim only protects a consumer that decodes all 8 bits of `boot_word`. Real consumers decode few bits. How many bits must a consumer decode before V2's resistance appears at all?
- Test: patched copy of the solver (`/tmp/work_da2/t1/gs_mask.py`, only change: goal = "bits in mask equal 0x96 on those bits"), spike V2, T=6, k searched 0..3, every bit-mask of size 1..4 (162 masks), then 5..7 (see below). Command: `python3 /tmp/work_da2/t1/run.py` (output `/tmp/work_da2/t1/out.txt`).
- Result (VERIFIED, MEASURED, T=6, spike netlist, modelled flips): masks that already collide with a legitimate state (F0, CC, 69) accept with 0 flips (25 masks of size 1..3 and 2 of size 4 collide: such a consumer is not even protected fault-free). Of masks that separate 0x96 from the other legal states: 1 bit: min 1 (2 of 2); 2 bits: min 1 in 16 of 17, min 2 in 1; 3 bits: min 1 in 34, min 2 in 14; 4 bits: min 1 in 28, min 2 in 36, min 3 in 4. For a consumer that decodes 4 bits, V2 is no better than "min 2" in 64 of 68 cases and falls to 1 flip in 28 of 68. Only the full word gives 3.
- Verdict: **attack lands partly.** The 3-flip figure is a property of an 8-bit-wide decoder, not of "V2". With the CT-1 result (boot_ok = 1 flip) this says V2's number measures decoder width as much as redundancy. Survives only as "for a full-word consumer".
- Additional check (VERIFIED, `python3 -m pytest -q tests` in the copy): 10 passed in 37.8 s, so the engine behind these numbers is the tested one.

### C2. "Unbounded PDR proof for k<=2"
- Attack: a PASS from a solver is worthless if the encoding is vacuous (assumptions contradictory, or the engine returns PASS for everything), or if "not PASS" is just tool failure.
- Test: re-ran ABC PDR through the project wrapper on controls (`formal/src/matrix.py` `run(..., mode='prove', eng='abc pdr')`, formal env on PATH, copy only): V2 spike k=2 PASS (8.9 s); V1 spike k=0 PASS; apt-0.33-type netlist `w2` k=1 PASS; and non-PASS for the known attackable cases: V1 k=1, `w2` k=2, and honest input k=0 (the legitimate key does reach the word). I opened the sby log of V1 k=1: `Status returned by engine: FAIL` from ABC PDR; the reported `NOSTATUS` comes only from the follow-up trace step that needs `yices` (not installed: "SMT Solver 'yices-smt2' not found").
- Result (VERIFIED): the encoding is not vacuous and PDR does separate attackable from non-attackable cases. D1-2 ("PDR k=3 NOSTATUS, attack not re-confirmed") is therefore a labelling artefact: the engine said FAIL; the wrapper prints NOSTATUS. Fix = map "engine FAIL, trace step failed" to "FAIL (no trace)".
- Remaining true weakness (INFERRED, partly known as CE-9): no certificate; same flip semantics as the solver; one netlist.
- Verdict: **survives** (as a statement about the one spike netlist, constant or free non-key input).

### C3. "Tool agrees with SYNFI"
- Attack: agreement of two tools on a minimum count means little if they model different faults on hand-built inputs.
- Test (read only; third-party code was not re-run, rules forbid): read `compare/synfi_run/SYNFI_RESULT.md` section 2. SYNFI does not search; it enumerates user-listed locations with a gate-TYPE replacement per location (e.g. NAND to NOR), is permanent for the evaluation, has no time model, and a multi-cycle scenario must be hand-written as stages. The project solver uses transient output bit flips with a built-in horizon. Different fault model, different time model.
- Result (VERIFIED by reading): agreement is on "minimum number of faulted locations" for three toy designs and one cycle-1 transition from a hand-chosen start state (matches IN-1, IN-2). It checks that two encodings reach the same count when the spec is hand-aligned, not that the model is right.
- Verdict: **partly** (true but weak; say "consistent with SYNFI on a hand-aligned one-cycle case"; never "validated against SYNFI").

### C4. "Layout results" (V1/V2 real sky130 layouts)
- Attack (answers an open inference in CE-3): V2 layout is only +1 cell over V1 (36 vs 35), so synthesis may have merged the three comparators back into one and the layout would then not be a V2 layout at all.
- Test: parsed `layout/v_designs/out_patched/v1_pnr.v` and `v2_pnr.v` (read only; regex over the cell instances; transitive fan-in cones of the nets `m0`, `m1`, `m2`).
- Result (VERIFIED): the V2 netlist keeps hierarchical net names `c0/_0_ ... c2/_1_`, `m0 m1 m2`; the cone of each `m` is 3 cells and the pairwise overlap of the three cones is 0 cells. So the three comparators are physically separate cells in the layout. The "+1 cell" is explained by V1 having only two comparators (V1 cone of `ok` = 7 cells) plus different glue. CE-3's merge suspicion is **not supported**. Not tested: any fault analysis on this netlist beyond EL2's mapped run (EL2-1).
- Still true (known, not repeated): LVS reference built from the same netlist, not signoff, no fault-site map in the physical sense.
- Verdict: **survives** (as a flow demo, with the same-netlist LVS caveat).

### C5. "Product readiness" (Face B, `product/`, package faultbound-wt)
- Attack: an adopter will bring a design that is not the toy; the first 15 minutes decide adoption.
- Test: fresh venv (Python 3.13) in `/tmp/work_da2/prod`, `pip install /tmp/work_da2/p/product`, then four new inputs: a 4-bit PIN lock with sync reset and a try counter (`d/pin.v`), the same with async reset (`d/pin_async.v`), a config with a mistyped output, and a config with a wrong `legitimate_value`.
- Results (VERIFIED, MEASURED, all copies):
  1. Install and the sync-reset PIN lock work: ATTACK_FOUND with 1 flip on one OR gate, exit code 1, 0.12 s. Good sign.
  2. The explanation text is canned toy-design prose and is wrong here: "combines 4 input bits ... (the redundant checks converge here) ... even though the checks upstream are duplicated". The PIN lock has no duplicated checks. A user will distrust the tool after one wrong sentence.
  3. Async-reset flop crashes with a raw Python traceback (`KeyError: 'Y'` in `_engine.py` line 48). The cell-type check promised in the README ("unsupported-cell check") does not cover `$_DFF_PN0_`/`$_DFF_PP0_`; known to CT (found by CT-4..15) but the product still ships it.
  4. Wrong `legitimate_value` (5 instead of the real 10): the tool reports `ATTACK_FOUND`, `min_faults 0`, prints "the attacker needs 0 coordinated single-cycle flips". The JSON field `honest_input_reaches_goal_fault_free` is False but the console prints no warning. A misconfigured run looks like a security finding.
  5. A mistyped output name gives a clear error (good).
- Verdict: **partly.** Works on the happy path, fails the first non-toy variant in two of four probes. "Product-ready" is not supported; "alpha for single-clock, sync-reset netlists" is.

### C6. The pivoted claim: "verdicts depend on how a fault is counted and on the exact netlist and scope"
- Attack (strongest): this is close to tautology. A stronger attacker model breaks more designs; any bound check changes when the netlist changes. The counting rule is the author's choice, so "depends on counting" is a statement about a free parameter, not a finding. And the physically defensible rule (a glitch on a wire hits every sink of that wire, so stem-flip costs 1) is the one under which V2 holds in only 6/32 re-syntheses, so the conservative "V2 holds on all 32" comes from the less realistic rule.
- Test: re-synthesised `rtl/v2.v` with the project script on this machine (`scripts/synth.sh rtl/v2.v v2 /tmp/work_da2/v2_apt.json plain`, apt Yosys 0.33), 85 gates, 8 flops. `glitchsat.solve(nl, 6, 2)`: ATTACK_FOUND with two flips, both at cycle 0: `$abc$275$new_n58_` (AND, fanout 3) and `$abc$275$new_n74_` (OR, fanout 2). Under fanout weighting that attack costs 5, which exceeds the 3-flip minimum.
- Result (VERIFIED): reproduces DA-2 independently on a fresh run, and shows the two nets are ABC-introduced shared nodes, not nets of the RTL.
- Verdict: **partly.** The finding is real but its honest form is narrower and more useful: "the number is a function of (fault model, counting, netlist); here are the three numbers and which is physically defensible", plus a metric that does not move with the counting rule: the structural cut size. DA-4 already suggests cuts; I add one rule for the report: state which rule is the realistic one (stem = 1) and that under it V2's 2-flip resistance is the fragile case (6 of 32). Do not present the weighting rule as a rescue of V2.

## Part 2. Inversion: how to guarantee the project is useless, fails the review, fails adoption

Recipe, is the project following it now, tonight fix. Status: YES (following), PARTLY, NO.

| # | Guaranteed-failure recipe | Now | Evidence | Fix tonight |
|---|---|---|---|---|
| 1 | Let the reviewer find the author cannot explain it (everything written up in process reports; section 17 blank) | YES | `docs/dossier/PROJECT_DOSSIER.md` s17 empty by design; the disclosure page is a draft | Prepare a 10-question oral self-test per file the author must pass before submitting; list 3 files the author re-types or re-derives by hand (worked_example.py, test_hamming.py, glitchsat build()). INFERRED value, cheap. |
| 2 | State a headline the evidence does not carry (V2 resists 2 flips) | PARTLY (scope paragraph added) | README top paragraph is ~250 words; C1 above shows decoder-width dependence | Replace the headline by a three-row table: full-word consumer / boot_ok / 4-bit consumer = 3 / 1 / 1-2 flips. One table beats caveats. |
| 3 | Ship a tool whose first wrong output is a confident wrong sentence | YES | C5 items 2 and 4 | Gate the canned "redundant checks converge" text on the number of gates with identical cone (or drop it for non-toy input); print a console warning when honest input does not reach the goal, and make min 0 print "misconfigured: goal reached with no fault". Two small patches in `product/` (author of that scope applies). |
| 4 | Crash on the first realistic design | YES | C5 item 3 (async reset KeyError) | Catch unsupported cell types in Netlist.__init__ and exit 3 with "cell type X not supported; run `synth -flatten; dfflegalize -cells $_DFF_P_`"; add the dfflegalize line to the Verilog flow (INFERRED fix, untested). |
| 5 | Make claims no one can reproduce | PARTLY | `make test` passes (10 passed, 37.8 s, VERIFIED here); formal env, SPICE, layout live in /tmp and are not in the bundle | Add one `REPRODUCE_FROM_ZERO.md` row per claim with a copy-paste command and its expected token; mark the not-rebuildable ones "NOT REPRODUCIBLE FROM THIS BUNDLE". |
| 6 | Bury the point in size (685 MB tree; 10,344 files under `compare/` incl. a venv and a third-party clone; 12k files) | YES | `du -sh .` 685M; `compare/synfi_run/venv`, `src` | Exclude `compare/synfi_run/venv` and `src` (and formal runs) from the bundle; keep only logs and scripts. Already noted as a rule for the bundle; make it a checked list. |
| 7 | Claim novelty or "first" or "proves secure" | NO (rules enforced; "nothing established as new") | README, FINAL_STATUS | Keep. Add a grep gate: fail the wrap-up if `first|novel|proves secure|breaks OpenTitan` appear outside quoted-critique contexts (INFERRED, 5-line script). |
| 8 | Rely on one engine, one netlist, one tool build | PARTLY | PDR on one netlist; solver and PDR share the flip semantics (CE-9) | Cheapest independent oracle tonight: brute-force enumerator over flip sets on the 85-gate netlist at k=1 (all 93 sites x 6 cycles) in plain Python without z3, compare with the solver. Validation already does this on spike; repeat on the apt netlist (INFERRED, ~20 lines). |
| 9 | Let a physical-glitch implication slip in | PARTLY | CE-1; SPICE bridge in flight | Banner line on every page: "bit flip in a netlist, not a glitch". Grep gate as in 7. |
| 10 | Hide the weak spot until the reviewer finds it | NO (limits are written) | dossier s10 | Keep, but put the top three limits on slide 2, not in an appendix. |
| 11 | No adoption path: undecided licence, unpublished package, no CI proof, name TBD | YES | LICENSE_CHOICE.md only; "CI never ran on GitHub"; package name `faultbound-wt` working title | Author decision; tonight prepare a one-line SPDX choice sheet (MIT vs Apache-2.0, consequences) and a tag-ready `pyproject` with license field blank-guarded. Do not publish (rules). |
| 12 | Make the front door unreadable so nobody reaches the content | YES (CO: 2-3/10) | CRITIQUE CO-1..15 | Rewrite top 20 lines of README as: one analogy sentence, one table (C1 fix), one command. FD step already queued; give it the 3-row table. |

Count: following now YES in 6 (1, 3, 4, 6, 11, 12), PARTLY in 4 (2, 5, 8, 9), NO in 2 (7, 10).

## Not done / limits (honest)
- Masks of 5..7 bits: NOT finished within the time cap (run killed); only sizes 1..4 are measured, so the width at which V2 reaches 3 is not located (full 8 bits gives 3).
- I did not re-run SYNFI, FIRMER or other third-party tools (rules).
- All solver numbers are bounded (T=6, k<=3), flips are modelled; nothing here concerns physical glitches.
- Recipe 8 and 4 fixes are INFERRED (not coded).

## Files
- This report. Scratch (not part of the deliverable): `/tmp/work_da2/t1/` (mask patch, outputs), `/tmp/work_da2/prod/` (product probes), `/tmp/work_da2/p/` (tree copy).
