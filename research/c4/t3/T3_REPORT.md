# T3 report: R27 sequential-counter at-most-k encoding applied

Labels: MEASURED = my command on the copy /tmp/work_t3/{base,work} (base = unmodified copy of the tree, work = patched). Machine: 4 cores, load from my own parallel jobs, so timings are noisy (factor ~2). Modelled bit flips, bounded verdicts. Nothing here is claimed as new.
Result: all 5 gates passed (gate 3 with the caveats below); patch APPLIED to the tree. Gate 6: flag `--amk {counter,legacy}`, default counter.

## What changed (tree files; diffs in glitchsat.diff, _engine.diff; originals in backup/)
- scripts/glitchsat.py and product/src/faultbound_wt/_engine.py: `seq_counter()` (Sinz, one-directional, aux vars named `__amk_i_j`), `solve(..., amk=None)`; `amk='counter'` (default): one counter sized for k, 'at most j' is an assumption literal, the minimisation loop reuses the solver with assumptions (no push/pop). `amk='legacy'`: the old PbLe + push/pop code, unchanged. `info['amk']` records the mode.
- Ported by hand to the H1/PS4/PS5 engines: all NetlistError checks, goal_mask/input_sites/init/count-rule/timeout handling, `minimize_incomplete` (product) untouched. Product timeout-while-minimizing still sets `minimize_incomplete`.
- Selection: glitchsat CLI `check ... --amk counter|legacy` (run_check(amk=)); product: `solve(amk=)` or env `FAULTBOUND_AMK=legacy` (product CLI/runner not edited: outside my scope).
- Two additions beyond R27's patch: (a) `atmost(j<0)` returns False (PbLe(-1) was unsat; without this solve(k=-1) was unbounded and mutation k_minus1/cli_k_neg hung); (b) a consistency check raises RuntimeError if the model has more than k faults (turns an inconsistent encoding into a loud error instead of an endless minimise loop).

## Gates (MEASURED)
1. 36 reproduce rows: `python3 ci/check_reproduce.py --rerun` -> 36/36 match, 0 problems. `scripts/reproduce.py` on base vs work, all summary fields except `faults`/`runtime_s` equal in all 36 rows (verdict, min_faults, cycles, honest_key_boots, k, design); witness size equal in all 36; witness set differs in 11/36 (non-unique, as H1 also saw). Sum of per-row runtime_s: 14.4 s -> 4.2 s (reproduce.py, serial, same machine).
2. `pytest tests`: 99 passed (14 s); `cd product; PYTHONPATH=src pytest tests`: 139 passed, 1 skipped (29 s); venv /tmp/work_t3/venv with `pip install ./product[test]`. Nothing built in the tree (product/build absent).
3. Mutation harness (research/c3/t2 harness, copy: mutate_t3.py, mt_override.py, score_merge.py, score_t3_out.txt, res_*.jsonl). Mutants k_plus1, k_minus1, drop_atmost, min_bound2 textually target the PbLe lines, so they were re-expressed on the counter code (same ids; mt_override.py). Rule: every (mutant,suite) that T2 counted as killed was re-run on the patched engines (T2 survivors were NOT re-run: they cannot lower a score; some were re-run anyway in the first batch). Result, killed/runs: tests/ vs glitchsat.py 50/69 = 72.5% (T2 72.5%, no change); product 50/74 = 67.6% vs T2 63.5% on the same 74 (T2 quoted 65.8% over 79 runs; 5 product mutants (init_all_zero, cycles_minus1, kind_label, pf_filter_none, pr_kind_inv) are NOT_APPLIED on today's product engine because PS4 changed their text, unrelated to T3, and are dropped from both sides). Gains: temporal_off1, simp_always, timeout_off (product) now count as killed; I did not investigate why (could be timing, hangs counted separately are not included). Caveat: rows run before my last two edits ((a) j<0 branch and (b) the consistency raise) were not repeated except drop_atmost/k_minus1/k_plus1/min_bound2/cli_k_neg; the edits only affect branches not reached in normal use, and reproduce, both suites and 40+150 xcheck netlists were re-run after them.
4. RT brute-force cross-check (research/c4/t3/xcheck_t3.py = RT's xcheck with paths on the copy): seeds 1,2,3 = 40+150+150 = 340 netlists x 2 engines x 3 reduce modes, counter mode: 0 disagreements (xcheck_t3.log). After the final two edits seeds 1 (40) and 2 (150) were re-run: 0 disagreements.
5. R27 speed cases (gate5.py speed; speed_cases.jsonl; scripts/glitchsat.py solve(), reduce full, 150 s timeout, same netlists /tmp/work_r27/nl):

| case | counter solve_s (wall) | legacy | verdict |
|---|---|---|---|
| dmr k=1 T=4 | 1.6 (3.5) | timeout at 150 s | UNSAT (NO_ATTACK) / UNKNOWN_TIMEOUT |
| dmr k=1 T=8 | 34.7 (39) | timeout at 150 s | NO_ATTACK / UNKNOWN_TIMEOUT |
| s2 k=2 T=12 | 0.35 (0.7) | 56.6 | NO_ATTACK both |
| s2 k=2 T=20 | 0.64 (1.4) | timeout at 150 s | NO_ATTACK / UNKNOWN_TIMEOUT |
| s2 (V2 spike) k=3 T=6 | 0.05 (0.2) | 4.7 (5.7) | ATTACK_FOUND, 3 faults both |
Wall-clock speedups are lower bounds where legacy timed out (dmr T=4 >= 43x, dmr T=8 >= 3.9x, s2 T=20 >= 107x; s2 T=12 80x; s2 k=3 28x). Verdicts agree wherever both finished; counter finishes the cells that timed out. M1 mask samples (gate5.py m1, m1_samples.jsonl, product engine goal_mask, v2 spike netlist, T=6, masks 1,4,5,3,2 plus 14,15,22,23,30 (min=2)): 10/10 give min flips equal to m1_all_masks.csv source rows (m_v2_spike.jsonl) in both modes. V2 spike k=3 also covered by the reproduce rows (gate 1) and by the CLI check above (`--amk counter` and `legacy`: both ATTACK_FOUND, minimum 2 faults, different witnesses).
6. `--amk` flag verified on the CLI: `python3 scripts/glitchsat.py check rtl/v2.v --top v2 --k 3 --cycles 6 --amk counter|legacy`.

## Not done / limits
- Mutation survivors of T2 were not systematically re-run; the "gained" mutants are unexplained. 10 product mutants never run in T2 were not run either.
- Timings single runs under load; no repeats. Legacy timeouts (150 s) mean the true legacy times are unknown.
- Product CLI/runner have no --amk option (only env `FAULTBOUND_AMK` and `solve(amk=)`); docs/README/Makefile/tests not edited (outside scope); no new tests added for the flag.
- Not re-run in the tree: make targets (rule). `make reproduce` outputs in results/ are from before the patch.
- Counter encoding is a bit slower on some SAT cells (R27: uart k=3 T=60, 4.5 s -> 33 s); not re-measured here.
