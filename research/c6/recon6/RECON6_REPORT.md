# RECON6 report: root test count reconciliation

## Cause of the differences
Three environments, one tree content. Dev tree (tar copy minus compare/synfi_run/venv and third_party_derived) and the unpacked bundle `project_full_tree_20261120T054144Z.zip` have identical tests/ file lists and identical per-file counts. The numbers differ only by environment:

| Setup | collected | result |
|---|---|---|
| CANONICAL: bundle, clean venv, `pip install ./product[test]` + pytest, no numpy, no Chrome/playwright | 190 | 189 passed, 2 skipped (22 s) |
| Same on the dev-tree copy | 190 | 189 passed, 2 skipped |
| System python3 (numpy present, product CLI not on PATH), dev copy | 203 | 202 passed, 1 skipped (`test_distance_sweep.py:75` needs yosys, iverilog and the product CLI) |
| INT2a, 2026-11-20 earlier (system python, numpy) | 197 | 196 passed, 1 skipped; `test_explainer_checks.py` (6 tests) did not exist yet |

Reconciliation: 197 (INT2a) - 13 (test_waterfall, needs numpy, absent in the clean venv) + 6 (test_explainer_checks, added later) = 190. 197 + 6 = 203 = system-python count today.

## The 2 skips in the canonical setup
1. `tests/test_waterfall.py:8` module skip: `could not import 'numpy'` (13 tests not collected).
2. `tests/test_explainer_checks.py:27` `test_hub_browser`: `google-chrome or playwright missing`.

## Per-file collected counts (canonical, identical in bundle and dev copy)
test_mt_oracle 61; test_h3 34; test_burst_sweep 18; test_decoder_variants 16; test_hardening 15; test_distance_sweep 12; test_engine 10; test_mt_targeted 8; test_explainer_checks 6; test_check_reproduce 5; test_h5 3; test_p08 2; total 190 (test_waterfall: 0 collected without numpy, 13 with).
No test needs compare/ or third_party_derived/. Product tests: 324 (not re-run by RECON6; integration step measured 324 in both; check_numbers collects 324).

## Changes (backups in research/c6/recon6/backup/)
- Canonical root count 189 passed, 2 skipped (190 collected) now in START.md, README.md, docs/ENGINE_STATUS.md, FINAL_STATUS.md, dossier (EVIDENCE_MAP, EVIDENCE_INDEX row 88, QA_ANSWER_CARDS, PROJECT_DOSSIER, DISCLOSURE_DRAFT, ONE_PAGE_KEY_POINTS, QA_SHEET), report (SLIDES_OUTLINE, REVIEW_NOTES, ONE_PAGE_SUMMARY, PROJECT_REPORT, CLAIMS_CHECK).
- SLIDES.pptx slide 24 (tile 196 -> 189, label "(2 skipped)") and its speaker notes; SLIDES.pdf regenerated with LibreOffice (24 pages). Dashboard text had no root count: not touched.
- docs/NUMBERS.md: T.root.collected = 190, T.root.passed = 189 passed, 2 skipped (with env table and history), INT2a.tests marked history, `current` block and `rows` updated, new rule T.root.196 (flags 196/197 as stale unless the line carries a history marker). `--pytest` expectation is read from `current` (now 190). scripts/check_numbers.py needed no change.
- research/c5/dash2/verify_numbers.py: two stale needles updated to the page's wording ("breaks V2 and V5 with <b>one event</b>", "do not run the Verilog path or the Action on untrusted input").

## Verification (fresh tar copy /tmp/work_recon6/fresh, clean venv)
- check_numbers.py: 62 files, 0 STALE, 17 HISTORICAL.
- `--verify --pytest`: all verify rows OK; collected tests 190 = 190, product/tests 324 = 324.
- verify_numbers.py: 228 checked, 0 mismatches.
- Nothing created in the project tree (product/build and egg-info absent). Work dir: /tmp/work_recon6.
