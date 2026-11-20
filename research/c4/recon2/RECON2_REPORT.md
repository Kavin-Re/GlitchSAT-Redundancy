# RECON2_REPORT: numbers reconciliation, second pass
Working title TBD; licence UNDECIDED. Modelled bit flips on toy netlists; nothing physical; nothing established as new. Work copy /tmp/work_recon2 (tar-pipe, exclusions as instructed), edits applied to the tree afterwards (tree files were byte-identical to the copy originals at that moment). Backups of every changed file: `research/c4/recon2/backup/` (same relative paths). No code, results/, rtl/, reference/, dashboard/ touched; no make run; no `product/build` or egg-info in the tree.

## 1. Test counts re-measured today (MEASURED, venv with `pip install -r ci/requirements-ci.txt "./product[test]"` on the copy)
| command | result |
|---|---|
| `pytest tests -q` | **99 passed** in 15.5 s (lead also 99; T3 99) |
| `pytest product/tests -q` | **139 passed, 1 skipped** in 33.2 s (T3: same; 140 collected) |
`check_numbers.py --pytest`: root 99 collected, product 140 collected, both equal NUMBERS.md. The RECON figures 98 and 138+1 are history (T2's `test_mt_targeted.py`, PS5 and T3 landed since). Files: `pytest_root.txt`, `pytest_product.txt`.

## 2. Mutation scores: which is which
- **Root `tests/`: 72.5% = 50/69 runs.** T2 after adding `test_mt_oracle.py` + `test_mt_targeted.py` (T2 before: 59.4%, 41/69); T3 re-ran it on the counter-encoding engine: 50/69, unchanged. Current.
- **Product: 67.6% = 50/74 runs.** T3, patched product engine. 74 = T2's 79 minus 5 mutants (init_all_zero, cycles_minus1, kind_label, pf_filter_none, pr_kind_inv) that PS4 made not applicable; T2's own score on those 74 was 63.5%. Current.
- **Product 65.8% = 52/79 runs**: T2's figure, pre-T3 engine, different denominator (10 more product runs of 89 never run). Quote only as T2's.
- **67% (29/43) root / 65% (28/43) product**: MT's figure over the easy first 43 mutants. History only; T2 says so itself.
All REPORTED (T2, T3), not re-run by RECON2 (harness needs ~45 min). Caveats in NUMBERS.md: killed/run, hang mutants separate (75.4% / 68.4% if counted), equivalence by reading, 3 unexplained product "gains", T2 survivors not re-run by T3.
Replaced as current in: NUMBERS.md (`T.mut.root`, `T.mut.prod`, new `T.mut.hist`), PROJECT_REPORT, ONE_PAGE_SUMMARY, PROJECT_DOSSIER s7.x (first-43 kept as history), EVIDENCE_INDEX row 7, EVIDENCE_MAP, QA_ANSWER_CARDS, CRITIQUE MT-1, SLIDES_OUTLINE slide 9, and SLIDES.pptx slide 9 (tiles 99 / 139 / 72.5% / "mutation score, root 50 of 69", notes; backup `backup/docs/report/SLIDES.pptx`; only text runs changed, deck not re-rendered: check that "72.5%" fits its tile).

## 3. NUMBERS.md additions (now 27 rules; section 9 plus new rows in section 1)
New rows with source and label: T.t3.gates, T.t3.speed (>=43x dmr k=1 T=4, 80x V2 k=2 T=12, >=107x T=20, summed reproduce rows 14.4 -> 4.2 s), T.t3.xcheck, R27.speed, LEAD.verified, LAY.radius (2.95 um), LAY.minsets (4 sets), LAY.supply (one supply net, INFERRED), LAY.whatif (HYPOTHETICAL 4.58/6.13), L2.spacing (1.84, 9.2, 16.3, 17.9, 23.5 um), L2.radius, L2.selectivity, L2.rail_all (still 1 in all five), L2.rail.perrail (1 -> 2/3), L2.cost (area x1.26-2.5, wire +29 to +50%, slack <= 0.02 ns), L2.drc (router DRC 0, antenna 0, LVS FAILS 4 of 4 spread variants), L2.sim, EL1.simul (EL1.dip/runt/setup already existed), B3.matrix, B3.valid, PS4.opts/sweep/masks/tests, PS5.width/scope/opts, EDU2.rerun, DASH.values (115/115), QA.falsify (19 claims, 11 re-run by QA), M1b.cells (0 of 1785), E2.unique, REP.pct, PRE.train.
Labels: MEASURED only for (a) my pytest runs and CSV `cmp`, (b) what the lead re-ran (check_reproduce --rerun 36/36 in 12.9 s, pytest tests 99, product CLI V2 k=2 none / k=3 min 3 / boot_ok 1, m1b CSV byte-identical, predictor hashes; row `LEAD.verified`). Everything else is REPORTED; where I could recompute from the agent's stored data (no solver) the row says RECOUNTED.

## 4. Checker (`scripts/check_numbers.py`, backup in `backup/scripts/`)
- 12 new rules: T.mut.pct, T.root.99, T.prod.139, L2.status, R27.applied, M1b.pending, L2.lvs, L2.hardening, L2.wire, L2.area, LAY.radius, B3.overclaim; T.mut.root rule rewritten (29/43, 28/43 as current); hist_re extended (first 43, history, before T2/T3, ...). Counts in `current` updated to 99 / 140.
- 5 new `--verify` recounts from stored data: M1b CSV identical to M1 CSV; B3 matrix_T6.jsonl (rail_all/half/unions `>3`, rail_cone V0 1, dip_subset 1, 0 unknown; 182 rows); layout minimal sets (4; 2.95/3.06/3.29/4.58); L2 summary_flow + metrics + minsets + fam (wire +29/31/49/36%, LVS match only base, router DRC 0, antenna 0, copy distances, radii, rail_all 1); PS4 scope sweep rows. All 10 verify checks OK. Note v15 wire is +49.5%, the L2 report rounds to +50% (accepted 49 or 50).

## 5. Stale lines found and fixed
Before my edits (on today's tree) the checker found 4 STALE (all QA report) plus the mutation and status items below, which had no rule. Fixed in README, START, docs/**: test counts 98 -> 99 and 138 -> 139 (+1 skipped; 98.9 s -> 33.2 s; 139 collected -> 140) in 16 files; mutation figures (above); "R27 patch NOT applied / no T3 report" (README, ENGINE_STATUS, FINAL_STATUS, PROJECT_DOSSIER 7.14 and next-steps, QA_SHEET Q35, EVIDENCE_INDEX 69, CRITIQUE R27-1) now "applied by T3"; "L2 in progress / absent" (README, FINAL_STATUS, PROJECT_DOSSIER, QA_SHEET Q32, EVIDENCE_INDEX 68, CRITIQUE LAY-1) now the L2 result; CRITIQUE VER-3 "M1b recheck pending" now done; PROJECT_DOSSIER line about M1b "is rechecking" fixed.

## 6. README / START claims against NUMBERS.md
| claim | verdict |
|---|---|
| README one-glance: V2 3 (stored) / 2 (apt 0.33) | OK (B2.v2.spike.word, B2.v2.apt) |
| 4-bit consumer 28/36/4 of 68; M1b 0 of 1785 | OK (M1.four, M1b.cells) |
| boot_ok / input nets / arbitrary non-accepting power-up: 1; 360 cells | OK (B2.*) |
| V1 and V0 "every scope cell tried: 1" | FIX applied: only known-power-up cells; arbitrary power-up gives 0 (B2.free) |
| V1 needs 2 in 31 of 264 | OK (E2.v1.min 233/31/0) |
| V2 over 264 configs 180/60/24 | OK (E2.v2.min, recomputed) |
| rail dips: none up to 3 events, 1 if selective (3 gates) | OK (B3.matrix, B3.subset) |
| counting rule 6/32 vs 32/32, REP 64/64, one recipe list | OK (REP.*, recomputed) |
| predictor 150/163 (92%), 58%, 1.4x slower, 928/928 near-duplicate | OK (VER.*, TEST.*) |
| L2 done: 11 to 18 um, selective dip still 1, LVS fails 4 of 4 | OK (L2.radius, L2.rail_all, L2.drc; corrected from "in progress") |
| faster encoding applied by T3 (`--amk counter`) | OK (T.t3.*; corrected from "not applied") |
| `make test` 99 passed; product 139 passed, 1 skipped; 36/36; ~25 s; 85 vs 83 gates | OK after update (T.root.passed, T.prod.passed, T.repro.*, G.v2.*); "~25 s" is machine dependent (lead's --rerun 12.9 s) |
| unbounded PDR V2 spike k <= 2, one netlist | OK (F.pdr, MEASURED by lead, not re-run) |
| START: three commands' outcomes; 864 configs; 150/163; r = 2.95 um, one supply net; 0 of 1785; 99 passed | OK |
| START/README product options shipped; branch rule and per-cycle input not shipped | OK (PS4.opts); `--init free_nongoal` and `--timeout-s` also shipped (PS5), not listed in START (not an error) |

## 7. What remains and why
- `research/c4/qa_sim/QA_SIM_REPORT.md` (outside my edit list): 6 STALE: l.166, 235, 270 (144/163 vs 150/163, "not reconciled"), l.209-210 and 268 (98 and 30 tests; l.268 is the quoted falsified claim), l.239 ("V2 survives rail dip" in a question stem; fine if marked as the reviewer's claim). Proposed edits: 144 -> 150/163 (raw column count is 144), 98 -> 99. Same file's falsifier table row 11 still says "not reconciled".
- 10 HISTORICAL lines (10 tests / 29/43 with history markers): harmless.
- `dashboard/` (not editable): previously flagged "DA_CYCLE1.md, not re-run" lines no longer match (already fixed upstream); the dashboard's embedded numbers were not re-scanned beyond the checker's rules. The DASH 115/115 check is the agent's.
- Not scanned: docs/report/review/* (frozen snapshots), FIX_LOG, WORDING_FLAGS, CRITIQUE and EVIDENCE_INDEX (skip list), though I updated their current-state rows by hand.
- Mutation scores, L2/layout/SPICE/B3 solver runs, EDU2, DASH, PS4/PS5 CLI timings, QA claims: REPORTED (labelled); recounted from stored data only where listed in section 4. `SLIDES.pptx` not re-rendered. `heldout.csv` still gives 144 on a raw recount (VER should add the corrected column).
- The checker finds only values in its rules; regexes are line based.

## 8. Final run on the copy
`python3 scripts/check_numbers.py`: 49 files, 6 STALE (all QA_SIM_REPORT), 10 HISTORICAL. `--verify`: 10/10 OK. `--pytest`: 99 and 140 collected, OK. Output: `check_numbers_final.txt`, `mismatches.md`. Scripts used: `fix_counts.py`, `patch_numbers.py` (idempotence not guaranteed; they were run once).
