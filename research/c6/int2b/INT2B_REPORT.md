# INT2b report
Scope: computer model of toy designs; nothing physical; no novelty claim. All checks below were run on a fresh copy in /tmp/work_int2b, then applied to the tree and re-run there (MEASURED, by the commands shown).

## Changes
- docs/explainers/index.html (new hub): 6 cards (Verdict Dial, Solver Replay, 264 builders, Explainer, Game, Dashboard), Coding view text link, Stage mode kiosk links, scope line. Offline, light/dark.
- docs/explainers/dev/check_hub.py (new): data part (9 links all exist, no external resource, scope line) + `--browser --shots DIR`.
- docs/explainers/explainer.html: one block "Try the live versions" (3 buttons) inserted before the "Where do the copies meet?" line, after the title and project box. Nothing deleted. check_game_answers.py: OVERALL PASS.
- dashboard/template.html: "Try the live demos" link row at the top of the Scope tab; dashboard/index.html rebuilt with dashboard/build.py (build.py itself unchanged). Only one line of index.html differs from before.
- tests/test_explainer_checks.py (new): check_dial, check_wall, check_theatre (data part), check_hub, check_game_answers via subprocess (exit 0), plus hub browser test skipped if chrome/playwright is missing. Result: 6 passed in 2.9 s.
- Makefile: 5 lines added to `test` (hub, dial, wall, theatre, game_answers checkers). Not run with make; `make -n test` only, on the copy.
- Allow-list: [A] +7 (index/dial/theatre/wall html, dashboard/index.html, CODING_VIEW.md, WHY_TWO_FLIPS.md); [B-include] explicit entries added; new `keep:docs/explainers/dev/shots` exclusion exemption (needs make_bundle.sh change, done; size cap still applies); verify_bundle.sh: shots check exempts docs/explainers/dev/shots/, plus a wow_checks step.
- Note: the existing [B-include] already contained docs, rtl, tb, tests, scripts, results, research as whole directories, so every item you listed was already included except docs/explainers/dev/shots (excluded by dir:shots) and the new files; research/c6 *_REPORT.md and PREREG.md are included along with the other non-backup, non-shots research files (policy unchanged).

## Measured
- Hub 390/1366 px, light and dark: no console errors, no horizontal scroll, min text 14 px, min link height 44 px (check_hub.py --browser: PASS).
- Explainer 390/1366: no overflow, no console errors, new buttons 48 px high.
- Dashboard 390/1366 all tabs: scrollWidth = viewport, no console errors, min font 12.48 px.
- research/c5/dash2/verify_numbers.py <root>: 228 checked, 2 mismatches, identical to the tree BEFORE my change (pre-existing, not touched: "costs <b>1 event</b>" and "do not run the product Verilog path..." page-text checks; for INT2a and the integration step).
- Bundle dry run before -> after: A 18 -> 25 files (1.84 -> 2.22 MB); B 2084 -> 2096 files (87.2 -> 90.2 MB); PII scan clean; a real build into /tmp/work_int2b/out on the copy: 0 forbidden paths in the zip (besides the allowed docs/explainers/dev/shots/, 9 files); contains docs/comms (8 files), results/comms (4), scripts/comms (5), v2e/v2_secded/v2c.v, both tb files, WHY_TWO_FLIPS.md, SLIDES.pdf. 99 *_REPORT.md/PREREG.md files in B; 0 research/c6 backup/shots files. The real build was not run in the tree.
- No product/build or egg-info created in the tree. Backups: research/c6/int2b/backup/. Screenshots: research/c6/int2b/shots/.
