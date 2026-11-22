# D3_REPORT: consistency and integration pass
Working title TBD. License: UNDECIDED. Modelled bit flips in toy netlists; nothing physical; nothing established as new.

## Files changed (backups in research/c4/d3/backup/, same relative paths)
README.md (rewritten, 51 lines), START.md, docs/FINAL_STATUS.md, docs/ENGINE_STATUS.md, docs/dossier/{PROJECT_DOSSIER (new s7.10-7.15, s9, s15), QA_SHEET (Q30-36, weakest ten), EVIDENCE_INDEX (rows 1-2 fixed, new section F rows 61-76), CRITIQUE (17 new rows), ONE_PAGE_KEY_POINTS, EVIDENCE_MAP, QA_ANSWER_CARDS, DISCLOSURE_DRAFT}.md, docs/report/{CLAIMS_CHECK,DEMO_5MIN,ONE_PAGE_SUMMARY,PROJECT_REPORT,REVIEW_NOTES}.md, docs/explainers/{W2,W3}_REPORT.md (text lines only). Scripts used: research/c4/d3/stale_fix.py, integrate.py (idempotent; run with a root path).

## What was done
- All RECON STALE lines in these files fixed: test counts now 98 passed (root) and 138 passed, 1 skipped (product), RECON 2026-11-19, with "quote your own count"; "not re-run" for DA_CYCLE1 replaced by "replicated by REP on 64 of 64 rows, one recipe list"; predictor stated as 150/163 (92%), 58% (18 of 31) on 2+ flip cells, within-1 95.7% fails the 98% bar, 1.4x slower, heuristic with sound lower bound, solver is the reference; 928/928 only with its near-duplicate caveat.
- Integrated: review panel W1, BP (recommendation and kill-list status, guidance only), SWEEP S1 implications, B3 (>3 for rail-wide events, 1 if selective; selectivity open; not brute-force validated for V2/V5), LAYOUT (r = 2.95 um, one supply net, no extraction; 4.6 um what-if hypothetical), L2 (research/c4/l2/ absent: marked in progress), R27 (patch exists, NOT applied; no T3 report found), V456 (V5 beats V2 only in apt full-word cell; V6 refuted; none beats V2 stored), PS4/PS5 shipped options (branch rule and per-cycle input not shipped), EDU kit, DASH Scope tab, QA weakest 10.
- M1b: only m1b_all_masks.csv existed at the end, no M1B_REPORT.md; M1-derived figures (88/96/44, width curve, 255/255, 68 mismatches) are marked 'recheck pending (M1b)' in README, START, FINAL_STATUS, dossier s7.15, ONE_PAGE, QA_SHEET, EVIDENCE_MAP, EVIDENCE_INDEX row 75. If M1B_REPORT.md lands later, apply its numbers to those places.

## check_numbers.py on the copy (/tmp/work_d3, tar-pipe copy with my edits; before: 38 STALE, 6 HISTORICAL)
```
check_numbers: 49 files scanned, 6 STALE, 6 HISTORICAL (rules: 15)
kind | row        | file                               | line  | found                              | should be                      | author
STAL | REP.rows   | dashboard/build.py                 | 144   | DA_CYCLE1.md, not re-run           | REPLICATED by REP on 64 of 64  | DASH step
STAL | REP.rows   | dashboard/index.html               | 181   | DA_CYCLE1.md, not re-run           | REPLICATED by REP on 64 of 64  | DASH step
STAL | VER.heldou | esearch/c4/review/QA_SIM_REPORT.md | 166   | 144/163                            | 150/163 (corrected; 144 is the | QA step
STAL | VER.heldou | esearch/c4/review/QA_SIM_REPORT.md | 235   | 144/163                            | 150/163 (corrected; 144 is the | QA step
STAL | T.root.pas | esearch/c4/review/QA_SIM_REPORT.md | 268   | 30 tests                           | 98 passed (root `pytest tests` | QA step
STAL | VER.heldou | esearch/c4/review/QA_SIM_REPORT.md | 270   | 144 of 163                         | 150/163 (corrected; 144 is the | QA step
HIST | T.root.pas | docs/ENGINE_STATUS.md              | 16    | 10 tests                           | 98 passed (10 only as history  | author (F2/docs)
HIST | T.root.pas | docs/dossier/PROJECT_DOSSIER.md    | 142   | 10 passed                          | 98 passed (10 only as history  | DOSSIER step (D2)
HIST | T.root.pas | docs/report/CLAIMS_CHECK.md        | 16    | 10 passed                          | 98 passed (10 only as history  | REPORT step (F2)
HIST | T.root.pas | docs/report/CLAIMS_CHECK.md        | 79    | 10 tests                           | 98 passed (10 only as history  | REPORT step (F2)
HIST | T.root.pas | docs/report/PROJECT_REPORT.md      | 53    | 10 passed                          | 98 passed (10 only as history  | REPORT step (F2)
HIST | T.root.pas | docs/report/REVIEW_NOTES.md        | 8     | 10 passed                          | 98 passed (10 only as history  | REPORT step (F2)
```
`--verify`: all 5 checks OK (144 raw / 150 corrected, E2 180/60/24, M1 88/96/44 and width curve, REP 26/6, 32/32, 64/64, 36 reproduce rows).

## Remaining mismatches and why
- 2 STALE `dashboard/build.py` l.144 and `dashboard/index.html` l.181 ("DA_CYCLE1.md, not re-run"): dashboard/ is outside my scope (a separate task); fix in build.py then rebuild.
- 4 STALE `research/c4/qa_sim/QA_SIM_REPORT.md` (l.166, 235, 268, 270: 144/163, "30 tests"): that report is QA's file, not in my edit list. Proposed edit: 144/163 -> 150/163 (144 is the raw column count), "30 tests" -> "98 passed today".
- 6 HISTORICAL "10 passed/10 tests" lines carry history markers (first writing / at review time); harmless.
- Not fixed, flagged: docs/report/review/* frozen snapshots (not scanned); red-team defects A1 and A6 not re-checked; heldout.csv itself still gives 144 (VER should add the corrected column).
- Limits: I ran no solver, synthesis or make; numbers come from the cited reports and NUMBERS.md. The kill-list status in dossier s7.10 is my reading of what was and was not done, not a measurement.
