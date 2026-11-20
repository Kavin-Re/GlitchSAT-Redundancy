# T2 report: test integration + mutation-survivor tests
All numbers MEASURED on a copy (/tmp/work_t2/proj, venv /tmp/work_t2/venv with `pip install ./proj/product[test]`); nothing was run in the tree. Mutant batches ran serially.

## Files added (only these; nothing existing edited or deleted)
- tests/test_mt_oracle.py, product/tests/test_mt_oracle.py: MT oracle test, adapted (engine import fixed per location; env switches MT_ENGINE/MT_ROOT removed). 61 tests each (30 seeds x reduce{none,full} + flop-only test).
- tests/test_mt_targeted.py, product/tests/test_mt_targeted.py: 8 new tests each (same body, engine import differs): single-cycle combinational attack under reduce none/coi/full (3), reductions agree at N=2, sequential dist-1 site, honest_boots needs the legitimate key, gate driving an input-port bit is rejected, goal/attacker port direction checks.
- research/c3/t2/: mutate_t2.py (runs MT's mutant list on a copy; OLD = suite minus the two new files, NEW = the two new files only), score.py, kill_targeted.py, results_t2.jsonl, score_out.txt, kill_targeted.log, T2_REPORT.md.

## Counts and runtime (MEASURED, clean copy, `pytest -q tests` / `cd product; PYTHONPATH=src pytest -q tests`)
| suite | old tests | new tests | total | time old -> time with new |
|---|---|---|---|---|
| tests/ | 30 | 69 | 99 | 26.7 s -> 26.3 s |
| product/tests | 37 passed + 1 skipped | 69 | 106 passed + 1 skipped | 25.8 s -> 27.3 s |
Root total is 30 + 69 = 99 passed (pytest printed 99). New tests take about 1.4 s (root) / 2.6 s (product) when run alone; the +/-1 s differences above are load noise. Budget (<40 s) met; each test < 0.1 s.
(MT's report quoted 27 product tests; the product suite on today's tree is 37 + 1 skipped, so the old-test baseline is the one measured here.)

## Survivor kills (kill_targeted.log, MEASURED): each mutant applied alone, only the new file run
temporal_off2, coi_nolast, dist_goal_none, honest_nofix (root and product), inport_drv_off (root and product), plus two newly found gaps goal_widthchk and attin_dirchk: all KILLED by test_mt_targeted.py in both suites; the oracle file alone kills none of these. dist_goal_none is killed by the same single-cycle test as temporal_off2 (so not distinct in practice). Note coi_nolast mutates the reduce='coi' branch only, so it needs a reduce='coi' call; the full-reduce suites never exercised that branch.
Command: `python research/c3/t2/kill_targeted.py temporal_off2,coi_nolast,dist_goal_none,honest_nofix,inport_drv_off,goal_widthchk,attin_dirchk` (with /tmp/work_t2/lite built from the copy).

## Mutation score (score_out.txt; commands: `python research/c3/t2/mutate_t2.py --old research/c3/mt/results_partial.json --out res.jsonl`, then `score.py res.jsonl`)
Mutants: the 98 MT mutants = 69 runs on root + 89 on product = 158 runs. 148 completed (86 from MT's earlier partial results, 62 finished here); 10 product-only runs NOT RUN (cut by the 45-min cap, loaded machine): pc_cfgprob_exit, pc_override_k, pc_nohonest, pcfg_neg, pcfg_cycles, pcfg_bool, pcfg_kinds, pcfg_model, pcfg_defaulted, pcfg_unkkey. TIMEOUT = 120 s hang counted separately (loop_off, extract_inv: infinite/very long run under mutation).
| suite | runs | killed before | hang | killed after new tests | score before -> after (killed/run) |
|---|---|---|---|---|---|
| tests/ vs glitchsat.py | 69 (all) | 41 | 2 | 50 | 59.4 % -> 72.5 % (75.4 % counting hangs) |
| product/tests vs product src | 79 of 89 | 42 | 2 | 52 | 53.2 % -> 65.8 % (68.4 % counting hangs) |
Note: the earlier MT figure (67 %/65 %) was over the easy first 43 mutants; the full-list score is lower. Old results for the 86 MT runs were reused, not re-run.

## Remaining survivors after new tests (one-line reason; equivalence judged by reading, NOT proven)
- Equivalent / performance only: min_nopop_brk (break leaves extra solver scope, model unchanged), temporal_off1 (extra unreachable sites, same verdict), simp_off, simp_always (term simplification only), dist_noinc (less pruning only), clk_free (clk becomes a free BitVec that is never referenced).
- Needs more (real gaps): unk_is_true and timeout_off (need a deterministic z3 timeout case: not written, flaky by nature); extract_inv and loop_off (hang the suite with TIMEOUT instead of failing: detected only by the 120 s cap; loop_off needs a combinational-loop netlist test through the product path with a short timeout); expl_k1, expl_nin, kind_label, sup_flop, reach_lt (explain() text / reach counts not asserted); cli_exit_unk, cli_honest_flag (root CLI exit code on UNKNOWN / honest flag not asserted).
- Product-only gaps (need more): pf_filter_kind, pf_unsup_gate, pr_incl_any, pr_excl_off, pr_lv_width, pr_bv_width, pr_kindlabel, pr_minfaults, pr_reduce_none, pr_dir_in, pc_exit_unknown (runner include/exclude globs, value-width boundary checks, report fields and exit-code mapping untested).
- Not measured: the 10 product runs listed above.

## Limits
Hang mutants make a suite look killed only via the 120 s timeout; not counted in "killed". Equivalence claims are by reading. Load on the machine varied (load average 6-15), so timings have +/-2 s noise.
