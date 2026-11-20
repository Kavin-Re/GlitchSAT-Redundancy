# Claims check: every number in docs/report/ and its source

Paths are relative to ``. "Docs" = PROJECT_REPORT.md, ONE_PAGE_SUMMARY.md, DEMO_5MIN.md, SLIDES.pptx, SLIDES_OUTLINE.md. Labels per `docs/EVIDENCE_LABELS.md`. Column "Re-checked" says what this refresh did: **YES** = I compared the number against the file or re-ran the command on 2026-11-19; **no** = copied from the source file, not re-checked.

Tool builds behind the numbers: Yosys 0.33 + z3-solver 5.4.1 (solver, sweep, validation); Yosys 0.38 + SymbiYosys (litex-hub 0.0.0_0074) + ABC + boolector (formal); OpenROAD f12e2f47, magic 8.3.464, netgen 1.5.272, KLayout 0.30.13 (layout).

## A. Engine (6 cycles)
| Number / claim | Where used | Source file | Label | Re-checked |
|---|---|---|---|---|
| 6 cycles; k up to 3; 36 result rows | all docs | results/reproduce_summary.json (`cycles`, `rows`) | MEASURED | YES: 36 rows; `make check-reproduce` printed "36/36 rows match" |
| V0 min 1 flip at k=1,2,3 (3 netlists) | report 6, summary, slide 6 | results/reproduce_summary.json | MEASURED | YES (re-run) |
| V1 min 1 flip, net `ok`, cycle 1 (spike netlist) | report 6, demo, slide 5 | results/reproduce_summary.json; docs/ENGINE_STATUS.md | MEASURED | YES (demo command printed `[('ok', 1)]`) |
| V2 spike: no attack k=1,2; attack min 3 at k=3 | report 6, summary, slide 6 | results/reproduce_summary.json | MEASURED | YES |
| V2 re-synthesized (plain, opt): no attack k=1; min 2 at k=2,3 | report 6, summary, slide 6 | results/reproduce_summary.json | MEASURED | YES (rows read from the JSON) |
| 1.178 s (V2 spike k=2); 5.139 s (k=3) | report 6 | results/reproduce_summary.json (original run) | MEASURED | YES in the file. A later re-run gave 1.326 s and 7.17 s; times vary by run. The file was restored to the original |
| `make test` 10 passed at first writing (now 189 passed (2 skipped); product tests 324 passed after `pip install ./product[test]`; RECON 2026-11-20 (re-measured by RECON6 on the unpacked bundle)); `make reproduce` about 25 s | report 4,5; demo | docs/ENGINE_STATUS.md | MEASURED | YES: 10 passed in 20.2 s; reproduce finished in well under a minute |
| Runtime 0.46 / 1.57 / 7.53 / 28.47 s at 4/6/8/10 cycles; 15-25 percent fewer fault variables | report 6 | results/reduction_benchmark.json; docs/ENGINE_STATUS.md | MEASURED | YES for 0.46 s and 304 vs 215 variables in the JSON; other cells no |
| Mutation: min cost 3 drops to 2, both caught | report 5 | results/mutation_summary.json; docs/ENGINE_STATUS.md | MEASURED | partly: RTL-level rows read (baseline 2, two mutants not caught); netlist-level no |
| 0x96 target, key 0xC3, fault-free stays 0x69 | report 1,4; demo; slide 2/4 | docs/ENGINE_STATUS.md | MEASURED | YES: replay printed `boot_word=69` fault-free |
| Fuzzing: 0 mismatches, about 6,700 programs (old tool builds) | report 5 | docs/FINAL_STATUS.md | UNVERIFIED (spike result, data not in repo; not reproducible from the repo) | no |

## B. Depth sweep and formal
| Number / claim | Where used | Source file | Label | Re-checked |
|---|---|---|---|---|
| 90 runs, cycles 8-20, k 1-3, all DONE, no timeouts | report 6.1, slide 9 | docs/DEEP_RESULTS.md; results/deep/sweep_main.json | MEASURED | YES: 90 entries, all status DONE |
| V2 spike k=2 at 20 cycles: no attack, 294.3 s; k=3: min 3, 474.9 s | report 6.1, slide 9 | results/deep/sweep_main.json | MEASURED | YES (294.27, 474.94) |
| V2 re-synthesized, k=2 at 20 cycles: min 2, 5.4 s | report 6.1, slide 9 | results/deep/sweep_main.json | MEASURED | YES (5.37) |
| Other cells of the sweep table (8 to 16 cycles) | report 6.1, slide 9 | docs/DEEP_RESULTS.md | MEASURED | no |
| k=4,5 on V2 spike: min stays 3 | report 6.1, slide 9 | results/deep/sweep_deepk.json | MEASURED | YES for k=4 (min 3 at 4 and 6 cycles); k=5 no |
| Practical limit about 20 to 22 cycles for k=3 | report 6.1, slide 9 | docs/DEEP_RESULTS.md section 4 | derived from measured times | no (reading of the table) |
| 40 sby-vs-solver netlist/k pairs, 0 disagreements | report 5, 6.3, summary, slide 7 | formal/FORMAL.md; formal/runs/glitchsat_crosscheck.json | MEASURED | partly: 40 pairs counted in the JSON; "0 disagreements" as stated, not recomputed |
| PDR proof, V2 spike, k<=2, any number of cycles; k=3 attack | report 6.2, summary, demo, slides 8,10 | formal/FORMAL.md section 4 | MEASURED | YES: re-ran k=2 from a copy: "Property proved", PASS in 0.83 s (the lead also re-ran it) |
| 10 clauses on 10 of 35 flops (k=2 invariant) | slide 8 notes | formal/FORMAL.md | MEASURED | no |
| 85 gates (40 AND, 25 OR, 20 NOT) on this machine | report 6.4, summary, slide 10 | formal/FORMAL.md, docs/FINAL_STATUS.md | MEASURED | YES: `scripts/synth.sh rtl/v2.v` here gave 40 AND, 25 OR, 20 NOT, 8 flops |
| 83 gates with 1 MUX in the formal worker's run | report 6.4, slide 10 | formal/FORMAL.md (37 AND, 25 OR, 20 NOT, 1 MUX) | MEASURED by another worker | no (sum checked: 83; netlist not re-created) |
| Spike netlist: 68 gates plus 8 flops, 16 MUX | report 6.4 | reference/spike_netlists/v2.json | MEASURED | YES (counted by script) |
| Two syntheses differ (apt 0.33 gives 85 gates, conda 0.38+92 gives 83). CORRECTED 2026-11-20: the build changes the netlist; the cause of 2 vs 3 flips is the encoding, not the Yosys version (`docs/report/WHY_TWO_FLIPS.md`) | report 6.4, slide 10 | docs/FINAL_STATUS.md; formal/FORMAL.md | MEASURED | YES (later re-run of both builds on a copy; see review/R2_accuracy.md rows R3, R4) |

## C. Independent validation
| Number / claim | Where used | Source file | Label | Re-checked |
|---|---|---|---|---|
| About 2.1M fault sets x 255 inputs; 0 disagreements; 13/13 witnesses; 5 boolector queries | report 5, summary, slide 7 | validation/VALIDATION.md | MEASURED | YES in the file text; not re-run (one `k1.py` run from `/tmp` worked) |
| 46,056 sets (T=4), 103,740 sets (T=6), no attack on V2 spike | report 5, summary, demo, slide 7 | validation/VALIDATION.md | MEASURED | YES in the file text; not re-run |

## D. Layout
| Number / claim | Where used | Source file | Label | Re-checked |
|---|---|---|---|---|
| 35 / 357.8 and 36 / 362.8 (cells / um^2) | report layout table | layout/v_designs/out_patched/RESULT.md | MEASURED | YES (table line read) |
| Placed components 76 (V1), 72 (V2) | report | same | MEASURED | YES |
| Slack +7.050 / +0.519 ns (V1), +7.035 / +0.476 ns (V2) | report | same | ESTIMATED (global-route parasitics, not signoff) | YES |
| Router DRC 0 | report, summary, demo, slide 11 | same | MEASURED | YES |
| LVS 422 vs 422, 430 vs 430, "match uniquely"; before 38 vs 39, 39 vs 40 | report, summary | same | MEASURED | YES |
| Antenna: 0 violations, 47 nets (V1), 48 nets (V2) | report 6.5, summary, slide 12 | layout/verify/VERIFY.md; layout/verify/ant/v1.log, v2.log | MEASURED | YES (log lines read) |
| 0 of 76 and 0 of 72 instances off the 5 nm grid; 0 off-grid GDS shapes (1870, 1937 top shapes) | report 6.5, slide 12 | layout/verify/ant/grid.txt | MEASURED | YES |
| Std-cell DRC errors are missing-tap rules (nwell.4, LU.2, LU.3); tested for dfxtp_1 only | report 6.5, slide 12 | layout/verify/VERIFY.md section 2 | MEASURED, one cell | no |
| a[26] short: filler over routed li1; 8 fillers removed; 514/514 devices; DRC li.3 x12, nwell.2a x3, hvi.5 x5, nwell.4 x1 | report 6.5, slide 12 | layout/verify/VERIFY.md section 3 | MEASURED | no |
| Rebuild: 6m36s, V1 reproduced (ODB byte-identical, GDS XOR 0) | report 6.5, slide 12 | layout/verify/VERIFY.md section 4 | MEASURED | no |
| ct_cmp as first built: LVS no match, 6 nets merged | report 7 | layout/triage/TRIAGE.md | MEASURED | no |

## E. Real designs and side audit
| Number / claim | Where used | Source file | Label | Re-checked |
|---|---|---|---|---|
| OTP FSM: k=1 SAT, T=4 and 6, flip of unlock flop | report 6.6, slide 13 | real_designs/REPORT.md | MEASURED | no |
| Door lock: 6 gates, combinational, k=1 SAT at T=4 and 6 | report 6.6, slide 13 | real_designs/second/REPORT.md; real_designs/second/door_results.json | MEASURED (worker's report) | YES: JSON has k=1 sat at T=4 and 6, k=2 minimises to 1 fault |
| Door lock layout: slack +7.739 / +2.027 ns; 28 devices, 20 nets; LVS "match uniquely with port errors" | report 6.6, slide 13 | real_designs/second/REPORT.md; layout/second/out/door_openroad.log, door_lvs.rpt | MEASURED (worker's report) | YES: slack lines and "Number of devices: 28 / nets: 20" found in the logs; the "port errors" wording is from the report |
| sqrt_q15 7.1509 LSB (slide says 7.15), input 31797, 25 inputs > 6 LSB, CBMC bound 8 | report 6.8, slide 13 | numerics_audit/AUDIT.md | MEASURED | YES (table line read) |
| CMSIS_5 #1386 / CMSIS-DSP #9 (not reproducible from the repo) | report 6.8 | numerics_audit/AUDIT.md; docs/FINAL_STATUS.md | UNVERIFIED in detail (summarising fetch tool) | no |

## F. Repo and framing
| Number / claim | Where used | Source file | Label | Re-checked |
|---|---|---|---|---|
| CI workflows exist, never ran on GitHub | report 6.7, slide 15 | ci/README.md | statement | YES: `.github/workflows/ci.yml` and `nightly.yml` exist |
| Clean-install test passed | report 6.7, slide 15 | ci/clean_install_log.txt | MEASURED | YES (log tail: every quickstart step exit 0) |
| No LICENSE file by design | report 6.7, slide 15 | LICENSE_CHOICE.md | statement | YES: only `LICENSE_CHOICE.md` matches `LICENSE*` in the project root |
| Validation scripts run from any directory | report 6.7, slide 15 | lead's note | statement | YES: ran `validation/k1.py` with absolute paths from `/tmp`, exit 0 |
| Self-score 3/10 now, ceiling about 6/10 | report 10 | docs/FINAL_STATUS.md | the project's own opinion, not a result | no |
| Prior-art statements (SYNFI, FIRMER, FIVER, CLEAVE, SCFI) | report 8, slide 14 | docs/PRIOR_ART.md; compare/COMPARISON.md | UNVERIFIED (abstract/README level) | no |
| SYNFI run result | report 8, slide 14 | compare/synfi_run/SYNFI_RESULT.md | agrees with our solver on V0, V1, V2 for a one-cycle transition from a hand-chosen start state (two-cycle chain crashed; re-synthesized V2 not run); V2 triples 182 of 35,990 effective | NO (reported by the SYNFI worker; not re-run by me) |
| "18 slides", "10 tests" at first writing (now 150) | deck | counted from the built deck / ENGINE_STATUS | n/a | YES (18 slides rendered) |

Re-checked count: more than 25 rows above were compared with files or re-run. Not verified by this refresh: the layout flow, the dashboard in a browser, fuzzing, the numerics audit, and all prior-art statements.


Later note (2026-11-19 about 19:30 UTC, F1): this check pre-dates critic CC (`research/c2/critics/cc/CC_FINDINGS.md`), the devil's-advocate review and the R10 and E1 reports. Several rows here ("self-score 3/10", "V2 resists 2 faults", "possibly new" search framing) are corrected in the documents named in `research/c2/f1/F1_FIX_LOG.md`.
