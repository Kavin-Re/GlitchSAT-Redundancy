# INT2a report: comms, demo and deck integration

License: UNDECIDED. Working title TBD. Toy designs, modelled bit flips, nothing physical, nothing established as new. No code changed. Backups of every edited file: `research/c6/int2a/backup/` (path with `/` replaced by `_`).

## Measured counts (fresh tar copy /tmp/work_int2a/copy; excludes work, dl, dl_repo, venv, compare/synfi_run/venv, third_party_derived, .git, handoff/*.zip, *.odb *.vcd *.fst *.vvp; log /tmp/work_int2a/measure.log)
| what | result | status |
|---|---|---|
| `python3 -m pytest -q tests` (system python3) | 196 passed, 1 skipped in 18.35 s; 197 collected. Skip: `test_distance_sweep.py::test_remeasure_stored` (needs product CLI) | MEASURED |
| same in venv /tmp/work_int2a/venv with `./product[test]` | 184 passed, 1 skipped (test_waterfall.py skipped as a module: no numpy in the venv) | MEASURED |
| `pytest -q product/tests` (venv) | 324 passed in 82.0 s | MEASURED |
| `python3 ci/check_reproduce.py` | 36/36 rows match, 0 FAILED, 0 problems | MEASURED |
| `python3 ci/check_reproduce.py --rerun` | 36/36 rows match (engine re-run), 0 FAILED, 0 problems | MEASURED |
| `docs/explainers/dev/check_dial.py --browser` | 467 passed, 0 failed | MEASURED |
| `docs/explainers/dev/check_wall.py` | 42 PASS, ALL PASS 0 failed | MEASURED |
| `docs/explainers/dev/check_theatre.py --browser` | 149 passed, 0 failed | MEASURED |
| `python3 scripts/check_numbers.py` (tree, after edits) | 62 files, 0 STALE, 16 HISTORICAL, 42 rules; `--verify` all OK | MEASURED |
Note: INT2b was due to add `tests/test_explainer_checks.py`; it was not in my copy (05:30 UTC). If it lands, the root count changes again.

## Edits (file: before -> after)
1. `docs/comms/CODING_VIEW.md`: header "cells that need P11's sweep say pending P11" -> sources with CSV rows; burst sentence "(circuit measurement: pending P14)" -> P14 result (burst.csv rows 2-7); interleaving "P01's question, not established" -> P01 measured floor (sweep_rows rows 2-9 vs 10-17); table rows V2m/V2s "pending P11" -> "not measured (P11 swept codebooks, not voters)"; row "other accept codebooks pending P11" -> P11 summary (distance_sweep rows 2-20) + 69_96 complement row (row 4) + new rows v2_secded (decoder_variants rows 74/83) and v2c (rows 110/119). Added sections "Random-flip channel (waterfall)", "Burst vs random" (with the 2x2 table), "Decoders" (with "this decoder, this code, this FSM: no general rule about ECC"). "No random-channel numbers (P12 territory)" -> teaching-model label; three more "may not claim" lines. 0 "pending" left.
3. `docs/DEMO_3MIN.md` (new): tab set-up, 10 beats summing to 3:00 (ESTIMATED, UNPILOTED), dial 3 -> 2 -> 1 -> 0 predict-first, theatre V1 / V2 / flag caveat, wall one reveal, staircase for comms audience, honest labels, fallbacks (keys, screenshots, PDF slides), 10-minute booth loop with `?kiosk=1` on theatre and wall. `docs/report/DEMO_5MIN.md`: pointer added; slide references updated to the new order (1 to 12 -> 1 to 14; 5 -> A6; 6, 7, 8 -> A7, A8, A9 or slide 7; 10 and 12 -> 12 and 14; 3 to 6 -> 3, 4, A6, A7).
4. Deck (`research/c6/int2a/add_slides.py`, python-pptx): 19 -> 24 pages; main 14: 1-4, NEW 5 Verdict Dial (p40 shot), NEW 6 Solver Replay (crop of p21 step2 shot, `research/c6/int2a/img/`), NEW 7 264-builders wall (p24 stage3 shot), 8 Why 2 and not 3, 9 Redundancy is a code, NEW 10 waterfall, NEW 11 burst vs random (table), 12 not proven, 13 what I did, 14 sentence. Appendix A1-A5 unchanged, old slides 5, 6, 7, 8, 9 -> A6-A10 (label "APPENDIX:", title prefix). Page numbers renumbered; new slides take the deck background. Old slide 9 "150 main tests passed" + notes -> 196 (1 skipped). Speaker notes in first person on all new slides. SLIDES.pdf regenerated with LibreOffice (24 pages); every new page inspected as an image: one title overflow found on the waterfall slide (two lines over the picture), fixed by a shorter title; no other overflow. No slide quoted "Yosys version dependence" (only the corrected-error notes) or persona scores. `docs/report/SLIDES_OUTLINE.md` regenerated in the new order (old sections kept verbatim, new sections from the deck).
5. `docs/report/WHY_TWO_FLIPS.md`: plain hashes 214a2987/152aad31, 005b02a5/a2aa7119, f8328dd0/71f4547e, b96bd545/5749a181 -> sweep_rows.csv values f3fe9621/32b82842, 35624e33/53556f01, 8abc2d13/b3ffbe1b, 03e0ce61/64b1b256 (rows cited) + one sentence: the old values are the synth.sh builds in `netlist_sha256.txt`, same minimum flips, different hash because the netlist sha depends on the Yosys working directory (embedded source paths). That cause is the integration step's diagnosis; I did not rebuild to confirm it.
6. `docs/NUMBERS.md`: T.root.collected 150 -> 197, T.root.passed 150 -> 196 passed 1 skipped (table + JSON rows + `current`); new section 14 with P12 (4 rows), P14 (3), P18 (2), P21, P24, P40, INT2a.tests/.repro/.wow, each with file and line/row; "should" texts 150 -> 196; new rule `T.root.150` (hist). No change to `scripts/check_numbers.py` (rules live in NUMBERS.md).
7. Count 150 -> 196 (1 skipped) and "(re-measured by INT)" -> "INT2a" in: START.md, docs/ENGINE_STATUS.md, docs/FINAL_STATUS.md, docs/dossier/{DISCLOSURE_DRAFT, ONE_PAGE_KEY_POINTS, EVIDENCE_MAP, QA_SHEET, PROJECT_DOSSIER, QA_ANSWER_CARDS}.md, docs/report/{CLAIMS_CHECK, ONE_PAGE_SUMMARY, PROJECT_REPORT, REVIEW_NOTES}.md (5 were STALE after the new rule; the rest current statements flagged HISTORICAL).
8. `docs/dossier/EVIDENCE_INDEX.md`: rows 81-88 (waterfall, burst, decoders, dial, theatre, wall, DEMO_3MIN, counts). `docs/dossier/CRITIQUE.md`: FE-3 to FE-6 (fixed in part / fixed) and FE-7 OPEN: P23 game, P36 verdict card, P31 front door, P38 author pack, P15 trap, licence, name, section-7 archive list.

## Not done / caveats
- DEMO_3MIN never spoken aloud; kiosk modes tested only by the pages' own headless checkers.
- Dial slide screenshot shows the V2e build (also 3), labelled on the slide; no stored-build screenshot exists.
- The tree's `__pycache__` was not touched; no product/build or egg-info created in the tree.
