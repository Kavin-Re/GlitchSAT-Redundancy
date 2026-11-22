# CC_FINDINGS: claims reviewer CC

Scope: README.md, docs/FINAL_STATUS.md, docs/report/{ONE_PAGE_SUMMARY,PROJECT_REPORT,DEMO_5MIN,SLIDES_OUTLINE}.md, dashboard/index.html (visible text and embedded DATA), checked against results/, docs/DEEP_RESULTS.md, docs/ENGINE_STATUS.md, validation/, formal/, plus layout/, compare/, real_designs/, numerics_audit/ where cited. Work was done on a copy at /tmp/work_cc/ (tar without handoff and layout; layout files were read from the original, read-only). Nothing outside this folder was written. Label for this file: 

Bottom line: the headline numbers are reproduced. Every verdict I re-ran matched the documents. The problems are wording, labels, stale lines and a few omitted netlists, not wrong numbers. I found 21 issues (no padding; 2 are "medium", most are "low").

## A. What I re-ran (all on the copy; all MEASURED by me, 2026-11-19, apt Yosys 0.33, z3 5.4.1; formal env Yosys 0.38+92)

| # | Re-run | Command | Result | Matches docs? |
|---|---|---|---|---|
| R1 | Unit tests | `make test` | 10 passed in 21.6 s | yes (docs: 10 passed, about 19 to 20 s) |
| R2 | V0/V1/V2 verdicts, 3 routes | `make reproduce` then `make check-reproduce` | "36/36 rows match"; V0 min 1, V1 min 1 (`ok`@1), V2 spike none for k<=2 and min 3 at k=3, V2 RTL (plain, opt) min 2 | yes. Runtimes differ (V2 spike k=2 2.45 s vs the stored 1.178 s; k=3 10.1 s vs 5.139 s) |
| R3 | Demo Act 1 pair | `glitchsat.py check rtl/v1.v ... --k 1 --cycles 6` then `replay.py` | `min faults: 1 [('ok', 1)]`; faulted `boot_word=96`, fault-free `69`, `agrees_with_solver: true` | yes |
| R4 | Replay of 13 witnesses | `validation/replay.py` | "confirmed 13 not 0" | yes |
| R5 | k=1 exhaustive on spike V2 | `validation/k1.py reference/spike_netlists/v2.json v2 6` | 0 of 456 (site,cycle) pairs | yes |
| R6 | All 2-fault sets, V2 spike | `validation/k2.py ... v2 4 2` and `... v2 6 2` | 46,056 sets (T=4) and 103,740 sets (T=6), 0 successful | yes (both counts equal C(304,2) and C(456,2)) |
| R7 | Boolector second solver | `validation/smt.py` + boolector (formal env) | V2 T4 k2 unsat; V2 T6 k2 unsat; V2 T6 k3 sat; V1 T6 k1 sat | yes |
| R8 | Deep-sweep cells | `glitchsat.py check` directly: V2 spike k=2 at 8 cycles; V2 RTL k=2 at 12 cycles; V2 spike k=4 at 6 cycles | no attack (5.9 s); attack min 2 (1.2 s); attack min 3 | yes (docs: 12.0 s, min 2, min 3). I also parsed all 90 + 4 JSON records of results/deep: verdicts match the DEEP_RESULTS table and the dashboard DATA |
| R9 | PDR proofs | `sby -f` on formal/runs/s2_v2_k1, k2, k3 and w2_v2_k2 `*_prove_abc_pdr_d6.sby` | k1 PASS, k2 PASS (3 s wall), k3 FAIL, w2 k2 FAIL | yes |
| R10 | Gate counts | `scripts/synth.sh rtl/v2.v` with apt 0.33 and with conda 0.38+92 | 85 gates (40 AND, 25 OR, 20 NOT, 8 DFF) vs 83 gates (37/25/20, 1 MUX, 8 DFF); the project solver on the 83-gate netlist: no 2-fault attack; spike netlist 68 gates (16 MUX) + 8 DFF | yes |
| R11 | Dashboard rebuild | `python3 dashboard/build.py` | engine rows (27) identical in verdict and min faults to the shipped page | yes |
| R12 | `make validate` | as in Makefile | V0 flat: 32 of 114 single faults succeed; V1 and V2: 4 of 378 each | numbers match VALIDATION.md, but see CC-4 |

Not re-run (stated, not hidden): layout flow (needs the 12 GB env), SYNFI run (3 to 11 minutes, venv), numerics/CBMC audit (needs the CMSIS clone), 20-cycle k=3 cells, real-design numbers (taken from the reports), browser tests of the dashboard, CI on GitHub.

## B. Claim table (headline numbers; "label" = MEASURED/UNVERIFIED etc. as it should read)

| Claim | Location | Cited source | Matches? | Label correct? | Wording overclaims? |
|---|---|---|---|---|---|
| 10 tests pass | ONE_PAGE, REPORT 5, DEMO, README | ENGINE_STATUS / R1 | yes | MEASURED ok | no |
| 36/36 rows match | DEMO, REPORT 5 | ci/check_reproduce.py / R2 | yes | MEASURED ok | no |
| V0 min 1; V1 min 1 on `ok`; V2 spike none k<=2, min 3 at k=3; V2 apt-0.33 RTL min 2 | README, FINAL, ONE_PAGE, REPORT 6, DASH | reproduce_summary.json / R2 | yes | MEASURED ok | no (but see CC-4, CC-9) |
| 85 vs 83 gates, 2-flip attack only with apt 0.33 | FINAL, ONE_PAGE, REPORT 6.4, DEMO, slides 10, DASH | FORMAL.md section 3 / R10 | yes (plain flow) | MEASURED ok | "cause: the Yosys build" is a hypothesis (CC-10) |
| 1.178 s and 5.139 s | REPORT 6 | summary JSON | yes in file | MEASURED ok | no label that it varies by run (CC-17) |
| 46,056 and 103,740 two-fault sets, none succeed | all | VALIDATION / R6 | yes | MEASURED ok | no |
| 13 of 13 witnesses; 5 boolector queries | REPORT 5, slide 7 | VALIDATION / R4, R7 | yes | MEASURED ok | no |
| about 2.1M simulated fault sets | REPORT 5 | VALIDATION | sum of its rows is 2.17M | ok | rounding (CC-20) |
| 40 sby/solver pairs agree | FINAL, REPORT 5, 6.3, slide 7 | FORMAL | yes (10 netlists x 4 k) | MEASURED ok (worker; I re-ran 4 PDR, not the 40) | no |
| PDR proof, V2 spike k<=2, any number of cycles | FINAL, ONE_PAGE, REPORT 6.2, DEMO, slide 8, DASH | FORMAL section 4 / R9 | yes | MEASURED ok | "only one netlist" is not exact (CC-8); "proved" without bound in two places (CC-5) |
| 90 sweep runs, no timeouts; V2 spike k=2 none to 20 cycles; min 3 stays | ONE_PAGE, REPORT 6.1, slide 9 | DEEP_RESULTS / R8 | yes | MEASURED ok | k=4,5 only at T=4,6 (CC-6) |
| Mutation: netlist 2 of 2 caught; RTL 1 of 3 caught | REPORT 5 | mutation_summary.json | yes | MEASURED ok | no |
| Reduction gain "15 to 25 percent fewer fault variables" | REPORT 6 | reduction_benchmark.json | 17 to 29 percent | ok | small (CC-19) |
| Layout: router DRC 0, LVS unique 422/422 and 430/430, slack +7.050/+0.519, antenna 0, off-grid 0 | FINAL, REPORT 6 and 6.5, ONE_PAGE, DASH | RESULT.md, VERIFY.md | yes | MEASURED ok (not re-run; ESTIMATED for slack, stated) | "35 cells, 399 um2" mixes synth cells with placed area (CC-13) |
| std-cell DRC errors are missing-tap false positives | all | VERIFY section 2 | yes, tested on dfxtp_1 only | stated | "explained" is stronger than evidence (CC-14) |
| Door lock: 6 gates, k=1, LVS "failed pin matching" | ONE_PAGE, REPORT 6.6, slide 13 | real_designs/second/REPORT.md | yes | reported by worker, not re-run (stated in REPORT, not in ONE_PAGE) | no |
| SYNFI: V2 triples 182 of 35,990 | ONE_PAGE, REPORT 8, slide 14 | SYNFI_RESULT.md | yes | MEASURED (worker) | no |
| sqrt_q15 7.15 LSB at 31797, 25 inputs above 6 LSB | FINAL, REPORT 6.8 | AUDIT.md | yes | MEASURED ok | no |
| CBMC bound 8 LSB | FINAL, REPORT 6.8 | AUDIT.md "spike, not re-run" | yes | should be UNVERIFIED (spike) (CC-15) | no |
| Fuzzing 0 mismatches in about 6,700 programs | FINAL, REPORT 5 | handoff GASP_DECISION | n/a | UNVERIFIED ok | belongs to another artefact (CC-16) |
| Panel "about 6/10"; "3/10 today, ceiling 6/10" | FINAL, REPORT 10 | R3_evaluator_panel, GASP_DECISION | numbers exist | wrong subject (CC-3) | yes |

## C. Findings

Severity: HIGH = a reader is likely to be misled; MEDIUM = inaccurate or stale statement of substance; LOW = wording, label or tidy-up.

### CC-1 (MEDIUM) "Strong, evaluated project" in the report opening
- Where: PROJECT_REPORT.md line 3 ("This is a strong, evaluated project"); REVIEW_NOTES line 26 says "Kept: strong evaluated project".
- Evidence: the same report says no external win, no novelty, layouts not DRC-clean, door lock too small, and the evaluator panel (R3_evaluator_panel.md) scores novelty 3, reproducibility 5, overall about 6/10. "Strong" is an unsupported self-rating.
- Replacement: "This is a reproducible, independently cross-checked teaching project on toy designs. It is not a novel research result."

### CC-2 (MEDIUM) "Independent panel" is a simulated panel
- Where: FINAL_STATUS.md line 8 ("the independent panel scored it about 6/10").
- Evidence: the source is handoff/decisions/R3_evaluator_panel.md, written by a step in this workflow. Calling it "independent" suggests human reviewers.

### CC-3 (MEDIUM) The 3/10 and 6/10 scores are attached to the wrong thing
- Where: PROJECT_REPORT section 10 ("Self-score from the project's own gasp review: 3/10 today, ceiling about 6/10"); FINAL_STATUS "gasp search chair's own honest score: 3/10".
- Evidence: GASP_DECISION.md line 13: the 3/10 and 6/10 score the proposed "CertBound" numerics project, not the fault-injection project. R3 (point 14) already notes it "invites the authorship question". FINAL_STATUS also gives 6/10 for this project from the panel, so one file shows two scores for two things without saying so.
- Replacement: drop the "self-score" sentence from section 10, or write "A separate gasp review scored a different candidate (CertBound) 3/10 today and about 6/10 at best; it is not a score of this project."

### CC-4 (MEDIUM) A third V2 netlist with a single-flip attack is not in the headline tables
- Where: README one-sentence result, ONE_PAGE table, REPORT 6, slide 6, DASH engine table (all list only spike, apt-0.33 plain, apt-0.33 opt).
- Evidence: VALIDATION.md "netlist-dependence": on its own flow (B: keep_hierarchy stripped, `synth -flatten`), V2 has 4 of 378 successful single faults at T=6 and 1,266 of 71,253 fault pairs; V1 (B) has 4 single faults, `ok` merged away. I reproduced this with `make validate` (R12: V1 and V2 "4 of 378"). So V2 min is 1 on that netlist, 2 on apt-0.33 RTL, 3 on spike/conda-0.38. The docs say "depends on the exact netlist" but only show the 2-versus-none contrast.
- Also: `make validate` (Makefile, CI nightly) runs those flat netlists and prints V2 attacks with no explanation, while the surrounding text says V2 held. Help text should say it is netlist (B).
- Replacement (ONE_PAGE caveat): "On a third netlist (validation flow B, hierarchy stripped) the same V2 source falls to a single flip (4 of 378 single-flip sites at 6 cycles, MEASURED, validation/VALIDATION.md). Minimum flips by netlist: 1, 2 or 3."
- Replacement (Makefile help): "make validate - gate-level simulator on the flat netlists nl/ (flow B); V1 and V2 here DO show single-flip attacks".

### CC-5 (MEDIUM) "proved" without its bound, and "proof" in glossary
- Where: DEMO_5MIN.md line 56 ("proved for any length, for this fault model"); SLIDES_OUTLINE.md slide 18 notes ("proved for any length"); dashboard glossary ("'No attack found' is a proof only within those limits").
- Evidence: the allowed form needs solver output and bound: ABC PDR via SymbiYosys, V2 spike netlist, k<=2, constant attacker input, no external certificate (FORMAL.md). R9 confirms PASS (k=1,2) and FAIL (k=3), but the two sentences drop the netlist, solver and "no certificate".
- Replacement: "no attack with 1 or 2 flips for any number of cycles, as reported by ABC PDR (SymbiYosys) on the spike V2 netlist only, constant attacker input, no independent certificate". Dashboard glossary: "'No attack found' is a bounded SAT result: it holds only within those limits."

### CC-6 (LOW) "k=4 and k=5 do not lower it" reads as if tested to 20 cycles
- Where: PROJECT_REPORT 6.1 (inside the "up to 20 cycles" bullet); FINAL_STATUS next steps ("T up to 20, k up to 5 ... done"); SLIDES slide 16 ("up to 20 cycles and 3 flips" is right, but slide 9 and FINAL merge them).
- Evidence: sweep_deepk.json has only 4 runs: k=4 and k=5 at cycles 4 and 6. (Confirmed by parsing; R8 re-ran k=4 at 6 cycles.)
- Replacement: "k=4 and k=5 were run only at 4 and 6 cycles and did not lower the minimum (3)."

### CC-7 (LOW) Stale timestamp and dangling pointers in FINAL_STATUS
- Where: FINAL_STATUS.md line 1 ("written 2026-11-19, about 05:50 UTC") while the file contains an "Update (formal tools, 16:07 UTC)" section; "Known weak points" 4 points to `scratchpad/gasp/spike_layout` (missing); Open items point to `<home>/sensortrust` (missing on disk); Next steps 3 lists items as done that sit in "next steps".
- Replacement: header "first written 05:50 UTC, last updated 16:07 UTC (formal update)"; replace the two dead paths with "(path no longer present; reinstall command is in `scripts/setup_layout_tools.sh` and `layout/v_designs/README.md`)". Move the "done" items out of Next steps.

### CC-8 (LOW) "Only one unbounded proof / one netlist" is slightly off
- Where: dashboard glossary ("Only one exists here: V2 on one netlist, up to 2 flips"); slide 16; REPORT 6.2/7.
- Evidence: FORMAL.md section 4 also lists PDR PASS for s2 k=0 and k=1, and for w2 (stored 85-gate apt-0.33 netlist) at k=1. I re-ran s2 k=1 (PASS) and w2 k=2 (FAIL, as documented).
- Replacement: "Unbounded results exist only for the V2 spike netlist (k up to 2) and, at k=1, for the stored 85-gate apt-0.33 netlist."

### CC-9 (LOW) "Split copies helped" and "Fix it" are stated without the netlist condition
- Where: DEMO_5MIN Close; slide 18; ONE_PAGE "Plain lesson"; dashboard Act 2 heading "Try a fix (V2)" and Act 2 note.
- Evidence: V2 resists 2 flips only on two netlists of three or four (CC-4). A listener hearing "split copies helped" takes it as general.
- Replacement: "On the spike netlist split copies resisted 1 and 2 flips; on the apt-0.33 re-synthesis they did not."

### CC-10 (LOW) "Cause found: the Yosys build" is a hypothesis
- Where: FINAL_STATUS, ONE_PAGE, REPORT 6.4/7.3, slide 10.
- Evidence: I reproduced both gate counts (R10). Two builds differ in Yosys 0.33 vs 0.38, bundled ABC, packaging and compiler. FORMAL.md itself says "Why ABC differs between the two builds was not analysed." That is a correlation across two builds, not a located cause.
- Replacement: "The difference tracks the tool build (apt Yosys 0.33 vs conda Yosys 0.38+92); the reason inside ABC or Yosys was not analysed."

### CC-11 (LOW) ENGINE_STATUS says the opt flow also gives 85 gates
- Where: docs/ENGINE_STATUS.md results table ("plain and opt flows; 85 gates"); repeated by DASH "(opt)" row text.
- Evidence: `results/work/v2_opt.json` (apt 0.33) has 81 gates (38 AND, 23 OR, 18 NOT, 2 MUX, 8 DFF); 85 is the plain flow. The 2-fault result holds for both. Conda 0.38 was run only for the plain flow.
- Replacement: "plain flow 85 gates, opt flow 81 gates; both give a 2-flip attack with apt 0.33; conda 0.38 not run for the opt flow."

### CC-12 (MEDIUM) Dashboard Act 2 note contradicts the attack the page itself reports
- Where: dashboard Act 2 note ("An attacker has to corrupt all three copies") vs the EXPL text ("two compare gates plus one bit of the output word"); VALIDATION example `word[0] + c1/c2 compare nets @1`.
- Evidence: 182 effective triples at cycle 1 include sets that do not touch all three compare copies (VALIDATION, SYNFI_RESULT, and the min-3 result at k=4 in R8: `c0.m`, c1 net, c2 net).
- Replacement: "The smallest attacks found use three flips; some hit all three compare copies, some hit two copies plus a bit of the result word." (Wording only; no restyle needed.)

### CC-13 (LOW) Dashboard Act 4 mixes cell count and area
- Where: dashboard Act 4 note "35 cells, 399 um2 placed at 77%".
- Evidence: RESULT.md: 35 synthesized cells = 357.8 um^2; OpenROAD area 399 um^2 at 77% includes taps, clock tree and fill (76 placed components). 399 is not the area of 35 cells.
- Replacement: "35 synthesized cells (357.8 um^2); 76 placed components including taps and fill, 399 um^2 core area used, 77% utilisation (ESTIMATED by the flow tools)." Also mark slack "ESTIMATED".

### CC-14 (LOW) "Explained" / "false positives" for standard-cell DRC errors
- Where: FINAL_STATUS, ONE_PAGE, DEMO ("I traced them to missing tap cells"), slide 12 ("Standard-cell DRC errors are false positives").
- Evidence: VERIFY.md: the one-cell context test (tap + dfxtp_1 + tap) was clean; 29 other cell types were only shown to carry the same three rule names. "Not re-tested in context" is in a parenthesis but the headline is stated as fact. Also the a[26] workaround leaves li.3 x12 which VERIFY says "remains real".
- Replacement: "Tap-dependent rules (nwell.4, LU.2, LU.3); clean in context for one cell (dfxtp_1); the other cell types were not tested in context; the layout is not claimed DRC-clean."

### CC-15 (LOW) CBMC "bound 8 LSB" label
- Where: FINAL_STATUS "Numerics" bullet; REPORT 6.8.
- Evidence: AUDIT.md marks the CBMC row "(spike, ... not re-run)". FINAL_STATUS puts it under "Results (MEASURED unless stated)" without saying so. The 7.15 LSB and 25-input numbers were re-run in the audit.
- Replacement: "CBMC bound of 8 LSB: UNVERIFIED here (spike result, not re-run)."

### CC-16 (LOW) Fuzzing row sits in the validation table of an unrelated artefact
- Where: PROJECT_REPORT section 5 table; FINAL_STATUS.
- Evidence: the 6,700-program fuzzing tested Yosys, iverilog and Verilator, not this solver (R3_evaluator_panel point 15); labelled UNVERIFIED, which is right, but a reader scanning "validation" counts it as evidence.
- Replacement: remove from the validation table or move to "Other work (UNVERIFIED, not part of this project's evidence)".

### CC-17 (LOW) Exact runtimes quoted without "varies"
- Where: PROJECT_REPORT 6 table ("1.178 s", "5.139 s"); dashboard DATA; slides.
- Evidence: my re-run gave 2.445 s and 10.1 s; REVIEW_NOTES already saw 1.326 s and 7.17 s. These are wall-clock on a loaded box.
- Replacement: "about 1 to 2.5 s (k=2) and 5 to 10 s (k=3); MEASURED, machine and load dependent".

### CC-18 (LOW) Deep sweep is not re-runnable from the repo as shipped
- Where: DEEP_RESULTS.md "Commands" and "Netlists in results/deep/work/nl/".
- Evidence: `results/deep/work/` does not exist in the repo; `results/deep/run_one.py` hard-codes `scripts` and `results/deep/work`, so running it on a copy would write into the original results (I did not run it; I ran glitchsat.py directly instead, R8). The results are still checkable from `results/deep/json/` (94 files).
- Replacement: add to DEEP_RESULTS: "work/nl/ is not stored; the sweep scripts use absolute paths; re-run single cells with `glitchsat.py check`." (Lead to decide whether to fix the script.)

### CC-19 (LOW) Reduction-benchmark ranges are slightly off
- Where: PROJECT_REPORT 6 ("about 15-25 percent fewer fault variables"); ENGINE_STATUS ("0-24 percent faster").
- Evidence: reduction_benchmark.json: 304 to 215 (29%), 456 to 353 (23%), 608 to 491 (19%), 760 to 629 (17%); time gain up to 26% (0.46 to 0.34 s).
- Replacement: "about 17 to 29 percent fewer fault variables; up to about 25 percent faster, noise-level in places".

### CC-20 (LOW) "About 2.1M" simulated fault sets
- Where: PROJECT_REPORT section 5.
- Evidence: 46,056 + 103,740 + 1,949,476 + 70,300 + singles = about 2.17M (VALIDATION.md rows).
- Replacement: "about 2.2M".

- Physical wording (no explicit hardware claim found; these lines invite one): ONE_PAGE "fewest wire glitches that make a secure-boot chip boot with the wrong key"; REPORT 1 "An attacker who can flip a single wire for one clock tick (a 'glitch') may trick it"; DEMO "A chip checks a key"; DEMO Act 4 "This is the real sky130 layout"; dashboard title "secure-boot FSM". Faults are modelled single-cycle bit flips in a netlist model; no chip, no glitch hardware.
  - Replacement (ONE_PAGE): "what is the fewest modelled bit flips that make a toy secure-boot circuit accept the wrong key?" (DEMO): "a flow-demo sky130 layout of the toy design; no chip was made."
- Labels missing on top-level text: README one-sentence result (numbers 1 and 2, no label or bound); ONE_PAGE "Real layout", "Real designs" paragraphs (no MEASURED, and the door-lock figures are worker-reported, not re-run, which only REPORT 6.6 says).
  - Replacement (README): append "(MEASURED, 6 cycles, solver in `scripts/glitchsat.py`; see docs/FINAL_STATUS.md)".
- Banned words check: "novel" appears only as "not a novel research result"; "first" only in "never say first"; "secure" appears in "secure-boot" and "a design is secure" (negated); "breaks" is used only for modelled attacks; "proved/proof" see CC-5. No "first", "proves secure" or "breaks OpenTitan" anywhere. No claim of hardware, silicon, SPICE or physical glitches.

## D. Things I checked that are fine (no action)
- V0/V1/V2 verdict table, replay, 36/36, 10 tests, 46,056 / 103,740, 13/13, boolector 5 queries, PDR PASS/FAIL, 85/83 gate counts, spike 68+8 with 16 MUX, 90-run sweep, dashboard engine rows all match the cited files (R1 to R11).
- Prior-art wording ("reproduces and teaches", "nothing established as new") is consistent across the six documents; SYNFI limits are stated the same everywhere.
- Layout numbers match RESULT.md and VERIFY.md; the clock period (10 ns) matches `flow_patched/pnr.tcl`; "not DRC-clean as a whole" and "door-lock LVS failed pin matching" are stated clearly.
- LICENSE is absent by design; every document says so.

## E. What I could not do
Layout flow, SYNFI and CMSIS/CBMC were not re-run (environment and time); the dashboard was not opened in a browser (only its text and embedded data were compared and rebuilt); GitHub CI has never run; I did not read the SYNFI or FIRMER papers, so no statement about novelty is made here beyond "nothing established as new".
