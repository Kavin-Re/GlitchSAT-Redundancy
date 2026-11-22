# RECON_REPORT: numbers reconciliation across README, START, FINAL_STATUS, report, dossier, wow, edu, product, dashboard
Working title TBD. License: UNDECIDED. Faults are modelled bit flips in toy netlists; nothing physical. RECON edited only `docs/NUMBERS.md`, `scripts/check_numbers.py` and this folder; every mismatch below is a proposed edit for the author of the file, none was applied.

## 1. What was delivered
- `docs/NUMBERS.md`: 83 rows (id, value, meaning, source file and key/line, how measured, status, date) plus a machine-readable JSON block (scan globs, 15 stale-value rules with "should be" text, author map).
- `scripts/check_numbers.py`: reads that block, scans 49 files line by line, prints a mismatch table (kind STALE or HISTORICAL, row id, file, line, found, should be, author). `--verify` recomputes from stored data: E2 180/60/24 (and V1 233/31/0, V0 264/0/0), M1 88/96/44 and the width curve 0,1,1,2,2,3,3,3, REP 26/6 and 32/32 and 64/64, reproduce rows 36, held-out 144 raw / 150 corrected. `--pytest` compares collected counts. `--md OUT` writes the table. Exit 0 clean, 1 stale found, 2 unreadable. Read-only.
- Tested on the tree copy `/tmp/work_recon/copy` (tar-pipe copy, exclusions as instructed) and read-only on the tree: all 5 `--verify` checks OK; `--pytest` OK in the venv (98 and 139 collected); missing file gives exit 2. Work files: `gen_numbers.py` (regenerates NUMBERS.md from its row list; edit rows there or edit NUMBERS.md by hand), `mismatches.md` (raw table).

## 2. Today's real test counts (MEASURED on the copy, venv with `pip install -r ci/requirements-ci.txt "./product[test]"`)
| command | result |
|---|---|
| `pytest tests --co -q` | 98 tests collected |
| `pytest tests -q` | **98 passed** in 26.7 s |
| `pytest product/tests --co -q` | 139 tests collected |
| `pytest product/tests -q` | **138 passed, 1 skipped** in 98.9 s |
Docs say 10, 30 (root) and 21, 27, 38 (product). Only 98 and 138+1 skipped are current. 38 was a integration step count that no step measured. The history is 10 (first writing) to 30 (RA, after H1 added 20) to 98 (MT and T2 added test_mt_oracle, test_mt_targeted) for the root; 21 (RA) to 27 (PS2) to 139 (PS3, PS4, PS5 and MT added files) for product. These counts will move again whenever a step adds a test, so pages should say "run `make test` and quote your own count" in addition to a dated number.

## 3. 144/163 versus 150/163: which is corrected, and why (MEASURED, recomputed by RECON)
**150/163 (92.0%) is the corrected audit figure** (VER_REPORT s3.1). 144/163 is a raw string comparison of the `pred` and `solver` columns of `research/c4/ver/heldout.csv` and is not a headline number. The gap is 6 cells:
1. 4 cells where the solver column is `>3` and the predictor column is `100` (structural lower bound 99, plus 1). The PREREG rule compares `>3` as 4 and caps the prediction at 4, so they match: 144 + 4 = 148.
2. 2 cells (`rc103_opt` mask 0x18, `rc117_opt` mask 0xf) where `heldout.csv` still holds the pre-correction solver value. With the opt flow yosys writes init `xx1001`; `gs_mask.py` mapped `x` to 0 and the aliased flop clobbered the real init. `rerun_x.json` (47 x-init cells rerun with `gs_mask2.py`) holds the corrected solver values 0 and 2, which equal the predictor: 148 + 2 = 150.
`check_numbers.py --verify` reproduces 144, and 150 after both steps. Caveat for the integration step: `heldout.csv` itself was not updated, so anyone recounting the raw column gets 144 again; VER should append the corrected column or a README line. Wording to quote: "150 of 163 (92.0%) after x-init corrections; 58% (18 of 31) on cells needing 2 or more flips; within-1 95.7% fails the 98% bar; the 928/928 pooled figure is near-duplicate cells". QA_SIM_REPORT lines 166, 235 and 270 carry 144 and say "not reconciled": update them (author QA).

## 4. Other reconciliations (all consistent unless noted)
- E2: 180/60/24 of 264 solved V2 configs recomputed from `raw/matrix.csv`; 792 solved + 72 ENGINE_UNSUPPORTED = 864. TEST's "20 cells at min 3" are 20 UNIQUE netlists behind the 24 min-3 configs: not a contradiction, but pages should say which one they mean (configs 24, unique netlists 20).
- M1: 255 masks, 27 colliding, 228 left; 88/96/44; width curve 0,1,1,2,2,3,3,3; four-bit masks 28/36/4 of 68: all recomputed OK. README "28 of 68 four-bit masks" is correct.
- REP: V2 26x2 and 6x3 (unit), 3 on 32/32 (fanout pins); V1 2 on 32/32; 64/64 agree: recomputed OK. 6/32 = 18.75% is quoted as 19 percent (rounded, fine).
- Gate counts: 85 (apt V2), 83 (conda V2), 81 (apt opt), 63 (apt plus opt_merge, edu), and 68/58/18 for the stored spike V2/V1/V0 are different netlists, all consistent with their sources. The "85 gates" convention counts combinational gates only (93 cells with 8 DFF); pages should say "85 combinational gates". README says "85 vs 83 gates" without that note (author author; low priority).
- reproduce: 36 rows confirmed in `results/reproduce_summary.json`; "11 of 36 witnesses differ" is RA's measurement, not re-run.
- Predictor speed: TEST said 3x to 7x faster; VER measured 1.4x slower on 163 held-out cells; no page in the scan carries a bare "faster" claim now (rule kept in the checker).
- Not re-runnable here (status stays REPORTED or MEASURED-by-others in NUMBERS.md): PDR 0.83 s, sby 40 pairs, layout numbers, SPICE (EL1), B3 matrix, R20 runs, MT mutation scores, numerics spike, fuzzing "6,700 programs" (UNVERIFIED, not in the repo).

## 5. Mismatch table (output of `python3 scripts/check_numbers.py`, 38 STALE, 6 HISTORICAL)
STALE = a wrong value presented as current. HISTORICAL = an old value on a line that marks it as history; harmless but tidy when touched. A single line can appear twice (once for the current wrong value, once for the old one).

| kind | row | file | line | found | should be | author |
|---|---|---|---|---|---|---|
| STALE | T.root.passed | `README.md` | 44 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | author |
| STALE | T.prod.passed | `README.md` | 50 | `Product tests (`product/tests`, 38` | 138 passed, 1 skipped (98.9 s) (product/tests after pip install ./product[test]; 139 collected) | author |
| STALE | REP.rows | `dashboard/build.py` | 144 | `DA_CYCLE1.md, not re-run` | REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted | DASH step |
| STALE | REP.rows | `dashboard/index.html` | 181 | `DA_CYCLE1.md, not re-run` | REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted | DASH step |
| STALE | T.root.passed | `docs/ENGINE_STATUS.md` | 16 | `30 tests` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | author (F2/docs) |
| STALE | REP.rows | `docs/ENGINE_STATUS.md` | 38 | `DA_CYCLE1.md`, MEASURED by that step, not re-run` | REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted | author (F2/docs) |
| STALE | T.root.passed | `docs/FINAL_STATUS.md` | 27 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | author |
| STALE | T.prod.passed | `docs/FINAL_STATUS.md` | 27 | `product tests: 38` | 138 passed, 1 skipped (98.9 s) (product/tests after pip install ./product[test]; 139 collected) | author |
| STALE | T.root.passed | `docs/dossier/DISCLOSURE_DRAFT.md` | 21 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/dossier/ONE_PAGE_KEY_POINTS.md` | 33 | `30 tests` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/dossier/PROJECT_DOSSIER.md` | 116 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/dossier/PROJECT_DOSSIER.md` | 117 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/dossier/PROJECT_DOSSIER.md` | 117 | `10 passed` | 98 passed (10 only as history with a marker such as 'first writing') | DOSSIER step (D2) |
| STALE | T.prod.passed | `docs/dossier/PROJECT_DOSSIER.md` | 122 | `Product tests: 38` | 138 passed, 1 skipped (98.9 s) (product/tests after pip install ./product[test]; 139 collected) | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/dossier/EVIDENCE_MAP.md` | 10 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | DOSSIER step (D2) |
| STALE | T.prod.passed | `docs/dossier/EVIDENCE_MAP.md` | 10 | `38 passed` | 138 passed, 1 skipped (98.9 s) (product/tests after pip install ./product[test]; 139 collected) | DOSSIER step (D2) |
| STALE | T.prod.passed | `docs/dossier/EVIDENCE_MAP.md` | 20 | `38 passed` | 138 passed, 1 skipped (98.9 s) (product/tests after pip install ./product[test]; 139 collected) | DOSSIER step (D2) |
| STALE | TEST.pooled | `docs/dossier/QA_ANSWER_CARDS.md` | 181 | `928/928` | 928/928 only with its caveat (near-duplicate cells, effective sample 3-5 designs; VER 150/163 on fresh cells) | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/dossier/QA_ANSWER_CARDS.md` | 234 | `30 tests` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/dossier/QA_SHEET.md` | 56 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | DOSSIER step (D2) |
| STALE | T.root.passed | `docs/report/CLAIMS_CHECK.md` | 16 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | REPORT step (F2) |
| STALE | T.root.passed | `docs/report/CLAIMS_CHECK.md` | 16 | `10 passed` | 98 passed (10 only as history with a marker such as 'first writing') | REPORT step (F2) |
| STALE | T.prod.passed | `docs/report/CLAIMS_CHECK.md` | 16 | `product tests 27` | 138 passed, 1 skipped (98.9 s) (27 and 21 only as history with a marker) | REPORT step (F2) |
| STALE | T.root.passed | `docs/report/CLAIMS_CHECK.md` | 79 | `10 tests` | 98 passed (10 only as history with a marker such as 'first writing') | REPORT step (F2) |
| STALE | T.root.passed | `docs/report/DEMO_5MIN.md` | 11 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | REPORT step (F2) |
| STALE | T.prod.passed | `docs/report/DEMO_5MIN.md` | 11 | `product tests: 27` | 138 passed, 1 skipped (98.9 s) (27 and 21 only as history with a marker) | REPORT step (F2) |
| STALE | T.root.passed | `docs/report/ONE_PAGE_SUMMARY.md` | 27 | `30 tests` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | REPORT step (F2) |
| STALE | T.prod.passed | `docs/report/ONE_PAGE_SUMMARY.md` | 27 | `product tests 27` | 138 passed, 1 skipped (98.9 s) (27 and 21 only as history with a marker) | REPORT step (F2) |
| STALE | T.root.passed | `docs/report/PROJECT_REPORT.md` | 45 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | REPORT step (F2) |
| STALE | REP.rows | `docs/report/PROJECT_REPORT.md` | 103 | `DA_CYCLE1.md`; MEASURED by that step, not re-run` | REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted | REPORT step (F2) |
| STALE | T.root.passed | `docs/report/PROJECT_REPORT.md` | 181 | `30 tests` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | REPORT step (F2) |
| STALE | T.root.passed | `docs/report/REVIEW_NOTES.md` | 8 | `30 passed` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | REPORT step (F2) |
| STALE | REP.rows | `docs/explainers/dev/W2_REPORT.md` | 16 | `DA_CYCLE1.md, MEASURED by that step, not re-run` | REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted | WOW steps (W1-W6) |
| STALE | REP.rows | `docs/explainers/dev/W3_REPORT.md` | 22 | `DA_CYCLE1.md (MEASURED by that step, not re-run` | REPLICATED by REP on 64 of 64 rows (research/c3/rep/REP_REPORT.md); DA numbers re-measured, not only quoted | WOW steps (W1-W6) |
| STALE | VER.heldout.exact | `research/c4/qa_sim/QA_SIM_REPORT.md` | 166 | `144/163` | 150/163 (corrected; 144 is the raw column count, see NUMBERS.md VER.heldout.raw) | QA step |
| STALE | VER.heldout.exact | `research/c4/qa_sim/QA_SIM_REPORT.md` | 235 | `144/163` | 150/163 (corrected; 144 is the raw column count, see NUMBERS.md VER.heldout.raw) | QA step |
| STALE | T.root.passed | `research/c4/qa_sim/QA_SIM_REPORT.md` | 268 | `30 tests` | 98 passed (root `pytest tests`, 2026-11-19, RECON); or 'run `make test` and quote your own count' | QA step |
| STALE | VER.heldout.exact | `research/c4/qa_sim/QA_SIM_REPORT.md` | 270 | `144 of 163` | 150/163 (corrected; 144 is the raw column count, see NUMBERS.md VER.heldout.raw) | QA step |
| HISTORICAL | T.root.passed | `docs/ENGINE_STATUS.md` | 16 | `10 tests` | 98 passed (10 only as history with a marker such as 'first writing') | author (F2/docs) |
| HISTORICAL | T.prod.passed | `docs/ENGINE_STATUS.md` | 16 | `product tests: 27` | 138 passed, 1 skipped (98.9 s) (27 and 21 only as history with a marker) | author (F2/docs) |
| HISTORICAL | T.prod.passed | `docs/FINAL_STATUS.md` | 27 | `product tests: 38 (count given at integration; 27` | 138 passed, 1 skipped (98.9 s) (27 and 21 only as history with a marker) | author |
| HISTORICAL | T.prod.passed | `docs/report/PROJECT_REPORT.md` | 45 | `product tests 27` | 138 passed, 1 skipped (98.9 s) (27 and 21 only as history with a marker) | REPORT step (F2) |
| HISTORICAL | T.root.passed | `docs/report/PROJECT_REPORT.md` | 53 | `10 passed` | 98 passed (10 only as history with a marker such as 'first writing') | REPORT step (F2) |
| HISTORICAL | T.root.passed | `docs/report/REVIEW_NOTES.md` | 8 | `10 passed` | 98 passed (10 only as history with a marker such as 'first writing') | REPORT step (F2) |

Rows I read by eye that the regexes do not catch (also stale, same fix): `README.md` line 44 "30 passed ... more may have been added since" (should say 98 passed on 2026-11-19, and give the command); `README.md` line 50 "38 tests, count from the integration step; PS2 measured 27" (should be 138 passed, 1 skipped); `docs/FINAL_STATUS.md` line 27 also says "tests/ may have gained tests from step T2 since, not re-counted here" (now counted: 98).

## 6. Proposed edits by author (not applied)
- **author** (`README.md` l.44, l.50; `docs/FINAL_STATUS.md` l.27; `docs/ENGINE_STATUS.md` l.16 and l.38): root tests 98 passed; product 138 passed, 1 skipped (139 collected); ENGINE_STATUS l.38 "not re-run here" for the 32-netlist counting-rule result should read "replicated by REP on 64 of 64 rows". Add one line "Counts as of 2026-11-19; see docs/NUMBERS.md" and run `python3 scripts/check_numbers.py` before each hand-off. Also decide whether NUMBERS.md and check_numbers.py go into `make help`/CI (a `check-numbers` target would be the integration step's edit).
- **DOSSIER (D2)** (`DISCLOSURE_DRAFT.md` l.21; `ONE_PAGE_KEY_POINTS.md` l.33 "30 tests"; `PROJECT_DOSSIER.md` l.116, 117, 122; `EVIDENCE_MAP.md` l.10, 20 "30 passed", "38 passed"; `QA_SHEET.md` l.56; `QA_ANSWER_CARDS.md` l.181 bare 928/928 in the heading (the body already carries the caveat) and l.234 "30 tests" (the same line says 98 passed: it is the quoted trap; fine to keep if marked as the trap, the checker will keep flagging it). `EVIDENCE_INDEX.md` rows 1 and 2 and `CRITIQUE.md` are skipped by the checker as logs; EVIDENCE_INDEX row 1 "30 passed" and row 2 "38 passed" are still stale as current figures and should be updated.
- **REPORT (F2)** (`CLAIMS_CHECK.md` l.16, l.79; `DEMO_5MIN.md` l.11 "30 passed (product tests: 27 ...)"; `ONE_PAGE_SUMMARY.md` l.27; `PROJECT_REPORT.md` l.45, 53, 103, 181; `REVIEW_NOTES.md` l.8): same count updates; PROJECT_REPORT l.103 should drop "not re-run" for DA (REP replicated 64/64). `docs/report/review/*` was not scanned (frozen review snapshots that say 10 tests).
- **DASH** (`dashboard/build.py` l.144 and generated `dashboard/index.html` l.181): "DA_CYCLE1.md, not re-run" should add "replicated by REP, 64 of 64". Note that this is shown on the page itself, so the fix is in `build.py` and then a rebuild by the author of that step.
- **WOW** (`docs/explainers/dev/W2_REPORT.md` l.16, `W3_REPORT.md` l.22): same "not re-run" wording about DA_CYCLE1.
- **QA** (`research/c4/qa_sim/QA_SIM_REPORT.md` l.166, 235, 270, 268): replace "144/163 ... not reconciled" with the section 3 explanation; replace "docs say 30" with "docs said 30; 98 passed today".
- **VER**: add the corrected solver column (or a README line) next to `heldout.csv` so a raw recount stops giving 144.
- **EDU, product/QUICKSTART.md, START.md**: no stale values found by the rules. docs/edu gate counts (68/85/63; hashes f954078f, d776226e) match the E2 and edu sources and were not re-run by RECON (edu answers depend on apt Yosys 0.33).

## 7. Limits
- The checker finds only values listed in its rules: it cannot discover a new wrong number. Add a rule when a row in NUMBERS.md changes. Regexes are line based: a number split over two lines is missed.
- HISTORICAL detection is a word list (stale, superseded, first writing, ...); a line that quotes 30 as current always counts as STALE.
- `docs/report/review/`, `docs/report/FIX_LOG.md`, `WORDING_FLAGS.md`, `docs/dossier/CRITIQUE.md` and `EVIDENCE_INDEX.md` are in the skip list on purpose (they are logs that quote old values). Removing EVIDENCE_INDEX from the skip list would add its two stale test rows.
- Layout, PDR, sby, SPICE, B3, R20, mutation numbers were not re-run (conda envs and time); they are labelled in NUMBERS.md as REPORTED or MEASURED-by-others. The 98.9 s product run includes tests added by PS4 and PS5; one test is skipped (not identified by RECON).
- Pages edited by other steps after 2026-11-19 22:00 UTC will change the hit list; rerun the script.
