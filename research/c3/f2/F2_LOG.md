# F2 log. Backups of every changed file: research/c3/f2/backup/ (same relative paths). Nothing run with make in the tree.

## Edits (file, line of first change, before -> after)
- `docs/FINAL_STATUS.md` line 11
  - before: `with a validated solver,`
  - after: `with a solver cross-checked against two other tools on the same fault model,`
- `docs/FINAL_STATUS.md` line 11
  - before: `and real open-source layouts of the example designs.`
  - after: `and sky130 flow-demo layouts of the example designs (open-source tools through DRC/LVS checks; not signed off, never fabricated).`
- `docs/FINAL_STATUS.md` line 11
  - before: `whether a "safe" design stays safe can depend`
  - after: `whether a "safe" design stays safe (within the model) can depend`
- `docs/FINAL_STATUS.md` line 13
  - before: `reproducible, validated analysis project`
  - after: `reproducible analysis project, cross-checked`
- `docs/FINAL_STATUS.md` line 18
  - before: `Tangible artifact (real chip layout)`
  - after: `Tangible artifact (flow-demo layout, no chip)`
- `docs/FINAL_STATUS.md` line 18
  - before: `Real sky130 GDS for the example designs through Yosys + OpenROAD + magic.`
  - after: `sky130 GDS from an open-source flow demonstration (Yosys + OpenROAD + magic, then DRC/LVS tools) for the example designs; no fabrication and no sign-off. The door-lock design's top-level LVS FAILED pin matching (`real_designs/second/REPORT.md`).`
- `docs/FINAL_STATUS.md` line 25
  - before: ``make test` 10 passed,`
  - after: ``make test` 30 passed (MEASURED by agent RA, 2026-11-19, `research/c3/ra/RA_REPORT.md`; product tests: 27 passed after `pip install ./product[test]`, MEASURED by agent PS2, `research/c3/ps2/PS2_REPORT.md`),`
- `docs/FINAL_STATUS.md` line 30
  - before: `Not a finding; no disclosure needed;`
  - after: `Not a finding; no vulnerability in a deployed product was claimed, and any such finding would need disclosure to the authors first;`
- `docs/FINAL_STATUS.md` line 20
  - before: `the CMSIS-DSP `arm_sqrt_q15` observation is already tracked upstream (CMSIS_5 #1386 / CMSIS-DSP #9, via a summarising fetch tool, so UNVERIFIED in detail)`
  - after: `the CMSIS-DSP `arm_sqrt_q15` observation is said to be already tracked upstream (CMSIS_5 #1386 / CMSIS-DSP #9: not reproducible from the repo; read via a summarising fetch tool, UNVERIFIED)`
- `docs/FINAL_STATUS.md` line 31
  - before: `(0 mismatches in about 6,700 programs`
  - after: `(0 mismatches in about 6,700 programs - not reproducible from the repo`
- `docs/FINAL_STATUS.md` line 52
  - before: `Tested in a real browser at 1100 px and 390 px:`
  - after: `Automated browser run (headless Chromium, no human testers) at 1100 px and 390 px:`
- `docs/ENGINE_STATUS.md` line 16
  - before: `(10 tests, ~19 s, all pass)`
  - after: `(30 tests, ~29 s, all pass as of RA's 2026-11-19 re-run; it was 10 tests before the H1 hardening tests; product tests: 27 pass after `pip install ./product[test]`)`
- `docs/report/CLAIMS_CHECK.md` line 16
  - before: `| `make test` 10 passed; `make reproduce` about 25 s |`
  - after: `| `make test` 10 passed (now 30 passed; product tests 27 passed after `pip install ./product[test]`); `make reproduce` about 25 s |`
- `docs/report/CLAIMS_CHECK.md` line 20
  - before: `| UNVERIFIED (spike result, data not in repo) | no |`
  - after: `| UNVERIFIED (spike result, data not in repo; not reproducible from the repo) | no |`
- `docs/report/CLAIMS_CHECK.md` line 67
  - before: `| CMSIS_5 #1386 / CMSIS-DSP #9 | report 6.8 |`
  - after: `| CMSIS_5 #1386 / CMSIS-DSP #9 (not reproducible from the repo) | report 6.8 |`
- `docs/report/CLAIMS_CHECK.md` line 79
  - before: `"10 tests" |`
  - after: `"10 tests" (now 30) |`
- `docs/report/DEMO_5MIN.md` line 11
  - before: `# 10 passed; reproduce`
  - after: `# 30 passed (product tests: 27 after `pip install ./product[test]`); reproduce`
- `docs/report/ONE_PAGE_SUMMARY.md` line 27
  - before: `10 tests pass [`
  - after: `30 tests pass (MEASURED, RA 2026-11-19; product tests 27 pass after `pip install ./product[test]`) [`
- `docs/report/PROJECT_REPORT.md` line 45
  - before: `| Unit tests (`make test`) | 10 passed |`
  - after: `| Unit tests (`make test`) | 30 passed (10 at first writing; 30 per RA 2026-11-19; product tests 27 passed after `pip install ./product[test]`, PS2) |`
- `docs/report/PROJECT_REPORT.md` line 53
  - before: `| 10 passed; 36/36 rows match |`
  - after: `| 10 passed at that time (now 30); 36/36 rows match |`
- `docs/report/PROJECT_REPORT.md` line 55
  - before: `in about 6,700 fuzzing programs`
  - after: `in about 6,700 fuzzing programs (not reproducible from the repo)`
- `docs/report/PROJECT_REPORT.md` line 135
  - before: `(CMSIS_5 #1386 / CMSIS-DSP #9, read via`
  - after: `(CMSIS_5 #1386 / CMSIS-DSP #9, not reproducible from the repo; read via`
- `docs/report/PROJECT_REPORT.md` line 181
  - before: ``tests/` (10 tests)`
  - after: ``tests/` (30 tests; 10 at first writing)`
- `docs/report/REVIEW_NOTES.md` line 8
  - before: `PASS: 10 passed in 20.2 s`
  - after: `PASS: 10 passed in 20.2 s (at review time; now 30 passed)`
- `docs/report/SLIDES_OUTLINE.md` line 89
  - before: `CMSIS_5 #1386 / CMSIS-DSP #9 read via`
  - after: `CMSIS_5 #1386 / CMSIS-DSP #9 (not reproducible from the repo) read via`
- `README.md` line 19
  - before: `make test                                       # engine tests
`
  - after: `make test                                       # engine tests (30 passed, MEASURED by RA)
`
- `README.md` line 25
  - before: ``make help` lists every target.`
  - after: `Product tests (`product/tests`, 27 passed, MEASURED by PS2) need the package installed first: `pip install ./product[test]`. `make help` lists every target.`
- `README.md` line 12
  - before: `
## Quickstart`
  - after: `
**Honest scope:** a verdict belongs to one netlist hash, one build, one flow and one counting rule (E2); read every claim with the scoped wording in `research/c2/b2_scope/B2_REPORT.md` (V2 scoped claim wording).

## Quickstart`
- `README.md` line 11
  - before: `(a real open-source sky130 layout)`
  - after: `(an open-source sky130 flow-demo layout; no fabrication, no sign-off)`
- `THIRD_PARTY.md` line 3
  - before: `The project's own code is not a copy of any third-party source.`
  - after: `The project's own code (outside `third_party_derived/`, see the last section) is not a copy of any third-party source; `third_party_derived/` does hold third-party-derived material.`
- `THIRD_PARTY.md` line EOF
  - before: `(appended)`
  - after: `section on third_party_derived/`
- `NOTICE.md` line EOF
  - before: `(appended)`
  - after: `paragraph on third_party_derived/`

## New file
- `scripts/make_bundle.sh`: no bundle script/target existed in Makefile. Dry run by default (prints file list, total size); `--build [OUT]` makes a tar.gz. Excludes third_party_derived, any venv (incl. compare/synfi_run/venv), real_designs/second/dl_repo, real_designs/work, work, dl, dl_repo, handoff/*.zip and any *.zip, *.odb/*.vcd/*.fst/*.vvp, caches, files over 3 MB. Dry-run tested on a copy (/tmp/work_f2/c, with decoy work/, dl_repo, .vcd, 4 MB file, zip): 2582 files, 154.7 MB uncompressed, 0 excluded paths in the list. MEASURED on the copy; the copy lacked handoff/ and the nested venv, so the real-tree total is not measured. Note: PNGs under 3 MB remain (dashboard/screens, docs/report/review/shots) and `compare/synfi_run/src` stays (keep its Apache notice) - owner may want to drop them.

## Not changed / for others
- docs/dossier/* still says '10 passed' and the 6,700 / CMSIS items (another agent). Also docs/wow/* and README prose elsewhere untouched.
- REVIEW_NOTES.md and PROJECT_REPORT.md line 53 are records of an earlier run: kept '10 passed' and annotated 'at that time (now 30)'.
- README had no product-test mention; I added the `pip install ./product[test]` line to the Quickstart note. README 'prove it' act title left (owner/dashboard choice per SE). README 'real' layout wording changed in line 11 only.
- NOTICE.md had no explicit 'no third-party-derived source' sentence; THIRD_PARTY.md did (corrected). Appended third_party_derived/ notice to both.
- LICENSE status unchanged (UNDECIDED).
