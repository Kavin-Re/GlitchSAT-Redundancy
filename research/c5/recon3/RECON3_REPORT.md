# RECON3_REPORT: numbers re-measure, third pass
Working title TBD; licence UNDECIDED. Modelled bit flips on toy netlists; nothing physical; nothing established as new. Work copy /tmp/work_recon3/p (tar-pipe, instructed exclusions), venv /tmp/work_recon3/venv (`pip install ./p/product[test] pytest z3-solver pyyaml`). No make run, no code/results/dashboard edit, no `product/build` or egg-info in the tree. Backups of every changed file: `research/c5/recon3/backup/` (same relative paths).

## 1. Measured today (MEASURED by RECON3 on the fresh copy)
| command | result |
|---|---|
| `pytest tests -q` | **133 passed** in 18.32 s (99 + 34 in tests/test_h3.py) |
| `pytest product/tests -q` | **310 passed** in 80.88 s (175 + 135 in test_h2.py; 0 skipped because pyyaml is installed; without it expect 309 + 1 skipped, not run) |
| `python3 ci/check_reproduce.py` | 36/36 rows match (engine NOT re-run), 0 FAILED, exit 0 |
| `python3 ci/check_reproduce.py --rerun` | 36/36 rows match (engine re-run), 0 FAILED, 0 problems, exit 0, no ENGINE_MANIFEST warning (output: `check_reproduce_rerun.txt`) |
| `check_numbers.py --verify --pytest` | 10/10 verify OK; collected 133 and 310, equal to NUMBERS.md after the edits (`check_numbers_final.txt`) |

## 2. Stale counts replaced (current-context only; history kept and marked)
99 -> 133 (root) and 139+1 skipped / 140 collected -> 310 (product) in: README, START, docs/FINAL_STATUS, ENGINE_STATUS, report/{ONE_PAGE_SUMMARY, PROJECT_REPORT, CLAIMS_CHECK, REVIEW_NOTES, SLIDES_OUTLINE}, dossier/{ONE_PAGE_FOR_THE_OWNER, EVIDENCE_INDEX, RUBRIC_MAP, VIVA_ANSWER_CARDS, VIVA_SHEET, AI_USE_DISCLOSURE_DRAFT, PROJECT_DOSSIER}; timings 15.5 s / 33.2 s -> 18.3 s / 80.9 s; date of those counts 2026-11-20 (RECON3). Left as history on purpose (now marked "at T3 time ... now 133 and 310"): T3 gate lines in ENGINE_STATUS, FINAL_STATUS, PROJECT_DOSSIER, CRITIQUE R27-1 (CRITIQUE is a skip-list file; edited by hand). I first over-replaced the lead's T3 "pytest tests 99 passed" with 133 and restored it to "99 passed at that time".
Deck: SLIDES.pptx slide 9 tiles 99 -> 133, 139 -> 310, footer "(1 product test skipped)" -> "(310 product tests, pyyaml installed)", notes sentence updated; only text runs changed via python-pptx, LibreOffice re-render checked (slide 9 viewed: tiles fit). Same in SLIDES_OUTLINE slide 9. Other deck slides (6, 8, 10, 14, 17) already carry 180/60/24, predictor 92% with baselines, polarity: no change.

## 3. NUMBERS.md
- New section "How RECON3 re-measured"; rows T.root.collected/passed, T.prod.collected/passed, T.hist.root/prod updated; PS4.tests and FIX2.rail.v1 ("0-to-1 control pending" -> done) corrected.
- New section 11 (labels MEASURED RECON3 / MEASURED lead RUN_LOG 195, 235, 236 / REPORTED): H2.tests, H2.canary, H2.newtests.onold, H2.chk_repro, H3.tests, H3.canary, H3.sha, H23.notfixed, PS6.tests, PS6.count, PS6.synth, PS4.PS5.status (PS4/PS5 detail rows already existed), RT2.fuzz (1120 netlists, 8406 runs, 0 disagreements, MEASURED by RT2, not re-run), LEDGER.cells, ANCHOR.pointer (ANCHOR.bf/grid already in section 10), DASH2.values (228 values, REPORTED), FIX3.status.
- Machine block: `current` counts 133/310; two new stale rules T.root.133 (99) and T.prod.310 (139, 140, 174, 175, 138+1), hist_re extended ("at T3 time", "then; now", "was the count then", "after H2", "PS6 copy", "H2 copy"); old rows list values updated. `scripts/check_numbers.py` itself unchanged (rules live in NUMBERS.md).

## 4. check_numbers result and what remains
After edits: 52 files, **4 STALE, all in `research/c4/viva/VIVA_SIM_REPORT.md` l.209-210** (outside my edit list: "current counts 99 root, 139 product + 1 skipped" and a sentence quoting them); proposed edit: 99 -> 133, 139 + 1 skipped -> 310. 17 HISTORICAL (10-test, 29/43, 67%/65% and T3-gate lines with markers; harmless). Not scanned: docs/report/review/* (frozen), skip-list files (CRITIQUE, EVIDENCE_INDEX, FIX_LOG, WORDING_FLAGS; I hand-updated the count rows in the first two). dashboard/ and product/README.md not edited or re-scanned for 133/310 (outside scope; the dashboard's DASH2 228-value check does not cover test counts as far as I saw).

## 5. Agreement check (README, START, ONE_PAGE_SUMMARY, deck notes, ONE_PAGE_FOR_THE_OWNER)
- Test counts: all five now say 133 / 310 (README, START, summary, owner page, deck slide 9 + notes).
- Mutation 72.5% root (50/69), 67.6% product (50/74): present in summary, PROJECT_REPORT, deck; was MISSING in README, START and the owner page: added (REPORTED, not re-run).
- E2 with baselines: README, START, summary, outline already had 180/60/24 of 264 + 152 distinct 94/38/20; owner page had only "1, 2 or 3 flips over 864 settings": added the counts and baseline.
- Predictor 92% with 62% / 83% baselines: consistent in all five (deck slides 10, 14 too).
- Polarity statement (1-to-0 only survives; rail-wide 0-to-1 costs 1 on V2 and V5, and V1, V0; survival depends on polarity): consistent in README, START, summary, owner page, deck slides 8 and 17.
No other disagreement found.

## 6. Limits
Mutation scores, RT2 fuzz, PS6 numbers, DASH2 228 values, canary results of H2/H3 are agent reports (lead re-ran the canary and a CLI check, RUN_LOG 235, 236); RECON3 did not re-run mutation (about 45 min) or the canaries. Single machine, Yosys 0.33, one run each. `check_numbers` finds only values covered by its rules.
