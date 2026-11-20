# BUNDLE rehearsal report

Tree state: other agents were still editing docs; this is a rehearsal. Final build is the lead's at 04:30 UTC.

## Files written
scripts/make_bundle.sh (rewritten, allow-list based), scripts/bundle_allowlist.txt (new), scripts/verify_bundle.sh (new), docs/BUNDLE.md (new). Rehearsal artefacts in this folder: verify_log_rehearsal.txt, hardcoded_paths.txt, SHA256SUMS_rehearsal.txt. The old make_bundle.sh was not backed up as a file (it was in the task text; it was a find-based exclude list).

## Dry run and build (MEASURED, `bash scripts/make_bundle.sh --build`, output /tmp/bundle_out/)
| Bundle | Files | Uncompressed | Zip | .md files | PII scan |
|---|---|---|---|---|---|
| A review kit | 18 | 1.30 MB | 958,652 B | 13 | clean |
| B full tree | 1,874 | 82.5 MB | 55,575,423 B | 175 | clean |
SHA256 (rehearsal names `project_review_kit_20261120T001044Z.zip`, `project_full_tree_20261120T001044Z.zip`): A 5435c3bb...a372da5, B b01987db...f6d8bf0 (full values in SHA256SUMS_rehearsal.txt).
Largest files in B: 3.0 MB `research/c5/dash2/shot_1366.png`, 2.7 MB `dashboard/screens/phone2.png`, then 1 to 1.7 MB PNGs and `research/c2/e2_variance/raw/synth_all.json` (954 KB). Nothing over 3 MB ships.
Exclusions hit in B: formal/runs 1,055 files; backup dirs 22; real_designs/work 21; shots dirs 13; __pycache__ 12; .odb 8; .vcd 6; .vvp 6; dl_repo 1 dir (21 files); .pytest_cache 1; one file over 3 MB (dashboard/screens/desktop2.png). third_party_derived and compare are not in the include list, so they never reach the walk.
A: SLIDES.pdf does not exist at docs/report/; the builder used the fallback research/c4/pres/render/SLIDES.pdf (421,654 B). If the lead wants a different PDF, place it at docs/report/SLIDES.pdf.

## PII/secret scan
First run failed on a false positive (`M@s.astype` in research/c3/m1/bf.py matched the email regex); the regex was narrowed to real TLDs. The scan correctly gives zero hits once dl_repo is excluded. Benign emails allowed by listed substring: claire@yosyshq.com (Yosys banner), security@opentitan.org, example placeholders. Not tested by planting a secret; the scan was not run against dl_repo to prove the hit (that folder is outside the walk). Binary files are not scanned. Owner name/email unknown to me and not in any list.

## verify_bundle.sh on B (MEASURED, about 6 min, Python 3.13.18, yosys 0.33, venv /tmp/bundle_verify_venv)
PASS: pip install ./product[test] and ci/requirements-ci.txt; `ci/check_reproduce.py` 36/36; `--rerun` 36/36 (engine re-run, 0 failed, 0 problems); `pytest tests` 133 passed (14.9 s); `pytest product/tests` 310 passed (80 s); START.md commands 1 to 3 (v1 k=1 ATTACK_FOUND on `ok`; v2 k=2 and v2 `boot_ok` run, rc 0; outputs in the log); `dashboard/build.py` ran and index.html SHA-256 unchanged; no forbidden path in the zip.
FAIL (1): `scripts/check_numbers.py` rc=1: 2 STALE rows, both in `research/c4/qa_sim/QA_SIM_REPORT.md` line 209 ("99 root", "139 product" where RECON3 says 133 and 310), plus 17 HISTORICAL rows (old counts quoted as history in docs). The same text is in the live tree, so this is a docs problem for the lead or the QA owner, not a bundle problem. Fix: label or update line 209, or drop that file from B.

## Absolute /tmp or <home> paths in B (MEASURED, grep -I -c; list in hardcoded_paths.txt)
600 files. By top folder: research 340, results 106 (logs and JSON), layout 92, docs 24, formal 12, tb/generated 9, handoff 3, integrations 4, product 3 (hits in product/tests/test_h2.py, test_ps6.py: strings, tests pass), scripts 2 (make_bundle.sh default output dir; setup_layout_tools.sh `/tmp/mm_root`, `/tmp/mm_dl`), ci 1 (clean_install_log.txt, a log), validation 1 (boolector.log), dashboard 1 (dashboard/real/shot.py, a screenshot helper), README_FIRST.txt, START.md.
Needed to run the START.md path: none. Failures caused by absolute paths during verify: none observed. START.md itself tells the reader to `cp -r <repo>`: wording fix for the lead (use the unzipped folder). setup_layout_tools.sh and the research scripts need their /tmp paths only for the layout/formal tool flows and are evidence-only (docs/BUNDLE.md says so). Not scrubbed (code freeze; scrubbing logs would change evidence).

## Open items for the lead (not fixed, outside my scope)
1. check_numbers stale rows (above). 2. START.md copy command path. 3. No docs/report/SLIDES.pdf. 4. docs that cite `formal/runs/*` or `numerics_audit/` point at files B does not contain. 5. The zip has no top-level folder (per CHECKPOINT): unzip into an empty directory. 6. 175 .md files and 340 research files with /tmp paths ship in B as evidence; bundle A is the one to hand a reader. 7. Rerun `scripts/verify_bundle.sh` on the final zip; it recreates /tmp/bundle_verify (only if it holds our marker file).
